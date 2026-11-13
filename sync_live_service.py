import os
import sys
import json
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.core.config import settings
from app.core.database import SessionLocal, engine, Base
from app.models.case import Case
from app.models.meta_post import MetaPost
from app.services.ai_classifier import ai_classifier
from app.services.facebook_graph import COMMENT_FIELDS, facebook_author_fields, graph_get, iter_connection, read_post_comments
from app.services.instagram_graph import MEDIA_FIELDS, get_instagram_connection, normalize_instagram_comment, read_instagram_comments

os.makedirs("static/covers", exist_ok=True)

def ensure_db_schema():
    """Asegura que las columnas necesarias existan en PostgreSQL."""
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE meta_posts ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'Facebook';"))
            conn.commit()
            print("Esquema de BD verificado (columna source presente).", flush=True)
        except Exception as e:
            print(f"Nota en esquema: {e}", flush=True)

def format_colombia_datetime(iso_str: str) -> str:
    if not iso_str:
        return "Fecha reciente"
    try:
        dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%S%z")
        col_tz = timezone(timedelta(hours=-5))
        dt_col = dt.astimezone(col_tz)
        meses = {
            1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
            7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"
        }
        return f"{dt_col.day} {meses[dt_col.month]} {dt_col.year}, {dt_col.strftime('%I:%M %p')}"
    except Exception:
        return iso_str[:16].replace("T", " ")

def get_month_key(iso_str: str) -> str:
    if not iso_str:
        return "2026-10"
    return iso_str[:7]

def download_and_cache_cover(post_id: str, remote_url: str) -> str:
    """
    Descarga la imagen de Meta y la almacena localmente en static/covers/{post_id}.jpg
    para evitar expiraciones de tokens CDN (error 403 Forbidden).
    """
    safe_id = post_id.replace(":", "_").replace("/", "_")
    local_path = os.path.join("static", "covers", f"{safe_id}.jpg")
    public_url = f"http://localhost:8000/static/covers/{safe_id}.jpg"

    if os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
        return public_url

    if remote_url and remote_url.startswith("http"):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            req = urllib.request.Request(remote_url, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as response:
                with open(local_path, "wb") as f:
                    f.write(response.read())
            print(f"Caratula guardada localmente: {local_path} ({os.path.getsize(local_path)} bytes)", flush=True)
            return public_url
        except Exception as e:
            print(f"No se pudo descargar portada para {post_id}: {e}", flush=True)

    return public_url if os.path.exists(local_path) and os.path.getsize(local_path) > 1000 else None

def is_meaningful_comment(text_val: str) -> bool:
    if not text_val:
        return False
    clean = text_val.strip()
    if len(clean) < 8:
        return False
    low = clean.lower()
    trivial = ["amen", "amén", "bendiciones", "saludos", "gracias", "excelente", "buen dia", "buenos dias", "exitos", "éxitos", "hola"]
    if low in trivial:
        return False
    return True

def generate_next_case_id(db) -> str:
    """Calcula el siguiente código de caso garantizando cero colisiones."""
    recent_ids = (
        db.query(Case.id)
        .filter(Case.id.like("CIV-2026-%"))
        .order_by(Case.id.desc())
        .limit(100)
        .all()
    )
    max_num = 0
    for (cid,) in recent_ids:
        parts = cid.split("-")
        if len(parts) >= 3 and parts[-1].isdigit():
            val = int(parts[-1])
            if val > max_num:
                max_num = val

    if max_num == 0:
        max_num = db.query(Case).count()

    while True:
        max_num += 1
        candidate = f"CIV-2026-{str(max_num).zfill(4)}"
        if not db.query(Case.id).filter(Case.id == candidate).first():
            return candidate

def sync_facebook_post_comments(db, post_id: str) -> dict:
    """Actualiza los comentarios reales de un post almacenado, sin crear casos.

    Permite verificar una publicación puntual sin recorrer todo el histórico
    ni convertir un comentario de apoyo en un caso ciudadano.
    """
    token = settings.META_PAGE_ACCESS_TOKEN
    if not token:
        raise RuntimeError("Token de Meta no disponible")
    meta_post = db.get(MetaPost, post_id)
    if meta_post is None:
        raise ValueError("La publicación aún no está almacenada en CIVIA")

    post = graph_get(post_id, token, fields="id,attachments{media_type,type,target,subattachments}")
    comments, total = read_post_comments(post, token)
    try:
        previous_ids = {c.get("id") for c in json.loads(meta_post.raw_comments_json or "[]")}
    except (ValueError, TypeError):
        previous_ids = set()
    captured = [
        {
            "id": comment["id"],
            **facebook_author_fields(comment),
            "content": comment["message"].strip(),
            "time": format_colombia_datetime(comment.get("created_time")),
            "source": "Facebook",
            "parent_id": (comment.get("parent") or {}).get("id"),
            "is_hidden": comment.get("is_hidden"),
        }
        for comment in comments
        if comment.get("id") and (comment.get("message") or "").strip()
    ]
    meta_post.raw_comments_json = json.dumps(captured, ensure_ascii=False)
    meta_post.total_comments = total
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "post_id": post_id,
        "total_comments": total,
        "captured_comments": len(captured),
        "new_comments_captured": len({c["id"] for c in captured} - previous_ids),
    }


