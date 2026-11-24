from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.dependencies import require_triage_user
from app.core.database import get_db
from app.schemas.triage import ConsolidateComments
from app.services.triage import consolidate_comments

router = APIRouter(prefix="/triage", tags=["Revisión de comentarios"])


@router.post("/consolidate")
def consolidate(payload: ConsolidateComments, db: Session = Depends(get_db), user=Depends(require_triage_user)):
    return consolidate_comments(db, payload, user)
