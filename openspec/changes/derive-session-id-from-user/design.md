## Context

Los endpoints del butler (`/api/butler/ask`, `/ask-voice`, `/ask-stream`, `/ask-voice-stream`)
están autenticados (`Depends(get_authenticated_user)`), pero el router descarta el usuario
(`_user`) y no lo propaga al servicio. `ButlerService.run()` y `stream()` resuelven el hilo así:

```python
thread_id = session_id or f"ephemeral-{uuid4()}"
```

Como el cliente no envía `session_id`, cada petición genera un hilo efímero y la memoria
(LangGraph + checkpointer Redis) nunca se reutiliza entre turnos. Verificado en vivo: con
`session_id` fijo el butler recuerda; sin él, olvida; y en Redis los 14 hilos existentes son
todos `ephemeral-…`.

## Goals / Non-Goals

**Goals:**
- Dar memoria persistente por defecto usando el **usuario autenticado** como identidad de sesión
  cuando no se envía `session_id`.
- No cambiar el comportamiento cuando el cliente **sí** envía `session_id`.
- Cambio mínimo y localizado en el slice `butler` (router + service).

**Non-Goals:**
- No se cambia el modelo de datos ni el TTL de Redis.
- No se namespacea el `session_id` explícito bajo el usuario (aislamiento entre usuarios con
  `session_id` colisionantes); se anota como posible mejora futura, fuera de alcance.
- No se añade gestión de múltiples conversaciones nombradas ni UI de sesiones.

## Decisions

### Decisión 1: Precedencia de `thread_id`
Resolver el hilo con esta prioridad:

```
thread_id = session_id            (si viene explícito → conversación a medida)
          | f"user-{user_id}"      (autenticado, sin session_id → memoria por usuario)
          | f"ephemeral-{uuid4()}" (salvaguarda: sin usuario; no esperable en endpoints auth)
```

Centralizar en un helper privado `_resolve_thread_id(session_id, user_id)` en `service.py`,
usado tanto por `run()` como por `_run_graph_to_queue()` (streaming), para no duplicar la lógica.

**Por qué `user-{id}`:** prefijo legible y estable; distingue los hilos por usuario de los
efímeros heredados en Redis. Una conversación persistente por usuario encaja con el modelo
"un butler por jugador".

### Decisión 2: Propagar el usuario desde el router
Renombrar `_user` → `user` en los 4 endpoints y pasar `user_id=user.id` a `service.run()` /
`service.stream()`. El router sigue delgado (solo pasa el id; la lógica de resolución vive en el
service).

**Alternativa considerada:** resolver el `thread_id` en el router y pasar `session_id` ya
calculado. Descartada: mete lógica de negocio en el router (contra la arquitectura por slices) y
duplica el cálculo entre endpoints.

### Decisión 3: Firma del servicio
`run()` y `stream()` añaden un parámetro `user_id: int | None = None` (keyword, con default para
no romper llamadas existentes en tests). `_run_graph_to_queue()` lo recibe y lo usa al construir
`config`. El `metadata` del run de streaming puede incluir `user_id` para trazabilidad en LangSmith.

### Capas afectadas (backend)
- **router.py** — propaga `user.id` en los 4 endpoints.
- **service.py** — `_resolve_thread_id()` + `user_id` en `run()`/`stream()`/`_run_graph_to_queue()`.
- **repository.py / models.py** — sin cambios. Sin acceso a datos nuevos.
- **Migraciones Alembic** — ninguna.

> Nota de proceso: plan técnico breve a nivel de archivos en
> `.claude/doc/derive-session-id-from-user/backend.md` antes de `/opsx:apply`.

## Risks / Trade-offs

- **[Cambio de comportamiento por defecto]** → Clientes que no enviaban `session_id` pasan de
  "sin memoria" a "memoria por usuario". Es la mejora buscada; el contrato HTTP (campo opcional)
  no cambia. Se documenta en `docs/`/`ARCHITECTURE.md`.
- **[Colisión de `session_id` entre usuarios]** → Pre-existente y fuera de alcance: dos usuarios
  que envíen el mismo `session_id` comparten hilo. Mitigación futura: namespacear como
  `f"{user_id}:{session_id}"`. Se deja anotado, sin implementar aquí.
- **[Persistencia inesperada para el mismo usuario]** → Todas las peticiones sin `session_id` de
  un usuario comparten un hilo y acumulan historia (hasta el TTL de 24h). Es el comportamiento
  deseado; si se quiere segmentar, el cliente envía `session_id`.
- **[Tests que llamaban al servicio sin `user_id`]** → El parámetro es opcional con default
  `None` (cae a efímero), preservando los tests existentes que no lo pasan.
