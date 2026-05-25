from pydantic import BaseModel, Field


class RoleResponse(BaseModel):
    id: int
    name: str
    description: str


class CreateRoleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str = Field(default="", max_length=255)


class UpdateRoleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str = Field(default="", max_length=255)
