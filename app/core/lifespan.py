from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.database import close_database, init_database, session_scope
from app.features.auth.seed import seed_admin_user


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await init_database()
    async with session_scope() as session:
        await seed_admin_user(session)
    yield
    await close_database()
