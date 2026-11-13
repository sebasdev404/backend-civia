"""Lectura de publicaciones: resúmenes ligeros y detalle bajo demanda."""

import json
from pathlib import Path

from sqlalchemy import JSON, and_, cast, case as sql_case, desc, func, or_
from sqlalchemy.exc import DataError
from sqlalchemy.orm import defer

from app.models.case import Case
from app.models.meta_post import MetaPost
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
    item.update(comment_id=notes.get("comment"), author_picture_url=None,
                author_is_protected="Perfil Protegido por Meta" in (case.author or ""))
    return notes.get("post"), item


def list_posts(db, *, month=None, search=None, network=None, limit=24, offset=0,
               include_details=False, post_id=None, cases_only=False, asset_base="http://127.0.0.1:8000"):
    query = db.query(MetaPost)
    reference = func.btrim(func.substring(Case.internal_notes, r"(?m)^\[Post ID\]:[ \t]*([^\r\n]+)"), " \t")
    image_key = func.split_part(Case.image_url, "?", 1)
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
            MetaPost.id.in_(db.query(reference).filter(reference.is_not(None))),
            func.split_part(MetaPost.cover_image, "?", 1).in_(db.query(image_key).filter(reference.is_(None), Case.image_url.is_not(None))),
        ))
    total = query.with_entities(func.count(MetaPost.id)).scalar() or 0
    if not include_details:
        query = query.options(defer(MetaPost.raw_comments_json))
    posts = query.order_by(desc(MetaPost.created_time), desc(MetaPost.id)).offset(offset).limit(limit).all()
    cases_total = db.query(func.count(Case.id)).scalar() or 0
    associated = {}
    counts = {}
    raw_counts = {}
    if posts:
        ids = [post.id for post in posts]
        covers = [post.cover_image.split("?")[0] for post in posts if post.cover_image]
        condition = or_(reference.in_(ids), and_(reference.is_(None), image_key.in_(covers)))
        if include_details:
            for case in db.query(Case).filter(condition).all():
                reference_id, item = _case_item(case)
                key = reference_id or (case.image_url.split("?")[0] if case.image_url else None)
                if key:
                    associated.setdefault(key, []).append(item)
            counts = {key: len(items) for key, items in associated.items()}
        else:
            key = func.coalesce(reference, image_key)
            counts = dict(db.query(key, func.count(Case.id)).filter(condition).group_by(key).all())
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

    results = []
    for post in posts:
        key = post.id
        if not counts.get(key) and post.cover_image:
            key = post.cover_image.split("?")[0]
        matched_count = counts.get(key, 0)
        cover, thumbnail = post_image_urls(post.id, post.cover_image, asset_base)
        item = {
            "id": post.id, "source": post.source or ("Instagram" if str(post.id).startswith("IG_") else "Facebook"),
            "title": post.title, "message": post.message if include_details else (post.message or "")[:360],
            "cover_image": cover, "thumbnail_url": thumbnail, "media_type": post.media_type,
            "published_at": post.published_at, "month_key": post.month_key, "permalink_url": post.permalink_url,
            "total_comments": max(post.total_comments or 0, matched_count, raw_counts.get(post.id, 0)), "cases_count": matched_count,
            "likes_count": post.likes_count or 0, "views_count": post.views_count or 0,
            "shares_count": post.shares_count or 0,
        }
        if include_details:
            try:
                raw = json.loads(post.raw_comments_json or "[]")
                raw = raw if isinstance(raw, list) else []
            except (ValueError, TypeError):
                raw = []
            by_id = {comment.get("id"): comment for comment in raw if isinstance(comment, dict)}
            matched = [dict(case) for case in associated.get(key, [])]
            for case in matched:
                comment = by_id.get(case.get("comment_id"))
                if comment:
                    case.update(
                        author=comment.get("author") or case["author"], author_id=comment.get("author_id"),
                        author_picture_url=comment.get("author_picture_url"),
                        author_is_protected=comment.get("author_is_protected", case["author_is_protected"]),
                        comment_permalink_url=comment.get("permalink_url"),
                    )
            item.update(cases=matched, raw_comments=raw, total_comments=max(item["total_comments"], len(raw)))
        results.append(item)
    return {"items": results, "total": total, "cases_total": cases_total, "limit": limit,
            "offset": offset, "has_more": offset + len(results) < total}
