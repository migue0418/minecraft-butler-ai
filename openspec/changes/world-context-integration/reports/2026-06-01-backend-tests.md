# Informe de tests — world-context-integration

**Fecha:** 2026-06-01
**Rama:** feature/world-context-integration

## Comandos ejecutados

```
uv run pytest tests/features/butler/test_schemas.py tests/features/butler/test_nodes.py -v
uv run pytest -q
```

## Resultados

### Tests unitarios (schemas + nodes)
- 16/16 passed en 3.91s

### Suite completa
- 89/89 passed en 16.96s (sin fallos)

## Tests nuevos añadidos

- `tests/features/butler/test_schemas.py` — 7 tests: validación de `WorldContextDTO` y `AskRequest`
- `tests/features/butler/test_nodes.py` — 9 tests: `format_world_context` (formato, orden, truncado)
- `tests/test_api.py` — 3 tests de integración de router: sin world_context, con world_context válido, con world_context inválido (422)

## Fix de regresión

`test_multi_turn_memory_with_memory_saver` fallaba porque el mock de `IntentOutput` no incluía `needs_world_context=False`, lo que hacía que LangGraph intentara serializar un `MagicMock` como bool. Corregido añadiendo `needs_world_context=False` al mock.
