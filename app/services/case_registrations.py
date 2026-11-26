from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from app.models.case_registration import CaseRegistration
from app.services import case_workflow as workflow


def listing(db, case):
    rows = db.query(CaseRegistration).filter_by(case_id=case.id).order_by(CaseRegistration.created_at.desc(), CaseRegistration.id.desc()).all()
    result = []
    for index, row in enumerate(rows):
        item = {key:getattr(row,key) for key in ('id','number','institution','issued_on','evidence_reference','reason','actor_id','actor_name','created_at','cancelled_at','cancelled_by','cancellation_reason')}
        item['is_current'] = index == 0 and not row.cancelled_at and case.institutional_radicado == row.number
        result.append(item)
    return result


def register(db, case, payload, user):
    workflow.require_revision(case,payload.expected_revision)
    number = workflow.text(payload.number,'Número externo',maximum=100)
    institution = workflow.text(payload.institution,'Entidad emisora',minimum=3,maximum=160)
    reason = workflow.text(payload.reason,'Motivo del registro',minimum=20)
    evidence = workflow.text(payload.evidence_reference,'Soporte',minimum=5,maximum=2000)
    if number.casefold() == case.id.casefold() or any(ord(c)<32 for c in number):
        raise HTTPException(422,'El número externo debe corresponder al documento, separado del ID interno de CIVIA.')
    if payload.issued_on > datetime.now(timezone(timedelta(hours=-5))).date():
        raise HTTPException(422,'La fecha de radicación no puede ser futura.')
    if payload.confirmed_review is not True:
        raise HTTPException(422,'Confirma que cotejaste los datos con el soporte externo.')
    current = listing(db,case)
    if current and current[0]['is_current'] and current[0]['number']==number and current[0]['institution']==institution:
        raise HTTPException(409,'Esa referencia ya está vigente. Su registro se conserva.')
    before = workflow.snapshot(case)
    db.add(CaseRegistration(case_id=case.id,number=number,institution=institution,issued_on=payload.issued_on,evidence_reference=evidence,reason=reason,actor_id=user.id,actor_name=user.full_name))
    case.institutional_radicado = number
    workflow.record(db,case,user,'registration_recorded',f'{institution} / {number}. {reason}',before,evidence)


def cancel(db, case, payload, user):
    workflow.require_revision(case,payload.expected_revision)
    reason = workflow.text(payload.reason,'Motivo de la anulación',minimum=20)
    if payload.confirmed_review is not True:
        raise HTTPException(422,'Confirma que revisaste la referencia antes de retirarla.')
    rows = db.query(CaseRegistration).filter_by(case_id=case.id).order_by(CaseRegistration.created_at.desc(),CaseRegistration.id.desc()).all()
    if not rows or rows[0].cancelled_at or rows[0].number != case.institutional_radicado:
        raise HTTPException(409,'No hay una referencia vigente registrada con soporte en CIVIA.')
    before = workflow.snapshot(case)
    rows[0].cancelled_at,rows[0].cancelled_by,rows[0].cancellation_reason = datetime.now(timezone.utc),user.id,reason
    case.institutional_radicado = None
    workflow.record(db,case,user,'registration_cancelled',reason,before,rows[0].evidence_reference)
