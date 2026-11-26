from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.services.auth_sessions import require_session


def get_current_user(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> User:
    scheme, _, token = (authorization or '').partition(' ')
    payload = decode_access_token(token) if scheme.lower() == 'bearer' and token else None
    if not payload or not isinstance(payload.get('sub'), str):
        raise HTTPException(401, 'Sesión inválida o vencida. Inicia sesión de nuevo.', headers={'WWW-Authenticate': 'Bearer'})
    user = db.get(User, payload['sub'])
    if not user or not user.is_active:
        raise HTTPException(401, 'La sesión ya no está disponible.', headers={'WWW-Authenticate': 'Bearer'})
    require_session(db, user, payload)
    if user.role not in ('ADMIN', 'ALCALDE', 'SECRETARIO', 'OPERADOR'):
        raise HTTPException(403, 'La cuenta no tiene un rol habilitado.')
    # Read permissions from the current account, never from cached JWT role claims.
    return user
