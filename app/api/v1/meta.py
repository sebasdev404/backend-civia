import logging
import os
import time
from fastapi import APIRouter, Request, Response, Query, HTTPException, status, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
import json
from datetime import datetime, timezone, timedelta

from app.core.config import settings
from app.core.database import get_db
from app.models.case import Case
from app.models.meta_post import MetaPost
from app.services.ai_classifier import ai_classifier
from sqlalchemy import desc, func

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meta", tags=["Meta Graph API & Webhooks"])

@router.get("/webhook")
def verify_meta_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token")
):
    """
    Endpoint obligatorio de verificación del Webhook de Meta (Facebook & Instagram).
    Meta envía un GET con hub.mode, hub.challenge y hub.verify_token.
    """
    expected_token = settings.META_VERIFY_TOKEN

    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        logger.info("Webhook de Meta verificado exitosamente.")
        # Meta exige responder con el challenge en texto plano
        return Response(content=str(hub_challenge), media_type="text/plain", status_code=200)
    
    logger.warning(f"Fallo de verificación de Webhook. Token recibido: '{hub_verify_token}', esperado: '{expected_token}'")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Token de verificación inválido"
    )

@router.post("/webhook")
async def receive_meta_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receptor de eventos en vivo de Meta (Facebook Page y cuenta de Instagram).
    Procesa publicaciones, comentarios y menciones de ciudadanos.
    """
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Error parseando JSON de Meta: {e}")
        return Response(content="INVALID_JSON", status_code=400)

    logger.info(f"Evento recibido de Meta: {json.dumps(payload)[:300]}")

    # Estructura típica de Meta Webhook para Páginas e Instagram
    # entry -> changes -> value -> message / comment_id
    if payload.get("object") in ["page", "instagram"]:
        entries = payload.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                message_text = value.get("message") or value.get("text")
                author_name = value.get("from", {}).get("name", "Ciudadano en Redes")
                network = "Facebook" if payload.get("object") == "page" else "Instagram"

                if message_text and len(message_text.strip()) > 5:
                    logger.info(f"Procesando comentario ciudadano con OpenAI: '{message_text}'")
                    try:
                        # 1. Clasificación automática con IA (OpenAI gpt-4o-mini)
                        ai_analysis = ai_classifier.classify_comment(message_text)

                        # 2. Generar código interno CIVIA
                        count = db.query(Case).count()
                        case_id = f"CIV-2026-{str(count + 1).zfill(4)}"

                        # 3. Guardar en base de datos PostgreSQL
                        new_case = Case(
                            id=case_id,
                            title=f"{ai_analysis.get('category')}: {ai_analysis.get('detected_problem', message_text[:60])}",
                            content=message_text,
                            category=ai_analysis.get("category", "General"),
                            sentiment=ai_analysis.get("sentiment", "Crítico"),
                            priority=ai_analysis.get("priority_suggestion", "Media"),
                            status="Pendiente",
                            location=f"{ai_analysis.get('neighborhood', 'Neiva')} ({ai_analysis.get('commune', 'Comuna General')})",
                            zone=ai_analysis.get("commune", "Comuna General"),
                            date_time="Hace un momento",
                            source=network,
                            author=author_name,
                            assigned_department=ai_analysis.get("assigned_department_suggestion", "Despacho Municipal"),
                            requires_followup=ai_analysis.get("requires_followup", True),
                            comments_count=1,
                        )
                        db.add(new_case)
                        db.commit()
                        logger.info(f"Nuevo caso creado automáticamente: {case_id}")
                    except Exception as err:
                        logger.error(f"Error procesando comentario con IA: {err}")
                        db.rollback()

    # Meta exige respuesta 200 OK inmediata
    return {"status": "EVENT_RECEIVED"}

@router.post("/simulate-comment")
def simulate_incoming_meta_comment(
    text: str,
    author: str = "Ciudadano de Neiva",
    network: str = "Facebook",
    db: Session = Depends(get_db)
):
    """
    Endpoint de prueba para simular que un ciudadano escribió un comentario en Facebook o Instagram.
    Ejecuta el pipeline completo: Meta -> OpenAI -> Caso CIVIA en PostgreSQL.
    """
    if not text.strip():
        raise HTTPException(status_code=400, detail="El comentario no puede estar vacío")

    # 1. Clasificación en vivo con OpenAI
    ai_analysis = ai_classifier.classify_comment(text)

    # 2. Generación de código interno CIVIA
    count = db.query(Case).count()
    case_id = f"CIV-2026-{str(count + 1).zfill(4)}"

    # 3. Guardar en Base de Datos
    new_case = Case(
        id=case_id,
        title=f"{ai_analysis.get('category')}: {ai_analysis.get('detected_problem', text[:60])}",
        content=text,
        category=ai_analysis.get("category", "General"),
        sentiment=ai_analysis.get("sentiment", "Crítico"),
        priority=ai_analysis.get("priority_suggestion", "Media"),
        status="Pendiente",
        location=f"{ai_analysis.get('neighborhood', 'Neiva')} ({ai_analysis.get('commune', 'Comuna General')})",
        zone=ai_analysis.get("commune", "Comuna General"),
        date_time="Hace un momento",
        source=network,
        author=author,
        assigned_department=ai_analysis.get("assigned_department_suggestion", "Despacho Municipal"),
        requires_followup=ai_analysis.get("requires_followup", True),
        comments_count=1,
    )
    db.add(new_case)
    db.commit()
    db.refresh(new_case)

    return {
        "status": "success",
        "message": "Comentario clasificado y procesado exitosamente con OpenAI",
        "case_id": case_id,
        "ai_analysis": ai_analysis
    }

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

@router.get("/months")
def get_available_months(db: Session = Depends(get_db)):
    """
    Retorna la lista de meses disponibles (desde Enero 2026 hasta la fecha)
    con el conteo exacto de publicaciones monitoreadas en cada mes.
    """
    month_counts = (
        db.query(MetaPost.month_key, func.count(MetaPost.id))
        .group_by(MetaPost.month_key)
        .order_by(desc(MetaPost.month_key))
        .all()
    )

    total_posts = db.query(MetaPost).count()

    meses_nombres = {
        "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
        "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
        "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre"
    }

    months_list = []

    # Calcular rango dinámico desde la DB
    if month_counts:
        oldest_key = min(mk for mk, _ in month_counts)
        newest_key = max(mk for mk, _ in month_counts)

        def key_to_label(mk):
            parts = mk.split("-")
            yr = parts[0] if len(parts) > 0 else "2026"
            mn = parts[1] if len(parts) > 1 else "01"
            return f"{meses_nombres.get(mn, mn)} {yr}"

        rango_label = f"Todos los meses ({key_to_label(oldest_key)} – {key_to_label(newest_key)})"
    else:
        rango_label = "Todas las publicaciones"

    months_list = [
        {
            "key": "all",
            "label": rango_label,
            "count": total_posts
        }
    ]

    for m_key, count in month_counts:
        parts = m_key.split("-")
        year = parts[0] if len(parts) > 0 else "2026"
        m_num = parts[1] if len(parts) > 1 else "10"
        m_name = meses_nombres.get(m_num, m_num)
        months_list.append({
            "key": m_key,
            "label": f"{m_name} {year}",
            "count": count
        })

    return months_list

@router.get("/posts")
def get_monitored_posts(
    request: Request,
    month: Optional[str] = Query(None, description="Mes en formato YYYY-MM o 'all'"),
    search: Optional[str] = Query(None, description="Buscar por texto"),
    network: Optional[str] = Query(None, description="Red social: Facebook, Instagram o all"),
    limit: int = Query(300, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    paginated: bool = Query(False),
    include_details: bool = Query(True, description="Incluir casos y comentarios completos"),
    cases_only: bool = Query(False, description="Solo publicaciones con casos vinculados"),
    db: Session = Depends(get_db),
):
    from app.services.meta_posts import list_posts
    page = list_posts(
        db, month=month, search=search, network=network, limit=limit, offset=offset,
        include_details=include_details, cases_only=cases_only, asset_base=str(request.base_url).rstrip("/"),
    )
    return page if paginated else page["items"]


@router.get("/posts/{post_id}")
def get_monitored_post(post_id: str, request: Request, db: Session = Depends(get_db)):
    from app.services.meta_posts import list_posts
    page = list_posts(db, post_id=post_id, limit=1, include_details=True,
                      asset_base=str(request.base_url).rstrip("/"))
    if not page["items"]:
        raise HTTPException(status_code=404, detail="Publicacion no encontrada")
    return page["items"][0]


@router.get("/post-thumbnail/{post_id}")
def get_post_thumbnail(post_id: str):
    from app.services.post_images import get_thumbnail
    thumbnail = get_thumbnail(post_id)
    if thumbnail is None:
        raise HTTPException(status_code=404, detail="Portada no disponible")
    return FileResponse(thumbnail, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


@router.get("/post-image/{post_id}")
def get_post_cover_image(post_id: str):
    """
    Retorna la carátula multimedia permanente del post almacenada localmente.
    Evita expiración de enlaces CDN de Meta.
    """
    import re
    from app.services.post_images import GENERIC_COVERS
    if not re.fullmatch(r"[A-Za-z0-9_-]+", post_id) or f"{post_id}.jpg" in GENERIC_COVERS:
        raise HTTPException(status_code=404, detail="Portada no disponible")
    safe_id = post_id
    local_file = os.path.join("static", "covers", f"{safe_id}.jpg")
    if os.path.exists(local_file) and os.path.getsize(local_file) > 500:
        return FileResponse(local_file, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Carátula no encontrada")

@router.post("/sync-live")
def sync_live_meta_content(db: Session = Depends(get_db)):
    """
    Sincronización en tiempo real con las APIs de Meta (Facebook e Instagram).
    Actualiza métricas de reproducciones, likes, nuevos comentarios ciudadanos y
    ejecuta el triaje automático con IA.
    """
    started_at = time.perf_counter()
    sync_stats = {}
    instagram_stats = {}
    try:
        from sync_live_service import sync_facebook_live_posts, sync_instagram_publications
        ig_synced = sync_instagram_publications(db, stats=instagram_stats, max_posts=50)
        fb_synced = sync_facebook_live_posts(db, stats=sync_stats, max_posts=50)
    except Exception as e:
        logger.warning(f"Error ejecutando sincronizador en vivo: {e}")
        db.rollback()
        raise HTTPException(status_code=502, detail="No fue posible completar la sincronización con Meta") from None

    total_posts = db.query(MetaPost).count()
    total_cases = db.query(Case).count()
    updated_at_str = datetime.now().strftime("%I:%M:%S %p")
    errors = sync_stats.get("errors", []) + instagram_stats.get("errors", [])

    return {
        "status": "partial" if errors else "success",
        "timestamp": updated_at_str,
        "message": "Sincronización con Meta finalizada con incidencias." if errors else "Sincronización con Meta finalizada.",
        "posts_monitored": total_posts,
        "cases_classified": total_cases,
        "facebook_synced": fb_synced,
        "posts_updated": sync_stats.get("posts_updated", 0) + instagram_stats.get("posts_updated", 0),
        "instagram_synced": ig_synced,
        "instagram_status": instagram_stats.get("status"),
        "instagram_detail": instagram_stats.get("detail"),
        "new_comments_captured": sync_stats.get("new_comments_captured", 0) + instagram_stats.get("new_comments_captured", 0),
        "api_latency_ms": round((time.perf_counter() - started_at) * 1000),
        "errors": errors,
        "detail": f"Publicaciones y comentarios consultados a las {updated_at_str}."
    }


@router.get("/instagram/status")
def get_instagram_status():
    from app.services.instagram_graph import get_instagram_connection
    return get_instagram_connection()



@router.get("/triage-comments")
def get_triage_comments(db: Session = Depends(get_db)):
    """
    Retorna comentarios reales de ciudadanos en Facebook e Instagram 
    que están en supervisión de triaje o pendientes de clasificación manual.
    """
    posts = db.query(MetaPost).order_by(desc(MetaPost.created_time)).limit(20).all()
    triage_items = []
    
    for p in posts:
        if p.raw_comments_json:
            try:
                comms = json.loads(p.raw_comments_json)
                for c in comms:
                    c_id = c.get("id") or str(hash(c.get("content", "")))
                    c_text = c.get("content") or c.get("message") or ""
                    c_author = c.get("author") or "Ciudadano Neiva"
                    
                    if len(c_text) > 15 and not c_text.lower().startswith("http"):
                        # Analizar toponimia o categoría básica
                        low = c_text.lower()
                        cat = "General"
                        if any(w in low for w in ["vía", "via", "calle", "hueco", "paviment", "asfalto"]):
                            cat = "Infraestructura Vial"
                        elif any(w in low for w in ["agua", "tubo", "fuga", "ceibas", "factura"]):
                            cat = "Servicios Públicos"
                        elif any(w in low for w in ["semáforo", "semaforo", "tránsito", "tráfico"]):
                            cat = "Movilidad"
                        elif any(w in low for w in ["luz", "poste", "luminaria", "lámpara"]):
                            cat = "Alumbrado Público"
                        elif any(w in low for w in ["seguridad", "robo", "atraco", "policía"]):
                            cat = "Seguridad"

                        triage_items.append({
                            "id": f"COMM-{c_id[-6:]}",
                            "source": p.source or "Facebook",
                            "author": c_author if c_author.startswith("@") else f"@{c_author.lower().replace(' ', '.')}",
                            "postTitle": p.title[:65] + "...",
                            "content": c_text,
                            "detectedIntent": "Reporte ciudadano",
                            "detectedLocation": "Neiva (General)",
                            "referenceStreet": "Sector Monitoreado",
                            "detectedCategory": cat,
                            "detectedTopic": f"Gestión de {cat}",
                            "detectedProblem": c_text[:60] + "...",
                            "aiConfidence": 92,
                            "requiresFollowup": True,
                            "possibleCaseMatch": None,
                            "metaDirectContactAllowed": True,
                            "dateTime": c.get("published_at") or p.published_at or "Reciente",
                        })
                        if len(triage_items) >= 12:
                            break
            except Exception:
                pass
        if len(triage_items) >= 12:
            break

    return triage_items
