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

class ForgotPasswordRequest(BaseModel):
    email: str

class ForgotPasswordResponse(BaseModel):
    message: str
    email: str
    dev_otp: Optional[str] = None  # Disponible en desarrollo para facilitar pruebas

class VerifyOtpRequest(BaseModel):
    email: str
    otp_code: str

class VerifyOtpResponse(BaseModel):
    message: str
    valid: bool

class ResetPasswordRequest(BaseModel):
    email: str
    otp_code: str
    new_password: str

class ResetPasswordResponse(BaseModel):
    message: str
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
