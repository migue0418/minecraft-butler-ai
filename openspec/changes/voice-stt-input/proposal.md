## Why

El butler actualmente solo acepta texto escrito, lo que limita su uso en el contexto de juego donde el jugador tiene las manos ocupadas con el teclado/ratón. Añadir STT permite que el jugador dicte comandos por voz, que se transcriben localmente con `faster-whisper` antes de entrar al pipeline del agente exactamente igual que un mensaje de texto.

## What Changes

- **Nuevo endpoint `POST /api/butler/ask-voice`**: acepta `multipart/form-data` con un fichero de audio y un `session_id` opcional. Transcribe con `faster-whisper` y delega en el mismo `ButlerService.run()`.
- **Nuevo slice `app/features/butler/stt/`**: encapsula la carga del modelo Whisper (singleton en lifespan) y la transcripción.
- **Diferenciación en el historial**: `HumanMessage` se crea con `metadata={"input_mode": "voice"}` o `"text"`, de modo que la conversación almacenada en Redis permite distinguir el origen de cada turno.
- **`ButlerState`**: nuevo campo opcional `input_mode: str` para propagar el modo a lo largo del grafo.
- **`ButlerAction` / respuesta**: sin cambios — el cliente recibe el mismo JSON; el modo de entrada es metadato interno.
- **Settings**: `WHISPER_MODEL` (default `base`) y `WHISPER_DEVICE` (default `cpu`).
- **Dockerfile**: `apt-get install ffmpeg` — requerido por faster-whisper para decodificar audio.
- **`docker-compose.yml`**: sin servicios nuevos (Whisper corre en proceso, no como servicio externo).
- **Sin migración Alembic**: no hay cambios en el modelo de datos relacional.

## Capabilities

### New Capabilities
- `voice-stt-input`: endpoint de voz y servicio de transcripción con faster-whisper.

### Modified Capabilities
- `butler`: el slice butler añade un nuevo endpoint y el campo `input_mode` en el estado del grafo.

## Impact

- **Slices afectados**: `app/features/butler/` (router, schemas, service, graph/state) y nuevo `app/features/butler/stt/`.
- **Dependencias nuevas**: `faster-whisper` (Python) + `ffmpeg` (sistema, en Dockerfile).
- **Sin cambios de esquema SQL** → sin migración Alembic.
- **Primera carga del modelo**: `faster-whisper` descarga el modelo de HuggingFace Hub la primera vez (~150 MB para `base`). En entornos con proxy SSL se aplica el mismo bypass existente.
