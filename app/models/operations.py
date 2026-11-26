import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, JSON, Integer, Index
from app.core.database import Base


class AuditEvent(Base):
    __tablename__='audit_events'
    id=Column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    actor_id=Column(String,nullable=False)
    actor_name=Column(String,nullable=False)
    action=Column(String(80),nullable=False,index=True)
    target_id=Column(String(160),nullable=True,index=True)
    details=Column(JSON,nullable=False,default=dict)
    created_at=Column(DateTime(timezone=True),nullable=False,default=lambda:datetime.now(timezone.utc),index=True)


class SystemSetting(Base):
    __tablename__='system_settings'
    key=Column(String(80),primary_key=True)
    value=Column(JSON,nullable=False)
    updated_by=Column(String,nullable=False)
    updated_at=Column(DateTime(timezone=True),nullable=False,default=lambda:datetime.now(timezone.utc),onupdate=lambda:datetime.now(timezone.utc))


class WebhookEvent(Base):
    __tablename__='webhook_events'
    id=Column(String(64),primary_key=True)
    payload=Column(JSON,nullable=False)
    status=Column(String(30),nullable=False,default='queued')
    attempts=Column(Integer,nullable=False,default=0)
    error=Column(Text,nullable=True)
    received_at=Column(DateTime(timezone=True),nullable=False,default=lambda:datetime.now(timezone.utc))
    processed_at=Column(DateTime(timezone=True),nullable=True)
    last_attempt_at=Column(DateTime(timezone=True),nullable=True)
    __table_args__=(Index('ix_webhook_events_status_received','status','received_at'),)


class MailOutbox(Base):
    __tablename__='mail_outbox'
    id=Column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    recipient_key=Column(String(64),nullable=False,index=True)
    kind=Column(String(30),nullable=False)
    ciphertext=Column(Text,nullable=False)
    status=Column(String(30),nullable=False,default='queued')
    attempts=Column(Integer,nullable=False,default=0)
    created_at=Column(DateTime(timezone=True),nullable=False,default=lambda:datetime.now(timezone.utc))
    next_attempt_at=Column(DateTime(timezone=True),nullable=False,default=lambda:datetime.now(timezone.utc))
    delivered_at=Column(DateTime(timezone=True),nullable=True)
    error=Column(Text,nullable=True)
