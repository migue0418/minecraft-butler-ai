from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str | None = None
    email: str | None = None
    is_active: bool
    roles: list[str]
    is_locked: bool = False
    locked_until: datetime | None = None


class UserDetailResponse(UserResponse):
    role_ids: list[int]


_USERNAME_PATTERN = r"^[a-zA-Z0-9_-]+$"


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=_USERNAME_PATTERN)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    is_active: bool = True
    role_ids: list[int] = Field(min_length=1)


class UpdateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=_USERNAME_PATTERN)
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    is_active: bool = True
    role_ids: list[int] = Field(min_length=1)


class ChangeOwnPasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)
