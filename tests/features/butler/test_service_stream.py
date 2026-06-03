from unittest.mock import AsyncMock, patch

import pytest


def _make_token_event(node: str, content: str) -> dict:
    return {
        "event": "on_chat_model_stream",
        "metadata": {"langgraph_node": node},
        "data": {"chunk": type("C", (), {"content": content})()},
    }


def _make_chain_start(node: str) -> dict:
    return {"event": "on_chain_start", "metadata": {"langgraph_node": node}, "data": {}}


def _make_chain_end(node: str, actions: list | None = None) -> dict:
    return {
        "event": "on_chain_end",
        "metadata": {"langgraph_node": node},
        "data": {"output": {"actions": actions or []}},
    }


@pytest.mark.asyncio
async def test_stream_emits_chunks_at_sentence_boundary():
    from app.features.butler.service import ButlerService

    events = [
        _make_chain_start("speak_action"),
        _make_token_event("speak_action", "Hola "),
        _make_token_event("speak_action", "jugador. "),
        _make_token_event("speak_action", "Como estas"),
        _make_chain_end("speak_action"),
    ]

    async def mock_astream_events(*args, **kwargs):
        for e in events:
            yield e

    mock_graph = AsyncMock()
    mock_graph.astream_events = mock_astream_events

    with patch(
        "app.features.butler.service.get_compiled_graph",
        new=AsyncMock(return_value=mock_graph),
    ):
        service = ButlerService()
        actions = [a async for a in service.stream("test")]

    assert len(actions) == 2
    assert "Hola jugador." in actions[0].message
    assert "Como estas" in actions[1].message


@pytest.mark.asyncio
async def test_stream_no_boundary_flushes_at_chain_end():
    from app.features.butler.service import ButlerService

    events = [
        _make_chain_start("speak_action"),
        _make_token_event("speak_action", "Texto sin punto final"),
        _make_chain_end("speak_action"),
    ]

    async def mock_astream_events(*args, **kwargs):
        for e in events:
            yield e

    mock_graph = AsyncMock()
    mock_graph.astream_events = mock_astream_events

    with patch(
        "app.features.butler.service.get_compiled_graph",
        new=AsyncMock(return_value=mock_graph),
    ):
        service = ButlerService()
        actions = [a async for a in service.stream("test")]

    assert len(actions) == 1
    assert actions[0].message == "Texto sin punto final"


@pytest.mark.asyncio
async def test_stream_ignores_tokens_from_non_responder_nodes():
    from app.features.butler.service import ButlerService

    events = [
        _make_token_event("classify_intent", '{"intent":'),
        _make_token_event("classify_intent", '"speak"}'),
        _make_chain_start("speak_action"),
        _make_token_event("speak_action", "Hola."),
        _make_chain_end("speak_action"),
    ]

    async def mock_astream_events(*args, **kwargs):
        for e in events:
            yield e

    mock_graph = AsyncMock()
    mock_graph.astream_events = mock_astream_events

    with patch(
        "app.features.butler.service.get_compiled_graph",
        new=AsyncMock(return_value=mock_graph),
    ):
        service = ButlerService()
        actions = [a async for a in service.stream("test")]

    assert len(actions) == 1
    assert actions[0].message == "Hola."


@pytest.mark.asyncio
async def test_stream_retry_resets_buffer():
    from app.features.butler.service import ButlerService

    # Primer intento: tokens parciales, luego reintento con respuesta correcta
    events = [
        _make_chain_start("speak_action"),
        _make_token_event("speak_action", "Respuesta rota"),
        _make_chain_start("speak_action"),  # retry reset
        _make_token_event("speak_action", "Respuesta correcta."),
        _make_chain_end("speak_action"),
    ]

    async def mock_astream_events(*args, **kwargs):
        for e in events:
            yield e

    mock_graph = AsyncMock()
    mock_graph.astream_events = mock_astream_events

    with patch(
        "app.features.butler.service.get_compiled_graph",
        new=AsyncMock(return_value=mock_graph),
    ):
        service = ButlerService()
        actions = [a async for a in service.stream("test")]

    # Solo debe llegar la respuesta tras el reset (el buffer se limpió)
    assert all("correcta" in a.message or "correcta." in a.message for a in actions)
    assert not any("rota" in a.message for a in actions)


@pytest.mark.asyncio
async def test_stream_move_action_from_chain_end():
    from app.features.butler.service import ButlerService

    events = [
        _make_chain_end(
            "move_action",
            [
                {
                    "type": "move_to_position",
                    "message": "Voy alli.",
                    "x": 10,
                    "y": 64,
                    "z": -5,
                },
            ],
        ),
    ]

    async def mock_astream_events(*args, **kwargs):
        for e in events:
            yield e

    mock_graph = AsyncMock()
    mock_graph.astream_events = mock_astream_events

    with patch(
        "app.features.butler.service.get_compiled_graph",
        new=AsyncMock(return_value=mock_graph),
    ):
        service = ButlerService()
        actions = [a async for a in service.stream("ve aqui")]

    assert len(actions) == 1
    assert actions[0].type == "move_to_position"
    assert actions[0].x == 10
