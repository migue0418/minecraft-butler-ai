import pytest
from pydantic import ValidationError

from app.features.butler.schemas import AskRequest, WorldContextDTO

_VALID_CTX = {
    "player": {
        "x": 10,
        "y": 64,
        "z": -20,
        "inventory": [{"item": "minecraft:dirt", "count": 64}],
    },
    "chests": [
        {"name": "despensa", "items": [{"item": "minecraft:bread", "count": 10}]},
    ],
    "nearby": {
        "animals": [{"type": "minecraft:cow", "count": 3}],
        "crops": [{"type": "minecraft:wheat", "mature": 5, "growing": 3}],
    },
}


def test_world_context_dto_valid():
    ctx = WorldContextDTO(**_VALID_CTX)
    assert ctx.player.x == 10
    assert ctx.player.y == 64
    assert ctx.chests[0].name == "despensa"
    assert ctx.nearby.animals[0].type == "minecraft:cow"
    assert ctx.nearby.crops[0].mature == 5


def test_world_context_dto_optional_fields():
    ctx = WorldContextDTO(
        player={"x": 0, "y": 64, "z": 0},
        nearby={"animals": [], "crops": []},
    )
    assert ctx.chests == []
    assert ctx.player.inventory == []


def test_world_context_dto_missing_player():
    with pytest.raises(ValidationError):
        WorldContextDTO(chests=[], nearby={"animals": [], "crops": []})


def test_world_context_dto_invalid_item_entry():
    with pytest.raises(ValidationError):
        WorldContextDTO(
            player={"x": 0, "y": 64, "z": 0, "inventory": [{"item": "minecraft:dirt"}]},
            nearby={"animals": [], "crops": []},
        )


def test_ask_request_without_world_context():
    req = AskRequest(message="hola")
    assert req.world_context is None
    assert req.session_id is None


def test_ask_request_with_world_context():
    req = AskRequest(message="¿tengo hierro?", world_context=_VALID_CTX)
    assert req.world_context is not None
    assert req.world_context.player.x == 10


def test_ask_request_world_context_invalid_raises_422():
    with pytest.raises(ValidationError):
        AskRequest(
            message="test",
            world_context={"player": "not-an-object", "nearby": {}},
        )
