## Context

Los endpoints `/api/butler/ask-stream` y `/api/butler/ask-voice-stream` exponen la respuesta del agente como SSE. Hoy, `ButlerService.stream()` ([app/features/butler/service.py](../../../app/features/butler/service.py)) es un async generator que:

1. Obtiene el grafo compilado.
2. Itera `graph.astream_events(initial_state, config, version="v2")`.
3. Por cada evento, acumula tokens y emite `ButlerAction` en fronteras de frase.

El router envuelve ese generador en otro generador (`generate()`) que añade el echo inicial y `[DONE]`, y lo pasa a `StreamingResponse`.

**Estado actual del problema.** FastAPI consume el generador final en un contexto de ejecución distinto al de la petición. LangSmith construye el árbol de runs a partir de un `contextvar` que apunta al run padre actual; al ejecutarse `astream_events` **dentro** del generador que FastAPI drena, ese `contextvar` no se propaga de forma coherente entre los puntos de suspensión (`yield`). Resultado: el run raíz `butler-{mode}-stream` se crea (primer evento) pero los runs hijos de los nodos quedan huérfanos o se descartan, dejando una traza plana input→output. Causa raíz confirmada en [langsmith-sdk #817](https://github.com/langchain-ai/langsmith-sdk/issues/817).

El camino no-streaming (`run()` → `graph.ainvoke()`) no sufre esto porque la ejecución del grafo y el cierre de callbacks ocurren íntegramente dentro del handler, en un único contexto, antes de devolver.

## Goals / Non-Goals

**Goals:**
- Que las trazas de los endpoints de streaming muestren el **árbol completo de nodos** del grafo en LangSmith, igual que el camino `ainvoke`.
- Preservar exactamente el comportamiento observable de streaming: troceado por frases, echo del usuario, eventos `move_to_position`, marcador `[DONE]`, orden de emisión.
- Preservar el manejo de **desconexión del cliente**: sin tasks de fondo huérfanas ni fugas de recursos cuando el consumidor se cancela.
- Propagar las excepciones del grafo al consumidor (no tragarlas en silencio).

**Non-Goals:**
- No se toca el camino no-streaming (`/ask`, `/ask-voice`).
- No se cambia el contrato HTTP/SSE ni el formato de los `ButlerAction`.
- No se modifican los nodos del grafo, el RAG, ni la configuración de tracing del `lifespan`.
- No se añade verificación automatizada de la UI de LangSmith (no es testeable en pytest); la confirmación visual es manual.

## Decisions

### Decisión 1: Patrón productor/consumidor con `asyncio.Queue`

La ejecución del grafo se mueve a una **task de fondo** (productor) creada con `asyncio.create_task`. El productor itera `astream_events` **completo dentro de su propia task** y empuja cada `ButlerAction` a una `asyncio.Queue`. `ButlerService.stream()` pasa a ser un consumidor que solo hace `await queue.get()` y los reproduce.

```
   ButlerService.stream()  (consumidor, lo drena FastAPI)
        │
        ├─ crea queue = asyncio.Queue()
        ├─ producer = asyncio.create_task(_run_graph_to_queue(queue, ...))
        │
        │   ┌──────────────────────────────────────────────────────────┐
        │   │ _run_graph_to_queue  (productor, task propia y estable)   │
        │   │   async for event in graph.astream_events(...):           │
        │   │       ... corte por frases ...                            │
        │   │       await queue.put(action)   ← tracing coherente ✅     │
        │   │   await queue.put(_SENTINEL)                              │
        │   └──────────────────────────────────────────────────────────┘
        │
        └─ while True:
               item = await queue.get()
               if item is _SENTINEL: break
               if isinstance(item, Exception): raise item
               yield item
```

**Por qué funciona para el tracing.** `astream_events` corre de principio a fin dentro de **una sola task** (el productor), sin que su `contextvar` de run padre se vea interrumpido por la forma en que FastAPI drena el consumidor. El árbol root+nodos se construye y se cierra en un contexto coherente. `asyncio.create_task` copia el contexto actual al crear la task, manteniendo la configuración de tracing del entorno.

**Alternativas consideradas:**
- **`wait_for_all_tracers()` al final del generador.** Solo fuerza el *flush*, no arregla la **ruptura de anidación** del `contextvar`; los hijos seguirían huérfanos. Descartada.
- **Envolver el bucle en `tracing_context(...)` / `tracing_v2_enabled()`.** Reestablece el flag de tracing pero no garantiza un padre estable a través de los `yield` que conducen a `StreamingResponse`. Frágil y dependiente de versión. Descartada.
- **Cambiar a `graph.astream(stream_mode=...)`.** Cambiaría la fuente de los tokens (`messages`/`updates` en vez de `on_chat_model_stream`) y obligaría a reescribir toda la lógica de corte por frases, con más superficie de regresión. El patrón productor/cola es ortogonal y conserva la lógica actual. Descartada para este cambio.

### Decisión 2: Sentinela de fin + propagación de excepciones por la cola

El productor señala el fin con un objeto centinela único (`_STREAM_DONE = object()`). Si `astream_events` lanza, el productor captura la excepción y la **pone en la cola** (en lugar del centinela); el consumidor la **re-lanza**, de modo que el error aflora donde hoy aflora (y el router puede gestionarlo). Esto evita que una excepción en la task de fondo quede silenciada (anti-patrón de *silent failure*).

### Decisión 3: Cancelación limpia ante desconexión del cliente

Cuando el cliente cierra la conexión, FastAPI cancela el consumidor. `stream()` envuelve su bucle en `try/finally`: en el `finally`, si la task productora sigue viva, la **cancela** y la espera (`await` con `contextlib.suppress(asyncio.CancelledError)`). Así no quedan tasks de fondo ejecutando el grafo tras la desconexión.

### Decisión 4: Sin cambios en el router (salvo verificación)

`generate()` en [router.py](../../../app/features/butler/router.py) sigue igual: itera `service.stream(...)` y añade echo + `[DONE]`. La corrección vive en el service, manteniendo el router delgado conforme a la arquitectura por slices. Se revisa que la propagación de excepciones no rompa el `StreamingResponse` (un error a mitad de stream cerrará la conexión, comportamiento aceptable y actual).

### Capas afectadas (backend)

- **router.py** — sin cambios funcionales; solo se valida que sigue drenando `service.stream()`.
- **service.py** — núcleo del cambio: `stream()` reescrito como consumidor + helper privado `_run_graph_to_queue()` productor. La lógica de corte por frases (`_flush_at_boundaries`, `_BOUNDARY`, manejo de `_RESPONDER_NODES` y `move_action`) se traslada al productor sin alterar su semántica.
- **repository.py / models.py** — no aplica. Sin acceso a datos ni modelos nuevos.
- **Migraciones Alembic** — ninguna. El cambio no toca el modelo de datos.

> Nota de proceso: antes de `/opsx:apply` se generará el plan técnico a nivel de archivos con el agente `backend-developer` en `.claude/doc/fix-langsmith-streaming-traces/backend.md`, conforme a las reglas del repo.

## Risks / Trade-offs

- **[Regresión en el troceado por frases al mover la lógica al productor]** → Mantener `_flush_at_boundaries`, `_BOUNDARY` y el manejo de buffer/retry idénticos; cubrir con tests unitarios que comparen la secuencia de `ButlerAction` emitida antes/después para entradas representativas (pregunta con RAG, move con coordenadas, saludo).
- **[Task productora huérfana si el consumidor muere sin cancelar]** → `try/finally` que cancela y espera la task; test que simule consumo parcial y verifique que la task queda cancelada.
- **[Excepción del grafo silenciada en la task de fondo]** → Propagación explícita de la excepción por la cola y re-lanzado en el consumidor; test que fuerce un fallo del grafo y verifique que `stream()` lo re-lanza.
- **[Back-pressure / memoria si el productor va muy por delante del consumidor]** → Usar `asyncio.Queue(maxsize=N)` acotada para que `queue.put` aplique contrapresión natural; el productor se suspende si el cliente consume lento.
- **[La corrección depende de comportamiento interno de LangSmith/LangGraph]** → La verificación final es manual en la UI; se documenta el resultado (captura/observación) en el informe del cambio. Si una versión futura cambia la propagación de contexto, el patrón productor/cola sigue siendo correcto funcionalmente aunque el tracing se reevalúe.

## Open Questions

- ¿Valor de `maxsize` de la cola? Propuesta: pequeño (p. ej. 32) — suficiente para no bloquear el troceado por frases y a la vez aplicar contrapresión. A confirmar en implementación.
- ¿El centinela debe distinguir "fin normal" de "fin por cancelación"? Propuesta: no; el `finally` del consumidor cubre la cancelación y el centinela solo marca fin normal.
