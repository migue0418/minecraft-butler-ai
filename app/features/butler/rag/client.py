from functools import lru_cache

from qdrant_client import QdrantClient as _QdrantClient

from app.core.settings import get_settings


@lru_cache(maxsize=1)
def get_qdrant_client() -> _QdrantClient:
    settings = get_settings()
    kwargs: dict = {"url": settings.qdrant_url}
    if settings.qdrant_api_key:
        kwargs["api_key"] = settings.qdrant_api_key
    return _QdrantClient(**kwargs)
