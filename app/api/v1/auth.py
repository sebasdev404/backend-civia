from fastapi import APIRouter, Depends, HTTPException, status, Header, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, List

from datetime import datetime, timezone
from app.core.database import get_db
from app.core.authentication import get_current_user
from app.models.user import User
from app.models.auth_session import AuthSession
from app.services.auth_sessions import issue_session, revoke_all, fingerprint, utc
from app.schemas.user import (
    UserLogin,
    UserUpdate,
    ChangePasswordRequest,
    UserCreate,
    UserResponse,
    TokenResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    VerifyOtpRequest,
    VerifyOtpResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from app.core.security import verify_password, get_password_hash, decode_access_token
from app.core.auth_limits import check_recovery_limit
from app.services.email_service import smtp_is_configured, send_password_changed_email
from app.services.password_recovery import require_code
from app.services.mail_queue import enqueue,process_outbox,invalidate_recovery_mail

router = APIRouter(prefix="/auth", tags=["Autenticación y Seguridad"])

@router.post("/login", response_model=TokenResponse)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Inicia sesión con correo y contraseña. Retorna token JWT y perfil."""
    email_clean = credentials.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).populate_existing().with_for_update().first()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo electrónico o contraseña incorrectos",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta de usuario ha sido desactivada por la administración",
        )

    token = issue_session(db, user)
    db.commit()

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=user
    )

@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Obtiene el perfil del usuario autenticado actualmente."""
    return current_user

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserCreate, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    """Crea una nueva cuenta de usuario (para administración interna)."""
    email_clean = user_in.email.strip().lower()
    existing = db.query(User).filter(User.email == email_clean).populate_existing().with_for_update().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe una cuenta con el correo '{email_clean}'",
        )

    hashed_pw = get_password_hash(user_in.password)
    new_user = User(
        email=email_clean,
        hashed_password=hashed_pw,
        full_name=user_in.full_name,
        role=user_in.role,
        department=user_in.department,
        avatar_url=user_in.avatar_url,
    )
    db.add(new_user)
    db.flush()
    from app.services.audit import record
    record(db,actor,'user_created',new_user.id,role=new_user.role)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.get("/users", response_model=List[UserResponse])
