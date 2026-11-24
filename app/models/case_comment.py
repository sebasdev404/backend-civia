from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON, func
from app.core.database import Base


class CaseComment(Base):
    __tablename__ = "case_comments"
    post_id = Column(String(100), primary_key=True)
    comment_id = Column(String(150), primary_key=True)
    case_id = Column(String(50), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    comment_json = Column(JSON, nullable=False)
    linked_by = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
