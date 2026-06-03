## Context

El contrato del mod Java ha evolucionado. El JSON de `world_context.nearby` ahora incluye `monsters` junto a `animals` y `crops`. Además, los cofres vacíos ya se envían con `"items": []` en lugar de omitirse. El backend tiene dos puntos de cambio: el modelo Pydantic (`schemas.py`) y el formateador de texto para el LLM (`nodes.py::format_world_context`).

Estructura actual de `NearbyContext`:
```python
class NearbyContext(BaseModel):
    animals: list[AnimalGroup] = []
    crops: list[CropGroup] = []
```

Estructura objetivo:
```python
class NearbyContext(BaseModel):
    animals: list[AnimalGroup] = []
    monsters: list[MonsterGroup] = []   # nuevo
    crops: list[CropGroup] = []
```

## Goals / Non-Goals

**Goals:**
- Aceptar y validar `monsters` en `NearbyContext` (mismo shape que `AnimalGroup`).
- Incluir monstruos en el texto formateado para el LLM, con posición prominente (preceden a animales por relevancia táctica).
- Mostrar cofres vacíos explícitamente en el texto (`"vacío"`).

**Non-Goals:**
- Cambiar la lógica de `needs_world_context` del clasificador (ya detecta preguntas de peligro).
- Añadir action types nuevos (p. ej. `flee_from_monster`).
- Persistir el historial de monstruos en Redis.

## Decisions

### D1 — `MonsterGroup` como modelo independiente (igual que `AnimalGroup`)
Aunque el shape es idéntico (`type: str`, `count: int`), tener modelos separados hace el contrato explícito y permite futuros campos específicos de monstruos (p. ej. `hostile: bool`, `health_fraction`) sin romper la interfaz de animales.

**Alternativa descartada:** reusar `AnimalGroup` con el campo `monsters`. Mezcla semánticamente conceptos distintos.

### D2 — Monstruos antes que animales en `format_world_context`
Desde el punto de vista del jugador, los monstruos son información táctica urgente. Se muestran primero en la sección "nearby" para que el LLM los vea sin truncado si el prompt es largo.

### D3 — Cofres vacíos mostrados como `"vacío"`
Antes: `format_world_context` omitía cofres sin items (por el `if items:` tras el filtro). Con el fix del mod, los cofres vacíos llegan con `items: []`, y es informativo para el LLM saber que existe el cofre pero está vacío (diferente de "el cofre no existe").

Cambio mínimo: quitar el `if items:` condicional y mostrar siempre el cofre, con el texto `"vacío"` cuando no hay items.

## Risks / Trade-offs

- `MonsterGroup` con default `[]` → requests sin `monsters` validan sin error (retrocompatibilidad con versiones anteriores del mod).
- Los cofres vacíos ahora aparecen en el prompt → aumento mínimo de tokens (~5 tokens por cofre vacío); aceptable y da contexto real.
