## Why

El butler actualmente guarda silencio mientras procesa y responde todo de golpe. Con mensajes de 2-4 frases y un LLM que tarda 2-4 segundos, la experiencia se siente como una carga: el jugador no sabe si la petición llegó, ni cuándo llegará la respuesta. Hay dos mejoras complementarias que juntas hacen la conversación mucho más natural: (1) mostrar lo que el jugador dijo/habló inmediatamente como primer mensaje del chat, y (2) enviar las `ButlerAction` al cliente conforme el grafo LangGraph las va generando en lugar de esperar a que todas estén listas.

Minecraft no permite editar mensajes ya escritos, por lo que el "streaming" aquí significa emitir cada `ButlerAction` completa como un evento SSE en cuanto el nodo correspondiente del grafo termina, no token a token.

## What Changes

- **Dos endpoints nuevos con SSE**: `POST /api/butler/ask-stream` y `POST /api/butler/ask-voice-stream` que devuelven `text/event-stream`. Los endpoints `/ask` y `/ask-voice` existentes no se tocan (retrocompatibles).
- **Echo del input del usuario**: el primer evento SSE es siempre `{"type": "echo", "message": "[Tú] <texto>"}` (o `"[Tú] 🎤 <transcript>"` para voz), emitido antes de que el grafo empiece a procesar.
- **`ButlerService.stream()`**: nuevo método async generator que usa `graph.astream()` con `stream_mode="values"` para detectar nuevas `ButlerAction` conforme los nodos del grafo completan y emitirlas en cuanto están listas.
- **Formato de evento SSE**: `data: <JSON de ButlerAction>\n\n`. Evento de cierre: `data: [DONE]\n\n`.
- Rate limiting: los endpoints streaming también tienen `@limiter.limit("20/minute")`.
- **Guía para el cliente Java**: documentada en el design para que pueda implementarse de forma independiente.

## Capabilities

### New Capabilities

- `butler-streaming`: endpoints SSE para recibir respuestas del butler en tiempo real, incluyendo el echo del mensaje del usuario como primer evento.

### Modified Capabilities

*(ninguna — los endpoints existentes no cambian)*

## Impact

- **Slice `butler`**: `service.py` (nuevo método `stream`), `router.py` (dos endpoints nuevos), `schemas.py` (nuevo modelo `StreamEvent`).
- Sin cambios de BD, migraciones ni dependencias nuevas (`StreamingResponse` está en FastAPI/Starlette).
- Retrocompatible: los endpoints `/ask` y `/ask-voice` siguen funcionando exactamente igual.
