# Informe de tests — world-context-monsters

**Fecha:** 2026-06-03
**Rama:** feature/world-context-monsters

## Resultado

```
105 passed, 6 warnings in 18.43s
```

## Tests nuevos añadidos

**Schemas (test_schemas.py):**
- `test_nearby_context_with_monsters` — valida `MonsterGroup` en `NearbyContext`
- `test_nearby_context_without_monsters_is_retrocompatible` — `monsters` default `[]`
- `test_world_context_dto_with_monsters` — DTO completo con 2 monstruos
- `test_world_context_dto_chest_with_empty_items_is_valid` — cofre `items: []` no da 422

**Nodes (test_nodes.py):**
- `test_format_world_context_includes_monsters` — monstruos aparecen en el texto
- `test_format_world_context_monsters_before_animals` — monstruos preceden a animales
- `test_format_world_context_empty_chest_shows_vacio` — cofre vacío → `"vacío"`
- `test_format_world_context_no_monsters_no_monsters_line` — sin monstruos, sin línea