def sync_facebook_live_posts(db, stats=None, max_posts=3000) -> int:
    """Descarga y sincroniza las publicaciones recientes de Facebook de Johan Steed."""
    if stats is None:
        stats = {}
    stats.update(posts_updated=0, new_comments_captured=0, errors=[])
    token = settings.META_PAGE_ACCESS_TOKEN
    page_id = settings.META_PAGE_ID or "275486829735525"

    if not token or len(token) < 20:
        print("Token de Meta no disponible o incompleto.", flush=True)
        raise RuntimeError("Token de Meta no disponible o incompleto")

    print(f"Consultando TODAS las publicaciones de Facebook para Página {page_id}...", flush=True)
    fields = (
        "id,created_time,message,full_picture,attachments{media_type,type,target,subattachments},"
        f"permalink_url,comments.filter(stream).summary(true).limit(10){{{COMMENT_FIELDS}}}"
    )
    all_raw_posts = []
    try:
        for page_num, data in enumerate(iter_connection(
            f"{page_id}/posts", token, fields=fields, limit=min(50, max_posts), max_pages=3000,
        ), start=1):
            batch = data.get("data", [])
            all_raw_posts.extend(batch)
            print(f"  Página {page_num}: {len(batch)} publicaciones (total: {len(all_raw_posts)})", flush=True)
            if len(all_raw_posts) >= max_posts:
                all_raw_posts = all_raw_posts[:max_posts]
                if max_posts >= 3000 and (data.get("paging") or {}).get("next"):
                    stats["errors"].append("Se alcanzó el límite de 3000 publicaciones; queda histórico por consultar")
                break
    except Exception as exc:
        stats["errors"].append(str(exc))
        if not all_raw_posts:
            raise
        print(f"Lectura parcial del histórico: {exc}", flush=True)

    print(f"Total publicaciones obtenidas de Facebook: {len(all_raw_posts)}", flush=True)

    new_posts_count = 0
    new_cases_count = 0
    total_db_cases = db.query(Case).count()

    for p in all_raw_posts:
        pid = p.get("id")
        created_time = p.get("created_time")
        message = p.get("message") or "Publicación Oficial de Johan Steed en Neiva"
        remote_pic = p.get("full_picture")
        permalink = p.get("permalink_url")
        try:
            comments_data, total_comments = read_post_comments(p, token)
        except Exception as exc:
            # Conservar el estado anterior si alguna página o nodo no pudo leerse.
            stats["errors"].append(f"{pid}: {exc}")
            print(f"Comentarios de {pid} sin actualizar: {exc}", flush=True)
            continue

        # Descargar carátula local
        cover_image = download_and_cache_cover(pid, remote_pic)

        att = p.get("attachments", {}).get("data", [])
        media_type = "image"
        if att and (att[0].get("media_type") == "video" or att[0].get("type") in ["video", "video_inline", "video_autoplay"]):
            media_type = "video"

        # Título limpio
        first_line = message.split("\n")[0].strip()
        title = first_line[:120] if first_line else f"Publicación del {format_colombia_datetime(created_time)}"

        # Buscar si ya existe en MetaPost
        meta_post = db.query(MetaPost).filter(MetaPost.id == pid).first()
        is_new = False
        if not meta_post:
            meta_post = MetaPost(id=pid)
            db.add(meta_post)
            is_new = True
            new_posts_count += 1

        meta_post.title = title
        meta_post.message = message
        meta_post.cover_image = cover_image
        meta_post.media_type = media_type
        meta_post.permalink_url = permalink
        meta_post.created_time = created_time
        meta_post.published_at = format_colombia_datetime(created_time)
        meta_post.month_key = get_month_key(created_time)
        meta_post.total_comments = max(total_comments, len(comments_data))
        meta_post.source = "Facebook"
        # Conservar métricas reales existentes; cero si aún no se han obtenido.
        meta_post.likes_count = meta_post.likes_count or 0
        meta_post.views_count = meta_post.views_count or 0
        meta_post.shares_count = meta_post.shares_count or 0

        # Contar únicamente IDs reales que no estaban en la captura anterior.
        try:
            previous_ids = {c.get("id") for c in json.loads(meta_post.raw_comments_json or "[]")}
        except (ValueError, TypeError):
            previous_ids = set()
        new_comment_ids = set()
        raw_comms = []
        for c in comments_data:
            c_id = c.get("id")
            c_text = c.get("message", "").strip()
            author_fields = facebook_author_fields(c)
            c_author = author_fields["author"]
            c_time = format_colombia_datetime(c.get("created_time"))

            if not c_text:
                continue

            raw_comms.append({
                "id": c_id,
                **author_fields,
                "content": c_text,
                "time": c_time,
                "source": "Facebook",
                "parent_id": (c.get("parent") or {}).get("id"),
                "is_hidden": c.get("is_hidden"),
            })
            if c_id and c_id not in previous_ids:
                new_comment_ids.add(c_id)

            # Si es un comentario relevante, verificar si ya tiene caso creado
            if c_id and is_meaningful_comment(c_text):
                existing_case = db.query(Case).filter(Case.internal_notes.contains(c_id)).first()
                if not existing_case:
                    # Crear caso clasificado con IA
                    try:
                        ai_res = ai_classifier.classify_comment(c_text)
                    except Exception:
                        ai_res = {
                            "category": "Atención Ciudadana",
                            "sentiment": "Enojo o ira: Frustración",
                            "priority_suggestion": "Media",
                            "commune": "Comuna General",
                            "neighborhood": "Neiva",
                            "detected_problem": c_text[:60],
                            "assigned_department_suggestion": "Despacho Municipal",
                            "requires_followup": True
                        }

                    try:
                        case_code = generate_next_case_id(db)
                        new_case = Case(
                            id=case_code,
                            title=f"{ai_res.get('category', 'Solicitud')}: {ai_res.get('detected_problem', c_text[:60])}",
                            content=c_text,
                            category=ai_res.get("category", "General"),
                            sentiment=ai_res.get("sentiment", "Enojo o ira: Frustración"),
                            priority=ai_res.get("priority_suggestion", "Media"),
                            status="Pendiente",
                            location=f"{ai_res.get('neighborhood', 'Neiva')} ({ai_res.get('commune', 'Comuna General')})",
                            zone=ai_res.get("commune", "Comuna General"),
                            date_time=c_time,
                            source="Facebook",
                            author=c_author,
                            assigned_department=ai_res.get("assigned_department_suggestion", "Despacho Municipal"),
                            requires_followup=ai_res.get("requires_followup", True),
                            comments_count=1,
                            image_url=cover_image,
                            internal_notes=f"[Post ID]: {pid}\n[Comment ID]: {c_id}\n[Canal]: Facebook Oficial - Johan Steed"
                        )
                        db.add(new_case)
                        db.flush()
                        new_cases_count += 1
                        print(f"Nuevo caso ciudadano creado: {case_code} desde comentario en Facebook: {c_author}", flush=True)
                    except Exception as err_case:
                        db.rollback()
                        print(f"Aviso al insertar comentario individual {c_id}: {err_case}", flush=True)

        meta_post.raw_comments_json = json.dumps(raw_comms, ensure_ascii=False)
        try:
            db.commit()
            stats["posts_updated"] += 1
            stats["new_comments_captured"] += len(new_comment_ids)
        except Exception as err_post:
            db.rollback()
            stats["errors"].append(f"No se pudo guardar la publicación {pid}")
            print(f"Aviso al actualizar publicación {pid}: {err_post}", flush=True)

    print(f"Facebook sincronizado: {new_posts_count} posts nuevos o actualizados, {new_cases_count} casos ciudadanos creados.", flush=True)
    return new_posts_count

