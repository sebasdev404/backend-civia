"""Review repeated source claims without merging, deleting or rewriting case data."""
from collections import Counter, defaultdict
from datetime import datetime, timezone

from app.models.case import Case
from app.models.case_comment import CaseComment
from app.models.case_provenance import CaseProvenanceReview
from app.models.meta_post import MetaPost
from app.services.provenance_recovery import reference, read_capture, digest

METHOD = "exact_source_case_comparison_v1"
ACTOR = "system:case-conflict-review"
FIELDS = ("content", "author", "date_time", "source", "title", "category", "sentiment", "priority", "status",
          "location", "zone", "assigned_department", "assigned_to", "public_response", "resolution_note",
          "resolved_by", "institutional_radicado", "priority_action", "requires_followup", "comments_count",
          "impact_if_solved", "impact_if_ignored", "media_type", "image_url")


def case_fingerprint(case):
    return digest({field: getattr(case, field, None) for field in (*FIELDS, "internal_notes")})


def has_attention(case):
    return bool(case.status not in ("Pendiente", "Nuevo", None, "") or any(getattr(case, field, None)
        for field in ("assigned_to", "public_response", "resolution_note", "resolved_by", "institutional_radicado", "priority_action")))


def matches_capture(case, raw, pid):
    return bool(raw and reference(case.internal_notes, "Post ID") == pid
        and case.content == (raw.get("content") or raw.get("message"))
        and case.author and case.author == raw.get("author")
        and case.date_time and case.date_time == (raw.get("published_at") or raw.get("time")))


def compare_conflicts(cases, posts, links, reviews):
    by_id = {case.id: case for case in cases}
    captures = {post.id: read_capture(post.raw_comments_json) for post in posts}
    claims = defaultdict(set)
    for case in cases:
        pid, cid = reference(case.internal_notes, "Post ID"), reference(case.internal_notes, "Comment ID")
        if pid and cid:
            claims[(pid, cid)].add(case.id)
    for link in links:
        claims[(link.post_id, link.comment_id)].add(link.case_id)
    results = []
    for review in reviews:
        evidence = review.evidence_json or {}
        pid, cid = evidence.get("post_id"), evidence.get("comment_id")
        case = by_id.get(review.case_id)
        owners = sorted(claims.get((pid, cid), set()) - {review.case_id})
        raw = (captures.get(pid) or {}).get(cid)
        result = {"method": METHOD, "case_id": review.case_id, "post_id": pid, "comment_id": cid,
                  "related_case_ids": owners, "classification": "insufficient_evidence", "attention_case_ids": [],
                  "differences": {}, "case_fingerprints": {}, "capture_fingerprint": digest(raw) if raw else None,
                  "action": "manual_review_no_merge"}
        if case:
            result["case_fingerprints"][case.id] = case_fingerprint(case)
        if not case or not owners or not matches_capture(case, raw, pid):
            results.append(result)
            continue
        related = [by_id.get(key) for key in owners]
        if any(owner is None or not matches_capture(owner, raw, pid) for owner in related):
            results.append(result)
            continue
        for owner in related:
            result["case_fingerprints"][owner.id] = case_fingerprint(owner)
            result["differences"][owner.id] = [field for field in FIELDS if getattr(case, field, None) != getattr(owner, field, None)]
        result["attention_case_ids"] = sorted(item.id for item in [case, *related] if has_attention(item))
        if len(owners) > 1:
            result["classification"] = "same_source_multiple_cases"
        elif result["attention_case_ids"]:
            result["classification"] = "same_source_attention_recorded"
        elif any(result["differences"].values()):
            result["classification"] = "same_source_metadata_differs"
        else:
            result["classification"] = "same_source_same_case_data"
        results.append(result)
    return results


def run_conflict_review(db, *, apply=False, expected_count=None):
    try:
        posts_query = db.query(MetaPost).order_by(MetaPost.id)
        cases_query = db.query(Case).order_by(Case.id)
        if apply:
            posts_query, cases_query = posts_query.with_for_update(), cases_query.with_for_update()
        posts, cases = posts_query.all(), cases_query.all()
        query = db.query(CaseProvenanceReview).filter_by(reason="comment_linked_to_other_case").order_by(CaseProvenanceReview.case_id)
        reviews = (query.with_for_update() if apply else query).all()
        if expected_count is not None and len(reviews) != expected_count:
            raise ValueError("El lote cambió. Repite la revisión antes de guardar.")
        results = compare_conflicts(cases, posts, db.query(CaseComment).all(), reviews)
        saved = 0
        if apply:
            by_id = {review.case_id: review for review in reviews}
            now = datetime.now(timezone.utc)
            for result in results:
                review = by_id[result["case_id"]]
                old = dict((review.evidence_json or {}).get("conflict_review") or {})
                old.pop("checked_at", None); old.pop("reviewed_by", None)
                if old == result:
                    continue
                evidence = dict(review.evidence_json or {})
                evidence["conflict_review"] = {**result, "checked_at": now.isoformat(), "reviewed_by": ACTOR}
                review.evidence_json = evidence
                review.checked_at = now
                saved += 1
            db.commit()
        return {"applied": apply, "reviewed": len(results), "saved": saved,
                "counts": dict(Counter(item["classification"] for item in results)), "items": results,
                "limitation": "Mismo comentario de origen no significa que ambos expedientes puedan fusionarse. No se modifican casos, vínculos ni estados de atención."}
    except Exception:
        db.rollback()
        raise
