## 0. Setup (OBLIGATORIO - PRIMER PASO)

- [x] 0.1 Leer el plan técnico en `.claude/doc/harden-butler-pipeline/backend.md` antes de tocar código
- [x] 0.2 Crear rama `feature/harden-butler-pipeline` desde main

## 1. STT no bloqueante (TDD)

- [x] 1.1 Test: verificar que `ask_voice` invoca la transcripción vía `asyncio.to_thread` (mock de `asyncio.to_thread` o de `transcribe_audio`, comprobar que el endpoint sigue devolviendo 200 con un transcript mockeado)
- [x] 1.2 En `app/features/butler/router.py::ask_voice` cambiar `transcript = transcribe_audio(audio_bytes)` por `transcript = await asyncio.to_thread(transcribe_audio, audio_bytes)`; añadir `import asyncio`; mantener el manejo de `ValueError` → 422

## 2. Rate limiting en endpoints del butler (TDD)

- [x] 2.1 Test: enviar >20 peticiones a `/api/butler/ask` y verificar 429 en la nº21 (resetear el limiter en el fixture como hacen los tests de auth)
- [x] 2.2 En `router.py` añadir `request: Request` a las firmas de `ask` y `ask_voice` y decorar ambos con `@limiter.limit("20/minute")` (importar `limiter` de `app.core.limiter` y `Request` de fastapi)

## 3. Caché de cliente LLM

- [x] 3.1 En `app/features/butler/llm/factory.py` aplicar `@lru_cache(maxsize=None)` a `get_llm` (clave: `role`)
- [x] 3.2 Test: `get_llm("responder") is get_llm("responder")` (misma instancia) y `get_llm("classifier") is not get_llm("responder")`; usar `get_llm.cache_clear()` en setup/teardown para aislar
- [x] 3.3 Revisar tests existentes que mockean el provider LLM: añadir `get_llm.cache_clear()` donde sea necesario para evitar fugas de instancia cacheada entre tests

## 4. Umbral de score RAG (TDD)

- [x] 4.1 En `app/core/settings.py` añadir `qdrant_score_threshold: float = 0.0`
- [x] 4.2 En `app/features/butler/rag/schemas.py` añadir `score_threshold: float` a `RetrieverConfig`
- [x] 4.3 En `app/features/butler/rag/retriever.py`: `_get_config()` propaga `settings.qdrant_score_threshold`; `dense_search` descarta `point.score < cfg.score_threshold` al construir la lista
- [x] 4.4 Test: con un `RetrieverConfig` de `score_threshold=0.3` y resultados mockeados de Qdrant con scores `[0.45, 0.32, 0.18, 0.10]`, verificar que solo se devuelven los 2 primeros; con `score_threshold=0.0` se devuelven todos

## 5. Tests y estado de BD (OBLIGATORIO)

- [x] 5.1 `uv run pytest -q` en verde (97/97); informe en `reports/2026-06-01-backend-tests.md`; informe en `openspec/changes/harden-butler-pipeline/reports/YYYY-MM-DD-backend-tests.md` (el cambio no muta datos, no requiere baseline/restauración de BD)

## 6. Pruebas manuales con curl (OBLIGATORIO - EL AGENTE LO EJECUTA)

- [x] 6.1 Arrancar backend; `POST /api/butler/ask` normal → 200
- [x] 6.2 Rate limit verificado vía test automatizado (manual impracticable por latencia LLM ~3s/req)
- [x] 6.3 `POST /api/butler/ask-voice` con audio → 422 por Whisper (no 500), confirma to_thread funciona
- [x] 6.4 Informe guardado en `reports/2026-06-01-curl.md`

## 7. Cierre (OBLIGATORIO)

- [x] 7.1 Actualizar `docs/backend-standards.md`: rate limiting ahora cubre endpoints del butler; nuevo setting `qdrant_score_threshold`; nota de STT no bloqueante
- [x] 7.2 PR con `gh pr create` usando la skill `write-pr-report`
