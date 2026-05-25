from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.features.auth.repository import AuthRepository
from app.features.auth.security import hash_password, verify_password
from app.features.roles.repository import RolesRepository
from app.features.users.models import User
from app.features.users.repository import UsersRepository
from app.features.users.schemas import (
    AdminResetPasswordRequest,
    ChangeOwnPasswordRequest,
    CreateUserRequest,
    UpdateUserRequest,
    UserDetailResponse,
    UserResponse,
)


class UsersService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users_repository = UsersRepository(session)
        self.roles_repository = RolesRepository(session)
        self.auth_repository = AuthRepository(session)

    async def list_users(self) -> list[UserResponse]:
        users = await self.users_repository.list_users()
        return [self._serialize_user(user) for user in users]

    async def get_user(self, user_id: int) -> UserDetailResponse:
        user = await self._get_user_or_404(user_id)
        return self._serialize_user_detail(user)

    async def create_user(self, payload: CreateUserRequest) -> UserDetailResponse:
        existing_user = await self.users_repository.get_user_by_username_without_roles(
            payload.username,
        )
        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un usuario con ese username",
            )

        roles = await self._get_roles_or_400(payload.role_ids)
        user = await self.users_repository.create_user(
            username=payload.username,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
            email=payload.email,
            is_active=payload.is_active,
            roles=roles,
        )
        await self.session.commit()
        user = await self._get_user_or_404(user.id)
        return self._serialize_user_detail(user)

    async def update_user(
        self,
        user_id: int,
        payload: UpdateUserRequest,
    ) -> UserDetailResponse:
        user = await self._get_user_or_404(user_id)
        duplicate_user = await self.users_repository.get_user_by_username_without_roles(
            payload.username,
        )
        if duplicate_user is not None and duplicate_user.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un usuario con ese username",
            )

        roles = await self._get_roles_or_400(payload.role_ids)
        await self._ensure_last_admin_is_not_removed(
            user=user,
            next_is_active=payload.is_active,
            next_role_names={role.name for role in roles},
        )

        user.username = payload.username
        user.full_name = payload.full_name
        user.email = payload.email
        user.is_active = payload.is_active
        user.roles = roles
        await self.session.flush()

        if not payload.is_active:
            await self.auth_repository.revoke_all_refresh_tokens_for_user(user.id)

        await self.session.commit()
        user = await self._get_user_or_404(user.id)
        return self._serialize_user_detail(user)

    async def delete_user(self, user_id: int) -> None:
        user = await self._get_user_or_404(user_id)
        await self._ensure_last_admin_is_not_removed(
            user=user,
            next_is_active=False,
            next_role_names=set(),
        )
        await self.auth_repository.revoke_all_refresh_tokens_for_user(user.id)
        await self.users_repository.delete_user(user)
        await self.session.commit()

    async def change_own_password(
        self,
        current_user: User,
        payload: ChangeOwnPasswordRequest,
    ) -> None:
        if not verify_password(payload.current_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="La contrasena actual no es valida",
            )

        current_user.password_hash = hash_password(payload.new_password)
        await self.auth_repository.revoke_all_refresh_tokens_for_user(current_user.id)
        await self.session.commit()

    async def reset_password(
        self,
        user_id: int,
        payload: AdminResetPasswordRequest,
    ) -> None:
        user = await self._get_user_or_404(user_id)
        user.password_hash = hash_password(payload.new_password)
        await self.auth_repository.revoke_all_refresh_tokens_for_user(user.id)
        await self.session.commit()

    async def _get_user_or_404(self, user_id: int) -> User:
        user = await self.users_repository.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )
        return user

    async def _get_roles_or_400(self, role_ids: list[int]):
        roles = await self.roles_repository.get_roles_by_ids(role_ids)
        if len(roles) != len(set(role_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uno o varios roles no existen",
            )

        roles_by_id = {role.id: role for role in roles}
        return [roles_by_id[role_id] for role_id in dict.fromkeys(role_ids)]

    async def _ensure_last_admin_is_not_removed(
        self,
        *,
        user: User,
        next_is_active: bool,
        next_role_names: set[str],
    ) -> None:
        current_role_names = {role.name for role in user.roles}
        is_current_active_admin = user.is_active and "admin" in current_role_names
        will_remain_active_admin = next_is_active and "admin" in next_role_names

        if not is_current_active_admin or will_remain_active_admin:
            return

        active_admins = await self.users_repository.count_active_users_with_role("admin")
        if active_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede eliminar o degradar al ultimo admin activo",
            )

    def _serialize_user(self, user: User) -> UserResponse:
        return UserResponse(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            email=user.email,
            is_active=user.is_active,
            roles=sorted(role.name for role in user.roles),
        )

    def _serialize_user_detail(self, user: User) -> UserDetailResponse:
        base = self._serialize_user(user)
        return UserDetailResponse(
            **base.model_dump(),
            role_ids=sorted(role.id for role in user.roles),
        )


def get_users_service(
    session: AsyncSession = Depends(get_session),
) -> UsersService:
    return UsersService(session)
