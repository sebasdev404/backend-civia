"""Default-deny API policy. Public entry points are listed explicitly."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.core.authentication import get_current_user
from app.core.database import get_db
from app.core.auth_limits import check_auth_limit,client_identity

PUBLIC = {
    ('POST', '/auth/login'), ('POST', '/auth/forgot-password'),
    ('POST', '/auth/verify-otp'), ('POST', '/auth/reset-password'),
    ('GET', '/meta/webhook'), ('POST', '/meta/webhook'),
    # These proxies return only public social-post images, also used by <img>.
    ('GET', '/meta/post-thumbnail/{post_id}'), ('GET', '/meta/post-image/{post_id}'),
}


def require_api_access(request: Request, db: Session = Depends(get_db)):
    path = request.scope['route'].path.removeprefix('/api/v1')
    method = request.method
    if (method, path) in PUBLIC:
        if path.startswith('/auth/'):
            check_auth_limit(db, client_identity(request,path), path)
        return
    user = get_current_user(request.headers.get('authorization'), db)
    request.state.user = user
    if path == '/auth/change-password':
        check_auth_limit(db, client_identity(request,path), path)
    if path.startswith('/seed') or path == '/meta/simulate-comment':
        raise HTTPException(410, 'La carga de demostración está deshabilitada.')
    if path in ('/auth/logout', '/auth/logout-all', '/auth/change-password'):
        return user
    if path.startswith(('/auth/users', '/auth/register', '/system/')) or path in ('/ai/credits', '/ai/sync-balance'):
        allowed = ('ADMIN',)
    elif method in ('GET', 'HEAD'):
        return user
    elif path.startswith('/case-consolidations') or path.startswith('/case-corrections'):
        # Their endpoint dependencies apply the existing decision-role policy.
        return user
    elif path.startswith('/cases'):
        if method == 'DELETE':
            allowed = ('ADMIN',)
        elif path.endswith('/priority-action'):
            allowed = ('ADMIN', 'ALCALDE')
        elif path.endswith(('/notes', '/public-response')) or (path == '/cases' and method == 'POST'):
            allowed = ('ADMIN', 'SECRETARIO', 'OPERADOR')
        else:
            allowed = ('ADMIN', 'SECRETARIO')
    elif path.startswith('/citizens'):
        allowed = ('ADMIN', 'SECRETARIO', 'OPERADOR') if path.endswith('/reply') else ('ADMIN', 'ALCALDE')
    elif path.startswith('/map'):
        allowed = ('ADMIN', 'SECRETARIO')
    elif path.startswith('/triage'):
        allowed = ('ADMIN', 'ALCALDE', 'OPERADOR')
    elif path.startswith(('/meta/', '/publications', '/conversation', '/ai/')):
        allowed = ('ADMIN', 'ALCALDE', 'SECRETARIO', 'OPERADOR')
    else:
        # New write endpoints need an explicit decision before other roles can use them.
        allowed = ('ADMIN',)
    if user.role not in allowed:
        raise HTTPException(403, 'Tu rol no permite realizar esta acción.')
    return user
