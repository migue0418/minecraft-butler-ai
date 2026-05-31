import os
import ssl
import warnings
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import truststore
from fastapi import FastAPI

from app.core.database import close_database, init_database, session_scope
from app.core.settings import get_settings
from app.features.auth.seed import seed_admin_user


def _configure_ssl_bypass() -> None:
    """Configura el bypass SSL para entornos con proxy corporativo.

    Aplica cuando SSL_VERIFY=false en settings. Cubre:
    - ssl module (truststore con CA del sistema Windows)
    - httpx (usado por huggingface_hub para descargar modelos)
    """
    import httpx
    from huggingface_hub.utils._http import set_client_factory

    truststore.inject_into_ssl()
    ssl._create_default_https_context = ssl._create_unverified_context  # noqa: SLF001
    warnings.filterwarnings("ignore", message=".*Unverified HTTPS.*")
    warnings.filterwarnings("ignore", message=".*InsecureRequestWarning.*")

    def _no_verify_factory() -> httpx.Client:
        return httpx.Client(verify=False)

    set_client_factory(_no_verify_factory)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if not settings.ssl_verify:
        _configure_ssl_bypass()

    if settings.langsmith_api_key:
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        if settings.langsmith_endpoint:
            os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint
            os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint

    tracing_enabled = settings.langchain_tracing or (
        os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true"
    )
    if tracing_enabled:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGSMITH_TRACING"] = "true"

    await init_database()
    async with session_scope() as session:
        await seed_admin_user(session)

    # Inicializar el grafo con checkpointer Redis antes de servir peticiones.
    # get_compiled_graph() crea el AsyncRedisSaver, ejecuta asetup() y compila el grafo.
    from app.features.butler.graph.graph import get_compiled_graph

    await get_compiled_graph()

    yield

    await close_database()
