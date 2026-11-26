from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy.orm import Session
from app.api.dependencies import require_signed_user
from app.core.database import get_db
from app.services import case_consolidation as service

router = APIRouter(prefix="/case-consolidations", tags=["Consolidación reversible de casos"])


class Pair(BaseModel):
    model_config = ConfigDict(extra="forbid")
    primary_case_id: str = Field(min_length=1, max_length=50)
    duplicate_case_id: str = Field(min_length=1, max_length=50)


class Decision(Pair):
    request_id: UUID
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    reason: str = Field(min_length=10, max_length=2000)
    confirmed_same_request: Literal[True]

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, value):
        if len(value.strip()) < 10:
            raise ValueError("Explica la decisión con al menos 10 caracteres")
        return value.strip()


class Undo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=10, max_length=2000)
    meaningful_reason = field_validator("reason")(Decision.meaningful_reason.__func__)


def require_decision_user(user=Depends(require_signed_user)):
    if user.role not in ("ADMIN", "SECRETARIO"):
        raise HTTPException(403, "La consolidación y su reversión corresponden a Administración o Secretaría")
    return user


@router.post("/compare")
def compare(payload: Pair, db: Session = Depends(get_db), user=Depends(require_signed_user)):
    return service.comparison(db, payload.primary_case_id, payload.duplicate_case_id)


@router.get("/case/{case_id}")
def get_history(case_id: str, db: Session = Depends(get_db), user=Depends(require_signed_user)):
    return service.history(db, case_id)


@router.post("")
def save(payload: Decision, db: Session = Depends(get_db), user=Depends(require_decision_user)):
    return service.consolidate(db, payload, user)


@router.post("/{operation_id}/undo")
def reverse(operation_id: UUID, payload: Undo, db: Session = Depends(get_db), user=Depends(require_decision_user)):
    return service.undo(db, str(operation_id), payload.reason, user)
