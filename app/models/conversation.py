"""Contexto editorial y análisis independientes de las capturas renovadas de Meta."""
from sqlalchemy import Column, DateTime, String, Text, func
from app.core.database import Base


class PostContext(Base):
    __tablename__ = "post_contexts"
    post_id = Column(String(100), primary_key=True)
    summary = Column(Text, nullable=False, default="")
    transcript = Column(Text, nullable=False, default="")
    updated_by = Column(String(100), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CommentAnalysis(Base):
    __tablename__ = "comment_analyses"
    post_id = Column(String(100), primary_key=True)
    comment_id = Column(String(150), primary_key=True)
    fingerprint = Column(String(64), nullable=False)
    result_json = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
