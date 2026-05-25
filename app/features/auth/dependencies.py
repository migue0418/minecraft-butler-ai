from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.features.auth.security import oauth2_password_bearer
from app.features.auth.service import AuthService, get_auth_service
from app.features.users.models import User


async def get_authenticated_user(
    token: str | None = Depends(oauth2_password_bearer),
    service: AuthService = Depends(get_auth_service),
) -> User:
    return await service.get_current_user(token)


def require_roles(*required_roles: str) -> Callable[..., User]:
    required_role_set = set(required_roles)

    async def dependency(user: User = Depends(get_authenticated_user)) -> User:
        role_names = {role.name for role in user.roles}
        if not role_names.intersection(required_role_set):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para acceder a este recurso",
            )
        return user

    return dependency
