## Context

El butler tiene un pipeline de texto bien establecido:
`POST /api/butler/ask` (JSON) → `ButlerService.run(message, session_id)` → grafo LangGraph → Redis Checkpointer.

El historial multi-turn se almacena como `list[AnyMessage]` con `add_messages`. La memoria es opaca al cliente: el JSON de respuesta es siempre `list[ButlerAction]`.

El objetivo es añadir una ruta paralela de voz que:
1. Recibe audio → transcribe localmente → entra al mismo pipeline de texto.
2. Marca en el historial si el turno fue dictado o escrito.
3. No rompe el contrato existente ni requiere que el cliente de texto cambie nada.

## Goals / Non-Goals

**Goals:**
- Endpoint `POST /api/butler/ask-voice` (multipart/form-data).
- Transcripción local con `faster-whisper` (sin API externa, sin coste por petición).
- Singleton del modelo cargado en lifespan (sin cold start por petición).
- Diferenciación texto vs voz en el historial Redis (`HumanMessage.metadata`).
- Configuración del modelo y dispositivo vía Settings/env.
- `ffmpeg` en Dockerfile para decodificar cualquier formato de audio común.

**Non-Goals:**
- Streaming de audio o STT en tiempo real (WebSocket/SSE) — fuera de alcance.
- TTS (texto a voz) en la respuesta — fuera de alcance.
- Almacenamiento del fichero de audio — se procesa en memoria y se descarta.
- Soporte multi-hablante / diarización.

## Decisions

### Decisión 1 — `faster-whisper` como motor STT

`faster-whisper` reimplementa Whisper con CTranslate2: 4× más rápido que el Whisper original de OpenAI con la misma precisión. Soporta detección automática de idioma (ES/EN y +90 más), corre en CPU sin GPU, y no requiere API key. Es el estándar de facto en 2025 para STT local en proyectos Python.

Alternativas descartadas:
- **openai-whisper** (más lento, mayor VRAM).
- **whisper.cpp** (require compilación nativa, más complejo de empaquetar en Docker).
- **API externa Whisper de OpenAI** (coste por petición, latencia de red, datos del jugador salen del proceso).

### Decisión 2 — Modelo `base` por defecto, configurable

`base` (~150 MB, ~3× tiempo real en CPU) es el punto óptimo para un servidor local de juego: latencia ~1-2 s para frases cortas, buena precisión en ES/EN. El usuario puede subir a `small`/`medium` si tiene CPU potente. Configurable con `WHISPER_MODEL` en Settings.

### Decisión 3 — Endpoint separado `POST /api/butler/ask-voice`

Mantener `POST /api/butler/ask` inalterado (JSON, retro-compatible). El endpoint de voz usa `multipart/form-data` porque:
- Subir ficheros de audio en JSON (base64) es ineficiente y no es REST idiomático.
- `python-multipart` ya está instalado.
- El mod Java puede enviar audio como `File` en un formulario.

El endpoint acepta `audio: UploadFile` + `session_id: str | None = Form(None)`.

### Decisión 4 — Diferenciación en el historial con `HumanMessage.metadata`

LangChain's `HumanMessage` acepta `metadata: dict`. Se usa:
```python
HumanMessage(content=transcript, metadata={"input_mode": "voice"})
HumanMessage(content=message, metadata={"input_mode": "text"})
```
Este metadata se persiste en Redis junto con el historial de mensajes. No requiere cambiar el schema de Redis ni `ButlerState` más allá de un campo `input_mode: str` informativo.

### Decisión 5 — Singleton de WhisperModel en lifespan

`WhisperModel` tarda ~1-3 s en cargar desde disco. Se instancia una vez en `lifespan` y se guarda en una variable global (igual que `_compiled_graph`). La función `get_whisper_model()` devuelve la instancia cacheada.

### Capa por capa

```
app/features/butler/stt/
├── __init__.py          # exporta get_whisper_model, transcribe_audio
└── service.py           # WhisperModel singleton + transcribe_audio(bytes) -> str
```

```
app/features/butler/
├── router.py            # añade POST /api/butler/ask-voice
├── schemas.py           # VoiceAskResponse (igual que list[ButlerAction], alias)
└── service.py           # run() acepta input_mode="text"|"voice" y lo pasa al state
```

```
app/features/butler/graph/
└── state.py             # añade input_mode: str = "text"
```

```
app/core/
└── lifespan.py          # llama get_whisper_model() en startup para precalentar
```

```
Dockerfile               # apt-get install -y ffmpeg
```

## Risks / Trade-offs

- **Latencia STT en CPU**: ~1-2 s para frases de 5-10 palabras con modelo `base`. Aceptable para el caso de uso (no es un juego en tiempo real de reacción ms).
- **Memoria del modelo**: `base` ~300 MB RAM en proceso. Si el servidor tiene memoria limitada, usar `tiny` (~100 MB).
- **ffmpeg en la imagen Docker**: añade ~30 MB a la imagen. Necesario para cualquier formato que no sea WAV crudo.
- **Formato de audio del mod Java**: el mod puede enviar webm/opus (común en grabación de micrófono). ffmpeg lo decodifica sin cambios en el código Python.

## Migration Plan

1. Sin cambios en datos persistidos (Redis, Postgres).
2. Primer arranque: faster-whisper descarga el modelo de HF Hub (~150 MB para `base`). Con `SSL_VERIFY=false` se aplica el bypass existente. En Docker se puede pre-descargar en el build si se quiere.
3. Rollback: revertir commit; el endpoint de texto no se toca.

## Open Questions

- ¿Pre-descargar el modelo Whisper en el `docker build` (cero cold start en producción) o dejarlo al primer arranque? → Dejar al primer arranque por ahora; si es un problema se añade un `RUN python -c "from faster_whisper import WhisperModel; WhisperModel('base')"` en el Dockerfile.
