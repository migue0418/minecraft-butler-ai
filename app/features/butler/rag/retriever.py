"""Módulo de recuperación RAG para el butler.

Pipeline (dense-only):
  1. dense_search(): búsqueda vectorial densa en Qdrant con el modelo de
     embeddings multilingüe. El modelo es cross-lingual, así que las consultas en
     español recuperan correctamente el corpus en inglés sin etapas léxicas.
  2. build_context(): formatea los docs como bloque de texto para el prompt.

Decisión (ver openspec/changes/fix-rag-multilingual-retrieval): se descartó la
rama sparse BM42 y el reranker FlashRank porque son léxicos solo-inglés y
degradaban el ranking en consultas en español (sparse devuelve ruido; los
rerankers de FlashRank no reordenan ES→EN). El denso multilingüe basta y es
superior en ES y EN.

Parent Document Retrieval:
  Los chunks de mecánicas wiki almacenan el campo `parent_content` en su payload.
  dense_search() lo extrae y lo usa como `content` en lugar del chunk.
"""

from __future__ import annotations

from qdrant_client.http.models import (
    FieldCondition,
    Filter,
    MatchValue,
)

from app.core.settings import get_settings
from app.features.butler.llm.factory import get_embedding_model
from app.features.butler.rag.client import get_qdrant_client
from app.features.butler.rag.schemas import RetrievedDoc, RetrieverConfig


def _get_config() -> RetrieverConfig:
    settings = get_settings()
    return RetrieverConfig(
        qdrant_url=settings.qdrant_url,
        collection=settings.qdrant_collection,
        api_key=settings.qdrant_api_key,
        top_k=settings.qdrant_top_k,
        prefetch_limit=settings.qdrant_prefetch_limit,
        embedding_model=settings.embedding_model,
    )


def _encode_dense(text: str) -> list[float]:
    model = get_embedding_model()
    return model.embed_query(text)


def dense_search(
    query: str,
    doc_type_filter: str | None = None,
    config: RetrieverConfig | None = None,
) -> list[RetrievedDoc]:
    """Recupera los top-K documentos por similitud vectorial densa.

    El vector de consulta se genera con el modelo de embeddings multilingüe
    (cross-lingual), de modo que una pregunta en español recupera documentos del
    corpus en inglés. Aplica un filtro opcional por `doc_type` y expone
    `parent_content` para los documentos de mecánicas wiki.
    """
    cfg = config or _get_config()
    client = get_qdrant_client()

    dense_vector = _encode_dense(query)

    qdrant_filter = None
    if doc_type_filter and doc_type_filter != "none":
        qdrant_filter = Filter(
            must=[
                FieldCondition(key="doc_type", match=MatchValue(value=doc_type_filter)),
            ],
        )

    results = client.query_points(
        collection_name=cfg.collection,
        query=dense_vector,
        using="dense",
        query_filter=qdrant_filter,
        limit=cfg.top_k,
        with_payload=True,
    )

    docs: list[RetrievedDoc] = []
    for point in results.points:
        payload = point.payload or {}
        doc_type = payload.get("doc_type", "")
        if doc_type == "mechanic" and "parent_content" in payload:
            content = payload["parent_content"]
        else:
            content = payload.get("content", "")
        docs.append(
            RetrievedDoc(
                id=str(point.id),
                content=content,
                doc_type=doc_type,
                score=point.score or 0.0,
                metadata={
                    k: v
                    for k, v in payload.items()
                    if k not in ("content", "parent_content")
                },
            ),
        )
    return docs


def build_context(docs: list[RetrievedDoc]) -> str:
    if not docs:
        return ""
    lines = ["=== Contexto recuperado ==="]
    for i, doc in enumerate(docs, start=1):
        lines.append(f"[{i}] ({doc.doc_type}) {doc.content}")
    return "\n".join(lines)


def get_retriever():
    def _retrieve(query: str, doc_type_filter: str | None = None) -> list[RetrievedDoc]:
        return dense_search(query, doc_type_filter=doc_type_filter)

    return _retrieve
