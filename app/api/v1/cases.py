from app.core.assets import asset_base
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from typing import List, Optional, Union, Dict, Any, Literal
from datetime import datetime

from app.core.database import get_db
from app.core.authentication import get_current_user
from app.models.case import Case
from app.models.case_comment import CaseComment
from app.models.case_provenance import CaseProvenanceReview
from app.models.case_workflow import CaseWorkflowEvent
from app.models.meta_post import MetaPost
from app.services.case_reads import list_case_summaries
from app.services import case_workflow as workflow
import uuid
from app.services.case_consolidation import assert_writable, duplicate_of, active_for_cases
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
    CaseNoRequest,
    CaseReopen,
    CaseRegistrationCreate,
    CaseRegistrationCancel,
    CasePriorityAction,
    MetaPostSummary,
)

router = APIRouter(prefix="/cases", tags=["Casos Ciudadanos"])


def writable_case(case_id, db, *, deleting=False):
    case = db.query(Case).filter_by(id=case_id).populate_existing().with_for_update().first()
    if case is None:
        raise HTTPException(404, 'Expediente no encontrado con ese ID exacto.')
    assert_writable(db, case.id, deleting=deleting)
    return case

def find_case_or_fallback(case_id: str, db: Session) -> Case:
    """Consulta un expediente existente. Una lectura nunca crea casos."""
    # 1. Búsqueda directa
    case_item = db.query(Case).filter(Case.id == case_id).first()
    if case_item:
        return case_item

    # A registered external reference may locate a case, but never by number guessing.
    matches = db.query(Case).filter(Case.institutional_radicado == case_id).limit(2).all()
    if len(matches) > 1:
        raise HTTPException(409, 'La referencia aparece en varios expedientes. Busca el ID interno exacto.')
    if matches:
        return matches[0]

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
    provenance: Literal["all", "needs_review", "recovered_local"] = Query("all"),
    include_duplicates: bool = Query(False),
    db: Session = Depends(get_db),
):
    if paginated:
        return list_case_summaries(db, search=search, priority=priority, category=category,
            source=source, status=status, department=department, priority_only=priority_only,
            limit=min(limit, 100), offset=skip, provenance=provenance, include_duplicates=include_duplicates, asset_base=asset_base(request))
    query = db.query(Case)
    if not include_duplicates:
        from app.services.case_reads import duplicate_target
        query = query.filter(duplicate_target().is_(None))
    if provenance != "all":
        query = query.filter(Case.id.in_(db.query(CaseProvenanceReview.case_id).filter(CaseProvenanceReview.status == provenance)))
        if provenance == "needs_review":
            from app.services.case_reads import has_active_consolidation
            query = query.filter(~has_active_consolidation())

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
    response_obj.workflow_revision = workflow.revision(case_item)
    response_obj.workflow_events = workflow.events(db, case_item.id)
    from app.services.case_registrations import listing
    response_obj.registrations = listing(db, case_item)
    response_obj.duplicate_of = duplicate_of(db, case_item.id)
    provenance = db.get(CaseProvenanceReview, case_item.id)
    if provenance:
        response_obj.provenance_status, response_obj.provenance_reason = provenance.status, provenance.reason
        response_obj.provenance_conflict = (provenance.evidence_json or {}).get("conflict_review")
        if provenance.status == "needs_review" and active_for_cases(db, [case_item.id]).first():
            response_obj.provenance_status = "consolidated"
    related_ids = [row.duplicate_case_id for row in active_for_cases(db, [case_item.id]).all()
                   if row.primary_case_id == case_item.id]
    response_obj.linked_comments = [{"post_id": link.post_id, "comment_id": link.comment_id,
        "original_case_id": link.case_id,
        "comment": link.comment_json, "linked_by": link.linked_by, "linked_at": link.created_at}
        for link in db.query(CaseComment).filter(CaseComment.case_id.in_([case_item.id, *related_ids])).order_by(CaseComment.created_at, CaseComment.comment_id)]
    
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
    cover, _ = post_image_urls(pid, candidate, asset_base(request))
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
def create_case(case_in: CaseCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    case_data = case_in.model_dump()
    protected = ('assigned_to', 'assigned_department', 'internal_notes', 'public_response', 'resolution_note', 'resolved_by', 'institutional_radicado', 'priority_action')
    if case_data.get('status') != workflow.PENDING or any(case_data.get(key) for key in protected) or case_data.get('comments_count') not in (None, 0, 1):
        raise HTTPException(422, 'Los casos nuevos empiezan pendientes; registra su atenci\u00f3n mediante las acciones del expediente.')
    for key, maximum in [('title',255), ('author',100), ('source',50), ('category',100), ('sentiment',50), ('location',150), ('content',20000)]:
        case_data[key] = workflow.text(case_data.get(key), key, maximum=maximum)
    if case_data['priority'] not in ('Alta', 'Media', 'Baja', 'Cr\u00edtica'):
        raise HTTPException(422, 'Prioridad no v\u00e1lida.')
    generated_id = (case_in.id.strip() if case_in.id is not None else None) or 'CASO-' + uuid.uuid4().hex[:16]
    if len(generated_id) > 50:
        raise HTTPException(422, 'Identificador demasiado largo.')
    if db.get(Case, generated_id):
        raise HTTPException(409, 'Ya existe un expediente con ese identificador.')
    case_data['id'] = generated_id
    case_data['date_time'] = case_data.get('date_time') or datetime.now().astimezone().isoformat(timespec='seconds')
    case_data['requires_followup'] = True
    new_case = Case(**case_data)
    db.add(new_case)
    db.flush()
    workflow.record(db, new_case, user, 'created', 'Expediente registrado manualmente. El c\u00f3digo interno no acredita radicaci\u00f3n externa.', {})
    return workflow.commit(db, new_case)


@router.patch('/{case_id}', response_model=CaseResponse)
def update_case(case_id: str, case_update: CaseUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    case_item = writable_case(case_id, db)
    updates = case_update.model_dump(exclude_unset=True, exclude={'expected_revision'})
    if 'priority_action' in updates and user.role not in ('ADMIN', 'ALCALDE'):
        raise HTTPException(403, 'Tu rol no permite cambiar la prioridad especial.')
    workflow.classify(db, case_item, updates, case_update.expected_revision, user)
    return workflow.commit(db, case_item)


@router.post('/{case_id}/dispatch', response_model=CaseResponse)
def dispatch_case(case_id: str, payload: CaseDispatch, db: Session = Depends(get_db), user=Depends(get_current_user)):
    case_item = writable_case(case_id, db)
    workflow.assign(db, case_item, payload, user)
    return workflow.commit(db, case_item)


@router.post('/{case_id}/notes', response_model=CaseResponse)
def add_case_note(case_id: str, payload: CaseNoteCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    case_item = writable_case(case_id, db)
    workflow.add_note(db, case_item, payload, user)
    return workflow.commit(db, case_item)


@router.post('/{case_id}/resolve', response_model=CaseResponse)
def resolve_case(case_id: str, payload: CaseResolve, db: Session = Depends(get_db), user=Depends(get_current_user)):
    case_item = writable_case(case_id, db)
    workflow.resolve(db, case_item, payload, user)
    return workflow.commit(db, case_item)


@router.post('/{case_id}/no-request', response_model=CaseResponse)
def mark_no_request(case_id: str, payload: CaseNoRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    case_item = writable_case(case_id, db)
    workflow.mark_no_request(db, case_item, payload, user)
    return workflow.commit(db, case_item)


@router.post('/{case_id}/reopen', response_model=CaseResponse)
def reopen_case(case_id: str, payload: CaseReopen, db: Session = Depends(get_db), user=Depends(get_current_user)):
    case_item = writable_case(case_id, db)
    workflow.reopen(db, case_item, payload, user)
    return workflow.commit(db, case_item)


@router.post('/{case_id}/registration', response_model=CaseResponse)
def register_external_reference(case_id: str, payload: CaseRegistrationCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.services.case_registrations import register
    case_item=writable_case(case_id,db)
    register(db,case_item,payload,user)
    return workflow.commit(db,case_item)


@router.post('/{case_id}/registration/cancel', response_model=CaseResponse)
def cancel_external_reference(case_id: str, payload: CaseRegistrationCancel, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.services.case_registrations import cancel
    case_item=writable_case(case_id,db)
    cancel(db,case_item,payload,user)
    return workflow.commit(db,case_item)


@router.post('/{case_id}/priority-action', response_model=CaseResponse)
def toggle_priority_action(case_id: str, payload: CasePriorityAction, db: Session = Depends(get_db), user=Depends(get_current_user)):
    case_item = writable_case(case_id, db)
    workflow.set_priority(db, case_item, payload, user)
    return workflow.commit(db, case_item)


@router.post('/{case_id}/public-response', response_model=CaseResponse)
def set_public_response(case_id: str, payload: CasePublicResponse, db: Session = Depends(get_db), user=Depends(get_current_user)):
    case_item = writable_case(case_id, db)
    workflow.save_draft(db, case_item, payload, user)
    return workflow.commit(db, case_item)


@router.delete('/{case_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_case(case_id: str, db: Session = Depends(get_db)):
    case_item = writable_case(case_id, db, deleting=True)
    if db.query(CaseWorkflowEvent.id).filter_by(case_id=case_item.id).first():
        raise HTTPException(409, 'El expediente tiene actuaciones registradas y debe conservarse.')
    db.delete(case_item)
    db.commit()
    return None
