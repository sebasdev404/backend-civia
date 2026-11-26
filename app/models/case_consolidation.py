from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON, CheckConstraint, Index, text
from app.core.database import Base


class CaseConsolidation(Base):
    __tablename__ = "case_consolidations"
    id = Column(String(36), primary_key=True)  # client operation ID for safe retries
    primary_case_id = Column(String(50), ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False, index=True)
    duplicate_case_id = Column(String(50), ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    evidence_json = Column(JSON, nullable=False)
    undone_at = Column(DateTime(timezone=True))
    undone_by = Column(String(100))
    undo_reason = Column(Text)
    __table_args__ = (
        CheckConstraint("primary_case_id <> duplicate_case_id", name="ck_consolidation_distinct_cases"),
        Index("uq_active_case_duplicate", "duplicate_case_id", unique=True,
              postgresql_where=text("undone_at IS NULL"), sqlite_where=text("undone_at IS NULL")),
    )
