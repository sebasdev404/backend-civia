from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class CitizenBase(BaseModel):
    name: str
    handle: str
    avatar: Optional[str] = None
    channel: str
    zone: str
    total_reports: Optional[int] = 1
    credibility_score: Optional[float] = 85.0
    sentiment_tendency: Optional[str] = "Crítico"
    status: Optional[str] = "Activo"

class CitizenCreate(CitizenBase):
    id: Optional[str] = None

class CitizenResponse(CitizenBase):
    id: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

