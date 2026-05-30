from fastapi import APIRouter, Depends, Path, status

from app.features.auth.dependencies import require_roles
from app.features.roles.schemas import (
    CreateRoleRequest,
    RoleResponse,
    UpdateRoleRequest,
)
from app.features.roles.service import RolesService, get_roles_service

router = APIRouter(prefix="/api/roles", tags=["Roles"])


@router.get("", response_model=list[RoleResponse])
async def list_roles(
    _: object = Depends(require_roles("admin")),
    service: RolesService = Depends(get_roles_service),
) -> list[RoleResponse]:
    return await service.list_roles()


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: int = Path(..., gt=0),
    _: object = Depends(require_roles("admin")),
    service: RolesService = Depends(get_roles_service),
) -> RoleResponse:
    return await service.get_role(role_id)


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: CreateRoleRequest,
    _: object = Depends(require_roles("admin")),
    service: RolesService = Depends(get_roles_service),
) -> RoleResponse:
    return await service.create_role(payload)


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int = Path(..., gt=0),
    payload: UpdateRoleRequest = ...,
    _: object = Depends(require_roles("admin")),
    service: RolesService = Depends(get_roles_service),
) -> RoleResponse:
    return await service.update_role(role_id, payload)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: int = Path(..., gt=0),
    _: object = Depends(require_roles("admin")),
    service: RolesService = Depends(get_roles_service),
) -> None:
    await service.delete_role(role_id)
