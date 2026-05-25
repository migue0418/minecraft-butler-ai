from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.roles.models import Role


class RolesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_roles(self) -> list[Role]:
        result = await self.session.execute(select(Role).order_by(Role.name.asc()))
        return list(result.scalars().all())

    async def get_role_by_id(self, role_id: int) -> Role | None:
        result = await self.session.execute(select(Role).where(Role.id == role_id))
        return result.scalar_one_or_none()

    async def get_role_by_name(self, name: str) -> Role | None:
        result = await self.session.execute(select(Role).where(Role.name == name))
        return result.scalar_one_or_none()

    async def get_roles_by_ids(self, role_ids: list[int]) -> list[Role]:
        if not role_ids:
            return []

        result = await self.session.execute(
            select(Role).where(Role.id.in_(set(role_ids))),
        )
        return list(result.scalars().all())

    async def create_role(self, name: str, description: str) -> Role:
        role = Role(name=name, description=description)
        self.session.add(role)
        await self.session.flush()
        await self.session.refresh(role)
        return role
