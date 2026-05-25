from datetime import datetime

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str
    remember_me: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthenticatedUserResponse(BaseModel):
    id: int
    username: str
    full_name: str | None = None
    email: str | None = None
    is_active: bool
    roles: list[str]


class SessionInfo(BaseModel):
    id: int
    created_at: datetime
    expires_at: datetime
    user_agent: str | None = None
    is_current: bool


class AccessTokenPayload(BaseModel):
    sub: str
    username: str
    roles: list[str] = []
    exp: int
