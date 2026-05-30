"""Módulo de recuperación RAG para el butler.

Pipeline:
  1. hybrid_search(): consulta Qdrant con prefetch dense + sparse y fusión RRF.
  2. rerank(): reordena con FlashRank para mayor precisión.
  3. build_context(): formatea los docs como bloque de texto para el prompt.

Parent Document Retrieval:
  Los chunks de mecánicas wiki almacenan el campo `parent_content` en su payload.
  hybrid_search() lo extrae y lo usa como `content` en lugar del chunk.
"""

from __future__ import annotations

from flashrank import Ranker, RerankRequest
from qdrant_client.http.models import (
    FusionQuery,
    Prefetch,
    SparseVector,
)

from app.core.settings import get_settings
from app.features.butler.llm.factory import get_embedding_model
from app.features.butler.rag.client import get_qdrant_client
from app.features.butler.rag.schemas import RetrievedDoc, RetrieverConfig

_SPARSE_MODEL = "Qdrant/bm42-all-minilm-l6-v2-attentions"

_ranker: Ranker | None = None
_sparse_model = None


def _get_ranker() -> Ranker:
    global _ranker
    if _ranker is None:
        _ranker = Ranker()
    return _ranker


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


def _encode_sparse(text: str) -> SparseVector:
    global _sparse_model
    from fastembed import SparseTextEmbedding

    if _sparse_model is None:
        _sparse_model = SparseTextEmbedding(model_name=_SPARSE_MODEL)
    result = list(_sparse_model.embed([text]))[0]
    return SparseVector(indices=result.indices.tolist(), values=result.values.tolist())


def hybrid_search(
    query: str,
    doc_type_filter: str | None = None,
    config: RetrieverConfig | None = None,
) -> list[RetrievedDoc]:
    cfg = config or _get_config()
    client = get_qdrant_client()

    dense_vector = _encode_dense(query)
    sparse_vector = _encode_sparse(query)

    qdrant_filter = None
    if doc_type_filter and doc_type_filter != "none":
        from qdrant_client.http.models import FieldCondition, Filter, MatchValue

        qdrant_filter = Filter(
            must=[
                FieldCondition(key="doc_type", match=MatchValue(value=doc_type_filter)),
            ],
        )

    prefetch_dense = Prefetch(
        query=dense_vector,
        using="dense",
        filter=qdrant_filter,
        limit=cfg.prefetch_limit,
    )
    prefetch_sparse = Prefetch(
        query=sparse_vector,
        using="sparse",
        filter=qdrant_filter,
        limit=cfg.prefetch_limit,
    )

    results = client.query_points(
        collection_name=cfg.collection,
        prefetch=[prefetch_dense, prefetch_sparse],
        query=FusionQuery(fusion="rrf"),
        limit=cfg.prefetch_limit,
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


def rerank(
    query: str,
    docs: list[RetrievedDoc],
    top_k: int | None = None,
) -> list[RetrievedDoc]:
    if not docs:
        return []

    cfg = _get_config()
    k = top_k if top_k is not None else cfg.top_k
    ranker = _get_ranker()

    passages = [{"id": doc.id, "text": doc.content} for doc in docs]
    request = RerankRequest(query=query, passages=passages)
    reranked = ranker.rerank(request)

    doc_by_id = {doc.id: doc for doc in docs}
    result: list[RetrievedDoc] = []
    for entry in reranked[:k]:
        original = doc_by_id.get(str(entry["id"]))
        if original:
            result.append(original.model_copy(update={"score": float(entry["score"])}))
    return result


def build_context(docs: list[RetrievedDoc]) -> str:
    if not docs:
        return ""
    lines = ["=== Contexto recuperado ==="]
    for i, doc in enumerate(docs, start=1):
        lines.append(f"[{i}] ({doc.doc_type}) {doc.content}")
    return "\n".join(lines)


def get_retriever():
    def _retrieve(query: str, doc_type_filter: str | None = None) -> list[RetrievedDoc]:
        docs = hybrid_search(query, doc_type_filter=doc_type_filter)
        return rerank(query, docs)

    return _retrieve
