from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.common import TimestampSchema

class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    avatar_url: str | None = None

class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)

class UserUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=255)
    avatar_url: str | None = None
    password: str | None = Field(None, min_leagth=8, max_length=128)

class UserResponse (UserBase, TimestampSchema):
    id: str
    is_active: bool
    is_verified: bool
    workspace_id: str | None
    role: str

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse (BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class RefreshTokenRequest(BaseModel):
    refresh_token: str