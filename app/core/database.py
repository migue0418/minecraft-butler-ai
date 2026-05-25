import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.migrations import run_migrations
from app.core.settings import get_settings


class Base(DeclarativeBase):
    pass


INIT_DATABASE_RETRIES = 10
INIT_DATABASE_RETRY_DELAY_SECONDS = 1
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_configured_database_url: str | None = None


def get_engine() -> AsyncEngine:
    global _engine, _session_factory, _configured_database_url

    settings = get_settings()
    if _engine is None or _configured_database_url != settings.database_url:
        _engine = create_async_engine(
            settings.database_url,
            future=True,
            pool_pre_ping=True,
        )
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
        _configured_database_url = settings.database_url

    return _engine


def import_model_modules() -> None:
    import app.features.auth.repository  # noqa: F401
    import app.features.roles.models  # noqa: F401
    import app.features.users.models  # noqa: F401


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


async def init_database() -> None:
    import_model_modules()
    for attempt in range(1, INIT_DATABASE_RETRIES + 1):
        try:
            await asyncio.to_thread(run_migrations)
            return
        except OperationalError:
            if attempt == INIT_DATABASE_RETRIES:
                raise
            await asyncio.sleep(INIT_DATABASE_RETRY_DELAY_SECONDS)


async def close_database() -> None:
    global _engine, _session_factory, _configured_database_url

    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
    _configured_database_url = None
