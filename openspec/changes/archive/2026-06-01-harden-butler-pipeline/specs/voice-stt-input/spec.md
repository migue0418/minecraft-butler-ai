## ADDED Requirements

### Requirement: Transcripción STT no bloqueante del event loop
El sistema SHALL ejecutar la transcripción de audio (CPU-bound, síncrona) fuera del hilo del event loop, de modo que `POST /api/butler/ask-voice` no bloquee el procesamiento de otras peticiones mientras Whisper transcribe. La transcripción se delega a un thread del pool mediante `asyncio.to_thread` (o equivalente).

#### Scenario: Petición concurrente no se bloquea durante la transcripción
- **WHEN** una petición a `/api/butler/ask-voice` está transcribiendo audio y llega una segunda petición a cualquier endpoint
- **THEN** la segunda petición se procesa sin esperar a que termine la transcripción de la primera

#### Scenario: La transcripción sigue devolviendo el mismo resultado
- **WHEN** se transcribe un audio válido de forma no bloqueante
- **THEN** el texto transcrito es idéntico al que producía la transcripción síncrona y el flujo del butler continúa igual
