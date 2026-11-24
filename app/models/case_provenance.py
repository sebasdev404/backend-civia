from sqlalchemy import Column, String, JSON, DateTime, ForeignKey, func
from app.core.database import Base


class CaseProvenanceReview(Base):
    __tablename__ = "case_provenance_reviews"
    case_id = Column(String(50), ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True)
    batch = Column(String(80), nullable=False, index=True)
    status = Column(String(40), nullable=False)
    reason = Column(String(80), nullable=False)
    evidence_json = Column(JSON, nullable=False)
    reviewed_by = Column(String(100), nullable=False)
    checked_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
