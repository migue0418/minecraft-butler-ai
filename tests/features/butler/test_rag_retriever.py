"""Tests TDD para app/features/butler/rag/ (client, schemas, retriever)."""

from unittest.mock import MagicMock, patch

import pytest

from app.features.butler.rag.schemas import RetrievedDoc, RetrieverConfig

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_config(top_k: int = 3, prefetch_limit: int = 10) -> RetrieverConfig:
    return RetrieverConfig(
        qdrant_url="http://localhost:6333",
        collection="minecraft_knowledge",
        api_key="",
        top_k=top_k,
        prefetch_limit=prefetch_limit,
        embedding_model="paraphrase-multilingual-MiniLM-L12-v2",
    )


def _make_qdrant_point(
    point_id: str,
    content: str,
    doc_type: str,
    score: float = 0.9,
    parent_content: str = "",
) -> MagicMock:
    payload: dict = {"content": content, "doc_type": doc_type}
    if parent_content:
        payload["parent_content"] = parent_content
    point = MagicMock()
    point.id = point_id
    point.score = score
    point.payload = payload
    return point


def _make_query_response(points: list) -> MagicMock:
    response = MagicMock()
    response.points = points
    return response


# ── RetrievedDoc schema ───────────────────────────────────────────────────────


class TestRetrievedDocSchema:
    def test_basic_construction(self):
        doc = RetrievedDoc(
            id="item_diamond_sword",
            content="Diamond Sword: A melee weapon.",
            doc_type="item",
            score=0.95,
        )
        assert doc.id == "item_diamond_sword"
        assert doc.doc_type == "item"
        assert doc.score == 0.95
        assert doc.metadata == {}

    def test_with_metadata(self):
        doc = RetrievedDoc(
            id="mob_creeper",
            content="Creeper: A hostile mob.",
            doc_type="mob",
            score=0.8,
            metadata={"mob_id": "creeper"},
        )
        assert doc.metadata["mob_id"] == "creeper"

    def test_model_dump_roundtrip(self):
        doc = RetrievedDoc(id="x", content="y", doc_type="mechanic", score=0.5)
        restored = RetrievedDoc(**doc.model_dump())
        assert restored == doc


# ── RetrieverConfig schema ────────────────────────────────────────────────────


class TestRetrieverConfig:
    def test_construction(self):
        cfg = _make_config()
        assert cfg.top_k == 3
        assert cfg.prefetch_limit == 10
        assert cfg.collection == "minecraft_knowledge"


# ── hybrid_search ─────────────────────────────────────────────────────────────


class TestHybridSearch:
    def test_returns_list_of_retrieved_docs(self):
        from app.features.butler.rag.retriever import hybrid_search

        mock_point = _make_qdrant_point("1", "Diamond Sword: weapon.", "item", 0.9)
        mock_response = _make_query_response([mock_point])
        mock_client = MagicMock()
        mock_client.query_points.return_value = mock_response

        with (
            patch(
                "app.features.butler.rag.retriever.get_qdrant_client",
                return_value=mock_client,
            ),
            patch(
                "app.features.butler.rag.retriever._encode_dense",
                return_value=[0.1] * 384,
            ),
            patch(
                "app.features.butler.rag.retriever._encode_sparse",
                return_value=MagicMock(indices=[1], values=[0.5]),
            ),
        ):
            result = hybrid_search("how to craft diamond sword", config=_make_config())

        assert len(result) == 1
        assert isinstance(result[0], RetrievedDoc)
        assert result[0].doc_type == "item"

    def test_mechanic_uses_parent_content(self):
        from app.features.butler.rag.retriever import hybrid_search

        mock_point = _make_qdrant_point(
            "2",
            content="Combat - Attacking: short chunk text",
            doc_type="mechanic",
            parent_content="Combat - Attacking: full parent section text...",
        )
        mock_response = _make_query_response([mock_point])
        mock_client = MagicMock()
        mock_client.query_points.return_value = mock_response

        with (
            patch(
                "app.features.butler.rag.retriever.get_qdrant_client",
                return_value=mock_client,
            ),
            patch(
                "app.features.butler.rag.retriever._encode_dense",
                return_value=[0.1] * 384,
            ),
            patch(
                "app.features.butler.rag.retriever._encode_sparse",
                return_value=MagicMock(indices=[1], values=[0.5]),
            ),
        ):
            result = hybrid_search("how does combat work", config=_make_config())

        assert result[0].content == "Combat - Attacking: full parent section text..."

    def test_doc_type_filter_passed_to_qdrant(self):
        from app.features.butler.rag.retriever import hybrid_search

        mock_client = MagicMock()
        mock_client.query_points.return_value = _make_query_response([])

        with (
            patch(
                "app.features.butler.rag.retriever.get_qdrant_client",
                return_value=mock_client,
            ),
            patch(
                "app.features.butler.rag.retriever._encode_dense",
                return_value=[0.1] * 384,
            ),
            patch(
                "app.features.butler.rag.retriever._encode_sparse",
                return_value=MagicMock(indices=[1], values=[0.5]),
            ),
        ):
            hybrid_search("diamond", doc_type_filter="item", config=_make_config())

        call_kwargs = mock_client.query_points.call_args.kwargs
        prefetches = call_kwargs.get("prefetch", [])
        assert len(prefetches) == 2
        assert prefetches[0].filter is not None
        assert prefetches[1].filter is not None

    def test_no_filter_when_doc_type_none(self):
        from app.features.butler.rag.retriever import hybrid_search

        mock_client = MagicMock()
        mock_client.query_points.return_value = _make_query_response([])

        with (
            patch(
                "app.features.butler.rag.retriever.get_qdrant_client",
                return_value=mock_client,
            ),
            patch(
                "app.features.butler.rag.retriever._encode_dense",
                return_value=[0.1] * 384,
            ),
            patch(
                "app.features.butler.rag.retriever._encode_sparse",
                return_value=MagicMock(indices=[], values=[]),
            ),
        ):
            hybrid_search("anything", doc_type_filter=None, config=_make_config())

        call_kwargs = mock_client.query_points.call_args.kwargs
        prefetches = call_kwargs.get("prefetch", [])
        assert prefetches[0].filter is None
        assert prefetches[1].filter is None

    def test_empty_collection_returns_empty_list(self):
        from app.features.butler.rag.retriever import hybrid_search

        mock_client = MagicMock()
        mock_client.query_points.return_value = _make_query_response([])

        with (
            patch(
                "app.features.butler.rag.retriever.get_qdrant_client",
                return_value=mock_client,
            ),
            patch(
                "app.features.butler.rag.retriever._encode_dense",
                return_value=[0.1] * 384,
            ),
            patch(
                "app.features.butler.rag.retriever._encode_sparse",
                return_value=MagicMock(indices=[], values=[]),
            ),
        ):
            result = hybrid_search("anything", config=_make_config())

        assert result == []


