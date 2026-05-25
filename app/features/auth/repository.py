import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy import Boolean, DateTime, ForeignKey, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.datetime import utcnow


class AuthRefreshToken(Base):
    __tablename__ = "auth_refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remember_me: Mapped[bool] = mapped_column(Boolean, default=False)


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_refresh_token(
        self,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
        user_agent: str | None,
        remember_me: bool,
    ) -> AuthRefreshToken:
        token = AuthRefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            remember_me=remember_me,
        )
        self.session.add(token)
        await self.session.flush()
        await self.session.refresh(token)
        return token

    async def get_refresh_token_by_hash(
        self,
        token_hash: str,
    ) -> AuthRefreshToken | None:
        result = await self.session.execute(
            select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash),
        )
        return result.scalar_one_or_none()

    async def get_refresh_token_by_id(
        self,
        token_id: int,
    ) -> AuthRefreshToken | None:
        result = await self.session.execute(
            select(AuthRefreshToken).where(AuthRefreshToken.id == token_id),
        )
        return result.scalar_one_or_none()

    async def revoke_refresh_token(
        self,
        token: AuthRefreshToken,
        revoked_at: datetime | None = None,
    ) -> None:
        token.revoked_at = revoked_at or utcnow()
        await self.session.flush()

    async def revoke_all_refresh_tokens_for_user(
        self,
        user_id: int,
        revoked_at: datetime | None = None,
    ) -> None:
        result = await self.session.execute(
            select(AuthRefreshToken).where(
                AuthRefreshToken.user_id == user_id,
                AuthRefreshToken.revoked_at.is_(None),
            ),
        )
        revoked_value = revoked_at or utcnow()
        for token in result.scalars():
            token.revoked_at = revoked_value
        await self.session.flush()

    async def list_active_sessions_for_user(
        self,
        user_id: int,
    ) -> list[AuthRefreshToken]:
        result = await self.session.execute(
            select(AuthRefreshToken)
            .where(
                AuthRefreshToken.user_id == user_id,
                AuthRefreshToken.revoked_at.is_(None),
                AuthRefreshToken.expires_at > utcnow(),
            )
            .order_by(AuthRefreshToken.created_at.desc()),
        )
        return list(result.scalars().all())


def generate_refresh_token() -> str:
    return secrets.token_hex(32)


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def refresh_token_expiration(days: int) -> datetime:
    return utcnow() + timedelta(days=days)
