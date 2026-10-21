from sqlalchemy import Column, String, Integer, Float, Text, DateTime, func
from app.core.database import Base

class Citizen(Base):
    __tablename__ = "citizens"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    handle = Column(String(100), nullable=False, unique=True, index=True)
    avatar = Column(String(255), nullable=True)
    channel = Column(String(50), default="Facebook")  # "Facebook", "Instagram", "WhatsApp", "Base de Datos"
    zone = Column(String(100), default="Neiva (General)")
    neighborhood = Column(String(150), nullable=True)
    phone = Column(String(50), nullable=True, index=True)
    followers_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)
    account_created_at = Column(String(100), nullable=True)
    user_type = Column(String(50), default="Negativo")  # "Positivo", "Negativo", "Bot"
    bot_probability = Column(Float, default=0.0)
    bot_origin = Column(String(150), nullable=True)  # "Granja de Cuentas / Campaña Opositora", "Perfil Falso Sin Foto", "Automatizado Spam", "Humano Verificado"
    total_reports = Column(Integer, default=1)
    credibility_score = Column(Float, default=85.0)
    sentiment_tendency = Column(String(50), default="Crítico")
    status = Column(String(50), default="Activo")
    notes = Column(Text, nullable=True)
    origen_dato = Column(String(50), default="BASE_SUBIDA")  # "BASE_SUBIDA", "META_COMMENT", "OPERADOR", "FORMULARIO"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
