"""Bounded case summaries with exact source-post references; no external I/O."""
from sqlalchemy import desc, func, or_

from app.models.case import Case
from app.models.meta_post import MetaPost
from app.services.post_images import post_image_urls


def filtered_cases(db, *, search=None, priority=None, category=None, source=None, status=None,
                   department=None, priority_only=False):
    query = db.query(Case)
    for column, value in ((Case.priority, priority), (Case.category, category),
                          (Case.source, source), (Case.status, status)):
        if value and value != "all":
            query = query.filter(column == value)
    if department and department != "all":
        query = query.filter(Case.assigned_department.contains(department, autoescape=True))
    if priority_only:
        query = query.filter(Case.priority_action.is_(True))
    if search and search.strip():
        term = "%" + search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.filter(or_(*[column.ilike(term, escape="\\") for column in (
            Case.title, Case.content, Case.location, Case.author, Case.id, Case.assigned_department,
        )]))
    return query


def list_case_summaries(db, *, limit=24, offset=0, asset_base="http://127.0.0.1:8000", **filters):
    query = filtered_cases(db, **filters)
    total = query.with_entities(func.count(Case.id)).scalar() or 0
    reference = func.btrim(func.substring(Case.internal_notes, r"(?m)^\[Post ID\]:[ \t]*([^\r\n]+)"), " \t")
    rows = query.with_entities(*[getattr(Case, field) for field in (
        "id", "source", "author", "priority", "title", "category", "sentiment", "location",
        "date_time", "status", "media_type", "image_url", "institutional_radicado",
        "assigned_department", "assigned_to", "priority_action", "comments_count",
        "impact_if_solved", "impact_if_ignored",
    )], func.left(Case.content, 600).label("content"), reference.label("post_id"),
        MetaPost.cover_image.label("post_cover"), MetaPost.id.label("matched_post_id"),
        MetaPost.media_type.label("post_media_type"), MetaPost.title.label("post_title"),
    ).outerjoin(MetaPost, MetaPost.id == reference).order_by(desc(Case.created_at), desc(Case.id)).offset(offset).limit(limit).all()
    items = []
    for row in rows:
        item = dict(row._mapping)
        pid = item["post_id"]
        # An orphan source reference must never borrow another post's picture.
        recorded = item.pop("post_cover") if item.pop("matched_post_id") else (
            item["image_url"] if not pid or (item["image_url"] or "").split("?", 1)[0].endswith(f"/{pid}.jpg") else None
        )
        cover, thumbnail = post_image_urls(pid, recorded, asset_base)
        item["image_url"] = cover
        item["thumbnail_url"] = thumbnail
        item["media_type"] = item.pop("post_media_type") or item["media_type"]
        item["media_available"] = bool(cover)
        items.append(item)
    return {"items": items, "total": total, "limit": limit, "offset": offset,
            "has_more": offset + len(items) < total}
