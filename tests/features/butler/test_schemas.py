import pytest
from pydantic import ValidationError

from app.features.butler.schemas import (
    AskRequest,
    MonsterGroup,
    NearbyContext,
    StreamEvent,
    WorldContextDTO,
)

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


def test_nearby_context_with_monsters():
    ctx = NearbyContext(
        monsters=[MonsterGroup(type="minecraft:zombie", count=2)],
        animals=[],
        crops=[],
    )
    assert ctx.monsters[0].type == "minecraft:zombie"
    assert ctx.monsters[0].count == 2


def test_nearby_context_without_monsters_is_retrocompatible():
    ctx = NearbyContext(animals=[], crops=[])
    assert ctx.monsters == []


def test_world_context_dto_with_monsters():
    data = {
        "player": {"x": -25, "y": 88, "z": -34, "inventory": []},
        "chests": [],
        "nearby": {
            "animals": [{"type": "minecraft:sheep", "count": 2}],
            "monsters": [
                {"type": "minecraft:zombie", "count": 1},
                {"type": "minecraft:spider", "count": 1},
            ],
            "crops": [],
        },
    }
    ctx = WorldContextDTO(**data)
    assert len(ctx.nearby.monsters) == 2
    assert ctx.nearby.monsters[0].type == "minecraft:zombie"


def test_world_context_dto_chest_with_empty_items_is_valid():
    data = {
        "player": {"x": 0, "y": 64, "z": 0, "inventory": []},
        "chests": [{"name": "piedra", "items": []}],
        "nearby": {"animals": [], "monsters": [], "crops": []},
    }
    ctx = WorldContextDTO(**data)
    assert ctx.chests[0].items == []


def test_stream_event_echo_type():
    event = StreamEvent(type="echo", message="[Tú] hola Alfred")
    assert event.type == "echo"
    assert event.x is None


def test_stream_event_speak_type():
    event = StreamEvent(type="speak", message="Hola jugador")
    assert event.type == "speak"


def test_stream_event_move_type_with_coords():
    event = StreamEvent(
        type="move_to_position",
        message="Me dirijo allí.",
        x=10,
        y=64,
        z=-5,
    )
    assert event.x == 10
    assert event.z == -5
