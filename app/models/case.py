from sqlalchemy import Column, String, Text, Boolean, DateTime, Integer, func
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

    # Campos de Flujo de Negocio y Despacho
    assigned_department = Column(String(100), nullable=True)  # Ej: Las Ceibas E.S.P., Sec. Infraestructura
    assigned_to = Column(String(100), nullable=True)          # Cuadrilla o funcionario asignado
    internal_notes = Column(Text, nullable=True)              # Bitácora interna de seguimiento
    public_response = Column(Text, nullable=True)             # Respuesta oficial para redes sociales
    resolution_note = Column(Text, nullable=True)             # Nota de cierre técnico
    resolved_by = Column(String(100), nullable=True)          # Usuario / Secretario que resolvió
    priority_action = Column(Boolean, default=False)          # Declaratoria de prioridad inmediata por el Alcalde
    institutional_radicado = Column(String(100), nullable=True) # Radicado oficial del sistema de correspondencia
    requires_followup = Column(Boolean, default=False)        # Necesidad probable de seguimiento
    comments_count = Column(Integer, default=1)               # Cantidad de comentarios agrupados

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

