from sqlalchemy import Column, String, Boolean, DateTime
from datetime import datetime
import uuid

from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, nullable=False, default="OPERADOR")  # "ADMIN", "ALCALDE", "SECRETARIO", "OPERADOR"
    department = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    reset_otp = Column(String(10), nullable=True)
    reset_otp_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def account_revision(self):
        import hashlib,json
        values={key:str(getattr(self,key,None)) for key in ('id','email','full_name','role','department','is_active','updated_at')}
        return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()
