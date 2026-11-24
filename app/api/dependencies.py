from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.api.v1.auth import get_current_user


def require_signed_user(authorization: str | None = Header(None), db: Session = Depends(get_db)):
    token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
    if not decode_access_token(token):
        raise HTTPException(401, "Inicia sesión para gestionar comentarios y casos")
    return get_current_user(authorization, db)


def require_triage_user(user=Depends(require_signed_user)):
    if user.role not in ("ADMIN", "ALCALDE", "OPERADOR"):
        raise HTTPException(403, "Tu rol no permite consolidar comentarios")
    return user
