from pydantic import BaseModel
from typing import Optional, Literal
from pydantic import Field, field_validator,ConfigDict,StrictBool
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
    password: str = Field(min_length=10, max_length=72)
    full_name: str
    role: Literal['ADMIN', 'ALCALDE', 'SECRETARIO', 'OPERADOR'] = "OPERADOR"
    department: Optional[str] = None
    avatar_url: Optional[str] = None

    @field_validator('password')
    @classmethod
    def bcrypt_password_length(cls, value):
        if len(value.encode('utf-8')) > 72:
            raise ValueError('La contraseña no puede superar 72 bytes.')
        return value

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(UserBase):
    id: str
    created_at: datetime
    account_revision: str

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    full_name:str=Field(min_length=1,max_length=150)
    role:Literal['ADMIN','ALCALDE','SECRETARIO','OPERADOR']
    department:Optional[str]=Field(default=None,max_length=150)
    is_active:StrictBool
    reason:str=Field(min_length=20,max_length=2000)
    expected_revision:str=Field(min_length=64,max_length=64)
    model_config=ConfigDict(extra='forbid')

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)

class ForgotPasswordResponse(BaseModel):
    message: str
    email: str

class VerifyOtpRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    otp_code: str = Field(pattern=r'^[0-9]{6}$')

class VerifyOtpResponse(BaseModel):
    message: str
    valid: bool

class ResetPasswordRequest(VerifyOtpRequest):
    new_password: str = Field(min_length=10, max_length=72)

    @field_validator('new_password')
    @classmethod
    def bcrypt_length(cls, value):
        if len(value.encode('utf-8')) > 72:
            raise ValueError('La contraseña no puede superar 72 bytes.')
        return value

class ResetPasswordResponse(BaseModel):
    message: str
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=10, max_length=72)

    @field_validator('new_password')
    @classmethod
    def bcrypt_length(cls, value):
        if len(value.encode('utf-8')) > 72:
            raise ValueError('La contraseña no puede superar 72 bytes.')
        return value
