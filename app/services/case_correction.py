"""Explicit correction of an evidenced test dispatch, with guarded reversal."""
import re
from datetime import datetime, timezone
from fastapi import HTTPException
from app.models.case import Case
from app.models.case_correction import CaseCorrection
from app.models.case_provenance import CaseProvenanceReview
from app.models.meta_post import MetaPost
from app.services.case_consolidation import active_for_cases, snapshot
from app.services.case_conflict_review import matches_capture, case_fingerprint
from app.services.provenance_recovery import reference, read_capture, digest

CHANGED_FIELDS = ("status", "assigned_department", "assigned_to", "requires_followup")


def public_record(row):
    return {key: getattr(row, key) for key in ("id", "case_id", "disposition", "reason", "created_by", "created_at",
                                             "undone_at", "undone_by", "undo_reason")}


def preview(db, case_id, *, lock=False):
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(404, "El expediente no existe")
    pid = reference(case.internal_notes, "Post ID")
    query = db.query(MetaPost).filter_by(id=pid)
    post = (query.with_for_update() if lock else query).populate_existing().first()
    query = db.query(Case).filter_by(id=case_id)
    case = (query.with_for_update() if lock else query).populate_existing().one()
    assignments = [line for line in (case.internal_notes or "").splitlines() if re.search(r"\[(?:despacho|asignaci[oó]n)\b", line, re.I)]
    test_note = assignments[-1] if assignments and "despacho de prueba" in assignments[-1].lower() else None
    rows = db.query(CaseCorrection).filter_by(case_id=case_id).order_by(CaseCorrection.created_at.desc(), CaseCorrection.id).all()
    blockers = []
    if not test_note:
        blockers.append("La última asignación registrada no está identificada explícitamente como despacho de prueba.")
    if case.status != "En Gestión" or not (case.assigned_to or case.assigned_department):
        blockers.append("No hay una asignación activa en gestión que pueda rectificarse con este flujo.")
    if any((case.public_response, case.resolution_note, case.resolved_by, case.institutional_radicado, case.priority_action)):
        blockers.append("Hay respuesta, cierre, radicado o prioridad especial: se requiere una revisión adicional.")
    if any(row.undone_at is None for row in rows):
        blockers.append("Ya existe una corrección activa para este expediente.")
    if active_for_cases(db, [case_id]).first():
        blockers.append("Deshaz primero la consolidación activa antes de corregir este expediente.")
    review = db.get(CaseProvenanceReview, case_id)
    evidence = review.evidence_json if review else {}
    cid = reference(case.internal_notes, "Comment ID") or (evidence or {}).get("comment_id")
    raw = (read_capture(post.raw_comments_json) or {}).get(cid) if post else None
    source = None
    if not post or post.id != reference(case.internal_notes, "Post ID") or not matches_capture(case, raw, post.id):
        blockers.append("No se pudo comprobar el comentario exacto contra su captura local.")
    else:
        source = {"post_id": post.id, "comment_id": cid, "post_title": post.title, "post_message": post.message,
                  "post_url": post.permalink_url, "comment": raw}
    data = snapshot(case)
    revision = digest({"case": data, "source": source, "test_note": test_note, "blockers": blockers})
    return {"case": data, "source": source, "test_note": test_note, "blockers": blockers,
            "revision": revision, "history": [public_record(row) for row in rows]}


def correct(db, payload, user):
    try:
        def prior():
            row = db.get(CaseCorrection, str(payload.request_id))
            if row and (row.case_id, row.disposition, row.reason, row.created_by) != (
                    payload.case_id, payload.disposition, payload.reason, user.id):
                raise HTTPException(409, "El identificador de operación ya corresponde a otra decisión")
            return row
        existing = prior()
        if existing:
            return public_record(existing)
        value = preview(db, payload.case_id, lock=True)
        existing = prior()
        if existing:
            return public_record(existing)
        if value["blockers"]:
            raise HTTPException(409, " ".join(value["blockers"]))
        if payload.revision != value["revision"]:
            raise HTTPException(409, "El expediente o su evidencia cambiaron. Actualiza la revisión antes de confirmar.")
        case = db.get(Case, payload.case_id)
        before = snapshot(case)
        case.assigned_to = case.assigned_department = None
        no_request = payload.disposition == "general_opinion"
        case.status = "No requiere gestión" if no_request else "Pendiente"
        case.requires_followup = not no_request
        now = datetime.now(timezone.utc)
        note = f"[{now.isoformat(timespec='seconds')}] [Corrección CIVIA por {user.id}]: Asignación de prueba retirada. "
        note += ("Opinión general sin solicitud concreta, según revisión humana. " if no_request else "Pendiente de revisión de la solicitud. ") + payload.reason
        case.internal_notes = (case.internal_notes or "") + "\n" + note
        record = CaseCorrection(id=str(payload.request_id), case_id=case.id, disposition=payload.disposition,
            reason=payload.reason, created_by=user.id, created_at=now,
            evidence_json={"method": "test_dispatch_correction_v1", "before": before, "after": snapshot(case),
                           "after_fingerprint": case_fingerprint(case), "review": {key: value[key] for key in ("source", "test_note", "revision")}})
        db.add(record)
        db.commit()
        return public_record(record)
    except Exception:
        db.rollback()
        raise


def undo(db, operation_id, reason, user):
    try:
        record = db.get(CaseCorrection, operation_id)
        if not record:
            raise HTTPException(404, "La corrección no existe")
        case = db.query(Case).filter_by(id=record.case_id).populate_existing().with_for_update().one()
        record = db.query(CaseCorrection).filter_by(id=operation_id).populate_existing().with_for_update().one()
        if record.undone_at:
            return public_record(record)
        if active_for_cases(db, [case.id]).first() or case_fingerprint(case) != record.evidence_json["after_fingerprint"]:
            raise HTTPException(409, "Hay cambios posteriores o una consolidación activa. Se requiere revisión manual para no sobrescribir seguimiento.")
        for field in CHANGED_FIELDS:
            setattr(case, field, record.evidence_json["before"][field])
        now = datetime.now(timezone.utc)
        case.internal_notes += f"\n[{now.isoformat(timespec='seconds')}] [Reversión de corrección CIVIA por {user.id}]: {reason}"
        record.undone_at, record.undone_by, record.undo_reason = now, user.id, reason
        db.commit()
        return public_record(record)
    except Exception:
        db.rollback()
        raise
