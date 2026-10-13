import logging
from fastapi import APIRouter, Request, Response, Query, HTTPException, status, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import json

from app.core.config import settings
from app.core.database import get_db
from app.models.case import Case
from app.services.ai_classifier import ai_classifier

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
        "message": "Comentario simulado y clasificado exitosamente con OpenAI",
        "case_id": case_id,
        "ai_analysis": ai_analysis
    }