def _prepare_instagram_media(media, token, comments_available):
    """Descarga recursos sin compartir la sesión SQLAlchemy entre hilos."""
    is_video = media.get("media_type") == "VIDEO"
    cover_url = media.get("thumbnail_url") if is_video else media.get("media_url")
    cover = download_and_cache_cover(f"IG_{media['id']}", cover_url) if cover_url else None
    captured = None
    error = None
    if comments_available:
        try:
            comments = read_instagram_comments(media["id"], token)
            captured = [
                {**normalize_instagram_comment(comment), "time": format_colombia_datetime(comment.get("timestamp")) if comment.get("timestamp") else "Fecha no disponible"}
                for comment in comments if (comment.get("text") or "").strip()
            ]
        except Exception as exc:
            error = f"Comentarios de Instagram {media['id']}: {exc}"
    return media, cover, captured, error


def sync_instagram_publications(db, stats=None, max_posts=3000, only_missing=False) -> int:
    """Importa publicaciones y comentarios reales de la cuenta profesional vinculada."""
    if stats is None:
        stats = {}
    stats.update(posts_updated=0, posts_skipped=0, new_comments_captured=0, errors=[])
    connection = get_instagram_connection(force_refresh=True)
    stats.update(status=connection["status"], detail=connection["detail"])
    if connection["status"] != "ready":
        stats["errors"].append(connection["detail"])
        return 0

    token = settings.META_PAGE_ACCESS_TOKEN
    new_posts = 0
    seen_posts = 0
    existing_ids = {post_id for (post_id,) in db.query(MetaPost.id).filter(MetaPost.source == "Instagram")} if only_missing else set()
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            for page in iter_connection(f"{connection['account_id']}/media", token, fields=MEDIA_FIELDS, limit=min(50, max_posts), max_pages=3000):
                batch = page.get("data", [])[:max_posts - seen_posts]
                seen_posts += len(batch)
                pending = [media for media in batch if media.get("id") and f"IG_{media['id']}" not in existing_ids]
                stats["posts_skipped"] += len(batch) - len(pending)
                for media, cover, captured, error in pool.map(lambda media: _prepare_instagram_media(media, token, connection["comments_available"]), pending):
                    media_id = media["id"]
                    post_id = f"IG_{media_id}"
                    post = db.get(MetaPost, post_id)
                    is_new = post is None
                    if is_new:
                        post = MetaPost(id=post_id, source="Instagram")
                        db.add(post)
                    caption = media.get("caption") or ""
                    timestamp = media.get("timestamp")
                    post.title = (caption.split("\n")[0].strip() or "Publicación de Instagram")[:120]
                    post.message = caption
                    post.source = "Instagram"
                    post.media_type = "video" if media.get("media_type") == "VIDEO" else "image"
                    post.permalink_url = media.get("permalink")
                    post.created_time = timestamp
                    post.published_at = format_colombia_datetime(timestamp) if timestamp else "Fecha no disponible"
                    post.month_key = timestamp[:7] if timestamp else None
                    post.cover_image = cover
                    post.likes_count = media.get("like_count") or 0
                    post.views_count = post.views_count or 0
                    post.shares_count = post.shares_count or 0
                    post.total_comments = media.get("comments_count") or 0
                    new_ids = set()
                    if captured is not None:
                        try:
                            previous_ids = {c.get("id") for c in json.loads(post.raw_comments_json or "[]")}
                        except (ValueError, TypeError):
                            previous_ids = set()
                        new_ids = {c["id"] for c in captured} - previous_ids
                        post.raw_comments_json = json.dumps(captured, ensure_ascii=False)
                        post.total_comments = max(post.total_comments, len(captured))
                    if error:
                        # Conservar la captura anterior si falla la lectura de comentarios.
                        stats["errors"].append(error)
                    try:
                        db.commit()
                        new_posts += int(is_new)
                        stats["posts_updated"] += 1
                        stats["new_comments_captured"] += len(new_ids)
                    except Exception:
                        db.rollback()
                        stats["errors"].append(f"No fue posible guardar la publicación de Instagram {media_id}")
                print(f"Instagram: {seen_posts} publicaciones revisadas, {stats['posts_updated']} guardadas.", flush=True)
                if seen_posts >= max_posts:
                    if max_posts >= 3000 and (page.get("paging") or {}).get("next"):
                        stats["errors"].append("Se alcanzó el límite de 3000 publicaciones de Instagram")
                    break
    except Exception as exc:
        stats["errors"].append(str(exc))
    if not connection["comments_available"]:
        stats["errors"].append("Falta instagram_manage_comments; se importaron únicamente publicaciones.")
    stats["status"] = "partial" if stats["errors"] else "success"
    return new_posts

def generate_fallback_covers():
    """Genera portadas fotográficas profesionales para publicaciones."""
    try:
        from update_covers import THEMES, process_cover
        for theme in THEMES:
            process_cover(theme)
    except Exception as e:
        print(f"Error generando portadas temáticas: {e}", flush=True)

def run_full_sync():
    print("==================================================", flush=True)
    print("INICIANDO SINCRONIZACIÓN TOTAL CIVIA (META & IG)", flush=True)
    print(f"Fecha actual: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print("==================================================", flush=True)

    ensure_db_schema()

    db = SessionLocal()
    try:
        fb_synced = sync_facebook_live_posts(db)
        ig_synced = sync_instagram_publications(db)
        total_posts = db.query(MetaPost).count()
        total_cases = db.query(Case).count()
        print(f"\nSINCRONIZACIÓN EXITOSA:\n- Total Publicaciones en Plataforma: {total_posts}\n- Total Casos Ciudadanos: {total_cases}", flush=True)
    finally:
        db.close()

if __name__ == "__main__":
    run_full_sync()

