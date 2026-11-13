from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from typing import List, Optional, Union, Dict, Any
from datetime import datetime

from app.core.database import get_db
from app.models.case import Case
from app.models.incident import Incident
from app.models.meta_post import MetaPost
from app.services.case_reads import list_case_summaries
from app.services.post_images import post_image_urls, real_image_url
import re
from app.schemas.case import (
    CaseCreate,
    CaseUpdate,
    CaseResponse,
    CaseDispatch,
    CaseNoteCreate,
    CaseResolve,
    CasePublicResponse,
    MetaPostSummary,
)

router = APIRouter(prefix="/cases", tags=["Casos Ciudadanos"])

def find_case_or_fallback(case_id: str, db: Session) -> Case:
    """Busca un caso por ID exacto, mapea CASO-XXX a CIV-2026-XXXX, 
    busca por radicado institucional, o crea el caso desde la tabla Incident si procede."""
    # 1. Búsqueda directa
    case_item = db.query(Case).filter(Case.id == case_id).first()
    if case_item:
        return case_item

    # 2. Mapeo entre prefijos CASO-XXX y CIV-2026-XXXX
    if case_id.startswith("CASO-"):
        num_str = case_id.replace("CASO-", "").lstrip("0") or "1"
        alt_id = f"CIV-2026-{num_str.zfill(4)}"
        case_item = db.query(Case).filter(Case.id == alt_id).first()
        if case_item:
            return case_item
    elif case_id.startswith("CIV-2026-"):
        num_str = case_id.replace("CIV-2026-", "").lstrip("0") or "1"
        alt_id = f"CASO-{num_str.zfill(3)}"
        case_item = db.query(Case).filter(Case.id == alt_id).first()
        if case_item:
            return case_item

    # 3. Buscar por número de radicado institucional
    case_item = db.query(Case).filter(Case.institutional_radicado == case_id).first()
    if case_item:
        return case_item

    # 4. Si el ID corresponde a un Incidente del mapa territorial, convertirlo y persistirlo como Caso
    incident = db.query(Incident).filter(Incident.id == case_id).first()
    if incident:
        rad_num = case_id.replace("CASO-", "").replace("CIV-2026-", "").zfill(4)
        cat_prefix = incident.category[:3].upper() if incident.category else "GEN"
        dept = "Las Ceibas - Empresas Públicas de Neiva E.S.P." if ("Servicios" in incident.category or "Agua" in incident.category) else "Secretaría de Infraestructura y Vías"
        new_case = Case(
            id=case_id,
            title=incident.title,
            content=incident.description,
            category=incident.category or "General",
            priority=incident.priority or "Media",
            sentiment=incident.sentiment or "Neutro",
            location=incident.neighborhood or "Neiva",
            source=incident.source or "Facebook",
            status=incident.status or "Pendiente",
            comments_count=incident.reports_count or 1,
            date_time=incident.date_time or datetime.now().strftime("%d %b %Y, %I:%M %p"),
            institutional_radicado=f"RAD-{cat_prefix}-2026-{rad_num}",
            assigned_department=dept,
            assigned_to="Equipo Operativo Comuna",
            priority_action=True if incident.priority == "Alta" else False,
            impact_if_solved="Atención y mitigación prioritaria de la problemática en el sector.",
            impact_if_ignored="Afectación prolongada a la comunidad y recurrencia de quejas.",
        )
        db.add(new_case)
        db.commit()
        db.refresh(new_case)
        return new_case

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Caso con id '{case_id}' no encontrado",
    )

