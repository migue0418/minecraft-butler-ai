## Context

`ButlerService.stream()` actualmente usa `graph.astream(stream_mode="values")` que emite el estado completo del grafo tras cada nodo. El nodo `speak_action`/`answer_question` llama al LLM y espera la respuesta entera antes de escribir al estado, por lo que el único evento de texto llega al final del todo.

Para emitir el texto frase a frase mientras el LLM genera, se necesita `graph.astream_events(version="v2")` que expone eventos de bajo nivel incluyendo `on_chat_model_stream` con cada token del LLM según llega.

El helper `_flush_at_boundaries` acumula tokens en un buffer y cada vez que detecta una frontera natural (punto, exclamación, interrogación, salto de línea, encabezado markdown) separa el texto en chunks y los devuelve listos para emitir.

## Goals / Non-Goals

**Goals:**
- Alfred escribe frase a frase conforme el LLM genera.
- Mínimo cambio: solo `service.py`.
- Acciones no-LLM (`move_to_position`) siguen funcionando.
- El mod Java no necesita cambios.

**Non-Goals:**
- Modificar el grafo, los nodos ni el router.
- Token a token (demasiado granular para Minecraft chat).
- Cambiar el comportamiento del endpoint no-streaming (`run()`).

## Decisions

### D1 — `astream_events(version="v2")` en lugar de `astream`

`astream_events` expone `on_chat_model_stream` con el content de cada token. Filtramos por `langgraph_node` para capturar solo los nodos que generan texto (`speak_action`, `answer_question`). El nodo `classify_intent` también llama al LLM pero con structured output — sus tokens no forman texto legible y no se deben emitir.

**Alternativa descartada:** Modificar los nodos para que hagan `llm.astream()` y acumulen tokens internamente. Mezcla responsabilidades: los nodos deben ser stateless; el buffering de streaming es responsabilidad del service.

### D2 — Frontera de chunk: `.`, `!`, `?`, `\n`, `##`

```python
BOUNDARY = re.compile(r'(?<=[.!?])\s+|(?<=\n)|(?=##\s)')
```

- `(?<=[.!?])\s+` — fin de frase seguido de espacio (evita `3.14` o `Sr.`)
- `(?<=\n)` — cualquier salto de línea
- `(?=##\s)` — inicio de encabezado markdown (LLM a veces usa `## Recomendaciones:`)

Si no hay frontera aún, el buffer se mantiene hasta el próximo token. Esto garantiza que no se emite un chunk a mitad de una palabra.

**Caso borde:** el LLM puede enviar `.` y el espacio siguiente en tokens separados. El lookbehind `(?<=[.!?])\s+` requiere el espacio en el mismo token o en la concatenación. Se resuelve acumulando en el buffer y evaluando el texto completo (no token a token) en cada llegada.

### D3 — `on_chain_end` de `move_action` para acciones no-LLM

`move_action` no genera tokens de LLM (usa regex). Su resultado queda en `event["data"]["output"]["actions"]` cuando el nodo termina. Se captura ahí y se emite como `ButlerAction`.

### D4 — Buffer vacío al terminar el nodo (`on_chain_end`)

Cuando `speak_action`/`answer_question` termina, el buffer puede tener texto residual que no llegó a formar una frontera (p. ej. la última frase sin punto final). Se emite como último chunk con `on_chain_end`.

### D5 — Compatibilidad con `with_retry`

Los nodos tienen `.with_retry(stop_after_attempt=3)` de `butler-resilience-observability`. Los eventos `on_chat_model_stream` vienen del modelo subyacente y atraviesan el wrapper de retry sin problema. Si un reintento ocurre, los tokens del primer intento fallido ya habrán sido emitidos — hay que limpiar el buffer al detectar un reintento (identificable porque el mismo nodo emite `on_chain_start` de nuevo). **Solución simple:** resetear el buffer en cada `on_chain_start` del nodo responder.

## Risks / Trade-offs

- **Chunks muy cortos**: una respuesta con muchas frases cortas genera muchos mensajes en el chat. Mitigación: el threshold de frontera es conservador (solo `.` seguido de espacio, no cualquier punto).
- **Retry + buffer**: si el LLM falla y reintenta, los tokens del primer intento ya se emitieron. Resetear el buffer en `on_chain_start` del nodo evita duplicados. Esto puede resultar en un mensaje truncado en el chat antes de que llegue la respuesta correcta — comportamiento aceptable para el MVP.
- **`on_chat_model_stream` de `classify_intent`**: el clasificador usa structured output; sus "tokens" son JSON parcial (`{"intent":"`). El filtro por `langgraph_node in ("speak_action", "answer_question")` los excluye.
