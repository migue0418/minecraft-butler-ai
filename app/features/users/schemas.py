from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str | None = None
    email: str | None = None
    is_active: bool
    roles: list[str]


class UserDetailResponse(UserResponse):
    role_ids: list[int]


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1)
    full_name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    is_active: bool = True
    role_ids: list[int] = Field(min_length=1)


class UpdateUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    full_name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    is_active: bool = True
    role_ids: list[int] = Field(default_factory=list)


class ChangeOwnPasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=1)


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=1)
