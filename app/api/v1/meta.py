from app.core.assets import asset_base
import logging
import os
import time
from fastapi import APIRouter, Request, Response, Query, HTTPException, status, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
import json
import hmac
import hashlib
from datetime import datetime, timezone, timedelta

from app.api.dependencies import require_triage_user
from app.core.config import settings
from app.core.database import get_db
from app.api.v1.auth import get_current_user
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
    
    logger.warning('Fallo de verificación de Webhook.')
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Token de verificación inválido"
    )

@router.post("/webhook")
async def receive_meta_webhook(request: Request, db: Session = Depends(get_db)):
    if not settings.META_APP_SECRET:
        raise HTTPException(503, 'La recepci\u00f3n de eventos no est\u00e1 configurada.')
    chunks=[];size=0
    async for chunk in request.stream():
        size+=len(chunk)
        if size>512*1024:raise HTTPException(413,'Evento demasiado grande.')
        chunks.append(chunk)
    body=b''.join(chunks)
    signature=request.headers.get('x-hub-signature-256','')
    expected='sha256='+hmac.new(settings.META_APP_SECRET.encode(),body,hashlib.sha256).hexdigest()
    import re
    if not re.fullmatch(r'sha256=[0-9a-f]{64}',signature) or not hmac.compare_digest(expected,signature):
        raise HTTPException(403,'Firma de evento inv\u00e1lida.')
    try:payload=json.loads(body)
    except (ValueError,UnicodeError):raise HTTPException(400,'JSON no v\u00e1lido.')
    if not isinstance(payload,dict) or not isinstance(payload.get('entry',[]),list):
        raise HTTPException(400,'Estructura de evento no v\u00e1lida.')
    from app.core.auth_limits import _consume
    from app.services.webhooks import enqueue
    _consume(db,'webhook:verified','meta',1000,60)
    enqueue(db,payload)
    return {'status':'EVENT_RECEIVED'}

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
        include_details=include_details, cases_only=cases_only, asset_base=asset_base(request),
    )
    return page if paginated else page["items"]


@router.get("/posts/{post_id}")
def get_monitored_post(post_id: str, request: Request, db: Session = Depends(get_db)):
    from app.services.meta_posts import list_posts
    page = list_posts(db, post_id=post_id, limit=1, include_details=True,
                      asset_base=asset_base(request))
    if not page["items"]:
        raise HTTPException(status_code=404, detail="Publicacion no encontrada")
    item = page["items"][0]
    if "facebook" in (item.get("source") or "").lower():
        from app.services.conversation import build_rows
        rows, _ = build_rows(db, [db.get(MetaPost, post_id)])
        item["conversation_analysis"] = {row["id"]: row for row in rows}
    return item


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

@router.post("/sync-live", status_code=202)
def sync_live_meta_content(db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.services.meta_sync_jobs import start_job
    return start_job(db, "connected")


@router.get("/sync-status")
def get_meta_sync_status(scope: str = Query("connected", max_length=200), db: Session = Depends(get_db),
                         user=Depends(get_current_user)):
    from app.services.meta_sync_jobs import job_data, latest_job
    return job_data(latest_job(db, scope))


@router.get("/sync-jobs/{job_id}")
def get_sync_job(job_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.models.publication import MetaSyncJob
    from app.services.meta_sync_jobs import job_data
    job = db.get(MetaSyncJob, job_id)
    if job is None:
        raise HTTPException(404, "Actualización no encontrada")
    return job_data(job)


@router.get("/instagram/status")
def get_instagram_status():
    from app.services.instagram_graph import get_instagram_connection
    return get_instagram_connection()



@router.get("/triage-comments")
def get_triage_comments(db: Session = Depends(get_db), user=Depends(require_triage_user)):
    from app.services.triage import pending_comments
    return pending_comments(db)
