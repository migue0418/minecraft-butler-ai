## Context

El grafo LangGraph actual usa `graph.ainvoke()` que espera a que todos los nodos completen antes de devolver el estado final. Para streaming, se necesita `graph.astream()` con `stream_mode="values"` que emite el estado completo del grafo tras cada nodo. Al comparar el estado actual con el anterior podemos detectar nuevas `ButlerAction` y emitirlas inmediatamente.

Los endpoints actuales (`/ask`, `/ask-voice`) no se modifican — los nuevos son `/ask-stream` y `/ask-voice-stream` con `StreamingResponse` de Starlette/FastAPI devolviendo `text/event-stream`.

## Goals / Non-Goals

**Goals:**
- Echo del mensaje del usuario como primer evento (antes de que el grafo procese).
- Cada `ButlerAction` emitida en cuanto su nodo termina, no al final de todo.
- Retrocompatibilidad total: los endpoints no-streaming siguen iguales.
- Rate limiting en los endpoints streaming.
- Documentar el protocolo SSE para el cliente Java.

**Non-Goals:**
- Streaming token a token del LLM (requeriría `astream_events` y parsear tokens parciales — sobre-ingeniería para este caso; las acciones completas son la unidad correcta).
- WebSocket (SSE es suficiente para unidireccional servidor→cliente).
- Modificar el grafo ni la lógica de nodos.

## Decisions

### D1 — `graph.astream(stream_mode="values")` para detectar nuevas acciones

```python
async def stream(self, message, session_id, input_mode, world_context):
    graph = await get_compiled_graph()
    thread_id = session_id or f"ephemeral-{uuid4()}"
    config = {...}
    sent = 0
    async for state in graph.astream(initial_state, config, stream_mode="values"):
        actions = state.get("actions", [])
        for action in actions[sent:]:
            yield ButlerAction(**action)
            sent += 1
```

Cada vez que un nodo completa y escribe nuevas acciones al estado, `astream` emite el estado actualizado. Se trackea cuántas acciones ya se emitieron (`sent`) para emitir solo las nuevas.

**Alternativa descartada:** `astream_events` con `version="v2"`. Más potente pero requiere filtrar eventos `on_chain_end` por nombre de nodo, más frágil ante cambios de topología del grafo.

### D2 — Protocolo SSE simple

```
POST /api/butler/ask-stream
Content-Type: application/json
Authorization: Bearer <token>

{"message": "...", "session_id": "...", "world_context": {...}}

→ HTTP 200 text/event-stream
data: {"type":"echo","message":"[Tú] ¿hay peligro cerca?"}

data: {"type":"speak","message":"¡Sí! Hay un zombie a 10 bloques..."}

data: [DONE]
```

Cada línea SSE: `data: <JSON>\n\n`. El evento de echo lleva `type: "echo"` para que el cliente pueda distinguirlo y mostrarlo de forma diferente (p. ej. en gris o con icono). El evento `[DONE]` señala el fin del stream.

### D3 — Echo antes de iniciar el grafo

El echo se emite sincrónicamente antes de llamar a `graph.astream()`. Para voz, primero se transcribe (aún síncrono con `to_thread`) y luego se emite el echo con el transcript.

```python
async def event_gen():
    yield f'data: {{"type":"echo","message":"[Tú] {escape(message)}"}}\n\n'
    async for action in service.stream(...):
        yield f"data: {json.dumps(action.model_dump(exclude_none=True))}\n\n"
    yield "data: [DONE]\n\n"
```

### D4 — Rate limiting en streaming

`@limiter.limit("20/minute")` igual que en los endpoints no-streaming. SlowAPI aplica el límite antes de que empiece el generador SSE, por lo que un 429 se devuelve como respuesta HTTP normal (no como evento SSE).

### D5 — `StreamEvent` en schemas.py

```python
class StreamEvent(BaseModel):
    type: str   # "echo" | "speak" | "move_to_position"
    message: str
    x: int | None = None
    y: int | None = None
    z: int | None = None
```

Es idéntico a `ButlerAction` pero con `type` extendido para incluir `"echo"`. Se puede usar el mismo modelo o crear un alias.

---

## Guía para el cliente Java (Fabric mod)

El mod Java necesita consumir el stream SSE. El patrón con `java.net.http.HttpClient`:

### Método `sendStreamAsync` en `ButlerHttpClient.java`

