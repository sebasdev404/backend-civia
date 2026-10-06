from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: str
    full_name: str
    role: str = "OPERADOR"
    department: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = True

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str = "OPERADOR"
    department: Optional[str] = None
    avatar_url: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(UserBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
