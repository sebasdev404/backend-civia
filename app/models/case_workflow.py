import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON, func, Index
from app.core.database import Base


class CaseWorkflowEvent(Base):
    __tablename__ = 'case_workflow_events'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(50), ForeignKey('cases.id', ondelete='RESTRICT'), nullable=False)
    event_type = Column(String(40), nullable=False)
    actor_id = Column(String, nullable=False)
    actor_name = Column(String, nullable=False)
    note = Column(Text, nullable=False)
    evidence_reference = Column(Text, nullable=True)
    before_state = Column(JSON, nullable=False)
    after_state = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False)
    __table_args__ = (Index('ix_case_workflow_events_case_created', 'case_id', 'created_at', 'id'),)
