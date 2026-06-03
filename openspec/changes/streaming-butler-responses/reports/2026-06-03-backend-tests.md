# Informe de tests — streaming-butler-responses

**Fecha:** 2026-06-03
**Rama:** feature/streaming-butler-responses

## Resultado

```
115 passed, 8 warnings in 31.30s
```

## Tests nuevos añadidos

**Schemas (`test_schemas.py`):**
- `test_stream_event_echo_type` — StreamEvent con type "echo"
- `test_stream_event_speak_type` — StreamEvent con type "speak"
- `test_stream_event_move_type_with_coords` — StreamEvent con coordenadas

**Service stream (`test_service_stream.py` — nuevo):**
- `test_stream_yields_actions_in_order` — 2 acciones secuenciales, orden correcto
- `test_stream_empty_graph_yields_nothing` — sin acciones, sin yields
- `test_stream_yields_move_action_with_coords` — action move con coordenadas

**Router SSE (`test_api.py`):**
- `test_ask_stream_first_event_is_echo` — primer evento echo con "[Tú]"
- `test_ask_stream_contains_action_events` — echo + speak + [DONE]
- `test_ask_stream_without_auth_returns_401` — 401 sin token
- `test_ask_voice_stream_echo_has_mic_prefix` — echo con 🎤 + transcript