# ── rerank ────────────────────────────────────────────────────────────────────


class TestRerank:
    def _make_docs(self, n: int) -> list[RetrievedDoc]:
        return [
            RetrievedDoc(
                id=str(i),
                content=f"doc {i}",
                doc_type="item",
                score=0.9 - i * 0.1,
            )
            for i in range(n)
        ]

    def test_returns_top_k_docs(self):
        from app.features.butler.rag.retriever import rerank

        docs = self._make_docs(10)
        mock_ranker = MagicMock()
        mock_ranker.rerank.return_value = [
            {"id": str(i), "score": 1.0 - i * 0.1} for i in range(10)
        ]

        with patch(
            "app.features.butler.rag.retriever._get_ranker",
            return_value=mock_ranker,
        ):
            result = rerank("query", docs, top_k=3)

        assert len(result) == 3

    def test_empty_docs_returns_empty(self):
        from app.features.butler.rag.retriever import rerank

        result = rerank("query", [])
        assert result == []

    def test_score_updated_from_reranker(self):
        from app.features.butler.rag.retriever import rerank

        docs = self._make_docs(2)
        mock_ranker = MagicMock()
        mock_ranker.rerank.return_value = [
            {"id": "0", "score": 0.99},
            {"id": "1", "score": 0.55},
        ]

        with patch(
            "app.features.butler.rag.retriever._get_ranker",
            return_value=mock_ranker,
        ):
            result = rerank("query", docs, top_k=2)

        assert abs(result[0].score - 0.99) < 0.001
        assert abs(result[1].score - 0.55) < 0.001


# ── build_context ─────────────────────────────────────────────────────────────


class TestBuildContext:
    def test_empty_docs_returns_empty_string(self):
        from app.features.butler.rag.retriever import build_context

        assert build_context([]) == ""

    def test_formats_docs_with_numbering(self):
        from app.features.butler.rag.retriever import build_context

        docs = [
            RetrievedDoc(
                id="1",
                content="Diamond Sword info",
                doc_type="item",
                score=0.9,
            ),
            RetrievedDoc(id="2", content="Creeper info", doc_type="mob", score=0.8),
        ]
        context = build_context(docs)
        assert "=== Contexto recuperado ===" in context
        assert "[1] (item) Diamond Sword info" in context
        assert "[2] (mob) Creeper info" in context

    def test_single_doc(self):
        from app.features.butler.rag.retriever import build_context

        docs = [
            RetrievedDoc(
                id="1",
                content="Some mechanic",
                doc_type="mechanic",
                score=0.7,
            ),
        ]
        context = build_context(docs)
        assert "[1] (mechanic)" in context


# ── get_retriever (integración del pipeline) ──────────────────────────────────


class TestGetRetriever:
    def test_returns_callable(self):
        from app.features.butler.rag.retriever import get_retriever

        retriever = get_retriever()
        assert callable(retriever)

    def test_pipeline_calls_hybrid_search_then_rerank(self):
        from app.features.butler.rag.retriever import get_retriever

        mock_doc = RetrievedDoc(id="1", content="test", doc_type="item", score=0.9)
        reranked_doc = RetrievedDoc(id="1", content="test", doc_type="item", score=0.99)

        with (
            patch(
                "app.features.butler.rag.retriever.hybrid_search",
                return_value=[mock_doc],
            ) as mock_hs,
            patch(
                "app.features.butler.rag.retriever.rerank",
                return_value=[reranked_doc],
            ) as mock_rr,
        ):
            retriever = get_retriever()
            result = retriever("diamond sword", doc_type_filter="item")

        mock_hs.assert_called_once_with("diamond sword", doc_type_filter="item")
        mock_rr.assert_called_once_with("diamond sword", [mock_doc])
        assert result == [reranked_doc]
