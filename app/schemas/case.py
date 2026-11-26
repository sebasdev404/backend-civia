from pydantic import BaseModel, ConfigDict, Field, StrictBool
from typing import Optional, Union, Dict, Any, List
from datetime import datetime, date

class CaseBase(BaseModel):
    source: str
    author: str
    priority: str
    title: str
    content: str
    category: str
    sentiment: str
    location: str
    zone: Optional[str] = None
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
    institutional_radicado: Optional[str] = None
    requires_followup: Optional[bool] = False
    comments_count: Optional[Union[int, str]] = 1

class CaseCreate(CaseBase):
    id: Optional[str] = Field(default=None, min_length=1, max_length=50)
    zone: Optional[str] = Field(default=None, max_length=50)
    date_time: Optional[str] = Field(default=None, max_length=100)
    model_config = ConfigDict(extra='forbid')

class CaseAction(BaseModel):
    expected_revision: Optional[str] = Field(default=None, min_length=64, max_length=64)
    model_config = ConfigDict(extra='forbid')

class CaseUpdate(CaseAction):
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
    institutional_radicado: Optional[str] = None
    requires_followup: Optional[bool] = None
    comments_count: Optional[Union[int, str]] = None

class CaseDispatch(CaseAction):
    assigned_department: str
    assigned_to: Optional[str] = None
    note: Optional[str] = None
    confirmed_review: StrictBool = False

class CaseNoteCreate(CaseAction):
    note: str
    author_name: Optional[str] = None  # Kept for old clients; actor is always the signed-in account.

class CaseResolve(CaseAction):
    resolution_note: str
    resolved_by: Optional[str] = None  # Ignored as identity.
    evidence_reference: Optional[str] = None
    confirmed_resolution: StrictBool = False

class CasePublicResponse(CaseAction):
    public_response: str

class CaseNoRequest(CaseAction):
    reason: str = ''
    confirmed_review: StrictBool = False

class CaseReopen(CaseAction):
    reason: str = Field(min_length=20, max_length=10000)
    confirmed_reopening: StrictBool = False

class CaseRegistrationCreate(CaseAction):
    number: str = Field(min_length=1, max_length=100)
    institution: str = Field(min_length=3, max_length=160)
    issued_on: date
    evidence_reference: str = Field(min_length=5, max_length=2000)
    reason: str = Field(min_length=20, max_length=10000)
    confirmed_review: StrictBool = False

class CaseRegistrationCancel(CaseAction):
    reason: str = Field(min_length=20, max_length=10000)
    confirmed_review: StrictBool = False

class CasePriorityAction(CaseAction):
    priority_action: StrictBool = False

class MetaPostSummary(BaseModel):
    id: str
    title: str
    message: Optional[str] = None
    cover_image: Optional[str] = None
    media_type: Optional[str] = "image"
    permalink_url: Optional[str] = None
    published_at: Optional[str] = None
    source: Optional[str] = "Facebook"
    total_comments: Optional[int] = 0
    likes_count: Optional[int] = 0

class CaseResponse(CaseBase):
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    post_data: Optional[MetaPostSummary] = None
    comment_url: Optional[str] = None
    linked_comments: List[Dict[str, Any]] = []
    provenance_status: Optional[str] = None
    provenance_reason: Optional[str] = None
    provenance_conflict: Optional[Dict[str, Any]] = None
    duplicate_of: Optional[str] = None
    workflow_revision: Optional[str] = None
    workflow_events: List[Dict[str, Any]] = Field(default_factory=list)
    registrations: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
