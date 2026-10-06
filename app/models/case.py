from sqlalchemy import Column, String, Text, DateTime, func
from app.core.database import Base

class Case(Base):
    __tablename__ = "cases"

    id = Column(String(50), primary_key=True, index=True)
    source = Column(String(50), nullable=False)
    author = Column(String(100), nullable=False)
    priority = Column(String(20), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(100), nullable=False, index=True)
    sentiment = Column(String(50), nullable=False)
    location = Column(String(150), nullable=False)
    zone = Column(String(50), default="centro", index=True)
    date_time = Column(String(100), nullable=False)
    status = Column(String(50), default="Pendiente", index=True)
    media_type = Column(String(20), default="none")
    image_url = Column(Text, nullable=True)
    impact_if_solved = Column(Text, nullable=True)
    impact_if_ignored = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

