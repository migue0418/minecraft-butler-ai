## Why

El mod Java ya recopila y envía un snapshot del estado del mundo (inventario del jugador, cofres registrados, animales y cultivos cercanos) con cada llamada a `/api/butler/ask` y `/api/butler/ask-voice`. El backend actualmente ignora ese campo. Integrar el contexto permite que Alfred responda preguntas como "¿tengo materiales para una armadura?" o "¿están listos los cultivos?" con datos reales del juego, sin depender únicamente del LLM.

La integración se diseña con optimización de tokens desde el principio: el contexto solo se inyecta en el prompt cuando el clasificador determina que es relevante, y en formato de texto compacto (~80 tokens) en lugar del JSON crudo (~800 tokens).

## What Changes

- `POST /api/butler/ask` acepta un campo `world_context` opcional en el body JSON.
- `POST /api/butler/ask-voice` acepta un campo `world_context` opcional como form field de texto (JSON serializado), junto a `audio` y `session_id`.
- `AskRequest` añade `world_context: WorldContextDTO | None = None`. Se añade `WorldContextDTO` con los sub-modelos Pydantic que reflejan la estructura del mod Java.
- `ButlerState` añade `world_context: dict | None` y `needs_world_context: bool`.
- `IntentOutput` (structured output del clasificador) añade `needs_world_context: bool`.
- Se añade `format_world_context(ctx: dict) -> str` — formateador de texto compacto que usa los IDs de Minecraft tal cual.
- `speak_action` y `answer_question` inyectan el contexto formateado en el system prompt solo cuando `needs_world_context=True` y `world_context is not None`. El contexto **no** se persiste en `messages` (es efímero por request).
- `ButlerService.run()` recibe y propaga `world_context`.

## Capabilities

### New Capabilities

- `world-context-integration`: Recepción del contexto del mundo Minecraft en los endpoints del butler, propagación por el grafo LangGraph e inyección selectiva en el LLM con formato compacto para minimizar uso de tokens.

### Modified Capabilities

- `butler`: El endpoint `POST /api/butler/ask` acepta ahora un campo opcional `world_context`. **No es breaking** — el campo es opcional y el comportamiento sin él es idéntico al actual.
- `voice-stt-input`: El endpoint `POST /api/butler/ask-voice` acepta ahora un form field `world_context` opcional. **No es breaking**.

## Impact

- **Slice `butler`**: `schemas.py`, `service.py`, `router.py`, `graph/state.py`, `graph/nodes.py`.
- Sin cambios de modelo de datos ni migraciones Alembic.
- Sin dependencias nuevas.
- Retrocompatible: clientes que no envíen `world_context` siguen funcionando exactamente igual.
