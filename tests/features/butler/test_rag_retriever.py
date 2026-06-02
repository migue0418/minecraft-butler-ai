"""Tests TDD para app/features/butler/rag/ (client, schemas, retriever).

Pipeline dense-only: dense_search() + build_context(). Sin sparse ni reranker
(ver openspec/changes/fix-rag-multilingual-retrieval).
"""

from unittest.mock import MagicMock, patch

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


# ── dense_search ──────────────────────────────────────────────────────────────


class TestDenseSearch:
    def test_returns_list_of_retrieved_docs(self):
        from app.features.butler.rag.retriever import dense_search

        mock_point = _make_qdrant_point("1", "Diamond Sword: weapon.", "item", 0.9)
        mock_client = MagicMock()
        mock_client.query_points.return_value = _make_query_response([mock_point])

        with (
            patch(
                "app.features.butler.rag.retriever.get_qdrant_client",
                return_value=mock_client,
            ),
            patch(
                "app.features.butler.rag.retriever._encode_dense",
                return_value=[0.1] * 384,
            ),
        ):
            result = dense_search("how to craft diamond sword", config=_make_config())

        assert len(result) == 1
        assert isinstance(result[0], RetrievedDoc)
        assert result[0].doc_type == "item"
        # Usa el named vector denso de Qdrant.
        assert mock_client.query_points.call_args.kwargs.get("using") == "dense"

    def test_mechanic_uses_parent_content(self):
        from app.features.butler.rag.retriever import dense_search

        mock_point = _make_qdrant_point(
            "2",
            content="Combat - Attacking: short chunk text",
            doc_type="mechanic",
            parent_content="Combat - Attacking: full parent section text...",
        )
        mock_client = MagicMock()
        mock_client.query_points.return_value = _make_query_response([mock_point])

        with (
            patch(
                "app.features.butler.rag.retriever.get_qdrant_client",
                return_value=mock_client,
            ),
            patch(
                "app.features.butler.rag.retriever._encode_dense",
                return_value=[0.1] * 384,
            ),
        ):
            result = dense_search("how does combat work", config=_make_config())

        assert result[0].content == "Combat - Attacking: full parent section text..."

    def test_doc_type_filter_passed_to_qdrant(self):
        from app.features.butler.rag.retriever import dense_search

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
        ):
            dense_search("diamond", doc_type_filter="item", config=_make_config())

        call_kwargs = mock_client.query_points.call_args.kwargs
        assert call_kwargs.get("query_filter") is not None

    def test_no_filter_when_doc_type_none(self):
        from app.features.butler.rag.retriever import dense_search

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
        ):
            dense_search("anything", doc_type_filter=None, config=_make_config())

        call_kwargs = mock_client.query_points.call_args.kwargs
        assert call_kwargs.get("query_filter") is None

    def test_empty_collection_returns_empty_list(self):
        from app.features.butler.rag.retriever import dense_search

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
        ):
            result = dense_search("anything", config=_make_config())

        assert result == []

    def test_uses_top_k_as_limit(self):
        from app.features.butler.rag.retriever import dense_search

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
        ):
            dense_search("anything", config=_make_config(top_k=5))

        assert mock_client.query_points.call_args.kwargs.get("limit") == 5


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

    def test_pipeline_calls_dense_search(self):
        from app.features.butler.rag.retriever import get_retriever

        mock_doc = RetrievedDoc(id="1", content="test", doc_type="item", score=0.9)

        with patch(
            "app.features.butler.rag.retriever.dense_search",
            return_value=[mock_doc],
        ) as mock_ds:
            retriever = get_retriever()
            result = retriever("diamond sword", doc_type_filter="item")

        mock_ds.assert_called_once_with("diamond sword", doc_type_filter="item")
        assert result == [mock_doc]


# ── Score threshold filtering ─────────────────────────────────────────────────


class TestScoreThreshold:
    def _make_points_with_scores(self, scores: list[float]) -> list:
        return [
            _make_qdrant_point(str(i), f"doc {i}", "item", score=s)
            for i, s in enumerate(scores)
        ]

    def _run_search(self, scores: list[float], threshold: float) -> list:
        from app.features.butler.rag.retriever import dense_search

        config = RetrieverConfig(
            qdrant_url="http://localhost:6333",
            collection="test",
            api_key="",
            top_k=10,
            prefetch_limit=20,
            embedding_model="test-model",
            score_threshold=threshold,
        )
        points = self._make_points_with_scores(scores)
        mock_response = _make_query_response(points)
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
        ):
            return dense_search("test query", config=config)

    def test_threshold_filters_low_score_docs(self):
        docs = self._run_search([0.45, 0.32, 0.18, 0.10], threshold=0.3)
        assert len(docs) == 2
        assert all(d.score >= 0.3 for d in docs)

    def test_zero_threshold_returns_all_docs(self):
        docs = self._run_search([0.45, 0.32, 0.18, 0.10], threshold=0.0)
        assert len(docs) == 4

    def test_high_threshold_returns_empty(self):
        docs = self._run_search([0.45, 0.32, 0.18], threshold=0.9)
        assert docs == []

    def test_exact_threshold_boundary_is_inclusive(self):
        docs = self._run_search([0.30, 0.29], threshold=0.3)
        assert len(docs) == 1
        assert docs[0].score == 0.30
