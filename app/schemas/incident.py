from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class IncidentBase(BaseModel):
    lat: float
    lng: float
    title: str
    description: str
    category: str
    priority: str
    sentiment: str
    source: str
    neighborhood: str
    zone: str
    status: Optional[str] = "Pendiente"
    reports_count: Optional[int] = 1
    date_time: Optional[str] = "Justo ahora"
    is_new: Optional[bool] = False

class IncidentCreate(IncidentBase):
    id: Optional[str] = None

class IncidentResponse(IncidentBase):
    id: str
    created_at: Optional[datetime] = None
    location_precision: Optional[str] = None
    evidence_text: Optional[str] = None
    verification_status: Optional[str] = None
    source_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

