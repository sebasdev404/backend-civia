import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Date, DateTime, ForeignKey, Index
from app.core.database import Base


class CaseRegistration(Base):
    __tablename__ = 'case_registrations'
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(50), ForeignKey('cases.id', ondelete='RESTRICT'), nullable=False)
    number = Column(String(100), nullable=False)
    institution = Column(String(160), nullable=False)
    issued_on = Column(Date, nullable=False)
    evidence_reference = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    actor_id = Column(String, nullable=False)
    actor_name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_by = Column(String, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    __table_args__ = (Index('ix_case_registrations_case_created', 'case_id', 'created_at'),)
