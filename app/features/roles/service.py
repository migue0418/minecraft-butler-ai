from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.features.roles.models import Role
from app.features.roles.repository import RolesRepository
from app.features.roles.schemas import CreateRoleRequest, RoleResponse, UpdateRoleRequest

SYSTEM_ROLE_NAMES = {"admin", "user"}


class RolesService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.roles_repository = RolesRepository(session)

    async def list_roles(self) -> list[RoleResponse]:
        roles = await self.roles_repository.list_roles()
        return [self._serialize_role(role) for role in roles]

    async def get_role(self, role_id: int) -> RoleResponse:
        role = await self._get_role_or_404(role_id)
        return self._serialize_role(role)

    async def create_role(self, payload: CreateRoleRequest) -> RoleResponse:
        existing_role = await self.roles_repository.get_role_by_name(payload.name)
        if existing_role is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un rol con ese nombre",
            )

        role = await self.roles_repository.create_role(
            name=payload.name,
            description=payload.description,
        )
        await self.session.commit()
        return self._serialize_role(role)

    async def update_role(
        self,
        role_id: int,
        payload: UpdateRoleRequest,
    ) -> RoleResponse:
        role = await self._get_role_or_404(role_id)
        existing_role = await self.roles_repository.get_role_by_name(payload.name)
        if existing_role is not None and existing_role.id != role.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un rol con ese nombre",
            )

        if role.name in SYSTEM_ROLE_NAMES and payload.name != role.name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede renombrar un rol del sistema",
            )

        role.name = payload.name
        role.description = payload.description
        await self.session.commit()
        await self.session.refresh(role)
        return self._serialize_role(role)

    async def _get_role_or_404(self, role_id: int) -> Role:
        role = await self.roles_repository.get_role_by_id(role_id)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rol no encontrado",
            )
        return role

    def _serialize_role(self, role: Role) -> RoleResponse:
        return RoleResponse(
            id=role.id,
            name=role.name,
            description=role.description,
        )


def get_roles_service(
    session: AsyncSession = Depends(get_session),
) -> RolesService:
    return RolesService(session)
