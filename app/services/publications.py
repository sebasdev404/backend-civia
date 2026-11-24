import json
import unicodedata
from datetime import datetime, timezone
from sqlalchemy import desc
from sqlalchemy.orm import defer

from app.core.config import settings
from app.models.meta_post import MetaPost
from app.models.publication import PublicationSource, ObservedPost, PublicationSnapshot
from app.services.automation_signals import comment_signals
from app.services.facebook_graph import GraphAPIError, facebook_author_fields, graph_get, iter_connection, read_post_comments
from app.services.post_images import post_image_urls

IDENTITY_NOTE = "Se muestran únicamente nombres que Meta entrega. Un nombre visible no verifica identidad y la lista de reacciones puede estar restringida."


def ensure_sources(db):
    defaults = [
        ("johan", "Johan Steed", f"https://www.facebook.com/{settings.META_PAGE_ID}", settings.META_PAGE_ID, "connected", "Publicaciones ya capturadas de las redes conectadas a CIVIA."),
        ("jorge-gechem", "Jorge Andrés Gechem", "https://www.facebook.com/JorgeAndresGA", "JorgeAndresGA", "not_checked", "Fuente registrada desde el enlace aportado. El acceso debe ser comprobado con Meta."),
    ]
    for identity, name, url, node, status, detail in defaults:
        if db.get(PublicationSource, identity) is None:
            db.add(PublicationSource(id=identity, name=name, url=url, graph_node=node, status=status, detail=detail))
    db.commit()


def sources(db):
    result = []
    for source in db.query(PublicationSource).order_by(PublicationSource.id):
        count = db.query(MetaPost).count() if source.id == "johan" else db.query(ObservedPost).filter(ObservedPost.source_id == source.id).count()
        result.append({"id": source.id, "name": source.name, "url": source.url, "status": source.status,
                       "detail": source.detail, "checked_at": source.checked_at, "posts_count": count})
    return result


def parse_rows(raw):
    try:
        value = json.loads(raw or "[]")
    except (ValueError, TypeError):
        return []
    by_id = {}
    for row in value if isinstance(value, list) else []:
        if isinstance(row, dict) and row.get("id"):
            by_id[str(row["id"])] = {**row, "id": str(row["id"]), "content": row.get("content") or row.get("message") or ""}
    return list(by_id.values())


def _summary(post, snapshot, own, asset_base):
    if own:
        cover, thumb = post_image_urls(post.id, post.cover_image, asset_base)
    else:
        cover = thumb = post.cover_image
    return {
        "id": post.id, "title": post.title, "message": (post.message or "")[:400],
        "source": (post.source or "Facebook") if own else "Facebook", "cover_image": cover, "thumbnail_url": thumb,
        "media_type": post.media_type, "published_at": post.published_at if own else post.created_time,
        "permalink_url": post.permalink_url, "total_comments": post.total_comments,
        # Cero histórico no prueba que la métrica haya sido consultada.
        "likes_count": snapshot.likes_count if snapshot else (post.likes_count if own and post.likes_count else None),
        "reactions_count": snapshot.reactions_count if snapshot else None,
        "shares_count": snapshot.shares_count if snapshot else (post.shares_count if own and post.shares_count else None),
        "metrics_status": snapshot.status if snapshot else "not_checked", "metrics_updated_at": snapshot.updated_at if snapshot else None,
    }


def list_publications(db, *, source_id="johan", search=None, network=None, limit=12, offset=0, asset_base="http://127.0.0.1:8000"):
    own = source_id == "johan"
    model = MetaPost if own else ObservedPost
    query = db.query(model)
    if not own:
        query = query.filter(ObservedPost.source_id == source_id)
    if search:
        query = query.filter(model.title.ilike(f"%{search.strip()}%") | model.message.ilike(f"%{search.strip()}%"))
    if network and network != "all":
        if own:
            query = query.filter(MetaPost.source.ilike(f"%{network}%"))
        elif network != "Facebook":
            query = query.filter(ObservedPost.id.is_(None))
    total = query.count()
    posts = query.options(defer(model.raw_comments_json)).order_by(desc(model.created_time), desc(model.id)).offset(offset).limit(limit).all()
    snapshots = {s.post_id: s for s in db.query(PublicationSnapshot).filter(PublicationSnapshot.post_id.in_([p.id for p in posts]))}
    return {"items": [_summary(p, snapshots.get(p.id), own, asset_base) for p in posts], "total": total,
            "limit": limit, "offset": offset, "has_more": offset + len(posts) < total}


