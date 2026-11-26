"""Lectura de publicaciones: resúmenes ligeros y detalle bajo demanda."""

import json
from pathlib import Path

from sqlalchemy import JSON, and_, cast, case as sql_case, desc, func, or_,select
from sqlalchemy.exc import DataError
from sqlalchemy.orm import defer

from app.models.case import Case
from app.models.case_comment import CaseComment
from app.models.meta_post import MetaPost
from app.models.publication import PublicationSnapshot
from app.models.case_consolidation import CaseConsolidation
from app.services.post_images import post_image_urls


def _case_item(case):
    notes = {}
    for line in (case.internal_notes or "").splitlines():
        if line.startswith("[Post ID]:"):
            notes["post"] = line.split(":", 1)[1].strip()
        elif line.startswith("[Comment ID]:"):
            notes["comment"] = line.split(":", 1)[1].strip()
    item = {key: getattr(case, key) for key in (
        "id", "author", "content", "category", "sentiment", "priority", "location",
        "date_time", "status", "priority_action", "assigned_department",
    )}
    item.update(comment_id=notes.get("comment"), author_picture_url=None, author_identity_status="historical_unverified",
                author_is_protected="Perfil Protegido por Meta" in (case.author or ""))
    return notes.get("post"), item


def list_posts(db, *, month=None, search=None, network=None, limit=24, offset=0,
               include_details=False, post_id=None, cases_only=False, asset_base="http://127.0.0.1:8000"):
    query = db.query(MetaPost)
    reference = func.btrim(func.substring(Case.internal_notes, r"(?m)^\[Post ID\]:[ \t]*([^\r\n]+)"), " \t")
    visible=~Case.id.in_(select(CaseConsolidation.duplicate_case_id).where(CaseConsolidation.undone_at.is_(None)))
    if post_id:
        query = query.filter(MetaPost.id == post_id)
    if month and month != "all":
        query = query.filter(MetaPost.month_key == month)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(MetaPost.title.ilike(term) | MetaPost.message.ilike(term))
    if network and network != "all":
        query = query.filter(MetaPost.source.ilike(f"%{network}%"))
    if cases_only:
        query = query.filter(or_(
            MetaPost.id.in_(db.query(CaseComment.post_id).join(Case,Case.id==CaseComment.case_id).filter(visible)),
            MetaPost.id.in_(db.query(reference).filter(reference.is_not(None),visible)),
        ))
    total = query.with_entities(func.count(MetaPost.id)).scalar() or 0
    if not include_details:
        query = query.options(defer(MetaPost.raw_comments_json))
    posts = query.order_by(desc(MetaPost.created_time), desc(MetaPost.id)).offset(offset).limit(limit).all()
    cases_total = db.query(func.count(Case.id)).filter(visible).scalar() or 0
    associated = {}
    counts = {}
    raw_counts = {}
    if posts:
        ids = [post.id for post in posts]
        condition = reference.in_(ids)
        if include_details:
            for case in db.query(Case).filter(condition,visible).all():
                reference_id, item = _case_item(case)
                key = reference_id
                if key:
                    associated.setdefault(key, []).append(item)
            for link, case in db.query(CaseComment, Case).join(Case, Case.id == CaseComment.case_id).filter(CaseComment.post_id.in_(ids),visible):
                if not any(item["id"] == case.id for item in associated.get(link.post_id, [])):
                    _, item = _case_item(case)
                    item["comment_id"] = link.comment_id
                    associated.setdefault(link.post_id, []).append(item)
            counts = {key: len(items) for key, items in associated.items()}
        else:
            key = reference
            pairs = db.query(key.label("key"), Case.id.label("case_id")).filter(condition,visible).union(
                db.query(CaseComment.post_id, CaseComment.case_id).join(Case,Case.id==CaseComment.case_id).filter(CaseComment.post_id.in_(ids),visible)
            ).subquery()
            counts = dict(db.query(pairs.c.key, func.count()).group_by(pairs.c.key).all())
            # PostgreSQL devuelve solo el conteo, sin transferir los comentarios al proceso web.
            raw_count = sql_case(
                (or_(MetaPost.raw_comments_json.is_(None), MetaPost.raw_comments_json == ""), 0),
                else_=func.json_array_length(cast(MetaPost.raw_comments_json, JSON)),
            )
            try:
                with db.begin_nested():
                    raw_counts = dict(db.query(MetaPost.id, raw_count).filter(MetaPost.id.in_(ids)).all())
            except DataError:
                # Mantener compatibilidad con capturas antiguas que no sean JSON válido.
                for identity, captured in db.query(MetaPost.id, MetaPost.raw_comments_json).filter(MetaPost.id.in_(ids)):
                    try:
                        parsed = json.loads(captured or "[]")
                        raw_counts[identity] = len(parsed) if isinstance(parsed, list) else 0
                    except (ValueError, TypeError):
                        raw_counts[identity] = 0

    snapshots = {row.post_id: row for row in db.query(PublicationSnapshot).filter(
        PublicationSnapshot.post_id.in_([post.id for post in posts])
    ).all()} if posts else {}
    results = []
    for post in posts:
        key = post.id
        matched_count = counts.get(key, 0)
        cover, thumbnail = post_image_urls(post.id, post.cover_image, asset_base)
        item = {
            "id": post.id, "source": post.source or ("Instagram" if str(post.id).startswith("IG_") else "Facebook"),
            "title": post.title, "message": post.message if include_details else (post.message or "")[:360],
            "cover_image": cover, "thumbnail_url": thumbnail, "media_type": post.media_type,
            "published_at": post.published_at, "month_key": post.month_key, "permalink_url": post.permalink_url,
            "total_comments": max(post.total_comments or 0, raw_counts.get(post.id, 0)), "cases_count": matched_count,
            "reported_comments": post.total_comments, "captured_comments": raw_counts.get(post.id,0),
            **post_metric_values(post, snapshots.get(post.id)),
        }
        if include_details:
            try:
                raw = json.loads(post.raw_comments_json or "[]")
                raw = raw if isinstance(raw, list) else []
            except (ValueError, TypeError):
                raw = []
            by_id = {comment.get("id"): comment for comment in raw if isinstance(comment, dict)}
            for link in db.query(CaseComment).filter(CaseComment.post_id == post.id):
                if link.comment_id in by_id:
                    by_id[link.comment_id]["case_id"] = link.case_id
            matched = [dict(case) for case in associated.get(key, [])]
            for case in matched:
                comment = by_id.get(case.get("comment_id"))
                if comment and case['author']==comment.get('author') and case['content']==(comment.get('content') or comment.get('message')):
                    case.update(
                        author_identity_status="captured_exact_match",
                        author=comment.get("author") or case["author"], author_id=comment.get("author_id"),
                        author_picture_url=comment.get("author_picture_url"),
                        author_is_protected=comment.get("author_is_protected", case["author_is_protected"]),
                        comment_permalink_url=comment.get("permalink_url"),
                    )
            item.update(cases=matched, raw_comments=raw, captured_comments=len(raw), total_comments=max(item["total_comments"], len(raw)))
        results.append(item)
    return {"items": results, "total": total, "cases_total": cases_total, "limit": limit,
            "offset": offset, "has_more": offset + len(results) < total}


def post_metric_values(post, snapshot):
    """Use captured counts, preserving confirmed zeros and unknown legacy values."""
    try:
        views = json.loads(getattr(snapshot, 'reactions_json', None) or '{}').get('views', {})
    except (ValueError, TypeError):
        views = {}
    return {
        "likes_count": snapshot.likes_count if snapshot else (post.likes_count or None),
        "reactions_count": snapshot.reactions_count if snapshot else None,
        "views_count": views.get('count', post.views_count or None),
        "views_status": views.get('status', 'historical' if post.views_count else 'not_checked'),
        "views_detail": views.get('detail', 'Vistas de contenido; no equivalen a alcance ni a reproducciones de tres segundos.' if views.get('metric') else 'No hay captura verificada de vistas; los valores históricos están pendientes de validar.'),
        "shares_count": snapshot.shares_count if snapshot else (post.shares_count or None),
        "metrics_status": snapshot.status if snapshot else "not_checked",
        "metrics_updated_at": snapshot.updated_at if snapshot else None,
        "metrics_detail": snapshot.detail if snapshot else "Métricas pendientes de consulta; un guion indica un dato no disponible.",
    }
