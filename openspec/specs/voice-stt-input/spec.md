# voice-stt-input Specification

## Purpose
Entrada de voz al butler mediante transcripción local con faster-whisper. Expone un endpoint de voz que acepta audio, lo transcribe de forma no bloqueante y lo procesa con el mismo pipeline que el endpoint de texto.

## Requirements

### Requirement: Transcripción de audio a texto con faster-whisper
El sistema SHALL transcribir ficheros de audio a texto usando `faster-whisper` ejecutado localmente en proceso, sin dependencias de APIs externas. El modelo Whisper SHALL cargarse una única vez en el arranque de la aplicación (lifespan) para evitar latencia por petición.

#### Scenario: Transcripción de audio en español
- **WHEN** se envía un fichero de audio con el mensaje "¿Cómo crafeo una espada de diamante?"
- **THEN** el servicio STT devuelve una transcripción en texto que contiene las palabras clave de la pregunta

#### Scenario: Modelo cargado en lifespan, no por petición
- **WHEN** arranca la aplicación
- **THEN** el modelo Whisper está instanciado y listo antes de servir la primera petición de voz

#### Scenario: Modelo configurable por entorno
- **WHEN** la variable `WHISPER_MODEL=small` está definida en el entorno
- **THEN** el servicio STT carga el modelo `small` en lugar del `base` por defecto

### Requirement: Endpoint de voz POST /api/butler/ask-voice
El sistema SHALL exponer un endpoint `POST /api/butler/ask-voice` protegido por JWT que acepte un fichero de audio y un `session_id` opcional vía `multipart/form-data`, transcriba el audio y devuelva la misma respuesta que `POST /api/butler/ask`.

#### Scenario: Petición de voz autenticada devuelve acciones del butler
- **WHEN** un cliente autenticado envía un audio válido a `POST /api/butler/ask-voice`
- **THEN** el servidor responde 200 con una lista de `ButlerAction` idéntica en formato a la del endpoint de texto

#### Scenario: Petición sin autenticar devuelve 401
- **WHEN** se llama a `POST /api/butler/ask-voice` sin token JWT
- **THEN** el servidor responde 401

#### Scenario: Audio inválido o vacío devuelve 422
- **WHEN** se envía un fichero de audio vacío o con formato no soportado
- **THEN** el servidor responde 422 con un mensaje de error en español

#### Scenario: session_id opcional propaga la sesión de conversación
- **WHEN** se envía un audio con `session_id="player-uuid"`
- **THEN** el historial Redis de esa sesión incluye el turno de voz transcrito

### Requirement: Diferenciación texto/voz en el historial de conversación
El sistema SHALL marcar el origen de cada turno en el historial de `messages` almacenado en Redis usando `HumanMessage.metadata`, de modo que sea posible distinguir si un turno fue dictado por voz o escrito manualmente.

#### Scenario: Turno de voz marcado en historial
- **WHEN** el endpoint de voz procesa un audio con transcripción "¿qué dropea una vaca?"
- **THEN** el `HumanMessage` correspondiente tiene `metadata={"input_mode": "voice"}`

#### Scenario: Turno de texto marcado en historial
- **WHEN** el endpoint de texto procesa el mensaje "¿qué dropea una vaca?"
- **THEN** el `HumanMessage` correspondiente tiene `metadata={"input_mode": "text"}`

#### Scenario: Historial multi-turn mezcla turnos de texto y voz
- **WHEN** se alternan peticiones de texto y voz con el mismo `session_id`
- **THEN** el historial contiene ambos tipos de `HumanMessage` con sus respectivos `input_mode`

### Requirement: Transcripción STT no bloqueante del event loop
El sistema SHALL ejecutar la transcripción de audio (CPU-bound, síncrona) fuera del hilo del event loop, de modo que `POST /api/butler/ask-voice` no bloquee el procesamiento de otras peticiones mientras Whisper transcribe. La transcripción se delega a un thread del pool mediante `asyncio.to_thread` (o equivalente).

#### Scenario: Petición concurrente no se bloquea durante la transcripción
- **WHEN** una petición a `/api/butler/ask-voice` está transcribiendo audio y llega una segunda petición a cualquier endpoint
- **THEN** la segunda petición se procesa sin esperar a que termine la transcripción de la primera

#### Scenario: La transcripción sigue devolviendo el mismo resultado
- **WHEN** se transcribe un audio válido de forma no bloqueante
- **THEN** el texto transcrito es idéntico al que producía la transcripción síncrona y el flujo del butler continúa igual
