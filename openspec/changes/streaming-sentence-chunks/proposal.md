## Why

El streaming de `streaming-butler-responses` ya envía un echo del jugador y cada `ButlerAction` conforme el grafo la produce. Sin embargo, como el grafo tiene un único nodo de acción al final que espera a que el LLM termine, Alfred sigue apareciendo "de golpe" con toda su respuesta. La impresión de conversación viva requiere que el texto aparezca frase a frase mientras el LLM genera, no cuando termina.

## What Changes

- `ButlerService.stream()` deja de usar `graph.astream(stream_mode="values")` y pasa a usar `graph.astream_events(version="v2")`.
- Se añade `_flush_at_boundaries(text) -> tuple[list[str], str]` en `service.py`: acumula tokens del LLM y devuelve chunks completos en cada frontera natural (`.`, `!`, `?`, `\n`, encabezados markdown `##`).
- Los eventos `on_chat_model_stream` de los nodos `speak_action` y `answer_question` se capturan token a token; en cada frontera detectada se emite un `ButlerAction(type="speak")` con el chunk.
- Al finalizar el nodo (`on_chain_end`), se vacía cualquier resto del buffer como último chunk.
- Las acciones no-LLM (`move_to_position`) se capturan del evento `on_chain_end` del nodo `move_action`.
- **Prompts del LLM actualizados** (`nodes.py`): `_MINECRAFT_SYSTEM_PROMPT` y `_MINECRAFT_SYSTEM_PROMPT_WITH_CONTEXT` reforzados para respuestas concisas, sin emojis, sin explicaciones innecesarias y directo al grano.
- **El mod Java no necesita cambios**: ya recibe múltiples `speak` events en secuencia y los ejecuta uno a uno.

## Capabilities

### New Capabilities

*(ninguna — mejora interna de `butler-streaming`)*

### Modified Capabilities

- `butler-streaming`: el método `stream()` ahora emite chunks de texto mientras el LLM genera, en lugar de una sola acción al finalizar.

## Impact

- **Slice `butler`**: `service.py` (método `stream` + helper `_flush_at_boundaries`) y `graph/nodes.py` (system prompts).
- Sin cambios en `router.py`, `schemas.py`, `nodes.py`, grafo, mod Java ni BD.
- Retrocompatible: los endpoints `/ask` y `/ask-voice` (no streaming) no se tocan.
