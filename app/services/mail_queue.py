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


def process_outbox(bind,limit=10):
    from app.services import password_recovery as recovery
    from app.services.email_service import send_password_changed_email
    with Session(bind=bind) as db:
        ids=[row.id for row in db.query(MailOutbox).filter(MailOutbox.status.in_(('queued','retry')),MailOutbox.next_attempt_at<=datetime.now(timezone.utc)).order_by(MailOutbox.created_at).limit(limit)]
    for identity in ids:
        with Session(bind=bind) as db:
            try:
                candidate=db.get(MailOutbox,identity)
                if not candidate:continue
                payload=json.loads(cipher().decrypt(candidate.ciphertext.encode()))
                user=db.query(User).filter_by(email=payload['email']).with_for_update().first()
                row=db.query(MailOutbox).filter_by(id=identity).populate_existing().with_for_update(skip_locked=True).first()
                if not row or row.status not in ('queued','retry'):continue
                now=datetime.now(timezone.utc);row.attempts+=1
                if not user or not user.is_active:
                    row.status='skipped';db.commit();continue
                delivered=False
                if row.kind=='recovery':
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
                    if row.kind=='recovery':user.reset_otp=None;user.reset_otp_expires_at=None
                else:
                    row.status='retry' if row.attempts<5 else 'failed'
                    row.next_attempt_at=now+timedelta(seconds=min(60*2**row.attempts,900))
                    row.error='El proveedor no confirmó la entrega. Se conserva el intento para revisión.'
                db.commit()
            except Exception:
                db.rollback()
                row=db.get(MailOutbox,identity)
                if row:
                    row.status='failed';row.error='No se pudo procesar la entrega. Revisa la configuración privada.';db.commit()
    with Session(bind=bind) as db:
        db.query(MailOutbox).filter(MailOutbox.status.in_(('delivered','superseded','expired','cancelled','skipped')),MailOutbox.created_at<datetime.now(timezone.utc)-timedelta(days=7)).delete(synchronize_session=False)
        db.query(MailOutbox).filter(MailOutbox.created_at<datetime.now(timezone.utc)-timedelta(days=30)).delete(synchronize_session=False)
        db.commit()
