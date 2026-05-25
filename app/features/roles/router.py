from fastapi import APIRouter, Depends, status

from app.features.auth.dependencies import require_roles
from app.features.roles.schemas import CreateRoleRequest, RoleResponse, UpdateRoleRequest
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
    role_id: int,
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
    role_id: int,
    payload: UpdateRoleRequest,
    _: object = Depends(require_roles("admin")),
    service: RolesService = Depends(get_roles_service),
) -> RoleResponse:
    return await service.update_role(role_id, payload)
