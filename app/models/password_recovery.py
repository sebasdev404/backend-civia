from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index
from app.core.database import Base


class PasswordRecovery(Base):
    __tablename__ = 'password_recoveries'
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    nonce = Column(String(36), nullable=False)
    code_digest = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    failed_attempts = Column(Integer, nullable=False, default=0)
    used_at = Column(DateTime(timezone=True), nullable=True)


class AuthRateLimit(Base):
    __tablename__ = 'auth_rate_limits'
    key_hash = Column(String(64), primary_key=True)
    attempts = Column(Integer, nullable=False)
    reset_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (Index('ix_auth_rate_limits_reset_at', 'reset_at'),)
