"""Reversible, audited duplicate relationships. Never overwrite or move case data."""
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import or_

from app.models.case import Case
from app.models.case_comment import CaseComment
from app.models.case_consolidation import CaseConsolidation
from app.models.case_provenance import CaseProvenanceReview
from app.models.case_correction import CaseCorrection
from app.models.meta_post import MetaPost
from app.services.case_conflict_review import FIELDS, has_attention, matches_capture
from app.services.provenance_recovery import reference, read_capture, digest


def active_for_cases(db, ids):
    return db.query(CaseConsolidation).filter(CaseConsolidation.undone_at.is_(None), or_(
        CaseConsolidation.primary_case_id.in_(ids), CaseConsolidation.duplicate_case_id.in_(ids)))


def duplicate_of(db, case_id):
    return db.query(CaseConsolidation.primary_case_id).filter_by(duplicate_case_id=case_id, undone_at=None).scalar()


def assert_writable(db, case_id, *, deleting=False):
    primary = duplicate_of(db, case_id)
    if primary:
        raise HTTPException(409, f"Este expediente es duplicado de {primary}. Atiende el principal o deshaz la consolidación.")
    if deleting and db.query(CaseConsolidation.id).filter(or_(CaseConsolidation.primary_case_id == case_id,
                                                           CaseConsolidation.duplicate_case_id == case_id)).first():
        raise HTTPException(409, "El expediente tiene un historial de consolidación y debe conservarse.")
    if deleting and db.query(CaseCorrection.id).filter_by(case_id=case_id).first():
        raise HTTPException(409, "El expediente tiene un historial de corrección y debe conservarse.")


def snapshot(record):
    return {col.name: (value.isoformat() if isinstance(value, datetime) else value)
            for col in record.__table__.columns for value in [getattr(record, col.name)]}


def serialize(record):
    return {key: getattr(record, key) for key in ("id", "primary_case_id", "duplicate_case_id", "reason",
            "created_by", "created_at", "undone_at", "undone_by", "undo_reason")}


def history(db, case_id):
    if not db.get(Case, case_id):
        raise HTTPException(404, "El expediente no existe")
    return [serialize(row) for row in db.query(CaseConsolidation).filter(or_(
        CaseConsolidation.primary_case_id == case_id, CaseConsolidation.duplicate_case_id == case_id))
        .order_by(CaseConsolidation.created_at.desc(), CaseConsolidation.id)]


def comparison(db, first_id, second_id, *, lock=False):
    if first_id == second_id:
        raise HTTPException(422, "Selecciona dos expedientes diferentes")
    ids = sorted([first_id, second_id])
    # Source locks first, then case locks in stable order, matching triage/recovery.
    initial = db.query(Case).filter(Case.id.in_(ids)).all()
    if len(initial) != 2:
        raise HTTPException(404, "Uno de los expedientes no existe")
    reviews = db.query(CaseProvenanceReview).filter(CaseProvenanceReview.case_id.in_(ids)).all()
    candidates = {row.case_id: row.evidence_json or {} for row in reviews if row.reason == "comment_linked_to_other_case"}
    pids = {reference(row.internal_notes, "Post ID") for row in initial}
    query = db.query(MetaPost).filter(MetaPost.id.in_(pids - {None})).order_by(MetaPost.id)
    posts = {row.id: row for row in (query.with_for_update() if lock else query).populate_existing()}
    query = db.query(Case).filter(Case.id.in_(ids)).order_by(Case.id)
    cases = list((query.with_for_update() if lock else query).populate_existing())
    links = db.query(CaseComment).filter(CaseComment.case_id.in_(ids)).order_by(CaseComment.post_id, CaseComment.comment_id).all()
    refs = {}
    for case in cases:
        pid, cid = reference(case.internal_notes, "Post ID"), reference(case.internal_notes, "Comment ID")
        refs[case.id] = {(row.post_id, row.comment_id) for row in links if row.case_id == case.id}
        if pid and cid:
            refs[case.id].add((pid, cid))
        candidate = candidates.get(case.id, {})
        if not refs[case.id] and candidate.get("post_id") and candidate.get("comment_id"):
            refs[case.id].add((candidate["post_id"], candidate["comment_id"]))
    shared = refs[ids[0]] & refs[ids[1]]
    source = None
    blockers = []
    if len(shared) != 1 or any(len(value) != 1 for value in refs.values()):
        blockers.append("No se encontró un único comentario de origen compartido. Revisa las referencias y los comentarios adicionales.")
    else:
        pid, cid = next(iter(shared))
        post = posts.get(pid)
        raw = (read_capture(post.raw_comments_json) or {}).get(cid) if post else None
        if not all(matches_capture(case, raw, pid) for case in cases):
            blockers.append("La captura no coincide exactamente en publicación, texto, autor registrado y fecha de ambos expedientes.")
        else:
            source = {"post_id": pid, "comment_id": cid, "comment": raw,
                      "post_title": post.title, "post_message": post.message, "post_url": post.permalink_url}
        # A pair cannot silently absorb a third claimant.
        others = {row.id for row in db.query(Case.id, Case.internal_notes).filter(~Case.id.in_(ids))
                  if reference(row.internal_notes, "Post ID") == pid and reference(row.internal_notes, "Comment ID") == cid}
        others.update(row.case_id for row in db.query(CaseComment.case_id).filter_by(post_id=pid, comment_id=cid) if row.case_id not in ids)
        others.update(row.case_id for row in db.query(CaseProvenanceReview).filter_by(reason="comment_linked_to_other_case")
                      if row.case_id not in ids and (row.evidence_json or {}).get("post_id") == pid
                      and (row.evidence_json or {}).get("comment_id") == cid)
        if others:
            blockers.append("Hay otros expedientes que reclaman el mismo comentario; este flujo solo consolida pares sin terceros.")
    active = active_for_cases(db, ids).all()
    if active:
        blockers.append("Uno de los expedientes ya pertenece a una consolidación activa. No se permiten cadenas ni grupos superpuestos.")
    snapshots = [snapshot(row) for row in cases]
    differences = [field for field in FIELDS if getattr(cases[0], field) != getattr(cases[1], field)]
    attention = [row.id for row in cases if has_attention(row)]
    revision = digest({"cases": snapshots, "links": [snapshot(row) for row in links], "source": source,
                       "blockers": blockers, "active": [snapshot(row) for row in active]})
    return {"cases": snapshots, "source": source, "differences": differences, "attention_case_ids": attention,
            "blockers": blockers, "revision": revision}


