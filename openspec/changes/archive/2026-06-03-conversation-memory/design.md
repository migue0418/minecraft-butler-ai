## Context

El butler es un grafo LangGraph compilado a nivel de módulo (`app/features/butler/graph/graph.py::compile_graph` → `builder.compile()`), instanciado en `service.py` (`_graph = compile_graph()`) e invocado con `ainvoke(state)` sin `thread_id`. El estado (`ButlerState`, TypedDict) tiene `message` (único), `intent`, `doc_type`, `retrieved_docs`, `actions` — todos se sobrescriben cada turno; no hay historial. `AskRequest` solo tiene `message`. El compose ya levanta `postgres` y `qdrant`; no hay Redis.

Para memoria multi-turn por jugador necesitamos: (1) persistir el estado del grafo por sesión, (2) acumular el historial de mensajes, (3) propagar un `session_id` desde la API.

## Goals / Non-Goals

**Goals:**
- El butler recuerda turnos anteriores de la misma sesión (`session_id` = UUID del jugador).
- Persistencia en Redis vía el checkpointer oficial de LangGraph, con TTL configurable.
- `session_id` opcional: sin él, comportamiento stateless actual (no breaking).
- Redis como servicio en `docker-compose.yml`.

**Non-Goals:**
- No se implementa resumen/compactación de historial largo (solo TTL en esta fase).
- No se persiste en PostgreSQL ni se añade migración Alembic.
- No se cambia el contenido de la respuesta ni los action types.

## Decisions

### Decisión 1 — Checkpointer: `langgraph-checkpoint-redis` (AsyncRedisSaver)
Se usa el paquete oficial `langgraph-checkpoint-redis`, que expone `AsyncRedisSaver` (la app es async, usa `ainvoke`). Se construye desde `settings.redis_url` y se ejecuta su `asetup()` (crea índices RediSearch que el saver necesita). Alternativa descartada: implementar un checkpointer propio sobre `redis-py` (reinventar; el oficial ya soporta TTL e índices).

### Decisión 2 — Ciclo de vida: compilar el grafo en el arranque, no en import
El checkpointer async mantiene una conexión Redis y requiere `asetup()`, así que el grafo **no puede** compilarse a nivel de módulo. Se introduce un proveedor cacheado `get_compiled_graph()` que:
1. crea el `AsyncRedisSaver` desde `settings.redis_url` (con TTL),
2. ejecuta `asetup()` una vez,
3. compila `builder.compile(checkpointer=saver)` y lo cachea.

`lifespan` invoca `get_compiled_graph()` al arrancar (índices listos antes de servir) y cierra la conexión al apagar. `ButlerService` deja de tener `_graph` a nivel de módulo y obtiene el grafo vía el proveedor. Alternativa considerada: guardar el grafo en `app.state` e inyectarlo por `Request`; descartada por más fricción en la DI actual (`get_butler_service()` no recibe request).

### Decisión 3 — Historial: `messages` con reducer `add_messages`
`ButlerState` gana `messages: Annotated[list[AnyMessage], add_messages]`. Flujo por turno:
- `ButlerService.run(message, session_id)` invoca el grafo con `{"messages": [HumanMessage(message)], ...}` y `config={"configurable": {"thread_id": <id>}}`.
- El reducer `add_messages` fusiona el nuevo `HumanMessage` sobre el historial persistido.
- `answer_question` construye el prompt del LLM con `state["messages"]` (historial completo) en lugar de solo el mensaje actual, y devuelve `{"messages": [AIMessage(...)], "actions": [...]}` → el `AIMessage` se acumula y persiste.
- `classify_intent` sigue clasificando sobre el mensaje actual (la clasificación no necesita historial).
- `move_action`/`speak_action` también añaden su `AIMessage` para mantener el historial coherente.

`message` (str) se mantiene en el estado por compatibilidad con los nodos actuales (classify/retrieve lo usan); `messages` es la fuente del historial.

