"""Atomic limits shared by API workers through PostgreSQL (SQLite in fixtures).

Only keyed digests are stored, never email addresses or IPs. Public proxy limits
by the original client IP remain a deployment responsibility: do not trust an
arbitrary X-Forwarded-For supplied by a caller.
"""
import hashlib
import hmac
import re
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import case, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.core.config import settings
from app.models.password_recovery import AuthRateLimit
from app.services.auth_sessions import utc


def client_identity(request,path):
    secret=settings.BFF_PROXY_SECRET
    identity=request.headers.get('x-civia-client','')
    timestamp=request.headers.get('x-civia-client-time','')
    signature=request.headers.get('x-civia-client-signature','')
    if secret and re.fullmatch('[0-9a-f]{64}',identity) and timestamp.isdigit() and len(timestamp)<=12 and abs(datetime.now(timezone.utc).timestamp()-int(timestamp))<=60:
        data=f'{request.method}\n{path}\n{timestamp}\n{identity}'
        expected=hmac.new(secret.encode(),data.encode(),hashlib.sha256).hexdigest()
        if re.fullmatch('[0-9a-f]{64}',signature) and hmac.compare_digest(expected,signature):return 'proxy:'+identity
    return request.client.host if request.client else 'unknown'


def _consume(db, scope, identity, limit, window):
    now = datetime.now(timezone.utc)
    digest = hmac.new(settings.SECRET_KEY.encode(), f'auth-limit:v1:{scope}:{identity}'.encode(), hashlib.sha256).hexdigest()
    table = AuthRateLimit.__table__
    insert = sqlite_insert if db.get_bind().dialect.name == 'sqlite' else pg_insert
    statement = insert(table).values(key_hash=digest, attempts=1, reset_at=now + timedelta(seconds=window))
    expired = table.c.reset_at <= now
    statement = statement.on_conflict_do_update(index_elements=[table.c.key_hash], set_={
        'attempts': case((expired, 1), (table.c.attempts < limit + 1, table.c.attempts + 1), else_=limit + 1),
        'reset_at': case((expired, now + timedelta(seconds=window)), else_=table.c.reset_at),
    }).returning(table.c.attempts, table.c.reset_at)
    attempts, reset_at = db.execute(statement).one()
    # Bounded cleanup; expired counters have no authentication value.
    old_keys = select(table.c.key_hash).where(table.c.reset_at < now - timedelta(days=1)).limit(100)
    db.execute(delete(table).where(table.c.key_hash.in_(old_keys)))
    db.commit()  # Rejected attempts must survive request rollback and worker restarts.
    if attempts > limit:
        retry = max(1, int((utc(reset_at) - now).total_seconds()) + 1)
        raise HTTPException(429, 'Demasiados intentos. Espera antes de volver a intentar.', headers={'Retry-After': str(retry)})


def check_auth_limit(db, host: str, path: str):
    limit, window = (30, 60) if path == '/auth/login' else (5, 900) if path == '/auth/forgot-password' else (10, 900)
    scope = '/auth/recovery-code' if path in ('/auth/verify-otp', '/auth/reset-password') else path
    _consume(db, 'connection:' + scope, host, limit, window)


def check_recovery_limit(db, email: str, *, sending: bool):
    _consume(db, 'recovery:send' if sending else 'recovery:check', email, 5 if sending else 10, 900)
