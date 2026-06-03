from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_stream_yields_actions_in_order():
    from app.features.butler.service import ButlerService

    states = [
        {"actions": []},
        {"actions": [{"type": "speak", "message": "primera"}]},
        {
            "actions": [
                {"type": "speak", "message": "primera"},
                {"type": "speak", "message": "segunda"},
            ],
        },
    ]

    async def mock_astream(*args, **kwargs):
        for s in states:
            yield s

    mock_graph = AsyncMock()
    mock_graph.astream = mock_astream

    with patch(
        "app.features.butler.service.get_compiled_graph",
        new=AsyncMock(return_value=mock_graph),
    ):
        service = ButlerService()
        actions = [a async for a in service.stream("test")]

    assert len(actions) == 2
    assert actions[0].message == "primera"
    assert actions[1].message == "segunda"


@pytest.mark.asyncio
async def test_stream_empty_graph_yields_nothing():
    from app.features.butler.service import ButlerService

    async def mock_astream(*args, **kwargs):
        yield {"actions": []}

    mock_graph = AsyncMock()
    mock_graph.astream = mock_astream

    with patch(
        "app.features.butler.service.get_compiled_graph",
        new=AsyncMock(return_value=mock_graph),
    ):
        service = ButlerService()
        actions = [a async for a in service.stream("test")]

    assert actions == []


@pytest.mark.asyncio
async def test_stream_yields_move_action_with_coords():
    from app.features.butler.service import ButlerService

    async def mock_astream(*args, **kwargs):
        yield {
            "actions": [
                {
                    "type": "move_to_position",
                    "message": "Voy allí.",
                    "x": 10,
                    "y": 64,
                    "z": -5,
                },
            ],
        }

    mock_graph = AsyncMock()
    mock_graph.astream = mock_astream

    with patch(
        "app.features.butler.service.get_compiled_graph",
        new=AsyncMock(return_value=mock_graph),
    ):
        service = ButlerService()
        actions = [a async for a in service.stream("ve aquí")]

    assert len(actions) == 1
    assert actions[0].type == "move_to_position"
    assert actions[0].x == 10
