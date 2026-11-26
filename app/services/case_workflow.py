"""Case state transitions, checked under a case lock by every write entry point."""
from datetime import datetime, timezone
import hashlib
from fastapi import HTTPException
from app.models.case_workflow import CaseWorkflowEvent
from app.services.case_conflict_review import case_fingerprint

PENDING = 'Pendiente'
ACTIVE = 'En Gestión'
RESOLVED = 'Resuelto'
GENERAL = 'No requiere gestión'
OPEN = (PENDING, ACTIVE)
FIELDS = ('status', 'assigned_department', 'assigned_to', 'requires_followup', 'public_response',
          'resolution_note', 'resolved_by', 'institutional_radicado', 'priority_action', 'priority', 'category', 'sentiment', 'comments_count')
PROTECTED_PATCH_FIELDS = {'status', 'assigned_department', 'assigned_to', 'internal_notes', 'public_response',
    'resolution_note', 'resolved_by', 'priority_action', 'institutional_radicado', 'requires_followup', 'comments_count',
    'impact_if_solved', 'impact_if_ignored'}


def revision(case):
    return hashlib.sha256(f'{case.id}\0{case_fingerprint(case)}'.encode()).hexdigest()


def require_revision(case, expected):
    if not expected:
        raise HTTPException(422, 'Actualiza el expediente antes de guardar; falta la versión revisada.')
    if expected != revision(case):
        raise HTTPException(409, 'El expediente cambió desde que lo abriste. Actualiza y revisa los cambios antes de guardar.')


def snapshot(case):
    return {key: getattr(case, key, None) for key in FIELDS}


def commit(db, case):
    try:
        db.commit()
        db.refresh(case)
    except Exception:
        db.rollback()
        raise
    return case


def require_open(case):
    if case.status not in OPEN:
        raise HTTPException(409, 'Este expediente no está abierto para atención. Su historial se conserva.')


def text(value, label, minimum=1, maximum=10000):
    value = (value or '').strip()
    if not minimum <= len(value) <= maximum:
        raise HTTPException(422, f'{label}: escribe entre {minimum} y {maximum} caracteres.')
    return value


def record(db, case, user, kind, note, before, evidence=None):
    event = CaseWorkflowEvent(case_id=case.id, event_type=kind, actor_id=user.id,
        actor_name=user.full_name, note=note, evidence_reference=evidence, before_state=before, after_state=snapshot(case))
    db.add(event)
    # Legacy text remains append-only. Untrusted brackets cannot forge origin markers.
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    safe_note = note.replace('[', '［').replace(']', '］').replace('\r', '').replace('\n', ' / ')
    safe_actor = user.full_name.replace('[', '［').replace(']', '］').replace('\n', ' ')
    entry = f'[{stamp}] [CIVIA {kind} por {safe_actor} / {user.id}]: {safe_note}'
    case.internal_notes = ((case.internal_notes or '') + '\n' + entry).strip()
    return event


def assign(db, case, payload, user):
    require_open(case)
    department = text(payload.assigned_department, 'Entidad o equipo', maximum=100)
    owner = text(payload.assigned_to, 'Persona responsable', maximum=100)
    instruction = text(payload.note, 'Próxima actuación', minimum=10)
    if payload.confirmed_review is not True:
        raise HTTPException(422, 'Confirma que revisaste el comentario y requiere atención.')
    require_revision(case, payload.expected_revision)
    before = snapshot(case)
    case.assigned_department, case.assigned_to = department, owner
    case.status, case.requires_followup = ACTIVE, True
    record(db, case, user, 'assigned', f'{department} / {owner}. Próxima actuación: {instruction}', before)


def add_note(db, case, payload, user):
    require_open(case)
    note = text(payload.note, 'Avance')
    require_revision(case, payload.expected_revision)
    record(db, case, user, 'note_added', note, snapshot(case))


def save_draft(db, case, payload, user):
    require_open(case)
    draft = text(payload.public_response, 'Borrador')
    require_revision(case, payload.expected_revision)
    before = snapshot(case)
    case.public_response = draft
    record(db, case, user, 'response_drafted', 'Borrador interno guardado. No acredita publicación ni envío.', before)