@router.get("", response_model=Union[List[CaseResponse], Dict[str, Any]])
def get_cases(
    request: Request,
    search: Optional[str] = Query(None, description="Búsqueda por texto en título, contenido o barrio"),
    priority: Optional[str] = Query(None, description="Filtrar por prioridad: Alta, Media, Baja"),
    category: Optional[str] = Query(None, description="Filtrar por categoría de problemática"),
    source: Optional[str] = Query(None, description="Filtrar por red social / canal"),
    status: Optional[str] = Query(None, description="Filtrar por estado: Pendiente, En Gestión, Resuelto"),
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    paginated: bool = Query(False),
    department: Optional[str] = Query(None),
    priority_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    if paginated:
        return list_case_summaries(db, search=search, priority=priority, category=category,
            source=source, status=status, department=department, priority_only=priority_only,
            limit=min(limit, 100), offset=skip, asset_base=str(request.base_url).rstrip("/"))
    query = db.query(Case)

    if priority and priority != "all":
        query = query.filter(Case.priority == priority)

    if category and category != "all":
        query = query.filter(Case.category == category)

    if source and source != "all":
        query = query.filter(Case.source == source)

    if status and status != "all":
        query = query.filter(Case.status == status)

    if search:
        search_fmt = f"%{search.lower()}%"
        query = query.filter(
            or_(
                Case.title.ilike(search_fmt),
                Case.content.ilike(search_fmt),
                Case.location.ilike(search_fmt),
                Case.author.ilike(search_fmt),
                Case.id.ilike(search_fmt),
            )
        )

    cases = query.order_by(desc(Case.created_at), desc(Case.id)).offset(skip).limit(limit).all()
    # Backward-compatible array for other screens, without generic stock images.
    results = [CaseResponse.model_validate(item) for item in cases]
    for item in results:
        item.image_url = real_image_url(item.image_url)
    return results

@router.get("/{case_id}", response_model=CaseResponse)
def get_case_by_id(case_id: str, request: Request, db: Session = Depends(get_db)):
    case_item = find_case_or_fallback(case_id, db)
    response_obj = CaseResponse.model_validate(case_item)
    
    # Enriquecer con información real del Post de Johan Steed
    post = None
    notes = case_item.internal_notes or ""
    pid_match = re.search(r'\[Post ID\]:\s*([^\s\n]+)', notes)
    if pid_match:
        pid = pid_match.group(1).strip()
        post = db.query(MetaPost).filter(MetaPost.id == pid).first()
    
    pid = pid_match.group(1).strip() if pid_match else None
    candidate = post.cover_image if post else case_item.image_url
    if pid and not post and not (candidate or "").split("?", 1)[0].endswith(f"/{pid}.jpg"):
        candidate = None
    cover, _ = post_image_urls(pid, candidate, str(request.base_url).rstrip("/"))
    response_obj.image_url = cover
    if post:
        p_url = post.permalink_url
        response_obj.post_data = MetaPostSummary(
            id=post.id,
            title=post.title,
            message=post.message or post.title,
            cover_image=cover,
            media_type=post.media_type or "image",
            permalink_url=p_url,
            published_at=post.published_at or case_item.date_time,
            source=post.source or case_item.source,
            total_comments=post.total_comments or 0,
            likes_count=post.likes_count or 0,
        )
        cid_match = re.search(r'\[Comment ID\]:\s*([^\s\r\n]+)', notes)
        if cid_match and p_url:
            cid = cid_match.group(1).strip()
            raw_cid = cid.split('_')[-1]
            sep = '&' if '?' in p_url else '?'
            response_obj.comment_url = f"{p_url}{sep}comment_id={raw_cid}"
        else:
            response_obj.comment_url = p_url
    return response_obj

@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(case_in: CaseCreate, db: Session = Depends(get_db)):
    if not case_in.id:
        count = db.query(Case).count()
        generated_id = f"CASO-{str(count + 1).zfill(3)}"
    else:
        generated_id = case_in.id

    existing = db.query(Case).filter(Case.id == generated_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un caso con id '{generated_id}'",
        )

    case_data = case_in.model_dump()
    case_data["id"] = generated_id
    new_case = Case(**case_data)
    db.add(new_case)
    db.commit()
    db.refresh(new_case)
    return new_case

@router.patch("/{case_id}", response_model=CaseResponse)
def update_case(case_id: str, case_update: CaseUpdate, db: Session = Depends(get_db)):
    case_item = find_case_or_fallback(case_id, db)
    update_data = case_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(case_item, field, value)

    db.commit()
    db.refresh(case_item)
    return case_item

@router.post("/{case_id}/dispatch", response_model=CaseResponse)
def dispatch_case(case_id: str, payload: CaseDispatch, db: Session = Depends(get_db)):
    """Despacha un caso a una Secretaría o entidad de Neiva, cambiando estado a En Gestión."""
    case_item = find_case_or_fallback(case_id, db)
    case_item.assigned_department = payload.assigned_department
    if payload.assigned_to:
        case_item.assigned_to = payload.assigned_to
    case_item.status = "En Gestión"

    if payload.note:
        now_str = datetime.now().strftime("%d %b %Y, %H:%M")
        new_note = f"[{now_str}] [Despacho a {payload.assigned_department}]: {payload.note}"
        if case_item.internal_notes:
            case_item.internal_notes = f"{case_item.internal_notes}\n{new_note}"
        else:
            case_item.internal_notes = new_note

    db.commit()
    db.refresh(case_item)
    return case_item

@router.post("/{case_id}/notes", response_model=CaseResponse)
def add_case_note(case_id: str, payload: CaseNoteCreate, db: Session = Depends(get_db)):
    """Registra una nota interna de seguimiento en la bitácora del caso."""
    case_item = find_case_or_fallback(case_id, db)
    now_str = datetime.now().strftime("%d %b %Y, %H:%M")
    new_note = f"[{now_str}] {payload.author_name}: {payload.note}"
    if case_item.internal_notes:
        case_item.internal_notes = f"{case_item.internal_notes}\n{new_note}"
    else:
        case_item.internal_notes = new_note

    db.commit()
    db.refresh(case_item)
    return case_item

@router.post("/{case_id}/resolve", response_model=CaseResponse)
def resolve_case(case_id: str, payload: CaseResolve, db: Session = Depends(get_db)):
    """Marca un caso como Resuelto, registrando la nota de cierre técnico y responsable."""
    case_item = find_case_or_fallback(case_id, db)
    case_item.status = "Resuelto"
    case_item.resolution_note = payload.resolution_note
    case_item.resolved_by = payload.resolved_by

    now_str = datetime.now().strftime("%d %b %Y, %H:%M")
    close_note = f"[{now_str}] [Caso Resuelto por {payload.resolved_by}]: {payload.resolution_note}"
    if case_item.internal_notes:
        case_item.internal_notes = f"{case_item.internal_notes}\n{close_note}"
    else:
        case_item.internal_notes = close_note

    db.commit()
    db.refresh(case_item)
    return case_item

@router.post("/{case_id}/priority-action", response_model=CaseResponse)
def toggle_priority_action(case_id: str, db: Session = Depends(get_db)):
    """Alterna la declaratoria de Prioridad Inmediata de la Alcaldía de Neiva."""
    case_item = find_case_or_fallback(case_id, db)
    case_item.priority_action = not (case_item.priority_action or False)
    now_str = datetime.now().strftime("%d %b %Y, %H:%M")
    if case_item.priority_action:
        alert_note = f"[{now_str}] [Alcaldía de Neiva - Despacho]: Se ha declarado PRIORIDAD DE INTERVENCIÓN INMEDIATA para este caso."
    else:
        alert_note = f"[{now_str}] [Alcaldía de Neiva - Despacho]: Se retira la declaratoria de prioridad inmediata."
    
    if case_item.internal_notes:
        case_item.internal_notes = f"{case_item.internal_notes}\n{alert_note}"
    else:
        case_item.internal_notes = alert_note

    db.commit()
    db.refresh(case_item)
    return case_item

@router.post("/{case_id}/public-response", response_model=CaseResponse)
def set_public_response(case_id: str, payload: CasePublicResponse, db: Session = Depends(get_db)):
    """Guarda la respuesta institucional oficial redactada para redes sociales."""
    case_item = find_case_or_fallback(case_id, db)
    case_item.public_response = payload.public_response
    db.commit()
    db.refresh(case_item)
    return case_item

@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(case_id: str, db: Session = Depends(get_db)):
    case_item = find_case_or_fallback(case_id, db)
    db.delete(case_item)
    db.commit()
    return None
