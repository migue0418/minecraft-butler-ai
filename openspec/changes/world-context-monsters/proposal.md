## Why

El mod Java ha actualizado el JSON de `world_context` con dos cambios: añade un campo `monsters` dentro de `nearby` (monstruos hostiles cercanos al jugador, agrupados por tipo y cantidad) y corrige el comportamiento de cofres vacíos (ahora envía `"items": []` en lugar de omitir el campo). El backend debe sincronizarse para procesar correctamente el nuevo contrato, validar el campo `monsters`, incluirlo en el texto formateado que recibe el LLM y cubrir el caso de cofres con lista vacía.

## What Changes

- Se añade `MonsterGroup` (`type: str`, `count: int`) en `schemas.py` — mismo shape que `AnimalGroup`.
- `NearbyContext` añade `monsters: list[MonsterGroup] = []`.
- `format_world_context` en `nodes.py` incluye los monstruos en el texto compacto, con prioridad sobre animales (son más relevantes para la pregunta "¿hay peligro cerca?").
- `format_world_context` también muestra cofres vacíos explícitamente (`"vacío"`) en lugar de omitirlos, para dar contexto completo al LLM.
- Tests: `test_schemas.py` cubre `NearbyContext` con monsters; `test_nodes.py` cubre el formato de monsters y cofres vacíos.

## Capabilities

### New Capabilities

*(ninguna — es una extensión del contrato existente)*

### Modified Capabilities

- `world-context-integration`: `NearbyContext` ahora incluye `monsters`; `format_world_context` los serializa. El campo `monsters` es opcional con default `[]` — retrocompatible con clientes que no lo envíen.

## Impact

- **Slice `butler`**: `schemas.py` (modelo), `graph/nodes.py` (`format_world_context`).
- Sin cambios de BD, migraciones ni dependencias nuevas.
- Retrocompatible: `monsters` tiene default `[]`; requests sin ese campo siguen validando correctamente.
