import logging
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

logger = logging.getLogger(__name__)


def _preload_rag() -> None:
    """Precalienta el RAG en el arranque para evitar cold-start en la primera petición.

    Fuerza la carga del modelo de embeddings (~150MB) y su primera inferencia, e inicializa
    el cliente Qdrant. Reutiliza los factories cacheados (`lru_cache`), de modo que la misma
    instancia caliente se reutiliza luego en `retrieve_context`. Debe invocarse después del
    bypass SSL para respetar la carga offline en entornos con proxy.

    Tolerante a fallos: si el modelo o Qdrant no están disponibles, registra un aviso y deja
    que el RAG se cargue perezosamente en la primera petición (no rompe el arranque).
    """
    from app.features.butler.llm.factory import get_embedding_model
    from app.features.butler.rag.client import get_qdrant_client

    try:
        model = get_embedding_model()
        model.embed_query("calentamiento")  # fuerza la primera inferencia
        client = get_qdrant_client()
        client.get_collections()  # abre la conexión y valida conectividad con Qdrant
    except Exception as exc:  # noqa: BLE001 - el precalentamiento es opcional
        logger.warning("No se pudo precalentar el RAG en el arranque: %s", exc)


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
    from app.features.butler.stt import get_whisper_model

    await get_compiled_graph()
    get_whisper_model()  # precalienta faster-whisper en startup → cero cold-start en /ask-voice
    _preload_rag()  # precalienta embeddings + Qdrant → cero cold-start en la primera pregunta RAG

    yield

    await close_database()
