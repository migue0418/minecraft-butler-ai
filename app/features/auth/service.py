from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.datetime import utcnow
from app.core.settings import get_settings
from app.features.auth.repository import (
    AuthRepository,
    generate_refresh_token,
    hash_refresh_token,
    refresh_token_expiration,
)
from app.features.auth.schemas import (
    AuthenticatedUserResponse,
    LoginRequest,
    SessionInfo,
    TokenResponse,
)
from app.features.auth.security import (
    REFRESH_COOKIE_NAME,
    clear_refresh_cookie,
    create_access_token,
    decode_access_token,
    set_refresh_cookie,
    verify_password,
)
from app.features.users.models import User
from app.features.users.repository import UsersRepository


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.auth_repository = AuthRepository(session)
        self.users_repository = UsersRepository(session)

    async def login(
        self,
        payload: LoginRequest,
        response: Response,
        request: Request,
    ) -> TokenResponse:
        user = await self.users_repository.get_user_by_username(payload.username)
        if user is None or not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales invalidas",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario inactivo",
            )

        await self._issue_refresh_token(
            user=user,
            response=response,
            request=request,
            remember_me=payload.remember_me,
        )
        await self.session.commit()
        return TokenResponse(
            access_token=create_access_token(
                user.id,
                user.username,
                sorted(role.name for role in user.roles),
            ),
        )

    async def refresh(self, request: Request, response: Response) -> TokenResponse:
        raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
        if not raw_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token missing",
            )

        token = await self.auth_repository.get_refresh_token_by_hash(
            hash_refresh_token(raw_token),
        )
        if token is None:
            clear_refresh_cookie(response)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        now = utcnow()
        if token.revoked_at is not None:
            await self.auth_repository.revoke_all_refresh_tokens_for_user(
                token.user_id,
                revoked_at=now,
            )
            await self.session.commit()
            clear_refresh_cookie(response)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token reuse detected",
            )

        if token.expires_at <= now:
            await self.auth_repository.revoke_refresh_token(token, revoked_at=now)
            await self.session.commit()
            clear_refresh_cookie(response)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired",
            )

        user = await self.users_repository.get_user_by_id(token.user_id)
        if user is None or not user.is_active:
            await self.auth_repository.revoke_all_refresh_tokens_for_user(
                token.user_id,
                revoked_at=now,
            )
            await self.session.commit()
            clear_refresh_cookie(response)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no disponible",
            )

        await self.auth_repository.revoke_refresh_token(token, revoked_at=now)
        await self._issue_refresh_token(
            user=user,
            response=response,
            request=request,
            remember_me=token.remember_me,
        )
        await self.session.commit()
        return TokenResponse(
            access_token=create_access_token(
                user.id,
                user.username,
                sorted(role.name for role in user.roles),
            ),
        )

    async def logout(self, request: Request, response: Response) -> None:
        raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
        if raw_token:
            token = await self.auth_repository.get_refresh_token_by_hash(
                hash_refresh_token(raw_token),
            )
            if token is not None and token.revoked_at is None:
                await self.auth_repository.revoke_refresh_token(token)
                await self.session.commit()
        clear_refresh_cookie(response)

    async def get_current_user(
        self,
        token: str | None,
    ) -> User:
        payload = decode_access_token(token)

        try:
            user_id = int(payload.sub)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token",
            ) from exc

        user = await self.users_repository.get_user_by_id(user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no disponible",
            )
        return user

    async def me(
        self,
        user: User,
    ) -> AuthenticatedUserResponse:
        return AuthenticatedUserResponse(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            email=user.email,
            is_active=user.is_active,
            roles=sorted(role.name for role in user.roles),
        )

    async def get_sessions(
        self,
        user: User,
        request: Request,
    ) -> list[SessionInfo]:
        sessions = await self.auth_repository.list_active_sessions_for_user(user.id)
        current_hash = None
        raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
        if raw_token:
            current_hash = hash_refresh_token(raw_token)

        return [
            SessionInfo(
                id=session.id,
                created_at=session.created_at,
                expires_at=session.expires_at,
                user_agent=session.user_agent,
                is_current=session.token_hash == current_hash,
            )
            for session in sessions
        ]

    async def revoke_session(
        self,
        session_id: int,
        user: User,
        request: Request,
        response: Response,
    ) -> None:
        session = await self.auth_repository.get_refresh_token_by_id(session_id)
        if session is None or session.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sesion no encontrada",
            )
        if session.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sesion ya revocada",
            )

        current_hash = None
        raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
        if raw_token:
            current_hash = hash_refresh_token(raw_token)

        await self.auth_repository.revoke_refresh_token(session)
        await self.session.commit()
        if current_hash == session.token_hash:
            clear_refresh_cookie(response)

    async def revoke_all_sessions_for_user(self, user_id: int) -> None:
        await self.auth_repository.revoke_all_refresh_tokens_for_user(user_id)
        await self.session.commit()

    async def _issue_refresh_token(
        self,
        user: User,
        response: Response,
        request: Request,
        remember_me: bool,
    ) -> None:
        settings = get_settings()
        raw_token = generate_refresh_token()
        token_hash = hash_refresh_token(raw_token)
        expires_at = refresh_token_expiration(settings.refresh_token_expire_days)
        user_agent = request.headers.get("user-agent")

        await self.auth_repository.create_refresh_token(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            remember_me=remember_me,
        )
        set_refresh_cookie(response, raw_token, remember_me=remember_me)


def get_auth_service(
    session: AsyncSession = Depends(get_session),
) -> AuthService:
    return AuthService(session)
