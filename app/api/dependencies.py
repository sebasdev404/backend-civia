from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.authentication import get_current_user


def require_signed_user(authorization: str | None = Header(None), db: Session = Depends(get_db)):
    return get_current_user(authorization, db)


def require_triage_user(user=Depends(require_signed_user)):
    if user.role not in ("ADMIN", "ALCALDE", "OPERADOR"):
        raise HTTPException(403, "Tu rol no permite consolidar comentarios")
    return user
