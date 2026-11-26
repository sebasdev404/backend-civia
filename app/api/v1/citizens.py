from app.core.assets import asset_base
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, Header, Request
from sqlalchemy.orm import Session, defer
from sqlalchemy import or_, func, desc, case
from typing import Optional, Dict, Any
import re

from app.core.database import get_db
from app.models.citizen import Citizen
from app.models.case import Case
from app.schemas.citizen import CitizenResponse, CitizenUploadRequest, CitizenDeleteRequest
from app.schemas.case import CaseAction, CasePublicResponse
from app.services import case_workflow as workflow
from app.services.case_consolidation import assert_writable
from app.services.provenance_recovery import reference
from app.services.post_images import post_image_urls
from app.models.meta_post import MetaPost
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


def delete_selected_citizens(db: Session, citizen_ids: list[str], *, missing_status=409, actor=None):
    ids = sorted(set(citizen_ids))
    try:
        # Lock the exact IDs and validate the entire selection before deleting any row.
        found = db.query(Citizen.id).filter(Citizen.id.in_(ids)).order_by(Citizen.id).with_for_update().all()
        if len(found) != len(ids):
            raise HTTPException(missing_status, "Uno o varios ciudadanos ya no existen. Actualiza la lista y revisa la selección.")
        deleted = db.query(Citizen).filter(Citizen.id.in_(ids)).delete(synchronize_session=False)
        if deleted != len(ids):
            raise HTTPException(409, "La selección cambió. Actualiza la lista e inténtalo nuevamente.")
        from app.services.audit import record
        record(db,actor,'contacts_deleted',count=deleted)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"success": True, "deleted_count": deleted, "deleted_ids": ids}


@router.post("/bulk-delete", dependencies=[Depends(require_contact_manager)])
def delete_citizens_bulk(payload: CitizenDeleteRequest, db: Session = Depends(get_db), actor=Depends(require_contact_manager)):
    return delete_selected_citizens(db, payload.citizen_ids, actor=actor)


@router.delete("/{citizen_id}", dependencies=[Depends(require_contact_manager)])
def delete_citizen(citizen_id: str, db: Session = Depends(get_db), actor=Depends(require_contact_manager)):
    return delete_selected_citizens(db, [citizen_id], missing_status=404, actor=actor)

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
async def save_contact_import(file: UploadFile = File(...), db: Session = Depends(get_db), actor=Depends(require_contact_manager)):
    parsed = await read_contact_upload(file)
    try:
        return import_contacts(db, parsed, actor=actor)
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


def known_social_authors(citizen):
    protected = ('usuario de facebook', 'perfil protegido', 'autor no disponible', 'ciudadano en redes')
    return {value for value in (citizen.name, citizen.handle) if value and not any(marker in value.lower() for marker in protected)}


class CitizenReplyRequest(CaseAction):
    case_id: str
    reply_text: str
    status: Optional[str] = None


@router.get('/{citizen_id}/comments')
def get_citizen_comments_and_posts(citizen_id: str, request: Request, db: Session = Depends(get_db)):
    citizen = db.get(Citizen, citizen_id)
    if not citizen:
        raise HTTPException(404, 'Ciudadano no encontrado')
    profile = CitizenResponse.model_validate(citizen).model_dump()
    profile['whatsapp_link'] = f"https://wa.me/{re.sub(r'[^0-9]', '', citizen.phone)}" if citizen.phone else None
    if citizen.channel in ('WhatsApp', 'Base de Datos'):
        return {'citizen': profile, 'total_comments': 0, 'comments': [], 'relationship_status': 'not_linked',
                'relationship_note': 'No hay un perfil social vinculado a este contacto.'}
    authors = known_social_authors(citizen)
    cases = db.query(Case).filter(Case.author.in_(authors), Case.source == citizen.channel).order_by(desc(Case.created_at)).limit(15).all()
    pids = {reference(case.internal_notes, 'Post ID') for case in cases} - {None}
    posts = {post.id: post for post in db.query(MetaPost).filter(MetaPost.id.in_(pids))} if pids else {}
    comments = []
    for case in cases:
        pid = reference(case.internal_notes, 'Post ID')
        post = posts.get(pid)
        comments.append({
            'case_id': case.id, 'author': case.author, 'comment_text': case.content, 'title': case.title,
            'sentiment': case.sentiment, 'category': case.category, 'location': case.location,
            'date_time': case.date_time, 'status': case.status, 'public_response': case.public_response,
            'workflow_revision': workflow.revision(case), 'ai_suggestion': None,
            'post': {'id': post.id if post else None, 'title': post.title if post else 'Origen no verificado',
                'cover_image': post_image_urls(post.id, post.cover_image, asset_base(request))[0] if post else None,
                'source': post.source if post else case.source,
                'permalink_url': post.permalink_url if post else None,
                'published_at': post.published_at if post else None},
        })
    return {'citizen': profile, 'total_comments': len(comments), 'comments': comments,
            'relationship_status': 'name_match_unverified',
            'relationship_note': 'Coincidencias exactas de nombre o usuario en el mismo canal; no certifican la identidad de la persona. Se muestran hasta 15 expedientes.'}


@router.post('/{citizen_id}/reply')
def register_official_reply(citizen_id: str, payload: CitizenReplyRequest, db: Session = Depends(get_db), user=Depends(require_contact_user)):
    citizen = db.get(Citizen, citizen_id)
    if not citizen:
        raise HTTPException(404, 'Ciudadano no encontrado')
    case = db.query(Case).filter_by(id=payload.case_id).populate_existing().with_for_update().first()
    if not case:
        raise HTTPException(404, 'Caso no encontrado')
    if citizen.channel in ('WhatsApp', 'Base de Datos') or case.source != citizen.channel or case.author not in known_social_authors(citizen):
        raise HTTPException(409, 'No hay una coincidencia social registrada para este expediente. Revisa su origen desde Gesti\u00f3n de casos.')
    assert_writable(db, case.id)
    if payload.status is not None:
        raise HTTPException(422, 'Guardar un borrador no cambia el estado. Atiende o cierra el caso desde su expediente.')
    workflow.save_draft(db, case, CasePublicResponse(public_response=payload.reply_text, expected_revision=payload.expected_revision), user)
    workflow.commit(db, case)
    return {'success': True, 'case_id': case.id, 'status': case.status, 'public_response': case.public_response,
            'workflow_revision': workflow.revision(case), 'message': 'Borrador interno guardado. No se envi\u00f3 ning\u00fan mensaje.'}