### Decisión 4 — `session_id` opcional con thread efímero
`AskRequest.session_id: str | None = None`. En `retrieve`/service: `thread_id = session_id or f"ephemeral-{uuid4()}"`. Como el grafo está compilado con checkpointer, siempre se pasa un `thread_id`; sin `session_id` cada petición usa un id único (sin memoria entre peticiones) y el TTL lo limpia.

### Decisión 5 — TTL
El `AsyncRedisSaver` aplica TTL por construcción (`ttl={"default_ttl": <minutos>, "refresh_on_read": True}`). `REDIS_SESSION_TTL_SECONDS` (default 86400) se convierte a minutos. `refresh_on_read` renueva el TTL en cada acceso para no expirar sesiones activas.

### Capa por capa (backend)
- `app/core/settings.py`: `redis_url: str = "redis://localhost:6379"`, `redis_session_ttl_seconds: int = 86400`.
- `app/core/lifespan.py`: crear checkpointer + `asetup()` + warm-up del grafo al arrancar; cerrar al apagar.
- `app/features/butler/graph/state.py`: `messages` con reducer.
- `app/features/butler/graph/graph.py`: `compile_graph(checkpointer)`; proveedor `get_compiled_graph()` (async, cacheado).
- `app/features/butler/graph/nodes.py`: `answer_question` usa `messages`; nodos devuelven `AIMessage`.
- `app/features/butler/service.py`: `run(message, session_id=None)` → thread_id + input messages.
- `app/features/butler/schemas.py`: `AskRequest.session_id: str | None`.
- `app/features/butler/router.py`: propagar `req.session_id`.
- Sin modelos SQLAlchemy, sin migración Alembic, sin cambios en `import_model_modules`.

### Infra
- `docker-compose.yml`: servicio `redis` (`redis:7-alpine`, healthcheck `redis-cli ping`, volumen `redis_data`), `backend.depends_on` redis (service_healthy), `environment.REDIS_URL: redis://redis:6379`.
- `.example.env`: `REDIS_URL`, `REDIS_SESSION_TTL_SECONDS`.

## Risks / Trade-offs

- **El grafo ya no se compila en import** → cualquier código que importe `_graph` directamente se rompe. Mitigación: centralizar en `get_compiled_graph()`; revisar imports (tests que parchean `app.features.butler.service._graph` deben actualizarse).
- **Tests necesitan Redis** → para unit tests del grafo usar `MemorySaver` (langgraph) y verificar acumulación de `messages`; para integración multi-turn, Redis del compose. No usar fakeredis si el saver requiere RediSearch (RedisStack). Decisión a validar en apply: la imagen `redis:7-alpine` puede no traer RediSearch; quizá se necesite `redis/redis-stack`.
- **Dependencia nueva** (`langgraph-checkpoint-redis`) → requiere confirmación e `uv add`.
- **Coherencia del historial entre intents** → si solo `answer_question` acumula, los turnos `speak`/`move` no quedan en el historial; se decide acumular el `AIMessage` en todos los nodos terminales.

## Migration Plan

1. Añadir dependencia y servicio Redis; sin migración de datos.
2. Desplegar: `REDIS_URL` en entorno; el arranque crea índices (`asetup`).
3. El mod Java empieza a enviar `session_id`; sin él, comportamiento actual.
4. Rollback: revertir commits + quitar `redis` del compose; no hay datos relacionales afectados.

## Open Questions

- **Imagen Redis**: ¿`redis:7-alpine` basta o el `AsyncRedisSaver` exige RediSearch (`redis/redis-stack`)? Se valida en apply al ejecutar `asetup()`; se elegirá la imagen que el checkpointer requiera.
- ¿`classify_intent` debería ver historial para resolver referencias ("¿y si...?") antes de enrutar? Por ahora no; se evalúa si el enrutado falla en seguimientos.
