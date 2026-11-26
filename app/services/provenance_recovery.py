"""Conservative local recovery. Never infer IDs by name alone, fuzzy text or position."""
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

from app.models.case import Case
from app.models.case_comment import CaseComment
from app.models.case_provenance import CaseProvenanceReview
from app.models.meta_post import MetaPost

BATCH = "legacy_missing_comment_id_20261124"
ACTOR = "system:legacy-provenance-recovery"
METHOD = "exact_post_text_author_timestamp_v1"


def reference(notes, key):
    match = re.search(r"(?m)^\[" + re.escape(key) + r"\]:[ \t]*([^\r\n]+)", notes or "")
    return match[1].strip() if match else None


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def read_capture(raw):
    try:
        rows = json.loads(raw or "[]")
    except (ValueError, TypeError):
        return None
    if not isinstance(rows, list):
        return None
    by_id = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        cid = str(row["id"])
        if cid in by_id and by_id[cid] != row:
            return None
        by_id[cid] = row
    return by_id


def plan_recovery(cases, posts, links, reviewed_ids=()):
    """Pure planning step; no writes. Recovered cohort remains auditable on repeat runs."""
    captures = {post.id: read_capture(post.raw_comments_json) for post in posts}
    claims = defaultdict(set)
    for case in cases:
        pid, cid = reference(case.internal_notes, "Post ID"), reference(case.internal_notes, "Comment ID")
        if pid and cid:
            claims[(pid, cid)].add(case.id)
    link_by_case = defaultdict(list)
    for link in links:
        claims[(link.post_id, link.comment_id)].add(link.case_id)
        link_by_case[link.case_id].append(link)
    reviewed_ids = set(reviewed_ids)
    plan = []
    for case in cases:
        if reviewed_ids and case.id not in reviewed_ids:
            continue
        if not reviewed_ids and link_by_case.get(case.id):
            continue
        old_cid = reference(case.internal_notes, "Comment ID")
        if old_cid and case.id not in reviewed_ids:
            continue
        pid = reference(case.internal_notes, "Post ID")
        record = {"case_id": case.id, "post_id": pid, "comment_id": None, "status": "needs_review",
                  "reason": "source_missing", "candidate_count": 0, "method": METHOD,
                  "case_fingerprint": digest([case.content, case.author, case.date_time]), "capture_fingerprint": None}
        capture = captures.get(pid)
        if not pid:
            record["reason"] = "post_reference_missing"
        elif pid not in captures:
            record["reason"] = "source_missing"
        elif capture is None:
            record["reason"] = "invalid_or_conflicting_capture"
        else:
            texts = [(cid, raw) for cid, raw in capture.items() if isinstance(case.content, str) and case.content.strip()
                     and (raw.get("content") or raw.get("message")) == case.content]
            timed = [(cid, raw) for cid, raw in texts if case.date_time and (raw.get("published_at") or raw.get("time")) == case.date_time]
            exact = [(cid, raw) for cid, raw in timed if case.author and raw.get("author") == case.author]
            record["candidate_count"] = len(exact)
            if len(exact) == 1:
                cid, raw = exact[0]
                record.update(comment_id=cid, capture_fingerprint=digest(raw))
                own_links = link_by_case.get(case.id, [])
                if claims[(pid, cid)] - {case.id}:
                    record["reason"] = "comment_linked_to_other_case"
                elif (old_cid and old_cid != cid) or any((link.post_id, link.comment_id) != (pid, cid) for link in own_links):
                    record["reason"] = "case_has_different_reference"
                else:
                    record.update(status="recovered_local", reason="exact_capture_match")
            elif len(exact) > 1:
                record["reason"] = "ambiguous_exact_match"
            elif timed:
                record["reason"] = "author_mismatch_or_missing"
            elif texts:
                record["reason"] = "timestamp_mismatch_or_missing"
            else:
                record["reason"] = "text_not_in_capture"
        plan.append(record)
    # Even unique capture matches cannot be assigned to two historical cases.
    proposed = defaultdict(list)
    for item in plan:
        if item["status"] == "recovered_local":
            proposed[(item["post_id"], item["comment_id"])].append(item)
    for matches in proposed.values():
        if len(matches) > 1:
            for item in matches:
                item.update(status="needs_review", reason="multiple_cases_for_same_comment")
    return plan


def run_recovery(db, *, apply=False, expected_recoverable=None):
    try:
        # Consistent lock order with the live triage writer: publications first, then cases.
        posts_query = db.query(MetaPost).order_by(MetaPost.id)
        cases_query = db.query(Case).order_by(Case.id)
        if apply:
            posts_query = posts_query.with_for_update()
            cases_query = cases_query.with_for_update()
        posts, cases = posts_query.all(), cases_query.all()
        links = db.query(CaseComment).all()
        prior_reviews = db.query(CaseProvenanceReview).filter_by(batch=BATCH).all()
        plan = plan_recovery(cases, posts, links, [row.case_id for row in prior_reviews])
        counts = Counter(item["status"] for item in plan)
        if expected_recoverable is not None and counts["recovered_local"] != expected_recoverable:
            raise ValueError("La captura cambió respecto de la vista previa. Repite la auditoría antes de aplicar.")
        changed_links = 0
        if apply:
            by_case = {case.id: case for case in cases}
            by_post = {post.id: read_capture(post.raw_comments_json) for post in posts}
            linked = {(link.post_id, link.comment_id) for link in links}
            reviews = {row.case_id: row for row in prior_reviews}
            now = datetime.now(timezone.utc)
            for item in plan:
                case = by_case[item["case_id"]]
                if item["status"] == "recovered_local":
                    pid, cid = item["post_id"], item["comment_id"]
                    if (pid, cid) not in linked:
                        db.add(CaseComment(post_id=pid, comment_id=cid, case_id=case.id,
                                           comment_json=by_post[pid][cid], linked_by=ACTOR))
                        linked.add((pid, cid))
                        changed_links += 1
                    if reference(case.internal_notes, "Comment ID") is None:
                        case.internal_notes = (case.internal_notes or "").rstrip() + f"\n[Comment ID]: {cid}\n[Recuperación de origen {now.isoformat(timespec='seconds')}]: coincidencia exacta de publicación, texto, autor registrado y fecha en la captura local. No certifica identidad ni consulta actual de Meta."
                review = reviews.get(case.id)
                if review is None:
                    review = CaseProvenanceReview(case_id=case.id, batch=BATCH)
                    db.add(review)
                review.status, review.reason = item["status"], item["reason"]
                # Keep the dated conflict comparison when rerunning the origin audit.
                previous_conflict = (review.evidence_json or {}).get("conflict_review")
                review.evidence_json = {**item, **({"conflict_review": previous_conflict} if previous_conflict else {})}
                review.reviewed_by, review.checked_at = ACTOR, now
            db.commit()
        return {"batch": BATCH, "applied": apply, "total_reviewed": len(plan), "counts": dict(counts),
                "reasons": dict(Counter(item["reason"] for item in plan)), "links_added": changed_links, "items": plan,
                "limitation": "Coincidencia de captura local; no verificación actual con Meta ni identidad verificada. No se eliminan ni fusionan casos."}
    except Exception:
        db.rollback()
        raise
