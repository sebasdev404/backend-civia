from sqlalchemy import Column, String, Integer, Float, DateTime, func
from app.core.database import Base

class Citizen(Base):
    __tablename__ = "citizens"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    handle = Column(String(100), nullable=False, unique=True, index=True)
    avatar = Column(String(10), nullable=True)
    channel = Column(String(50), nullable=False)
    zone = Column(String(100), nullable=False)
    total_reports = Column(Integer, default=1)
    credibility_score = Column(Float, default=85.0)
    sentiment_tendency = Column(String(50), default="Crítico")
    status = Column(String(50), default="Activo")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

