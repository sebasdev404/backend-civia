import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from app.core.config import settings
from app.core.security import create_access_token
from app.models.auth_session import AuthSession


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def fingerprint(user):
    return hashlib.sha256(user.hashed_password.encode()).hexdigest()


def issue_session(db, user):
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    sid = str(uuid.uuid4())
    db.add(AuthSession(id=sid, user_id=user.id, credential_fingerprint=fingerprint(user), created_at=now, expires_at=expires))
    token = create_access_token({'sub': user.id, 'jti': sid}, expires - now)
    return token


def require_session(db, user, payload):
    sid = payload.get('jti')
    session = db.get(AuthSession, sid) if isinstance(sid, str) and len(sid) == 36 else None
    if (not session or session.user_id != user.id or session.revoked_at is not None
            or utc(session.expires_at) <= datetime.now(timezone.utc)
            or not hmac.compare_digest(session.credential_fingerprint, fingerprint(user))):
        raise HTTPException(401, 'La sesión terminó. Inicia sesión de nuevo.', headers={'WWW-Authenticate': 'Bearer'})
    return session


def revoke_all(db, user_id):
    db.query(AuthSession).filter_by(user_id=user_id, revoked_at=None).update(
        {AuthSession.revoked_at: datetime.now(timezone.utc)}, synchronize_session='fetch')
