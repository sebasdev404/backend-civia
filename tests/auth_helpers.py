"""Registered sessions for disposable SQLite fixtures only."""
from app.models.user import User
from app.services.auth_sessions import issue_session
from app.core.security import create_access_token, decode_access_token


def prime_sessions(db):
    if db.get_bind().dialect.name != 'sqlite':
        raise RuntimeError('Session fixtures require isolated SQLite')
    tokens = {user.id: issue_session(db, user) for user in db.query(User).all()}
    db.commit()
    db.info['fixture_session_tokens'] = tokens


def fixture_token(db, user_id, **claims):
    token = db.info['fixture_session_tokens'][user_id]
    if not claims: return token
    return create_access_token({**decode_access_token(token), **claims})
