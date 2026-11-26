"""One current, expiring recovery code per account; no plaintext code in storage."""
import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.user import User
from app.models.password_recovery import PasswordRecovery
from app.services.auth_sessions import fingerprint, utc
from app.services.email_service import generate_otp_code, send_otp_email

logger = logging.getLogger('civia.recovery')
INVALID_CODE = 'El código no es válido o ya no está disponible. Solicita uno nuevo si es necesario.'


def _digest(user, nonce, code):
    data = f'recovery:v1:{user.id}:{fingerprint(user)}:{nonce}:{code}'.encode()
    return hmac.new(settings.SECRET_KEY.encode(), data, hashlib.sha256).hexdigest()


def prepare_recovery(db, user, code):
    """Caller holds the account lock and commits only after SMTP accepts delivery."""
    now = datetime.now(timezone.utc)
    row = db.get(PasswordRecovery, user.id)
    if row is None:
        row = PasswordRecovery(user_id=user.id)
        db.add(row)
    row.nonce = str(uuid.uuid4())
    row.code_digest = _digest(user, row.nonce, code)
    row.created_at = now
    row.expires_at = now + timedelta(minutes=15)
    row.failed_attempts = 0
    row.used_at = None
    return row


def deliver_recovery(bind, email):
    # Runs after the generic HTTP response, so SMTP and account lookup cannot
    # make the response identify whether an account exists. No real mail in QA.
    try:
        with Session(bind=bind) as db:
            user = db.query(User).filter_by(email=email).with_for_update().first()
            if not user or not user.is_active:
                return
            code = generate_otp_code()
            prepare_recovery(db, user, code)
            if not send_otp_email(user.email, user.full_name, code):
                db.rollback()
                return
            user.reset_otp = None  # Obsolete fields are never accepted as evidence.
            user.reset_otp_expires_at = None
            db.commit()
    except Exception:
        # Never include recipient, code, SQL parameters, or provider response.
        logger.error('No se pudo completar una solicitud de recuperacion.')


def require_code(db, email, code):
    # Same lock order as sending/changing a password: account, then challenge.
    user = db.query(User).filter_by(email=email).populate_existing().with_for_update().first()
    row = db.query(PasswordRecovery).filter_by(user_id=user.id).populate_existing().with_for_update().first() if user else None
    candidate = _digest(user, row.nonce, code) if user and row else '0' * 64
    matches = hmac.compare_digest(candidate, row.code_digest if row else '1' * 64)
    valid = (user and user.is_active and row and not row.used_at and row.failed_attempts < 5
             and utc(row.expires_at) > datetime.now(timezone.utc))
    if not valid or not matches:
        if valid:
            row.failed_attempts += 1
            db.commit()
        raise HTTPException(400, INVALID_CODE)
    return user, row