def find_post(db, source_id, post_id):
    if source_id == "johan":
        return db.get(MetaPost, post_id)
    return db.query(ObservedPost).filter(ObservedPost.id == post_id, ObservedPost.source_id == source_id).first()


def publication_detail(db, source_id, post_id, *, offset=0, limit=5, reactions_offset=0, search=None, signals_only=False, asset_base="http://127.0.0.1:8000"):
    post = find_post(db, source_id, post_id)
    if post is None:
        return None
    snapshot = db.get(PublicationSnapshot, post.id)
    rows = parse_rows(post.raw_comments_json)
    all_count = len(rows)
    evidence = comment_signals(rows)
    by_id = {c["id"]: c["content"] for c in rows}
    for row in rows:
        row["automation"] = evidence[row["id"]]
        row["parent_content"] = by_id.get(str(row.get("parent_id")))
        row["author_is_protected"] = row.get("author_is_protected", not bool(row.get("author_id")))
    if search:
        term = search.casefold().strip()
        rows = [r for r in rows if term in (r["content"] + " " + (r.get("author") or "")).casefold()]
    if signals_only:
        rows = [r for r in rows if r["automation"]["status"] == "review"]
    try:
        captured = json.loads(snapshot.reactions_json or "{}") if snapshot else {}
    except (ValueError, TypeError):
        captured = {}
    participants = captured.get("items", [])
    return {**_summary(post, snapshot, source_id == "johan", asset_base), "message": post.message,
            "comments": rows[offset:offset + limit], "comments_total": len(rows), "captured_comments": all_count,
            "comments_has_more": offset + limit < len(rows), "identity_note": IDENTITY_NOTE,
            "reaction_people": participants[reactions_offset:reactions_offset + limit], "reaction_people_total": len(participants),
            "reaction_people_status": captured.get("status", "not_checked"),
            "reaction_people_detail": captured.get("detail", "Las identidades de quienes reaccionaron no han sido consultadas."),
            "reaction_people_truncated": captured.get("truncated", False),
            "metrics_detail": snapshot.detail if snapshot else "Actualiza esta publicación para consultar sus métricas disponibles en Meta."}


