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
    
    # Flujo de Negocio y Despacho
    assigned_department: Optional[str] = None
    assigned_to: Optional[str] = None
    internal_notes: Optional[str] = None
    public_response: Optional[str] = None
    resolution_note: Optional[str] = None
    resolved_by: Optional[str] = None
    priority_action: Optional[bool] = False

class CaseCreate(CaseBase):
    id: Optional[str] = None

class CaseUpdate(BaseModel):
    priority: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    sentiment: Optional[str] = None
    impact_if_solved: Optional[str] = None
    impact_if_ignored: Optional[str] = None
    assigned_department: Optional[str] = None
    assigned_to: Optional[str] = None
    internal_notes: Optional[str] = None
    public_response: Optional[str] = None
    resolution_note: Optional[str] = None
    resolved_by: Optional[str] = None
    priority_action: Optional[bool] = None

class CaseDispatch(BaseModel):
    assigned_department: str
    assigned_to: Optional[str] = None
    note: Optional[str] = None

class CaseNoteCreate(BaseModel):
    note: str
    author_name: str

class CaseResolve(BaseModel):
    resolution_note: str
    resolved_by: str

class CasePublicResponse(BaseModel):
    public_response: str

class CaseResponse(CaseBase):
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

