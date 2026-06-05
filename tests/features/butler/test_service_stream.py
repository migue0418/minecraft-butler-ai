import asyncio
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


@pytest.mark.asyncio
async def test_stream_reraises_producer_exception():
    """Si el grafo (productor) lanza, stream() debe re-lanzar en el consumidor,
    no tragar el error en silencio."""
    from app.features.butler.service import ButlerService

    async def mock_astream_events(*args, **kwargs):
        yield _make_chain_start("speak_action")
        raise RuntimeError("grafo roto")

    mock_graph = AsyncMock()
    mock_graph.astream_events = mock_astream_events

    with patch(
        "app.features.butler.service.get_compiled_graph",
        new=AsyncMock(return_value=mock_graph),
    ):
        service = ButlerService()
        with pytest.raises(RuntimeError, match="grafo roto"):
            async for _ in service.stream("test"):
                pass


@pytest.mark.asyncio
async def test_stream_cancels_producer_on_early_consumer_exit():
    """Si el consumidor cierra el stream tras consumo parcial (desconexión del
    cliente), la task productora del grafo debe cancelarse limpiamente."""
    from app.features.butler.service import ButlerService

    cancelled = {"value": False}

    async def mock_astream_events(*args, **kwargs):
        try:
            yield _make_chain_start("speak_action")
            yield _make_token_event("speak_action", "Primera frase. ")
            i = 0
            while True:  # productor infinito hasta que lo cancelen
                yield _make_token_event("speak_action", f"relleno {i}. ")
                i += 1
                await asyncio.sleep(0)
        except (asyncio.CancelledError, GeneratorExit):
            cancelled["value"] = True
            raise

    mock_graph = AsyncMock()
    mock_graph.astream_events = mock_astream_events

    with patch(
        "app.features.butler.service.get_compiled_graph",
        new=AsyncMock(return_value=mock_graph),
    ):
        service = ButlerService()
        agen = service.stream("test")
        first = await asyncio.wait_for(agen.__anext__(), timeout=2.0)
        # Simula desconexión del cliente: cierra el generador consumidor.
        await asyncio.wait_for(agen.aclose(), timeout=2.0)

    assert "Primera frase." in first.message
    assert cancelled["value"] is True