def capture_metrics(db, post_id, token, *, identities=False):
    snapshot = db.get(PublicationSnapshot, post_id)
    if snapshot is None:
        snapshot = PublicationSnapshot(post_id=post_id)
        db.add(snapshot)
    issues = []
    successful = 0
    # Consultar los edges soportados por separado: una expansion de campos
    # rechazada no debe ocultar los conteos que si estan disponibles.
    for attribute, extra in (("reactions_count", {}), ("likes_count", {"type": "LIKE"})):
        try:
            metric = graph_get(f"{post_id}/reactions", token, limit=0, summary="total_count", **extra)
            count = (metric.get("summary") or {}).get("total_count")
            if isinstance(count, int):
                setattr(snapshot, attribute, count)
                successful += 1
        except Exception as exc:
            code = getattr(exc, "code", None)
            issues.append(f"Meta no entrego {attribute} (codigo {code or type(exc).__name__}). Se conserva la captura anterior.")
    try:
        metric = graph_get(post_id, token, fields="id,shares")
        count = (metric.get("shares") or {}).get("count")
        if isinstance(count, int):
            snapshot.shares_count = count
            successful += 1
    except Exception as exc:
        issues.append(f"Meta no entrego compartidos ({type(exc).__name__}).")
    post = db.get(MetaPost, post_id)
    if post is not None:
        try:
            result = graph_get(f"{post_id}/insights", token, metric="post_media_view")
            count = next((v.get('value') for row in result.get('data', []) if row.get('name') == 'post_media_view'
                          for v in row.get('values', []) if isinstance(v.get('value'), int)), None)
            if count is None:
                raise ValueError('Missing view metric')
            captured = json.loads(snapshot.reactions_json or '{}')
            captured['views'] = {'count': count, 'metric': 'post_media_view', 'status': 'available', 'checked_at': datetime.now(timezone.utc).isoformat()}
            snapshot.reactions_json = json.dumps(captured, ensure_ascii=False)
            post.views_count = count
            successful += 1
        except Exception as exc:
            captured = json.loads(snapshot.reactions_json or '{}')
            captured['views'] = {**captured.get('views', {}), 'status': 'unavailable', 'detail': 'Meta devolvió la consulta sin un conteo de vistas.' if isinstance(exc, ValueError) else f'Meta no entregó vistas (código {getattr(exc, "code", None) or type(exc).__name__}).'}
            snapshot.reactions_json = json.dumps(captured, ensure_ascii=False)
            issues.append('No se pudieron actualizar las vistas; no se sustituyen por cero.')
    snapshot.status = "unavailable" if not successful else "partial" if issues else "available"
    snapshot.detail = "Metricas devueltas por Meta; un guion indica que ese dato no fue entregado."
    if issues:
        snapshot.detail += " Algunas metricas no pudieron actualizarse; se conserva cualquier captura anterior."
    if identities:
        people = {}
        try:
            truncated = False
            for index, page in enumerate(iter_connection(f"{post_id}/reactions", token, fields="id,name,type", limit=50)):
                for person in page.get("data", []):
                    if person.get("id"):
                        people[str(person["id"])] = {"id": str(person["id"]), "name": person.get("name"), "type": person.get("type"), "identity_verified": False}
                if index >= 4:
                    truncated = bool((page.get("paging") or {}).get("next"))
                    break
            snapshot.reactions_json = json.dumps({**json.loads(snapshot.reactions_json or '{}'), "items": list(people.values()), "status": "partial" if truncated or (snapshot.reactions_count is not None and len(people) < snapshot.reactions_count) else "available",
                "truncated": truncated, "detail": "Solo identidades entregadas por Meta; no equivale a la lista completa de personas que reaccionaron."}, ensure_ascii=False)
        except Exception:
            previous = json.loads(snapshot.reactions_json or "{}")
            snapshot.reactions_json = json.dumps({**previous, "status": "unavailable", "detail": "Meta restringió la lectura de identidades. El conteo de reacciones puede estar disponible aunque los nombres no lo estén."}, ensure_ascii=False)
    db.commit()
    return issues


def normalized_comments(comments):
    return [{"id": c["id"], **facebook_author_fields(c), "content": (c.get("message") or "").strip(),
             "time": c.get("created_time"), "likes_count": c.get("like_count"),
             "parent_id": (c.get("parent") or {}).get("id"), "source": "Facebook"}
            for c in comments if c.get("id") and (c.get("message") or "").strip()]


def source_permission_error(source, exc):
    code = exc.code if isinstance(exc, GraphAPIError) else None
    source.status = "missing_permissions" if code in (10, 200, 283) else "unavailable"
    source.detail = (f"Meta rechazó el acceso a esta fuente (código {code}). Se necesita acceso autorizado a la página o la capacidad Page Public Content Access aprobada por Meta. Si es un perfil personal, un token de otra página no habilita su lectura."
                     if code in (10, 200, 283) else f"No se pudo consultar esta fuente en Meta ({type(exc).__name__}). Se conservan las capturas anteriores.")
    source.checked_at = datetime.now(timezone.utc)


