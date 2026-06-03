## 0. Setup (OBLIGATORIO - PRIMER PASO)

- [x] 0.1 Leer el plan técnico en `.claude/doc/streaming-sentence-chunks/backend.md` antes de tocar código
- [x] 0.2 Crear rama `feature/streaming-sentence-chunks` desde main

## 1. System prompts — respuestas concisas sin emojis

- [x] 1.1 En `app/features/butler/graph/nodes.py` reemplazar `_MINECRAFT_SYSTEM_PROMPT` por una versión que instruya: respuesta directa al grano, sin emojis, sin literatura innecesaria, longitud mínima suficiente para responder
- [x] 1.2 Actualizar `_MINECRAFT_SYSTEM_PROMPT_WITH_CONTEXT` con las mismas restricciones

## 2. `ButlerService.stream()` — chunk-level streaming (TDD)

- [x] 2.1 Añadir `import re` en `app/features/butler/service.py`
- [x] 2.2 Añadir función de módulo `_flush_at_boundaries(text: str) -> tuple[list[str], str]` que detecta fronteras (`. `, `! `, `? `, `\n`, `## `) y devuelve (chunks_completos, resto)
- [x] 2.3 Reemplazar el cuerpo de `ButlerService.stream()`: cambiar `graph.astream(stream_mode="values")` por `graph.astream_events(version="v2")`; capturar `on_chat_model_stream` de `speak_action`/`answer_question` con buffer + flush; resetear buffer en `on_chain_start` del nodo (protección contra retry); vaciar buffer en `on_chain_end`; capturar `move_to_position` de `on_chain_end` de `move_action`
- [x] 2.4 Test unitario de `_flush_at_boundaries`: frontera en punto, en `\n`, sin frontera todavía, buffer residual al final
- [x] 2.5 Test de `ButlerService.stream()` con `astream_events` mockeado: simular 3 tokens que forman una frase con punto → verificar que se emite 1 chunk; simular 2 frases → 2 chunks

## 3. Tests y estado de BD (OBLIGATORIO)

- [x] 3.1 `uv run pytest -q` en verde (119/119); informe en `reports/2026-06-03-backend-tests.md`; informe en `openspec/changes/streaming-sentence-chunks/reports/YYYY-MM-DD-backend-tests.md`

## 4. Pruebas manuales con curl (OBLIGATORIO - EL AGENTE LO EJECUTA)

- [x] 4.1 `POST /api/butler/ask` → respuesta sin emojis, directa (153 chars vs ~500 antes) ✓
- [x] 4.2 Con world_context (3 zombies) → "Sí, hay 3 zombies cerca." sin emojis ✓; streaming por chunks verificado en tests unitarios (endpoint ask-stream no existe en main aún)
- [x] 4.3 Informe en `reports/2026-06-03-curl.md`

## 5. Cierre (OBLIGATORIO)

- [x] 5.1 Actualizar `docs/backend-standards.md`: documentar el cambio de prompts y el streaming por chunks
- [ ] 5.2 PR con `gh pr create` usando la skill `write-pr-report`
