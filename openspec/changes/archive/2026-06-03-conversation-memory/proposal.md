## Why

El butler es hoy sin estado: cada `POST /api/butler/ask` se procesa de forma aislada, sin recordar turnos anteriores. Para una conversación natural ("¿cómo fabrico una espada de diamante?" → "¿y si no tengo suficientes materiales?") el agente debe recordar el contexto por jugador. Añadimos memoria multi-turn persistida con el checkpointer de Redis de LangGraph, indexada por `session_id` (= UUID del jugador del mod Java).

## What Changes

- **Memoria de conversación por sesión**: el grafo LangGraph se compila con un **checkpointer de Redis**, que persiste el estado por `thread_id = session_id`. Los turnos de una misma sesión comparten historial.
- **Historial acumulado en el estado**: `ButlerState` gana un campo `messages` con reducer `add_messages` que acumula los mensajes de usuario y asistente. `answer_question` (y `classify_intent`) usan el historial, no solo el mensaje actual.
- **`session_id` en el contrato de la API (opcional)**: `AskRequest` gana `session_id` opcional. `POST /api/butler/ask` lo propaga a `ButlerService.run(message, session_id)` y este al `config={"configurable": {"thread_id": session_id}}` del grafo. Si falta, se usa un `thread_id` efímero (sin memoria persistente entre peticiones), de modo que el contrato actual no se rompe.
- **Expiración por TTL**: las claves de sesión en Redis expiran tras un TTL configurable (default 24h) para autolimpiar sesiones inactivas. El historial dentro de la ventana del TTL es completo.
- **Ciclo de vida del checkpointer**: el grafo deja de compilarse a nivel de módulo; se compila una vez con el checkpointer Redis creado en el arranque (lifespan), con su `setup()` de índices. Se cierra al apagar.
- **Infra**: se añade el servicio `redis` a `docker-compose.yml` (con healthcheck y volumen), `backend` pasa a `depends_on` redis, y se inyecta `REDIS_URL`.
- **Settings/.env**: nuevas variables `REDIS_URL` (default `redis://localhost:6379`) y `REDIS_SESSION_TTL_SECONDS` (default `86400`).
- **Dependencia**: paquete del checkpointer Redis de LangGraph (`langgraph-checkpoint-redis`). Requiere confirmación del usuario antes de instalar.

## Capabilities

### New Capabilities
- `conversation-memory`: memoria multi-turn del butler persistida en Redis por `session_id`, incluyendo el contrato de API (`session_id`), el historial acumulado en el grafo y el ciclo de vida del checkpointer.

### Modified Capabilities
<!-- No existe spec `butler` en openspec/specs/ (init-butler-graph sin archivar), así que el contrato de /api/butler/ask se cubre dentro de la nueva capability conversation-memory. -->

## Impact

- **Slice afectado**: `app/features/butler/` — `graph/graph.py` (compile con checkpointer), `graph/state.py` (`messages` + reducer), `graph/nodes.py` (usar historial), `service.py` (`run(message, session_id)` + config thread_id), `schemas.py` (`AskRequest.session_id`), `router.py` (propagar session_id).
- **Core**: `app/core/settings.py` (`redis_url`), `app/core/lifespan.py` (crear/cerrar checkpointer Redis, `setup`), posible nuevo `app/core/redis.py` (cliente/pool).
- **Infra**: `docker-compose.yml` (servicio `redis` + volumen + healthcheck), `.example.env` (`REDIS_URL`). El `Dockerfile` del backend no cambia (redis es un servicio aparte del compose).
- **Dependencias**: `langgraph-checkpoint-redis` (+ `redis`). Confirmación del usuario antes de `uv add`.
- **Sin cambios de datos relacionales**: no toca PostgreSQL ni requiere migración Alembic. El estado conversacional vive en Redis (con TTL).
- **Contrato de API (no breaking)**: `session_id` es opcional; el mod Java puede enviarlo para obtener memoria persistente. Sin él, el comportamiento es como hoy (sin memoria entre peticiones).
- **Tests**: `tests/test_api.py` / `tests/features/butler/` (servicio con session_id, persistencia multi-turn, propagación de thread_id).
