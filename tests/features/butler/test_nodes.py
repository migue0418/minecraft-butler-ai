from app.features.butler.graph.nodes import format_world_context


def _make_ctx(**overrides):
    base = {
        "player": {"x": 100, "y": 64, "z": -50, "inventory": []},
        "chests": [],
        "nearby": {"animals": [], "crops": []},
    }
    base.update(overrides)
    return base


def test_format_world_context_includes_position():
    result = format_world_context(_make_ctx())
    assert "Posición: (100, 64, -50)" in result


def test_format_world_context_includes_inventory():
    ctx = _make_ctx(
        player={
            "x": 0,
            "y": 64,
            "z": 0,
            "inventory": [
                {"item": "minecraft:iron_ingot", "count": 5},
                {"item": "minecraft:dirt", "count": 64},
            ],
        },
    )
    result = format_world_context(ctx)
    assert "minecraft:dirt" in result
    assert "64×" in result


def test_format_world_context_inventory_sorted_by_count():
    ctx = _make_ctx(
        player={
            "x": 0,
            "y": 64,
            "z": 0,
            "inventory": [
                {"item": "minecraft:iron_ingot", "count": 1},
                {"item": "minecraft:dirt", "count": 100},
            ],
        },
    )
    result = format_world_context(ctx)
    dirt_pos = result.index("minecraft:dirt")
    iron_pos = result.index("minecraft:iron_ingot")
    assert dirt_pos < iron_pos, "items with higher count should appear first"


def test_format_world_context_truncates_inventory_to_10():
    inventory = [{"item": f"minecraft:item{i}", "count": i + 1} for i in range(15)]
    ctx = _make_ctx(
        player={"x": 0, "y": 64, "z": 0, "inventory": inventory},
    )
    result = format_world_context(ctx)
    assert "5 tipos más" in result


def test_format_world_context_includes_chests():
    ctx = _make_ctx(
        chests=[
            {"name": "despensa", "items": [{"item": "minecraft:bread", "count": 20}]},
        ],
    )
    result = format_world_context(ctx)
    assert "despensa" in result
    assert "minecraft:bread" in result


def test_format_world_context_includes_animals():
    ctx = _make_ctx(
        nearby={"animals": [{"type": "minecraft:cow", "count": 8}], "crops": []},
    )
    result = format_world_context(ctx)
    assert "minecraft:cow" in result
    assert "8" in result


def test_format_world_context_includes_crops():
    ctx = _make_ctx(
        nearby={
            "animals": [],
            "crops": [{"type": "minecraft:wheat", "mature": 12, "growing": 8}],
        },
    )
    result = format_world_context(ctx)
    assert "minecraft:wheat" in result
    assert "12 maduros" in result
    assert "8 creciendo" in result


def test_format_world_context_empty_inventory_no_inventory_line():
    ctx = _make_ctx()
    result = format_world_context(ctx)
    assert "Inventario" not in result


def test_format_world_context_always_has_header():
    result = format_world_context(_make_ctx())
    assert result.startswith("Contexto del mundo del jugador:")
