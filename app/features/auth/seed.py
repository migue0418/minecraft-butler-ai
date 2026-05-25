from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.features.auth.security import hash_password
from app.features.roles.repository import RolesRepository
from app.features.users.repository import UsersRepository


async def seed_admin_user(session: AsyncSession) -> None:
    users_repository = UsersRepository(session)
    roles_repository = RolesRepository(session)
    settings = get_settings()

    admin_role = await roles_repository.get_role_by_name("admin")
    if admin_role is None:
        admin_role = await roles_repository.create_role(
            name="admin",
            description="Administracion del sistema",
        )

    user_role = await roles_repository.get_role_by_name("user")
    if user_role is None:
        await roles_repository.create_role(
            name="user",
            description="Usuario operativo",
        )

    admin_user = await users_repository.get_user_by_username(settings.admin_username)
    if admin_user is None:
        admin_user = await users_repository.create_user(
            username=settings.admin_username,
            password_hash=hash_password(settings.admin_password),
            full_name="Administrador",
            email=None,
            is_active=True,
            roles=[admin_role],
        )
        await session.commit()
        return

    if all(role.name != "admin" for role in admin_user.roles):
        admin_user.roles = [*admin_user.roles, admin_role]
        await session.commit()
