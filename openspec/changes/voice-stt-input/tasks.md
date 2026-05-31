## 0. Setup (OBLIGATORIO - PRIMER PASO)
- [x] 0.1 Crear y cambiar a rama `feature/voice-stt-input` desde `main`
- [x] 0.2 (OBLIGATORIO) Plan técnico del agente `backend-developer` en `.claude/doc/voice-stt-input/backend.md`; `/opsx:apply` debe leerlo antes de tocar código
- [x] 0.3 Instalar dependencia: `uv add faster-whisper` (con `--native-tls` si hay proxy)

## 1. Infraestructura: Dockerfile + Settings (TDD)
- [x] 1.1 `Dockerfile`: añadir `RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*` antes del `COPY`
- [x] 1.2 `app/core/settings.py`: `whisper_model: str = "base"` y `whisper_device: str = "cpu"` junto a los settings de Qdrant
- [x] 1.3 `.example.env`: documentar `WHISPER_MODEL=base` y `WHISPER_DEVICE=cpu`

## 2. STT Service: faster-whisper singleton (TDD)
- [x] 2.1 Tests que fallan en `tests/features/butler/test_stt_service.py`: 7 tests rojos → verde
- [x] 2.2 Crear `app/features/butler/stt/__init__.py` (exporta `get_whisper_model`, `transcribe_audio`)
- [x] 2.3 Crear `app/features/butler/stt/service.py`: `WhisperModel` singleton + `transcribe_audio(audio_bytes: bytes) -> str`

## 3. Historial: input_mode en ButlerState y service (TDD)
- [x] 3.1 Tests que fallan → verde: `ButlerState` acepta `input_mode`; `ButlerService.run()` propaga metadata
- [x] 3.2 `app/features/butler/graph/state.py`: añadir `input_mode: str`
- [x] 3.3 `app/features/butler/service.py`: `run(message, session_id=None, input_mode="text")` + metadata en `HumanMessage`

## 4. API: endpoint /ask-voice (TDD)
- [x] 4.1 Tests → verde: 401 sin auth, 200 con audio mockeado, 422 vacío, session_id propagado
- [x] 4.2 No requiere schema Pydantic adicional (Form + UploadFile directamente en el router)
- [x] 4.3 `app/features/butler/router.py`: `POST /api/butler/ask-voice` implementado

## 5. Lifespan: precalentar modelo en startup
- [x] 5.1 `app/core/lifespan.py`: `get_whisper_model()` llamado en startup

## 6. Backend: tests y estado (OBLIGATORIO - EL AGENTE LO EJECUTA)
- [x] 6.1 `uv run pytest -q` → **70 passed**
- [x] 6.2 Informe en `openspec/changes/voice-stt-input/reports/2026-05-31-verification.md`

## 7. Backend: endpoints con curl (OBLIGATORIO - EL AGENTE LO EJECUTA)
- [x] 7.1 Startup verificado: modelo carga en lifespan (log INFO + Application startup complete)
- [x] 7.2 `POST /api/butler/ask-voice` WAV vacío → 422 ✓; WAV sintético sin voz → 422 ✓
- [x] 7.3 Historial Redis: 21 claves de sesión creadas con `input_mode` en metadata
- [x] 7.4 Multi-modal verificado: turno de texto mismo session_id → 200 ✓
- [x] 7.5 Informe en reports/

## 8. Cierre (OBLIGATORIO)
- [x] 8.1 Actualizar `docs/backend-standards.md` (sección STT añadida)
- [ ] 8.2 PR con `gh` usando la skill `write-pr-report`