```java
public static CompletableFuture<Void> sendStreamAsync(
        String message,
        Consumer<ButlerAction> onAction,
        Runnable onDone,
        Consumer<Throwable> onError) {

    JsonObject body = new JsonObject();
    body.addProperty("message", message);
    // añadir session_id y world_context igual que sendAsync

    HttpRequest req = HttpRequest.newBuilder()
            .uri(URI.create(BASE_URL + "/api/butler/ask-stream"))
            .header("Content-Type", "application/json")
            .header("Authorization", "Bearer " + cachedToken)
            .header("Accept", "text/event-stream")
            .POST(HttpRequest.BodyPublishers.ofString(body.toString()))
            .build();

    return HTTP.sendAsync(req, HttpResponse.BodyHandlers.ofLines())
            .thenAccept(resp -> {
                resp.body().forEach(line -> {
                    if (!line.startsWith("data: ")) return;
                    String data = line.substring(6).trim();
                    if ("[DONE]".equals(data)) {
                        onDone.run();
                        return;
                    }
                    try {
                        JsonObject obj = GSON.fromJson(data, JsonObject.class);
                        String type = obj.get("type").getAsString();
                        String msg = obj.get("message").getAsString();

                        if ("echo".equals(type)) {
                            // Mostrar input del usuario en el chat (en gris o con prefijo)
                            onAction.accept(new ButlerAction("echo", msg, null, null, null));
                        } else {
                            onAction.accept(new ButlerAction(type, msg,
                                obj.has("x") && !obj.get("x").isJsonNull() ? obj.get("x").getAsInt() : null,
                                obj.has("y") && !obj.get("y").isJsonNull() ? obj.get("y").getAsInt() : null,
                                obj.has("z") && !obj.get("z").isJsonNull() ? obj.get("z").getAsInt() : null));
                        }
                    } catch (Exception e) {
                        AIButler.LOGGER.warn("Error parsing SSE event: {}", data);
                    }
                });
            })
            .exceptionally(ex -> { onError.accept(ex); return null; });
}
```

**Clave:** `BodyHandlers.ofLines()` devuelve un `Stream<String>` lazy que procesa cada línea conforme llega del servidor. Cada `.forEach()` se ejecuta en el hilo del CompletableFuture, por lo que `onAction` debe hacer `server.execute(() -> ...)` para ejecutar en el hilo del servidor.

### En `ButlerCommand.java` (comando `/butler ask`)

```java
// ANTES (no streaming):
ButlerHttpClient.sendAsync(message, worldCtx)
    .thenAccept(actions -> server.execute(() ->
        actions.forEach(a -> ButlerActionExecutor.execute(a, source))));

// DESPUÉS (streaming):
ButlerHttpClient.sendStreamAsync(
    message,
    action -> server.execute(() -> ButlerActionExecutor.execute(action, source)),
    () -> { /* stream completado */ },
    err -> server.execute(() -> source.sendSuccess(
        () -> Component.literal("[Alfred] Error de conexión."), false))
);
```

### En `VoiceKeyBinding.java` (push-to-talk)

Igual pero llamando a `/api/butler/ask-voice-stream` con multipart. La voz tiene una particularidad: la transcripción ocurre en el servidor antes del echo, así que el jugador verá `[Tú] 🎤 <lo que dijo>` unos instantes después de soltar la tecla.

### En `ButlerActionExecutor.java` — acción "echo"

Añadir el case `"echo"` para mostrar el mensaje del usuario de forma diferenciada:

```java
case "echo" ->
    source.sendSuccess(
        () -> Component.literal("§7" + action.message()),  // §7 = gris en Minecraft
        false);
```

El código `§7` pone el texto en gris oscuro, diferenciando visualmente el input del usuario de las respuestas de Alfred.

## Risks / Trade-offs

- **`BodyHandlers.ofLines()` bloquea mientras hay stream activo**: el `forEach` retiene el hilo del CompletableFuture hasta que llega `[DONE]`. Con virtual threads (Java 25, ya en el proyecto) esto es trivial.
- **Timeout de la conexión SSE**: si el grafo tarda más de N segundos, el mod puede cortar la conexión. El timeout del `HttpClient` por defecto es ilimitado; se puede añadir `.timeout(Duration.ofSeconds(30))` al request si se quiere proteger.
- **Rate limit 429 como respuesta HTTP**: el cliente Java debe tratar el 401/429 antes de intentar parsear el body como SSE. El patrón de retry de auth existente en `sendAsync` debe portarse a `sendStreamAsync`.
