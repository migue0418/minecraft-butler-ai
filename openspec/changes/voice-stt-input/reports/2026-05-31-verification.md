# Informe de verificación — voice-stt-input

Fecha: 2026-05-31

## Suite de tests

`uv run pytest -q` → **70 passed** (57 previos + 13 nuevos).

Tests nuevos:
- `tests/features/butler/test_stt_service.py` — 7 tests del slice STT (singleton, transcripción, audio vacío, cleanup de tempfile, autodetección de idioma)
- `tests/test_api.py` — 6 tests nuevos (input_mode text/voice en metadata, 401 sin auth, 200 con audio válido mockeado, 422 vacío, session_id propagado)

## Endpoint /ask-voice (backend en vivo, puerto 8000)

| Caso | HTTP | Resultado |
|---|---|---|
| Audio vacío (`b""`) | 422 | `"El fichero de audio está vacío."` ✅ |
| WAV sintético (tono 440Hz, sin habla) | 422 | `"No se pudo transcribir el audio."` ✅ — faster-whisper detecta correctamente que no hay voz |
| Texto follow-up mismo `session_id` | 200 | Respuesta correcta del butler ✅ |
| Sin autenticación | 401 | ✅ |

## input_mode en historial Redis

- 21 claves Redis creadas para la sesión de prueba → historial persiste correctamente.
- `HumanMessage.metadata={"input_mode": "text"|"voice"}` se serializa junto con el historial de LangGraph.
- La diferenciación texto/voz queda almacenada en el checkpoint de Redis para cada turno.

## Modelo Whisper en startup

- `get_whisper_model()` invocado en lifespan → modelo cargado antes de la primera petición.
- Mensaje HF Hub visible en startup log (descarga en primer arranque si no está en caché).
- `compute_type="int8"` en CPU: ~2× más rápido y mitad de memoria vs float32.

## Notas

- El WAV sintético (tono puro, sin habla) devuelve 422 de forma correcta. En uso real el cliente envía audio del micrófono del jugador con voz real.
- La imagen Docker requiere `redis/redis-stack` (ya configurado) y ahora también `ffmpeg` (añadido al Dockerfile).
- Tests usan `MemorySaver` + `MagicMock()` para el modelo Whisper — sin Redis ni modelo real en la suite.
