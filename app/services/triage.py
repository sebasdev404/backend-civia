"""Explicit, transactional review of captured comments; no AI or external side effects."""
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import tuple_
from app.models.case import Case
from app.models.case_comment import CaseComment
from app.models.meta_post import MetaPost
from app.services.case_consolidation import assert_writable
from app.services import case_workflow as workflow


def captured_comments(post):
    try:
        data = json.loads(post.raw_comments_json or "[]")
    except (ValueError, TypeError):
        return {}
    return {str(c["id"]): c for c in data if isinstance(c, dict) and c.get("id")} if isinstance(data, list) else {}


def legacy_references(db):
    result = {}
    for case_id, notes in db.query(Case.id, Case.internal_notes).filter(Case.internal_notes.isnot(None)):
        post = re.search(r"(?m)^\[Post ID\]:[ \t]*([^\r\n]+)", notes)
        comment = re.search(r"(?m)^\[Comment ID\]:[ \t]*([^\r\n]+)", notes)
        if post and comment:
            result.setdefault((post[1].strip(), comment[1].strip()), set()).add(case_id)
    return result


def pending_comments(db, limit=50):
    assigned = set(legacy_references(db))
    assigned.update((p, c) for p, c in db.query(CaseComment.post_id, CaseComment.comment_id))
    result = []
    # Recent captured publications only; do not claim a census of all Meta history.
    posts = db.query(MetaPost).order_by(MetaPost.created_time.desc(), MetaPost.id.desc()).limit(200)
    for post in posts:
        for cid, comment in captured_comments(post).items():
            content = comment.get("content") or comment.get("message") or ""
            if (post.id, cid) in assigned or not isinstance(content, str) or not content.strip():
                continue
            key = hashlib.sha256(f"{post.id}\0{cid}".encode()).hexdigest()
            result.append({"id": key, "post_id": post.id, "comment_id": cid,
                "source": post.source or "Canal no disponible", "author": comment.get("author") or "Autor no disponible",
                "post_url": post.permalink_url, "comment_url": comment.get("permalink_url"),
                "author_picture_url": comment.get("author_picture_url"),
                "author_is_protected": comment.get("author_is_protected", not comment.get("author") or "Perfil Protegido por Meta" in (comment.get("author") or "")),
                "postTitle": post.title, "content": content, "detectedIntent": "Por revisar",
                "detectedLocation": "No determinada", "referenceStreet": "Sin ubicación confirmada",
                "detectedCategory": "Por revisar", "detectedTopic": "Por revisar", "detectedProblem": content[:100],
                "aiConfidence": None, "requiresFollowup": False, "possibleCaseMatch": None,
                "metaDirectContactAllowed": False, "dateTime": comment.get("published_at") or comment.get("time") or "Fecha no disponible"})
            if len(result) >= limit:
                return result
    return result


def consolidate_comments(db, payload, user):
    keys = sorted({(ref.post_id, ref.comment_id) for ref in payload.comments})
    try:
        # Stable lock order serializes overlapping requests across server processes.
        posts = {p.id: p for p in db.query(MetaPost).filter(MetaPost.id.in_({p for p, _ in keys})).order_by(MetaPost.id).with_for_update()}
        captured = {pid: captured_comments(post) for pid, post in posts.items()}
        if any(cid not in captured.get(pid, {}) for pid, cid in keys):
            raise HTTPException(404, "Uno o varios comentarios no están en la captura. Actualiza la bandeja.")
        texts = [captured[pid][cid].get("content") or captured[pid][cid].get("message") or "" for pid, cid in keys]
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise HTTPException(422, "No se puede crear una solicitud desde un comentario vacío")
        prior = legacy_references(db)
        links = db.query(CaseComment).filter(tuple_(CaseComment.post_id, CaseComment.comment_id).in_(keys)).all()
        for link in links:
            prior.setdefault((link.post_id, link.comment_id), set()).add(link.case_id)
        related = set().union(*(prior.get(key, set()) for key in keys))
        target_id = payload.target_case_id
        if len(related) > 1 or (target_id and related and related != {target_id}):
            raise HTTPException(409, "La selección incluye comentarios vinculados a otro caso. No se movió ninguno.")
        target_id = target_id or next(iter(related), None)
        case = db.query(Case).filter(Case.id == target_id).with_for_update().first() if target_id else None
        if target_id and case is None:
            raise HTTPException(404, "El caso de destino no existe")
        if case:
            assert_writable(db, case.id)
        if case and case.status not in workflow.OPEN:
            raise HTTPException(409, "El caso de destino está cerrado. Revisa su gestión antes de asociar comentarios.")
        created = case is None
        before = workflow.snapshot(case) if case else {}
        first = captured[keys[0][0]][keys[0][1]]
        if created:
            texts = [captured[p][c].get("content") or captured[p][c].get("message") for p, c in keys]
            authors = {captured[p][c].get("author") or "Autor no disponible" for p, c in keys}
            channels = {posts[p].source or "Canal no disponible" for p, _ in keys}
            case = Case(id="CIV-" + uuid.uuid4().hex[:24].upper(),
                title=payload.title or ("Solicitud ciudadana: " + texts[0])[:255], content="\n\n".join(texts),
                author=(next(iter(authors)) if len(authors) == 1 else f"Varios autores ({len(authors)})")[:100],
                source=(next(iter(channels)) if len(channels) == 1 else "Facebook / Instagram"),
                priority="Media", category="Por revisar", sentiment="Sin evaluar", location="No especificada",
                zone="Sin determinar", status="Pendiente", media_type="none", requires_followup=True,
                date_time=str(first.get("published_at") or first.get("time") or datetime.now(timezone.utc).isoformat()),
                comments_count=0, institutional_radicado=None)
            if len(posts) == 1:
                case.internal_notes = f"[Post ID]: {keys[0][0]}"
            db.add(case)
            db.flush()
        linked_keys = {(link.post_id, link.comment_id) for link in links}
        added = 0
        adopted = 0
        for pid, cid in keys:
            if (pid, cid) not in linked_keys:
                db.add(CaseComment(post_id=pid, comment_id=cid, case_id=case.id,
                    comment_json=captured[pid][cid], linked_by=user.id))
                if (pid, cid) in prior:
                    adopted += 1
                else:
                    added += 1
        if created:
            case.comments_count = added
        else:
            case.comments_count = max(case.comments_count or 0, adopted) + added
        if added or adopted:
            note = f"{added} comentarios asociados; {adopted} vínculos anteriores normalizados."
            workflow.record(db, case, user, 'created_from_comments' if created else 'comments_linked', note, before)
        db.commit()
        return {"case_id": case.id, "created": created, "linked": added,
                "already_linked": len(keys) - added, "comments_count": case.comments_count}
    except Exception:
        db.rollback()
        raise
