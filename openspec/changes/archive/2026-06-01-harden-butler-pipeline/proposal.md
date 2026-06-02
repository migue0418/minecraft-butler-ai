## Why

El slice `butler` tiene cuatro puntos débiles de bajo riesgo y alto retorno: un bug de concurrencia (la transcripción STT bloquea el event loop), una exposición de coste (los endpoints que llaman al LLM no tienen rate limiting), un descuido de rendimiento (el cliente LLM se reconstruye en cada nodo) y un desperdicio de tokens (el RAG inyecta documentos irrelevantes sin filtrar por relevancia). Los cuatro son cambios pequeños sin impacto en el modelo de datos.

## What Changes

- **STT async**: `transcribe_audio()` (CPU-bound, síncrono) pasa a ejecutarse con `asyncio.to_thread()` en el endpoint `/api/butler/ask-voice`, liberando el event loop durante la transcripción.
- **Rate limiting**: se añade `@limiter.limit(...)` a `POST /api/butler/ask` y `POST /api/butler/ask-voice` (requiere `Request` en la firma), protegiendo el gasto de tokens del LLM frente a bucles o abuso.
- **Caché de cliente LLM**: `get_llm(role)` se cachea con `lru_cache` por rol (igual que ya hace `get_embedding_model`), evitando construir un `ChatAnthropic`/`ChatOpenAI` nuevo en cada invocación de nodo.
- **Umbral de relevancia RAG**: nuevo setting `qdrant_score_threshold`; `dense_search()` descarta los documentos por debajo del umbral antes de pasarlos al prompt, reduciendo tokens y eliminando ruido que degrada la respuesta.

## Capabilities

### New Capabilities

*(ninguna — son mejoras a capabilities existentes)*

### Modified Capabilities

- `api-rate-limiting`: se añade rate limiting a los endpoints del butler (`/ask`, `/ask-voice`), antes solo en auth.
- `voice-stt-input`: la transcripción STT pasa a ser no bloqueante del event loop.
- `rag-pipeline`: filtrado de documentos recuperados por umbral de score antes de construir el contexto.

*(La caché de `get_llm` es una optimización interna sin contrato observable; se documenta en design/tasks, no genera requisito de spec.)*

## Impact

- **Slice `butler`**: `stt/service.py` (o el wrapper en `router.py`), `router.py`, `llm/factory.py`, `rag/retriever.py`, `rag/schemas.py`.
- **Core**: `app/core/settings.py` (nuevo `qdrant_score_threshold`).
- Sin cambios de modelo de datos ni migraciones Alembic.
- Sin dependencias nuevas.
- Retrocompatible: el rate limit es permisivo; el umbral RAG por defecto es conservador (no rompe respuestas actuales).