def get_all_users(db: Session = Depends(get_db)):
    """Retorna la lista de todos los usuarios registrados en el sistema CIVIA."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return users


@router.patch('/users/{user_id}',response_model=UserResponse)
def update_user(user_id:str,payload:UserUpdate,db:Session=Depends(get_db),actor:User=Depends(get_current_user)):
    accounts=db.query(User).order_by(User.id).populate_existing().with_for_update().all()
    account=next((item for item in accounts if item.id==user_id),None)
    if not account:raise HTTPException(404,'Cuenta no encontrada.')
    if account.account_revision!=payload.expected_revision:raise HTTPException(409,'La cuenta cambió. Actualiza el listado antes de modificarla.')
    if not payload.full_name.strip() or len(payload.reason.strip())<20:raise HTTPException(422,'Completa el nombre y el motivo de la modificación.')
    if user_id==actor.id and (payload.role!='ADMIN' or not payload.is_active):raise HTTPException(409,'No puedes retirar tu propio acceso administrativo.')
    if account.role=='ADMIN' and account.is_active and (not payload.is_active or payload.role!='ADMIN') and sum(a.role=='ADMIN' and a.is_active for a in accounts)<=1:
        raise HTTPException(409,'Debe conservarse al menos una cuenta administradora activa.')
    old={key:getattr(account,key) for key in ('role','department','is_active')}
    if account.role!=payload.role or account.is_active!=payload.is_active:revoke_all(db,account.id)
    account.full_name=payload.full_name.strip();account.role=payload.role;account.is_active=payload.is_active;account.department=(payload.department or '').strip() or None
    from app.services.audit import record
    record(db,actor,'user_updated',account.id,before=old,after={key:getattr(account,key) for key in old},reason=payload.reason.strip())
    db.commit();db.refresh(account)
    return account

@router.delete("/users/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(user_id: str, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    """Elimina una cuenta de usuario por su ID."""
    if user_id == actor.id:
        raise HTTPException(409, 'No puedes eliminar tu propia cuenta.')
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    db.delete(user)
    from app.services.audit import record
    record(db,actor,'user_deleted',user_id)
    db.commit()
    return {"message": f"Usuario {user.email} eliminado exitosamente"}

@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(req: ForgotPasswordRequest, background: BackgroundTasks, db: Session = Depends(get_db)):
    """Accept a request without exposing account existence or SMTP delivery time."""
    email_clean = req.email.strip().lower()
    if not smtp_is_configured():
        raise HTTPException(503, 'La recuperación por correo no está disponible. Contacta al administrador.')
    check_recovery_limit(db, email_clean, sending=True)
    enqueue(db,email_clean)
    db.commit()
    background.add_task(process_outbox,db.get_bind())
    return ForgotPasswordResponse(
        message='Si el correo corresponde a una cuenta activa, recibirás un código. Revisa también spam; si no llega, contacta al administrador.',
        email=email_clean,
    )

@router.post("/verify-otp", response_model=VerifyOtpResponse)
def verify_otp(req: VerifyOtpRequest, db: Session = Depends(get_db)):
    email_clean = req.email.strip().lower()
    check_recovery_limit(db, email_clean, sending=False)
    require_code(db, email_clean, req.otp_code)
    return VerifyOtpResponse(
        message="Código de verificación confirmado exitosamente.",
        valid=True
    )

@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(req: ResetPasswordRequest, background: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Valida el código OTP y actualiza la contraseña del usuario en la base de datos.
    Limpia el OTP y genera un token JWT para iniciar sesión inmediatamente.
    """
    email_clean = req.email.strip().lower()
    check_recovery_limit(db, email_clean, sending=False)
    user, recovery = require_code(db, email_clean, req.otp_code)
    user.hashed_password = get_password_hash(req.new_password)
    recovery.used_at = datetime.now(timezone.utc)
    user.reset_otp = None
    user.reset_otp_expires_at = None
    invalidate_recovery_mail(db,user.email)
    enqueue(db,user.email,'password_changed')
    revoke_all(db, user.id)
    access_token = issue_session(db, user)
    db.commit()
    db.refresh(user)
    background.add_task(process_outbox,db.get_bind())

    return ResetPasswordResponse(
        message="¡Tu contraseña ha sido restablecida con éxito! Ingresando a CIVIA...",
        access_token=access_token,
        token_type="bearer",
        user=user
    )


@router.post('/logout')
def logout(authorization: str = Header(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    payload = decode_access_token(authorization.partition(' ')[2])
    if not payload:
        raise HTTPException(401, 'La sesi\u00f3n ya no est\u00e1 vigente.')
    session = db.query(AuthSession).filter_by(id=payload['jti'], user_id=user.id).with_for_update().one()
    session.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {'message': 'Sesi\u00f3n cerrada.'}


@router.post('/logout-all')
def logout_all(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.query(User).filter_by(id=user.id).populate_existing().with_for_update().one()
    revoke_all(db, user.id)
    db.commit()
    return {'message': 'Todas tus sesiones fueron cerradas.'}


@router.post('/change-password', response_model=TokenResponse)
def change_password(payload: ChangePasswordRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    account = db.query(User).filter_by(id=user.id).populate_existing().with_for_update().one()
    if not verify_password(payload.current_password, account.hashed_password):
        raise HTTPException(400, 'La contrase\u00f1a actual no es correcta.')
    if payload.current_password == payload.new_password:
        raise HTTPException(422, 'Elige una contrase\u00f1a diferente de la actual.')
    account.hashed_password = get_password_hash(payload.new_password)
    account.reset_otp = None
    account.reset_otp_expires_at = None
    invalidate_recovery_mail(db,account.email)
    revoke_all(db, account.id)
    token = issue_session(db, account)
    db.commit()
    db.refresh(account)
    return TokenResponse(access_token=token, user=account)


@router.get('/sessions')
def list_sessions(authorization: str = Header(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    payload = decode_access_token(authorization.partition(' ')[2])
    if not payload:
        raise HTTPException(401, 'La sesi\u00f3n ya no est\u00e1 vigente.')
    current = payload['jti']
    rows = db.query(AuthSession).filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None),
        AuthSession.expires_at > datetime.now(timezone.utc), AuthSession.credential_fingerprint == fingerprint(user)).order_by(AuthSession.created_at.desc()).all()
    return [{'created_at': utc(row.created_at), 'expires_at': utc(row.expires_at), 'is_current': row.id == current} for row in rows]