def sync_external(db, source_id, progress):
    source = db.get(PublicationSource, source_id)
    token = settings.META_PAGE_ACCESS_TOKEN
    progress(stage="access", detail=f"Comprobando acceso a {source.name}")
    try:
        identity = graph_get(source.graph_node, token, fields="id,name,link")
        name = unicodedata.normalize("NFKD", identity.get("name", "")).encode("ascii", "ignore").decode().lower()
        if source_id == "jorge-gechem" and not all(part in name for part in ("jorge", "andres", "gechem")):
            source.status, source.detail = "identity_mismatch", "La identidad devuelta por Meta no coincide con Jorge Andrés Gechem. No se importó contenido."
            source.checked_at = datetime.now(timezone.utc)
            db.commit()
            return {"status": "partial", "posts_updated": 0, "detail": source.detail}
        node = identity["id"]
        posts = graph_get(f"{node}/posts", token, fields="id,message,created_time,permalink_url,full_picture,attachments{media_type,type,target,subattachments}", limit=12).get("data", [])
    except Exception as exc:
        source_permission_error(source, exc)
        db.commit()
        return {"status": "partial", "posts_updated": 0, "detail": source.detail}
    source.status, source.detail, source.checked_at = "available", "Meta autorizó la lectura de esta fuente; se consultan hasta 12 publicaciones recientes por actualización.", datetime.now(timezone.utc)
    source.graph_node = node
    db.commit()
    errors, updated = [], 0
    for index, item in enumerate(posts):
        progress(stage="comments", completed=index, total=len(posts), detail=f"Consultando publicación {index + 1} de {len(posts)}")
        try:
            comments, total = read_post_comments(item, token)
            post = db.get(ObservedPost, item["id"])
            if post is None:
                post = ObservedPost(id=item["id"], source_id=source_id)
                db.add(post)
            post.message = item.get("message") or ""
            post.title = (post.message.split("\n")[0] or "Publicación de " + source.name)[:255]
            post.created_time, post.permalink_url = item.get("created_time"), item.get("permalink_url")
            post.cover_image = item.get("full_picture")
            attachments = (item.get("attachments") or {}).get("data", [])
            post.media_type = "video" if attachments and "video" in str(attachments[0]).lower() else "image"
            post.total_comments, post.raw_comments_json = total, json.dumps(normalized_comments(comments), ensure_ascii=False)
            db.commit()
            errors.extend(capture_metrics(db, post.id, token))
            updated += 1
        except Exception:
            db.rollback()
            errors.append("No se pudo actualizar una publicación; se conservan los datos anteriores.")
    return {"status": "partial" if errors else "success", "posts_updated": updated, "errors": errors,
            "detail": f"Se actualizaron {updated} publicaciones de {source.name}."}


def refresh_publication(db, source_id, post_id, progress):
    post = find_post(db, source_id, post_id)
    token = settings.META_PAGE_ACCESS_TOKEN
    if source_id == "johan" and (post.source or "").lower() == "instagram":
        return {"status": "partial", "detail": "Actualiza Instagram desde Sincronizar redes; las reacciones de Facebook no aplican a esta publicación."}
    progress(stage="comments", detail="Consultando comentarios de esta publicación")
    errors = []
    try:
        remote = graph_get(post_id, token, fields="id,attachments{media_type,type,target,subattachments}")
        comments, count = read_post_comments(remote, token)
        post.raw_comments_json = json.dumps(normalized_comments(comments), ensure_ascii=False)
        post.total_comments = count
        db.commit()
    except Exception:
        db.rollback()
        errors.append("Meta no permitió actualizar los comentarios. Se conserva la captura anterior.")
    progress(stage="reactions", detail="Consultando métricas e identidades disponibles en Meta")
    errors.extend(capture_metrics(db, post_id, token, identities=True))
    return {"status": "partial" if errors else "success", "posts_updated": 1,
            "detail": "Se completaron las consultas disponibles. Revisa las observaciones de Meta." if errors else "Publicación actualizada. Los nombres restringidos por Meta no se pueden recuperar.", "errors": errors}
