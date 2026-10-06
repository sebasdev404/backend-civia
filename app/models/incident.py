from sqlalchemy import Column, String, Text, Float, Integer, Boolean, DateTime, func
from app.core.database import Base

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String(50), primary_key=True, index=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=False, index=True)
    priority = Column(String(20), nullable=False, index=True)
    sentiment = Column(String(50), nullable=False)
    source = Column(String(50), nullable=False)
    neighborhood = Column(String(150), nullable=False)
    zone = Column(String(50), nullable=False, index=True)
    status = Column(String(50), default="Pendiente", index=True)
    reports_count = Column(Integer, default=1)
    date_time = Column(String(100), nullable=False)
    is_new = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

