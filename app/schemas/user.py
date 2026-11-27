from pydantic import BaseModel
from typing import Optional, Literal
from pydantic import Field, field_validator,ConfigDict,StrictBool
from datetime import datetime
from app.core.password_policy import validate_new_password

class UserBase(BaseModel):
    email: str
    full_name: str
    role: str = "OPERADOR"
    department: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = True

class UserCreate(BaseModel):
    email: str
    password: str = Field(default='1234', min_length=4, max_length=72)
    full_name: str
    role: Literal['ADMIN', 'ALCALDE', 'SECRETARIO', 'OPERADOR'] = "OPERADOR"
    department: Optional[str] = None
    avatar_url: Optional[str] = None

    @field_validator('email')
    @classmethod
    def valid_email(cls, value):
        import re
        value = value.strip().lower()
        if len(value) > 254 or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}", value):
            raise ValueError('Ingresa un correo electrónico válido')
        return value

    @field_validator('password')
    @classmethod
    def bcrypt_password_length(cls, value):
        # The owner chose 1234 as the initial credential for admin-created accounts.
        return value if value == '1234' else validate_new_password(value)

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(UserBase):
    id: str
    created_at: datetime
    account_revision: str

    class Config:
        from_attributes = True

class UserAdministrationResponse(UserResponse):
    welcome_email_status: Optional[str] = None
    welcome_email_detail: Optional[str] = None


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
        return validate_new_password(value)

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
        return validate_new_password(value)
