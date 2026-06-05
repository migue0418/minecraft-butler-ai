# Informe de tests backend — fix-langsmith-streaming-traces

Fecha: 2026-06-05
Rama: `feature/fix-langsmith-streaming-traces`

## Alcance del cambio
Refactor de `ButlerService.stream()` al patrón productor/consumidor con `asyncio.Queue`
para corregir las trazas planas de LangSmith en los endpoints de streaming
(`/api/butler/ask-stream`, `/api/butler/ask-voice-stream`). No toca modelo de datos.

## Estado de la BD
**Sin mutación de datos.** El cambio no añade ni modifica modelos SQLAlchemy, no requiere
migración Alembic y no muta filas. No procede baseline ni restauración de BD.

## Tests unitarios

### TDD — tests nuevos (antes de implementar)
- `test_stream_reraises_producer_exception`: verifica que una excepción del grafo se
  re-lanza en el consumidor (no se traga). **Estado pre-implementación:** verde (el código
  original ya propagaba; se conserva como garantía de no-regresión).
- `test_stream_cancels_producer_on_early_consumer_exit`: verifica que al cerrar el stream
  tras consumo parcial (desconexión del cliente) la task productora del grafo se cancela
  limpiamente. **Estado pre-implementación:** ROJO (el código original dejaba el generador
  del grafo a merced del GC, sin limpieza determinista) → confirma el bug.

### Tras la implementación
Comando dirigido al módulo:
```
uv run pytest tests/features/butler/test_service_stream.py tests/features/butler/test_flush_at_boundaries.py -q
→ 16 passed
```
Los 5 tests preexistentes de `test_service_stream.py` (misma secuencia de `ButlerAction`:
troceado por frases, ignorar nodos no-responder, reset por retry, `move_action`) siguen en
verde → el refactor preserva el comportamiento observable (tarea 1.1).

### Suite completa
```
uv run pytest -q
→ 128 passed, 8 warnings in 21.00s
```
Las 8 warnings son `DeprecationWarning` de SlowAPI (preexistentes, ajenas a este cambio).

## Conclusión
- Comportamiento de streaming preservado (no-regresión cubierta por tests preexistentes).
- Bug de limpieza ante desconexión corregido y cubierto por test.
- Propagación de excepciones cubierta por test.
- Suite completa en verde, sin mutación de BD.
