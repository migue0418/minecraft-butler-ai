"""Tests TDD para el precalentamiento del RAG en el arranque (app/core/lifespan.py)."""

import logging
from unittest.mock import MagicMock, patch


def test_preload_rag_warms_embedding_and_qdrant():
    """_preload_rag carga el modelo de embeddings, fuerza una primera inferencia
    e inicializa el cliente Qdrant."""
    from app.core.lifespan import _preload_rag

    mock_model = MagicMock()
    mock_get_embedding = MagicMock(return_value=mock_model)
    mock_get_qdrant = MagicMock()

    with (
        patch(
            "app.features.butler.llm.factory.get_embedding_model",
            new=mock_get_embedding,
        ),
        patch(
            "app.features.butler.rag.client.get_qdrant_client",
            new=mock_get_qdrant,
        ),
    ):
        _preload_rag()

    mock_get_embedding.assert_called_once()
    mock_model.embed_query.assert_called_once()
    mock_get_qdrant.assert_called_once()


def test_preload_rag_swallows_errors(caplog):
    """Si el precalentamiento falla (p. ej. Qdrant caído), _preload_rag no propaga
    el error: el arranque debe completarse igualmente."""
    from app.core.lifespan import _preload_rag

    mock_model = MagicMock()
    mock_get_embedding = MagicMock(return_value=mock_model)
    mock_get_qdrant = MagicMock(side_effect=ConnectionError("Qdrant caído"))

    with (
        patch(
            "app.features.butler.llm.factory.get_embedding_model",
            new=mock_get_embedding,
        ),
        patch(
            "app.features.butler.rag.client.get_qdrant_client",
            new=mock_get_qdrant,
        ),
        caplog.at_level(logging.WARNING),
    ):
        # No debe lanzar
        _preload_rag()

    assert any("rag" in r.message.lower() or "RAG" in r.message for r in caplog.records)
