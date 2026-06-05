## Why

Los endpoints de streaming del butler (`/api/butler/ask-stream` y `/api/butler/ask-voice-stream`) producen trazas **planas** en LangSmith: solo aparece el run raíz `butler-{mode}-stream` con input→output, sin el árbol de nodos del grafo (`classify_intent`, `retrieve_context`, `answer_question`...). Esto incumple la requirement de observabilidad existente (que promete "la latencia de cada nodo") y deja la depuración del agente ciega justo en el camino que se usa en producción. La causa raíz está confirmada ([langsmith-sdk #817](https://github.com/langchain-ai/langsmith-sdk/issues/817)): el grafo se ejecuta **dentro** del async generator que FastAPI consume en otro contexto de ejecución, lo que rompe la propagación del `contextvar` del run padre y desvincula los nodos hijos.

## What Changes

- Refactor del método `ButlerService.stream()` para **desacoplar la ejecución del grafo del generador SSE** mediante un patrón productor/consumidor con `asyncio.Queue`:
  - Una **task de fondo** (productor) ejecuta `graph.astream_events(...)` en un contexto de tracing estable y empuja los `ButlerAction` a la cola.
  - El generador que consume `StreamingResponse` (consumidor) solo **drena la cola** y emite SSE, sin tocar el contexto de tracing.
- Se preserva el comportamiento observable actual: streaming **por frases** (corte en fronteras de fin de frase), echo del usuario, eventos `move_to_position` y el marcador `[DONE]`.
- Se preserva el **manejo de desconexión del cliente**: si el consumidor se cancela, la task productora se cancela limpiamente (sin tasks huérfanas ni fugas).
- Se propaga la corrección a los dos endpoints de streaming, que comparten `service.stream()`.
- NO se modifica el camino no-streaming (`/ask`, `/ask-voice` vía `run()` → `ainvoke`), que ya traza correctamente.

## Capabilities

### New Capabilities
<!-- Ninguna. El cambio corrige el comportamiento de una capability existente. -->

### Modified Capabilities
- `butler-graph`: la requirement "Observabilidad con LangSmith" se refina para exigir explícitamente que el **árbol completo de nodos** se conserve también en los caminos de **streaming**, no solo en las invocaciones `ainvoke`. Hoy el spec promete "la latencia de cada nodo" sin distinguir streaming, y el streaming lo incumple.

## Impact

- **Slice afectado**: `butler` (backend).
  - `app/features/butler/service.py` → método `stream()` (reescritura del bucle de consumo de eventos con productor/cola).
  - `app/features/butler/router.py` → generadores de `ask_stream` y `ask_voice_stream` (sin cambios de contrato; siguen drenando `service.stream()`).
- **Contrato HTTP**: sin cambios. Mismos endpoints, mismo formato SSE (`data: {json}\n\n`, echo inicial, `[DONE]` final), mismos `ButlerAction`.
- **Datos**: ninguno. No toca modelos SQLAlchemy ni requiere migración Alembic.
- **Dependencias**: ninguna nueva (se usa `asyncio` de la stdlib; LangGraph/LangSmith ya presentes).
- **Verificación**: requiere confirmación manual en la UI de LangSmith de que la traza de streaming vuelve a mostrar el árbol de nodos. La suite de pytest no cubre la UI de tracing, así que se añade cobertura del comportamiento del productor/cola (orden de acciones, cancelación) sin depender de LangSmith.
