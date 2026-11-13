from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, Header
from sqlalchemy.orm import Session, defer
from sqlalchemy import or_, func, desc, case
from typing import Optional, Dict, Any
import re

from app.core.database import get_db
from app.models.citizen import Citizen
from app.models.case import Case
from app.schemas.citizen import CitizenResponse, CitizenUploadRequest, CitizenDeleteRequest
from app.services.ai_classifier import ai_classifier
from app.api.v1.auth import get_current_user
from app.core.security import decode_access_token
from app.services.citizen_import import parse_contact_file, import_contacts, MAX_FILE_BYTES

def require_contact_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    # Contact records require a signed session, including when demo mode exists elsewhere.
    token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
    if not decode_access_token(token):
        raise HTTPException(401, "Inicia sesión para consultar o importar ciudadanos")
    return get_current_user(authorization, db)


router = APIRouter(dependencies=[Depends(require_contact_user)], prefix="/citizens", tags=["Inteligencia Ciudadana & Base Telefónica"])


def require_contact_manager(current_user=Depends(require_contact_user)):
    if current_user.role not in ("ADMIN", "ALCALDE"):
        raise HTTPException(403, "Solo administradores y dirección pueden eliminar ciudadanos")
    return current_user


def delete_selected_citizens(db: Session, citizen_ids: list[str], *, missing_status=409):
    ids = sorted(set(citizen_ids))
    try:
        # Lock the exact IDs and validate the entire selection before deleting any row.
        found = db.query(Citizen.id).filter(Citizen.id.in_(ids)).order_by(Citizen.id).with_for_update().all()
        if len(found) != len(ids):
            raise HTTPException(missing_status, "Uno o varios ciudadanos ya no existen. Actualiza la lista y revisa la selección.")
        deleted = db.query(Citizen).filter(Citizen.id.in_(ids)).delete(synchronize_session=False)
        if deleted != len(ids):
            raise HTTPException(409, "La selección cambió. Actualiza la lista e inténtalo nuevamente.")
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"success": True, "deleted_count": deleted, "deleted_ids": ids}


@router.post("/bulk-delete", dependencies=[Depends(require_contact_manager)])
def delete_citizens_bulk(payload: CitizenDeleteRequest, db: Session = Depends(get_db)):
    return delete_selected_citizens(db, payload.citizen_ids)


@router.delete("/{citizen_id}", dependencies=[Depends(require_contact_manager)])
def delete_citizen(citizen_id: str, db: Session = Depends(get_db)):
    return delete_selected_citizens(db, [citizen_id], missing_status=404)

async def read_contact_upload(file: UploadFile):
    content = await file.read(MAX_FILE_BYTES + 1)
    await file.close()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, "Archivo demasiado grande (maximo 10 MB)")
    try:
        return parse_contact_file(content, file.filename or "")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/import/preview")
async def preview_contact_import(file: UploadFile = File(...), db: Session = Depends(get_db)):
    parsed = await read_contact_upload(file)
    return import_contacts(db, parsed, preview=True)


@router.post("/import")
async def save_contact_import(file: UploadFile = File(...), db: Session = Depends(get_db)):
    parsed = await read_contact_upload(file)
    try:
        return import_contacts(db, parsed)
    except Exception:
        db.rollback()
        raise


