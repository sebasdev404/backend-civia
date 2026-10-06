from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class CaseBase(BaseModel):
    source: str
    author: str
    priority: str
    title: str
    content: str
    category: str
    sentiment: str
    location: str
    zone: Optional[str] = "centro"
    date_time: Optional[str] = "Hace unos minutos"
    status: Optional[str] = "Pendiente"
    media_type: Optional[str] = "none"
    image_url: Optional[str] = None
    impact_if_solved: Optional[str] = None
    impact_if_ignored: Optional[str] = None

class CaseCreate(CaseBase):
    id: Optional[str] = None

class CaseUpdate(BaseModel):
    priority: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    sentiment: Optional[str] = None
    impact_if_solved: Optional[str] = None
    impact_if_ignored: Optional[str] = None

class CaseResponse(CaseBase):
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

