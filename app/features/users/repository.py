from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.roles.models import Role
from app.features.users.models import User


class UsersRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _user_query(self):
        return select(User).options(selectinload(User.roles))

    async def count_users(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(User))
        return int(result.scalar_one())

    async def list_users(self) -> list[User]:
        result = await self.session.execute(
            self._user_query().order_by(User.username.asc()),
        )
        return list(result.scalars().all())

    async def get_user_by_id(self, user_id: int) -> User | None:
        result = await self.session.execute(
            self._user_query().where(User.id == user_id),
        )
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> User | None:
        result = await self.session.execute(
            self._user_query().where(User.username == username),
        )
        return result.scalar_one_or_none()

    async def get_user_by_username_without_roles(self, username: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.username == username),
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        *,
        username: str,
        password_hash: str,
        full_name: str | None,
        email: str | None,
        is_active: bool,
        roles: list[Role],
    ) -> User:
        user = User(
            username=username,
            password_hash=password_hash,
            full_name=full_name,
            email=email,
            is_active=is_active,
        )
        user.roles = roles
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def delete_user(self, user: User) -> None:
        await self.session.delete(user)
        await self.session.flush()

    async def count_active_users_with_role(self, role_name: str) -> int:
        result = await self.session.execute(
            select(func.count(distinct(User.id)))
            .join(User.roles)
            .where(
                User.is_active.is_(True),
                Role.name == role_name,
            ),
        )
        return int(result.scalar_one())
