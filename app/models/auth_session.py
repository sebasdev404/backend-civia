from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from app.core.database import Base


class AuthSession(Base):
    __tablename__ = 'auth_sessions'
    id = Column(String(36), primary_key=True)
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    credential_fingerprint = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    __table_args__ = (Index('ix_auth_sessions_user_expires', 'user_id', 'expires_at'),)
