import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import truststore
from fastapi import FastAPI

from app.core.database import close_database, init_database, session_scope
from app.core.settings import get_settings
from app.features.auth.seed import seed_admin_user


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if not settings.ssl_verify:
        truststore.inject_into_ssl()

    if settings.langsmith_api_key:
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        if settings.langsmith_endpoint:
            os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint
            os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
        if settings.langchain_tracing:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGSMITH_TRACING"] = "true"

    await init_database()
    async with session_scope() as session:
        await seed_admin_user(session)
    yield
    await close_database()
