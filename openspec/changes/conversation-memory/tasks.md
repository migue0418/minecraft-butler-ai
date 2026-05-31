## 0. Setup (OBLIGATORIO - PRIMER PASO)
- [x] 0.1 Crear y cambiar a rama `feature/conversation-memory` desde `main`
- [x] 0.2 (OBLIGATORIO) Plan técnico del agente `backend-developer` en `.claude/doc/conversation-memory/backend.md`; `/opsx:apply` debe leerlo antes de tocar código
- [x] 0.3 Confirmar con el usuario e instalar dependencia: `uv add langgraph-checkpoint-redis` (+ `redis` si no es transitiva); `uv lock`

## 1. Infra: Redis en docker-compose + Settings
- [x] 1.1 `docker-compose.yml`: servicio `redis` (healthcheck `redis-cli ping`, volumen `redis_data`), `backend.depends_on` redis (service_healthy), `REDIS_URL` en environment
- [x] 1.2 `app/core/settings.py`: `redis_url` y `redis_session_ttl_seconds`; documentar en `.example.env`
- [x] 1.3 Validar imagen Redis: `redis:7-alpine` es suficiente; el constructor directo `AsyncRedisSaver(redis_url=...)` + `asetup()` no requiere RediSearch (validado al arrancar con Redis real)

## 2. Grafo: checkpointer + historial (TDD)
- [x] 2.1 Tests que fallan: `state.messages` acumula con `add_messages`; `answer_question` construye el prompt desde `messages`; `compile_graph` acepta checkpointer; `get_compiled_graph()` cachea. Usar `MemorySaver` para multi-turn en unit tests
- [x] 2.2 `graph/state.py`: `messages: Annotated[list, add_messages]`
- [x] 2.3 `graph/graph.py`: `compile_graph(checkpointer)` + proveedor async cacheado `get_compiled_graph()`
- [x] 2.4 `graph/nodes.py`: `answer_question` usa `messages` y devuelve `AIMessage`; `speak_action`/`move_action` añaden su `AIMessage`
- [x] 2.5 `core/lifespan.py`: crear `AsyncRedisSaver` desde `settings.redis_url` (con TTL), `asetup()`, warm-up de `get_compiled_graph()`; cerrar al apagar

## 3. API: session_id end-to-end (TDD)
- [x] 3.1 Tests que fallan: `AskRequest` acepta `session_id` opcional; `ButlerService.run(message, session_id)` pasa `thread_id`; sin `session_id` usa id efímero
- [x] 3.2 `schemas.py`: `AskRequest.session_id: str | None = None`
- [x] 3.3 `service.py`: `run(message, session_id=None)` → `thread_id = session_id or ephemeral`; input `{"messages": [HumanMessage(message)], ...}`; usa `get_compiled_graph()`
- [x] 3.4 `router.py`: propagar `req.session_id`
- [x] 3.5 Actualizar tests existentes que parchean `service._graph` (ya no existe a nivel de módulo)

## 4. Backend: tests y estado (OBLIGATORIO - EL AGENTE LO EJECUTA)
- [x] 4.1 `uv run pytest -q` en verde (PostgreSQL en marcha; nunca SQLite). Unit del grafo con `MemorySaver`
- [x] 4.2 Informe en `openspec/changes/conversation-memory/reports/2026-05-31-verification.md`

## 5. Backend: endpoint multi-turn con curl (OBLIGATORIO - EL AGENTE LO EJECUTA)
- [x] 5.1 Turno 1 + Turno 2 con mismo session_id: T2 usa contexto del T1 (vacas → cantidades) ✓
- [x] 5.2 Sin session_id responde 200 sin persistir (stateless) ✓
- [x] 5.3 TTL verificado en Redis: 86389s (~24h). Contenedor limpiado.

## 6. Cierre (OBLIGATORIO)
- [x] 6.1 Actualizar `docs/` (backend-standards: sección memoria; roadmap: conversation-memory a completados)
- [x] 6.2 PR con `gh` usando la skill `write-pr-report` — PR #5
