from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy.orm import Session
from app.api.dependencies import require_signed_user
from app.api.v1.case_consolidations import Undo, require_decision_user
from app.core.database import get_db
from app.services import case_correction as service

router = APIRouter(prefix="/case-corrections", tags=["Corrección de despachos de prueba"])


class Correction(Undo):
    request_id: UUID
    case_id: str = Field(min_length=1, max_length=50)
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    disposition: Literal["needs_review", "general_opinion"]
    confirmed_review: Literal[True]


@router.get("/case/{case_id}")
def review(case_id: str, db: Session = Depends(get_db), user=Depends(require_signed_user)):
    return service.preview(db, case_id)


@router.post("")
def save(payload: Correction, db: Session = Depends(get_db), user=Depends(require_decision_user)):
    return service.correct(db, payload, user)


@router.post("/{operation_id}/undo")
def reverse(operation_id: UUID, payload: Undo, db: Session = Depends(get_db), user=Depends(require_decision_user)):
    return service.undo(db, str(operation_id), payload.reason, user)