@router.get("", response_model=Dict[str, Any])
def list_citizens(
    user_type: Optional[str] = Query("all", description="Filtrar por: all, Positivo, Negativo, Bot"),
    followers_filter: Optional[str] = Query("all", description="all, under_50, 50_500, over_500"),
    account_age_filter: Optional[str] = Query("all", description="all, recent, older"),
    search: Optional[str] = Query(None, description="Buscar por nombre, teléfono, barrio o handle"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Lista la base de datos de ciudadanos, teléfonos y perfiles de Facebook/Instagram,
    con segmentación entre humanos reales (positivos/negativos) y bots de ataque.
    """
    query = db.query(Citizen).options(defer(Citizen.source_data))

    # Filtro Tipo de Usuario
    if user_type and user_type != "all":
        query = query.filter(Citizen.user_type == user_type)

    # Filtro Seguidores
    if followers_filter == "under_50":
        query = query.filter(Citizen.followers_count < 50)
    elif followers_filter == "50_500":
        query = query.filter(Citizen.followers_count >= 50, Citizen.followers_count <= 500)
    elif followers_filter == "over_500":
        query = query.filter(Citizen.followers_count > 500)

    # Filtro Antigüedad
    if account_age_filter == "recent":
        query = query.filter(or_(Citizen.account_created_at.like("%días%"), Citizen.account_created_at.like("%mes%")))
    elif account_age_filter == "older":
        query = query.filter(Citizen.account_created_at.like("%año%"))

    # Búsqueda libre
    if search:
        s = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Citizen.name).like(s),
                func.lower(Citizen.handle).like(s),
                func.lower(Citizen.phone).like(s),
                func.lower(Citizen.neighborhood).like(s),
                func.lower(Citizen.notes).like(s),
            )
        )

    total_matched = query.count()
    # Ordenar: primero ciudadanos reales de Neiva (por reportes y seguidores), perfiles bot al final
    citizens = query.order_by(
        case((Citizen.user_type == 'Bot', 1), else_=0),
        desc(Citizen.total_reports),
        desc(Citizen.followers_count), Citizen.name, Citizen.id
    ).offset(offset).limit(limit).all()
    source_users = dict(db.query(Citizen.id, Citizen.source_data["whatsapp_username"].as_string()).filter(
        Citizen.id.in_([c.id for c in citizens]), Citizen.source_data.isnot(None)
    ).all())

    totals = db.query(
        func.count(Citizen.id),
        func.sum(case((Citizen.user_type == "Bot", 1), else_=0)),
        func.sum(case((Citizen.user_type == "Positivo", 1), else_=0)),
        func.sum(case((Citizen.user_type == "Negativo", 1), else_=0)),
        func.sum(case((Citizen.phone.isnot(None) & (Citizen.phone != ""), 1), else_=0)),
        func.sum(case((Citizen.user_type == "Sin clasificar", 1), else_=0)),
    ).one()
    total_all, total_bots, total_positives, total_negatives, total_with_phone, unclassified = [int(v or 0) for v in totals]

    return {
        "total": total_matched, "limit": limit, "offset": offset, "has_more": offset + len(citizens) < total_matched,
        "metrics": {
            "total_registered": total_all, "total_unclassified": unclassified,
            "total_with_phone": total_with_phone,
            "total_bots_detected": total_bots,
            "total_positives": total_positives,
            "total_negatives": total_negatives,
            "bot_percentage": round((total_bots / total_all * 100), 1) if total_all > 0 else 0
        },
        "items": [
            {
                "id": c.id,
                "name": c.name,
                "handle": c.handle,
                "phone": c.phone,
                "followers_count": c.followers_count,
                "following_count": c.following_count,
                "account_created_at": c.account_created_at,
                "user_type": c.user_type,
                "bot_probability": c.bot_probability,
                "bot_origin": c.bot_origin,
                "neighborhood": c.neighborhood, "zone": c.zone,
                "has_source_data": c.id in source_users,
                "whatsapp_username": source_users.get(c.id),
                "channel": c.channel,
                "total_reports": c.total_reports,
                "sentiment_tendency": c.sentiment_tendency,
                "notes": c.notes,
                "origen_dato": c.origen_dato,
                "whatsapp_link": f"https://wa.me/{re.sub(r'[^0-9]', '', c.phone)}" if c.phone else None
            }
            for c in citizens
        ]
    }

@router.post("/upload", response_model=Dict[str, Any])
def upload_citizens_database(payload: CitizenUploadRequest, db: Session = Depends(get_db)):
    import csv
    import io
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["Nombre", "phone", "neighborhood", "notes"])
    for item in payload.citizens:
        writer.writerow([item.name, item.phone, item.neighborhood, item.notes])
    try:
        parsed = parse_contact_file(stream.getvalue().encode("utf-8"), "contactos.csv")
        return import_contacts(db, parsed)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/{citizen_id}", response_model=CitizenResponse)
def get_citizen(citizen_id: str, db: Session = Depends(get_db)):
    citizen = db.get(Citizen, citizen_id)
    if not citizen:
        raise HTTPException(404, "Ciudadano no encontrado")
    return citizen


class CitizenReplyRequest(BaseModel):
    case_id: str
    reply_text: str
    status: Optional[str] = "En Gestión"

@router.get("/{citizen_id}/comments")
def get_citizen_comments_and_posts(
    citizen_id: str,
    db: Session = Depends(get_db)
):
    """
    Retorna el historial completo de en qué publicaciones comentó el usuario,
    el texto de su respuesta/comentario, el post original de Meta,
    y la propuesta de respuesta institucional inteligente generada por IA.
    """
    citizen = db.query(Citizen).filter(Citizen.id == citizen_id).first()
    if not citizen:
        # Buscar por handle
        citizen = db.query(Citizen).filter(Citizen.handle == citizen_id).first()
    if not citizen:
        raise HTTPException(status_code=404, detail="Ciudadano no encontrado")

    if citizen.channel in ("WhatsApp", "Base de Datos"):
        return {"citizen": CitizenResponse.model_validate(citizen).model_dump(),
                "total_comments": 0, "comments": [], "relationship_status": "not_linked"}

    # 1. Buscar casos asociados al autor
    cases = db.query(Case).filter(
        or_(
            Case.author == citizen.name,
            Case.author == citizen.handle,
            Case.author.ilike(f"%{citizen.name}%")
        )
    ).order_by(desc(Case.created_at)).limit(15).all()

    # Solo comentarios legítimos pertenecientes a este autor

    # Cargar posts de Meta
    from app.models.meta_post import MetaPost
    posts = {p.id: p for p in db.query(MetaPost).all()}
    fallback_post = db.query(MetaPost).first()

    comments_data = []
    for c in cases:
        # Detectar qué post corresponde según image_url o permalink
        matched_post = None
        for pid, p in posts.items():
            if pid in (c.image_url or ""):
                matched_post = p
                break
        if not matched_post:
            matched_post = fallback_post

        # Generar propuesta de respuesta institucional por IA (Modo instantáneo con caché)
        ai_prop = ai_classifier.generate_smart_response(
            comment_text=c.content or c.title,
            context=c.category,
            user_type=citizen.user_type,
            fast_mode=True
        )

        post_cover = matched_post.cover_image if matched_post else c.image_url
        if not post_cover or "http" not in post_cover:
            post_cover = f"http://localhost:8000/static/covers/default_cover.jpg"

        comments_data.append({
            "case_id": c.id,
            "author": c.author,
            "comment_text": c.content,
            "title": c.title,
            "sentiment": c.sentiment,
            "category": c.category,
            "location": c.location,
            "date_time": c.date_time,
            "status": c.status,
            "public_response": c.public_response,
            "ai_suggestion": {
                "topic": ai_prop.get("topic", c.category),
                "tone": ai_prop.get("tone", "Institucional Empático"),
                "recommended_action": ai_prop.get("recommended_action", "Atención con radicado institucional"),
                "suggested_reply": ai_prop.get("response_text", ""),
                "talking_points": ai_prop.get("talking_points", [])
            },
            "post": {
                "id": matched_post.id if matched_post else "POST-GENERIC",
                "title": matched_post.title if matched_post else "Publicación Institucional - Alcaldía de Neiva",
                "cover_image": post_cover,
                "source": matched_post.source if matched_post else c.source,
                "permalink_url": matched_post.permalink_url if matched_post else "https://facebook.com/275486829735525",
                "published_at": matched_post.published_at if matched_post else "Octubre 2026"
            }
        })

    return {
        "citizen": {
            "id": citizen.id,
            "name": citizen.name,
            "handle": citizen.handle,
            "phone": citizen.phone,
            "followers_count": citizen.followers_count,
            "user_type": citizen.user_type,
            "bot_probability": citizen.bot_probability,
            "bot_origin": citizen.bot_origin,
            "neighborhood": citizen.neighborhood,
            "channel": citizen.channel,
            "total_reports": citizen.total_reports,
            "sentiment_tendency": citizen.sentiment_tendency,
            "notes": citizen.notes,
            "whatsapp_link": f"https://wa.me/{re.sub(r'[^0-9]', '', citizen.phone)}" if citizen.phone else None
        },
        "total_comments": len(comments_data),
        "comments": comments_data
    }

@router.post("/{citizen_id}/reply")
def register_official_reply(
    citizen_id: str,
    payload: CitizenReplyRequest,
    db: Session = Depends(get_db)
):
    """
    Registra y guarda la respuesta institucional oficial enviada al ciudadano,
    actualizando el estado del caso a 'En Gestión' o 'Resuelto'.
    """
    case = db.query(Case).filter(Case.id == payload.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    case.public_response = payload.reply_text
    if payload.status:
        case.status = payload.status
    db.commit()

    return {
        "success": True,
        "case_id": case.id,
        "status": case.status,
        "public_response": case.public_response,
        "message": f"Respuesta institucional guardada para el caso {case.id}."
    }
