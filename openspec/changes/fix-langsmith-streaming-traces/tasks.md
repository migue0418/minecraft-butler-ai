## 0. Setup (OBLIGATORIO - PRIMER PASO)

- [x] 0.1 Crear y cambiar a la rama `feature/fix-langsmith-streaming-traces` desde `main`
- [x] 0.2 Generar el plan técnico a nivel de archivos con el agente `backend-developer` en `.claude/doc/fix-langsmith-streaming-traces/backend.md` (OBLIGATORIO antes de tocar código; `/opsx:apply` debe leerlo)

## 1. Backend: tests del patrón productor/cola (TDD - tests primero)

- [x] 1.1 Test: `ButlerService.stream()` emite la **misma secuencia** de `ButlerAction` que el comportamiento actual para entradas representativas (pregunta con RAG → `speak` troceado por frases; `move` con coordenadas → `move_to_position`; saludo → `speak`). Usar el grafo de test con `MemorySaver` (`compile_graph(MemorySaver())`) y LLM/retriever mockeados; sin LangSmith.
- [x] 1.2 Test: si la task productora (grafo) lanza una excepción, `stream()` la **re-lanza** en el consumidor (no la traga en silencio)
- [x] 1.3 Test: si el consumidor se interrumpe (consumo parcial / `aclose()` del generador), la **task productora queda cancelada** y no quedan tasks de fondo vivas
- [x] 1.4 Ejecutar los tests y confirmar que **fallan** (rojo) contra la implementación actual donde aplique

## 2. Backend: implementación del productor/consumidor (slice butler)

- [x] 2.1 En `app/features/butler/service.py`: añadir helper privado `_run_graph_to_queue(queue, message, session_id, input_mode, world_context)` (productor) que ejecuta `graph.astream_events(...)` en su propia task, traslada la lógica de corte por frases (`_flush_at_boundaries`, `_BOUNDARY`, `_RESPONDER_NODES`, manejo de `move_action`) **sin cambiar su semántica**, y empuja `ButlerAction` a una `asyncio.Queue` acotada (`maxsize` pequeño, p. ej. 32)
- [x] 2.2 En `app/features/butler/service.py`: reescribir `stream()` como **consumidor**: crea la cola, lanza el productor con `asyncio.create_task`, drena la cola hasta el centinela de fin (`_STREAM_DONE`), re-lanza excepciones recibidas por la cola, y en `try/finally` cancela y espera la task productora ante cancelación/desconexión (`contextlib.suppress(asyncio.CancelledError)`)
- [x] 2.3 Verificar que `app/features/butler/router.py` (`ask_stream`, `ask_voice_stream`) sigue funcionando sin cambios: el contrato SSE (echo inicial, `data: {json}`, `[DONE]`) se preserva
- [x] 2.4 Confirmar que el camino no-streaming (`run()` → `ainvoke`) queda intacto

## 3. Backend: tests y estado de BD (OBLIGATORIO)

- [x] 3.1 `uv run pytest -q` en verde (suite completa). Este cambio NO muta la BD (sin modelos/migraciones), por lo que no requiere baseline ni restauración de datos; dejar constancia de ello en el informe
- [x] 3.2 Guardar informe en `openspec/changes/fix-langsmith-streaming-traces/reports/YYYY-MM-DD-backend-tests.md` (comandos, resultados, nota de "sin mutación de BD")

## 4. Backend: endpoints con curl (OBLIGATORIO - EL AGENTE LO EJECUTA)

- [x] 4.1 Arrancar el backend (`uv run uvicorn app.main:app --reload`) con servicios disponibles (PostgreSQL, Redis, Qdrant)
- [x] 4.2 Obtener token (login) y llamar a `POST /api/butler/ask-stream` con curl; verificar `200`, `Content-Type: text/event-stream`, echo inicial, eventos `speak` por frases y `[DONE]` final
- [x] 4.3 Llamar a `POST /api/butler/ask-voice-stream` (multipart con audio de prueba); verificar el stream SSE equivalente y el echo con el transcript
- [x] 4.4 Caso de error: petición sin token → `401`; payload inválido → `422`. Documentar comandos y respuestas en el informe del cambio
- [x] 4.5 Verificación de tracing (MANUAL, requiere LangSmith): con `LANGCHAIN_TRACING_V2=true`, lanzar una petición a `/api/butler/ask-stream` y confirmar en la UI de LangSmith que la traza `butler-text-stream` muestra el **árbol de nodos anidado** (no plana). Anotar el resultado/observación en el informe

## 5. Cierre (OBLIGATORIO)

- [x] 5.1 Actualizar documentación técnica afectada en `docs/` y, si procede, la nota de streaming/observabilidad en `ARCHITECTURE.md`
- [x] 5.2 Generar la descripción del PR con la skill `write-pr-report` y abrir el PR con `gh pr create`
