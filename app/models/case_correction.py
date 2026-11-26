from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON, Index, text
from app.core.database import Base


class CaseCorrection(Base):
    __tablename__ = "case_corrections"
    id = Column(String(36), primary_key=True)
    case_id = Column(String(50), ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False, index=True)
    disposition = Column(String(40), nullable=False)
    reason = Column(Text, nullable=False)
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    evidence_json = Column(JSON, nullable=False)
    undone_at = Column(DateTime(timezone=True))
    undone_by = Column(String(100))
    undo_reason = Column(Text)
    __table_args__ = (Index("uq_active_case_correction", "case_id", unique=True,
        postgresql_where=text("undone_at IS NULL"), sqlite_where=text("undone_at IS NULL")),)
