## 0. Setup (OBLIGATORIO - PRIMER PASO)

- [x] 0.1 Leer el plan técnico en `.claude/doc/streaming-butler-responses/backend.md` antes de tocar código
- [x] 0.2 Crear rama `feature/streaming-butler-responses` desde main

## 1. Schemas (TDD)

- [x] 1.1 En `app/features/butler/schemas.py`: añadir `StreamEvent(type: str, message: str, x/y/z opcionales)` — mismo shape que `ButlerAction` pero `type` puede ser `"echo"`
- [x] 1.2 Test: `StreamEvent` valida con type "echo" y con type "speak"

## 2. Service — `ButlerService.stream()` (TDD)

- [x] 2.1 En `app/features/butler/service.py`: añadir método async generator `stream(message, session_id, input_mode, world_context) -> AsyncIterator[ButlerAction]` usando `graph.astream(stream_mode="values")` y emitiendo nuevas acciones detectadas por diff del estado
- [x] 2.2 Test: con grafo mockeado que emite estado con 2 acciones secuenciales, verificar que `stream()` las yield en orden

## 3. Router — endpoints SSE (TDD)

- [x] 3.1 En `app/features/butler/router.py`: añadir `POST /api/butler/ask-stream` con `StreamingResponse(media_type="text/event-stream")`, `@limiter.limit("20/minute")`, echo como primer evento, luego acciones del `service.stream()`, cerrar con `[DONE]`
- [x] 3.2 En `router.py`: añadir `POST /api/butler/ask-voice-stream` con misma lógica multipart que `ask-voice` + echo del transcript con prefijo `🎤`
- [x] 3.3 Test: `POST /ask-stream` → primer evento es echo, segundo es speak, último es `[DONE]`
- [x] 3.4 Test: `POST /ask-stream` sin auth → 401 (no stream)
- [x] 3.5 Test: `POST /ask-voice-stream` con audio mockeado → echo con prefijo voz, luego acciones

## 4. Tests y estado de BD (OBLIGATORIO)

- [x] 4.1 `uv run pytest -q` en verde (115/115); informe en `reports/2026-06-03-backend-tests.md`

## 5. Pruebas manuales con curl (OBLIGATORIO - EL AGENTE LO EJECUTA)

- [x] 5.1 `curl -N POST /api/butler/ask-stream` → echo + speak (monstruos) + [DONE] ✓
- [x] 5.2 `POST /api/butler/ask-voice-stream` → 422 por audio silencioso (endpoint activo) ✓
- [x] 5.3 Informe en `reports/2026-06-03-curl.md`

## 6. Cierre (OBLIGATORIO)

- [x] 6.1 Actualizar `docs/backend-standards.md`: documentar los endpoints streaming, formato SSE, protocolo [DONE]
- [ ] 6.2 PR con `gh pr create` usando la skill `write-pr-report`
