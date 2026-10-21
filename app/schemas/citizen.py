from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class CitizenBase(BaseModel):
    name: str
    handle: str
    avatar: Optional[str] = None
    channel: Optional[str] = "Facebook"
    zone: Optional[str] = "Neiva (General)"
    neighborhood: Optional[str] = None
    phone: Optional[str] = None
    followers_count: Optional[int] = 0
    following_count: Optional[int] = 0
    account_created_at: Optional[str] = None
    user_type: Optional[str] = "Negativo"  # "Positivo", "Negativo", "Bot"
    bot_probability: Optional[float] = 0.0
    bot_origin: Optional[str] = None
    total_reports: Optional[int] = 1
    credibility_score: Optional[float] = 85.0
    sentiment_tendency: Optional[str] = "Crítico"
    status: Optional[str] = "Activo"
    notes: Optional[str] = None
    origen_dato: Optional[str] = "BASE_SUBIDA"

class CitizenCreate(CitizenBase):
    id: Optional[str] = None

class CitizenResponse(CitizenBase):
    id: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class CitizenUploadItem(BaseModel):
    name: str
    phone: Optional[str] = None
    neighborhood: Optional[str] = None
    handle: Optional[str] = None
    notes: Optional[str] = None
    user_type: Optional[str] = None

class CitizenUploadRequest(BaseModel):
    citizens: List[CitizenUploadItem]
    source_tag: Optional[str] = "Base_Importada_CSV"
