from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing import Optional, List, Dict, Any, Annotated
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
    user_type: Optional[str] = "Sin clasificar"
    bot_probability: Optional[float] = 0.0
    bot_origin: Optional[str] = None
    total_reports: Optional[int] = 0
    credibility_score: Optional[float] = 0.0
    sentiment_tendency: Optional[str] = "Sin evaluar"
    status: Optional[str] = "Activo"
    notes: Optional[str] = None
    origen_dato: Optional[str] = "BASE_SUBIDA"
    source_data: Optional[Dict[str, Any]] = None

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


class CitizenDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    citizen_ids: List[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]] = Field(min_length=1, max_length=500)