def resolve(db, case, payload, user):
    require_open(case)
    if case.status != ACTIVE or not (case.assigned_department or '').strip() or not (case.assigned_to or '').strip():
        raise HTTPException(409, 'Asigna entidad y responsable antes de cerrar el caso.')
    note = text(payload.resolution_note, 'Resultado de la atención', minimum=20)
    reference = text(payload.evidence_reference, 'Referencia del soporte', minimum=5, maximum=2000)
    if payload.confirmed_resolution is not True:
        raise HTTPException(422, 'Confirma que verificaste la solución y su soporte.')
    require_revision(case, payload.expected_revision)
    before = snapshot(case)
    case.status, case.requires_followup = RESOLVED, False
    case.resolution_note, case.resolved_by = note, user.full_name
    record(db, case, user, 'resolved', note, before, reference)


def mark_no_request(db, case, payload, user):
    if case.status != PENDING or case.assigned_to or case.resolution_note or case.resolved_by:
        raise HTTPException(409, 'Solo un expediente pendiente y sin atención asignada puede clasificarse como conversación general.')
    reason = text(payload.reason, 'Motivo de la decisión', minimum=20)
    if payload.confirmed_review is not True:
        raise HTTPException(422, 'Confirma que revisaste el comentario y su contexto.')
    require_revision(case, payload.expected_revision)
    before = snapshot(case)
    case.status, case.requires_followup = GENERAL, False
    record(db, case, user, 'no_request', reason, before)


def reopen(db, case, payload, user):
    if user.role not in ('ADMIN', 'SECRETARIO'):
        raise HTTPException(403, 'La reapertura requiere Administración o Secretaría.')
    if case.status not in (RESOLVED, GENERAL):
        raise HTTPException(409, 'Solo un caso resuelto o sin solicitud de atención puede reabrirse.')
    reason = text(payload.reason, 'Motivo de la reapertura', minimum=20)
    if payload.confirmed_reopening is not True:
        raise HTTPException(422, 'Confirma que revisaste la decisión anterior y corresponde revisar el caso de nuevo.')
    require_revision(case, payload.expected_revision)
    before = snapshot(case)
    case.status, case.requires_followup = PENDING, True
    case.assigned_department = case.assigned_to = None
    case.resolution_note = case.resolved_by = None
    case.public_response = None
    record(db, case, user, 'reopened', reason, before)


def classify(db, case, updates, expected, user):
    if set(updates) & PROTECTED_PATCH_FIELDS:
        raise HTTPException(422, 'Usa las acciones de asignación, avance, borrador o cierre; la actualización general no modifica estado, origen ni historial.')
    require_open(case)
    require_revision(case, expected)
    if not updates:
        raise HTTPException(422, 'No hay cambios de clasificación para guardar.')
    normalized = {}
    for key, value in updates.items():
        if key == 'priority' and value not in ('Alta', 'Media', 'Baja', 'Crítica'):
            raise HTTPException(422, 'Prioridad no válida.')
        normalized[key] = text(value, key, maximum=100 if key == 'category' else 50)
    before = snapshot(case)
    for key, value in normalized.items():
        setattr(case, key, value)
    record(db, case, user, 'classified', 'Clasificación revisada por el usuario.', before)


def set_priority(db, case, payload, user):
    require_open(case)
    require_revision(case, payload.expected_revision)
    before = snapshot(case)
    if case.priority_action == payload.priority_action:
        return
    case.priority_action = payload.priority_action
    record(db, case, user, 'priority_changed', 'Prioridad especial activada.' if case.priority_action else 'Prioridad especial retirada.', before)


def events(db, case_id):
    result = []
    for row in db.query(CaseWorkflowEvent).filter_by(case_id=case_id).order_by(CaseWorkflowEvent.created_at.desc(), CaseWorkflowEvent.id.desc()):
        item = {key: getattr(row, key) for key in ('id', 'event_type', 'actor_id', 'actor_name', 'note',
            'evidence_reference', 'before_state', 'after_state', 'created_at')}
        if item['created_at'].tzinfo is None:
            item['created_at'] = item['created_at'].replace(tzinfo=timezone.utc)
        result.append(item)
    return result
