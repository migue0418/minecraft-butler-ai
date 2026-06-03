## ADDED Requirements

### Requirement: Endpoint SSE POST /api/butler/ask-stream
El sistema SHALL exponer `POST /api/butler/ask-stream` protegido por JWT con el mismo body que `/ask` (`message`, `session_id`, `world_context` opcionales). La respuesta SHALL ser `text/event-stream` con eventos SSE. El primer evento SHALL ser el echo del mensaje del usuario. Cada `ButlerAction` SHALL emitirse como evento SSE en cuanto el nodo del grafo que la genera complete, sin esperar a las demás. El último evento SHALL ser `data: [DONE]`.

#### Scenario: Primer evento es el echo del mensaje del usuario
- **WHEN** un cliente autenticado envía `{"message": "hola Alfred"}` a `/api/butler/ask-stream`
- **THEN** el primer evento SSE es `data: {"type":"echo","message":"[Tú] hola Alfred"}` antes de que el grafo empiece a procesar

#### Scenario: Las acciones llegan conforme el grafo las genera
- **WHEN** el grafo genera dos acciones `speak` en secuencia
- **THEN** la primera acción llega como evento SSE antes de que la segunda esté lista (no se acumulan)

#### Scenario: El stream termina con [DONE]
- **WHEN** el grafo ha emitido todas sus acciones
- **THEN** el servidor envía `data: [DONE]` y cierra el stream

#### Scenario: Petición sin autenticar devuelve 401
- **WHEN** se llama a `/api/butler/ask-stream` sin token JWT
- **THEN** el servidor responde 401 (no inicia el stream)

#### Scenario: Rate limit devuelve 429
- **WHEN** una IP supera 20 peticiones por minuto
- **THEN** el servidor responde 429 (no inicia el stream)

### Requirement: Endpoint SSE POST /api/butler/ask-voice-stream
El sistema SHALL exponer `POST /api/butler/ask-voice-stream` con el mismo contrato multipart que `/ask-voice` (`audio`, `session_id`, `world_context` opcionales). Tras transcribir el audio, el primer evento SSE SHALL ser el echo del transcript. El resto del protocolo es idéntico a `/ask-stream`.

#### Scenario: Echo contiene el transcript del audio
- **WHEN** un cliente envía audio con el mensaje "¿hay peligro cerca?"
- **THEN** el primer evento SSE es `data: {"type":"echo","message":"[Tú] 🎤 ¿hay peligro cerca?"}` (o similar con indicador de voz)

#### Scenario: Audio inválido devuelve 422 antes de iniciar el stream
- **WHEN** se envía audio vacío a `/api/butler/ask-voice-stream`
- **THEN** el servidor responde 422 (no inicia el stream)

### Requirement: Formato del evento echo
El evento echo SHALL tener `type: "echo"` y el campo `message` con el texto del usuario precedido de un prefijo identificable (p. ej. `"[Tú] "` para texto, `"[Tú] 🎤 "` para voz). Este formato permite al cliente distinguir el echo de las respuestas de Alfred y mostrarlo de forma diferenciada.

#### Scenario: Echo de texto tiene prefijo [Tú]
- **WHEN** el usuario envía el mensaje "¿cómo crafteo una espada?"
- **THEN** el evento echo contiene `"message": "[Tú] ¿cómo crafteo una espada?"`

#### Scenario: Echo de voz tiene indicador de micrófono
- **WHEN** el usuario envía audio que se transcribe como "muévete aquí"
- **THEN** el evento echo contiene `"message": "[Tú] 🎤 muévete aquí"`
