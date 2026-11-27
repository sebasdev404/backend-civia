"""Encrypted durable mail queue. Lock order: account then outbox then challenge."""
import base64
import hashlib
import hmac
import json
from datetime import datetime,timezone,timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.operations import MailOutbox
from app.models.user import User
from app.models.password_recovery import PasswordRecovery
from app.services.auth_sessions import utc


def cipher():
    key=HKDF(algorithm=hashes.SHA256(),length=32,salt=None,info=b'civia-mail-outbox-v1').derive(settings.SECRET_KEY.encode())
    return Fernet(base64.urlsafe_b64encode(key))


def recipient_key(email):
    return hmac.new(settings.SECRET_KEY.encode(),('mail:'+email.strip().lower()).encode(),hashlib.sha256).hexdigest()


def enqueue(db,email,kind='recovery'):
    from app.services import password_recovery as recovery
    payload={'email':email}
    if kind=='recovery':payload['code']=recovery.generate_otp_code()
    row=MailOutbox(recipient_key=recipient_key(email),kind=kind,ciphertext=cipher().encrypt(json.dumps(payload).encode()).decode(),status='queued')
    db.add(row)
    return row


def invalidate_recovery_mail(db,email):
    db.query(MailOutbox).filter(MailOutbox.recipient_key==recipient_key(email),MailOutbox.kind=='recovery',MailOutbox.status.in_(('queued','retry'))).update({'status':'cancelled'},synchronize_session='fetch')


def enqueue_welcome(db, user, password):
    base = settings.PUBLIC_APP_URL.strip() or settings.BACKEND_CORS_ORIGINS[0]
    payload = {'email': user.email, 'user_id': user.id, 'password': password, 'login_url': base.rstrip('/') + '/login'}
    row = MailOutbox(recipient_key=recipient_key(user.email), kind='welcome',
        ciphertext=cipher().encrypt(json.dumps(payload).encode()).decode(), status='queued')
    db.add(row)
    return row


def welcome_statuses(db, users):
    """Admin-visible state only; never decrypt or return invitation credentials."""
    if not users:
        return {}
    keys = {recipient_key(user.email): user for user in users}
    latest = {}
    for row in db.query(MailOutbox).filter(MailOutbox.kind == 'welcome', MailOutbox.recipient_key.in_(keys)).order_by(MailOutbox.created_at.desc(), MailOutbox.id):
        user = keys[row.recipient_key]
        if user.id not in latest and utc(row.created_at) >= utc(user.created_at):
            latest[user.id] = row.status
    return latest


def welcome_detail(status):
    return {
        'queued': 'Correo de bienvenida en cola de envío.',
        'retry': 'Correo de bienvenida pendiente; se reintentará automáticamente.',
        'delivered': 'Correo de bienvenida aceptado por el servidor de correo. No confirma lectura ni recepción en la bandeja de entrada.',
        'failed': 'No se pudo enviar la bienvenida. Revisa el servicio de correo; la cuenta está creada.',
        'expired': 'El envío de bienvenida venció; contacta al administrador para recuperar el acceso.',
        'superseded': 'Bienvenida cancelada porque las credenciales o la cuenta cambiaron.',
        'skipped': 'Bienvenida cancelada porque la cuenta no está disponible o está inactiva.',
    }.get(status)


def process_outbox(bind,limit=10):
    from app.services import password_recovery as recovery
    from app.services.email_service import send_password_changed_email, send_welcome_email
    from app.core.security import verify_password
    with Session(bind=bind) as db:
        ids=[row.id for row in db.query(MailOutbox).filter(MailOutbox.status.in_(('queued','retry')),MailOutbox.next_attempt_at<=datetime.now(timezone.utc)).order_by(MailOutbox.created_at).limit(limit)]
    for identity in ids:
        with Session(bind=bind) as db:
            try:
                candidate=db.get(MailOutbox,identity)
                if not candidate or candidate.status not in ('queued','retry'):continue
                payload=json.loads(cipher().decrypt(candidate.ciphertext.encode()))
                user=db.query(User).filter_by(email=payload['email']).with_for_update().first()
                row=db.query(MailOutbox).filter_by(id=identity).populate_existing().with_for_update(skip_locked=True).first()
                if not row or row.status not in ('queued','retry'):continue
                now=datetime.now(timezone.utc);row.attempts+=1
                if not user or not user.is_active:
                    if row.kind == 'welcome': row.ciphertext = ''
                    row.status='skipped';db.commit();continue
                delivered=False
                if row.kind == 'welcome':
                    if utc(row.created_at) + timedelta(hours=24) <= now:
                        row.status = 'expired'; row.ciphertext = ''; db.commit(); continue
                    if user.id != payload.get('user_id') or not verify_password(payload.get('password', ''), user.hashed_password):
                        row.status = 'superseded'; row.ciphertext = ''; db.commit(); continue
                    delivered = send_welcome_email(user.email, user.full_name, payload['password'], user.role, payload['login_url'])
                elif row.kind=='recovery':
                    if utc(row.created_at)+timedelta(minutes=15)<=now:
                        row.status='expired';db.commit();continue
                    current=db.get(PasswordRecovery,user.id)
                    if current and utc(current.created_at)>=utc(row.created_at):
                        same=hmac.compare_digest(current.code_digest,recovery._digest(user,current.nonce,payload['code']))
                        row.status='delivered' if same else 'superseded';db.commit();continue
                    # SMTP failure rolls back the candidate code and keeps the old one.
                    with db.begin_nested() as transaction:
                        challenge=recovery.prepare_recovery(db,user,payload['code'])
                        challenge.created_at=utc(row.created_at);challenge.expires_at=utc(row.created_at)+timedelta(minutes=15)
                        delivered=recovery.send_otp_email(user.email,user.full_name,payload['code'])
                        if not delivered:transaction.rollback()
                else:delivered=send_password_changed_email(user.email,user.full_name)
                if delivered:
                    row.status='delivered';row.delivered_at=now;row.error=None
                    if row.kind == 'welcome': row.ciphertext = ''
                    if row.kind=='recovery':user.reset_otp=None;user.reset_otp_expires_at=None
                else:
                    row.status='retry' if row.attempts<5 else 'failed'
                    if row.kind == 'welcome' and row.status == 'failed': row.ciphertext = ''
                    row.next_attempt_at=now+timedelta(seconds=min(60*2**row.attempts,900))
                    row.error='El proveedor no confirmó la entrega. Se conserva el intento para revisión.'
                db.commit()
            except Exception:
                db.rollback()
                row=db.get(MailOutbox,identity)
                if row and row.status in ('queued', 'retry'):
                    if row.kind == 'welcome': row.ciphertext = ''
                    row.status='failed';row.error='No se pudo procesar la entrega. Revisa la configuración privada.';db.commit()
    with Session(bind=bind) as db:
        db.query(MailOutbox).filter(MailOutbox.status.in_(('delivered','superseded','expired','cancelled','skipped')),MailOutbox.created_at<datetime.now(timezone.utc)-timedelta(days=7)).delete(synchronize_session=False)
        db.query(MailOutbox).filter(MailOutbox.created_at<datetime.now(timezone.utc)-timedelta(days=30)).delete(synchronize_session=False)
        db.commit()