def consolidate(db, payload, user):
    try:
        existing = db.get(CaseConsolidation, str(payload.request_id))
        if existing:
            if (existing.primary_case_id, existing.duplicate_case_id, existing.created_by, existing.reason) != (
                    payload.primary_case_id, payload.duplicate_case_id, user.id, payload.reason):
                raise HTTPException(409, "El identificador de operación ya fue utilizado para otra decisión")
            return serialize(existing)
        preview = comparison(db, payload.primary_case_id, payload.duplicate_case_id, lock=True)
        # Recheck after acquiring the case locks: another request may just have committed.
        existing = db.get(CaseConsolidation, str(payload.request_id))
        if existing:
            if (existing.primary_case_id, existing.duplicate_case_id, existing.created_by, existing.reason) == (
                    payload.primary_case_id, payload.duplicate_case_id, user.id, payload.reason):
                return serialize(existing)
            raise HTTPException(409, "El identificador de operación ya fue utilizado")
        if preview["blockers"]:
            raise HTTPException(409, " ".join(preview["blockers"]))
        if preview["revision"] != payload.revision:
            raise HTTPException(409, "Los expedientes o su evidencia cambiaron. Actualiza la comparación antes de confirmar.")
        if payload.duplicate_case_id in preview["attention_case_ids"]:
            raise HTTPException(409, "El expediente con seguimiento debe conservarse como principal. Si ambos tienen seguimiento, requieren una revisión adicional.")
        row = CaseConsolidation(id=str(payload.request_id), primary_case_id=payload.primary_case_id,
            duplicate_case_id=payload.duplicate_case_id, reason=payload.reason, created_by=user.id,
            created_at=datetime.now(timezone.utc), evidence_json={"method": "reversible_duplicate_pair_v1",
                "confirmed_same_request": True, "comparison": preview})
        db.add(row)
        db.commit()
        return serialize(row)
    except Exception:
        db.rollback()
        raise


def undo(db, operation_id, reason, user):
    try:
        row = db.get(CaseConsolidation, operation_id)
        if not row:
            raise HTTPException(404, "La consolidación no existe")
        list(db.query(Case).filter(Case.id.in_([row.primary_case_id, row.duplicate_case_id])).order_by(Case.id).with_for_update())
        row = db.query(CaseConsolidation).filter_by(id=operation_id).populate_existing().with_for_update().one()
        if row.undone_at is None:
            row.undone_at, row.undone_by, row.undo_reason = datetime.now(timezone.utc), user.id, reason
            db.commit()
        return serialize(row)
    except Exception:
        db.rollback()
        raise
