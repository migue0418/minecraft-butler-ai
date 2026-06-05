## Why

La memoria conversacional del butler funciona (Redis + checkpointer verificados: con un `session_id` estable recuerda turnos anteriores), pero en la práctica **nunca se usa**: el cliente no envía un `session_id`, así que cada petición cae en la rama `thread_id = session_id or f"ephemeral-{uuid4()}"` y abre un hilo nuevo. Evidencia: de 14 hilos en Redis, los 14 son efímeros y 0 tienen un `session_id` real. Resultado percibido: "no hay historial" (y se culpa erróneamente a Redis). Como los endpoints del butler están autenticados, podemos usar el **usuario autenticado** como sesión por defecto y dar memoria persistente sin depender de que el cliente gestione nada.

## What Changes

- Cuando la petición **no** trae `session_id`, derivar el `thread_id` del **usuario autenticado** (`user-{user_id}`) en lugar de un hilo efímero. Así cada jugador tiene un butler con memoria persistente por defecto.
- Mantener la precedencia: un `session_id` explícito **sigue mandando** (permite varias conversaciones por usuario). El hilo efímero queda solo como salvaguarda si no hubiera usuario (no debería ocurrir en endpoints autenticados).
- Pasar el id del usuario autenticado desde el router al `ButlerService` (hoy el router ya depende de `get_authenticated_user` pero no propaga el id).
- Aplica a los cuatro endpoints que usan el grafo: `/ask`, `/ask-voice`, `/ask-stream`, `/ask-voice-stream`.

## Capabilities

### New Capabilities
<!-- Ninguna. -->

### Modified Capabilities
- `conversation-memory`: se modifica el criterio de `thread_id` y el contrato de `session_id` opcional. Antes: sin `session_id` → hilo efímero, sin memoria. Ahora: sin `session_id` → `thread_id` derivado del usuario autenticado, con memoria persistente. El comportamiento con `session_id` explícito no cambia.

## Impact

- **Slice afectado**: `butler` (backend).
  - `app/features/butler/router.py` → propagar `user.id` al servicio en los 4 endpoints.
  - `app/features/butler/service.py` → `run()` y `stream()`/`_run_graph_to_queue()` aceptan `user_id`; helper para resolver `thread_id` (`session_id` → `user-{id}` → efímero).
- **Contrato HTTP**: sin cambios de forma. `session_id` sigue siendo opcional; cambia el comportamiento por defecto cuando se omite (ahora persiste por usuario).
- **Datos**: ninguno. Sin modelos SQLAlchemy ni migración Alembic. La memoria vive en Redis con su TTL actual.
- **Dependencias**: ninguna nueva.
- **Compatibilidad**: clientes que ya enviaban `session_id` no se ven afectados. Clientes que no lo enviaban pasan de "sin memoria" a "memoria por usuario" (mejora, no ruptura del contrato HTTP).
