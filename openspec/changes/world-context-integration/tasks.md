## 0. Setup (OBLIGATORIO - PRIMER PASO)

- [x] 0.1 Leer el plan técnico en `.claude/doc/world-context-integration/backend.md` antes de tocar código
- [x] 0.2 Crear rama `feature/world-context-integration` desde main

## 1. Backend: schemas (TDD — modelo primero)

- [x] 1.1 Añadir en `app/features/butler/schemas.py` los modelos Pydantic: `ItemEntry`, `PlayerContext`, `ChestContext`, `AnimalGroup`, `CropGroup`, `NearbyContext`, `WorldContextDTO`; añadir `world_context: WorldContextDTO | None = None` a `AskRequest`
- [x] 1.2 Escribir tests unitarios en `tests/features/butler/test_schemas.py`: validación de `WorldContextDTO` con estructura completa, con campos opcionales ausentes y con estructura inválida (422)

## 2. Backend: state y service

- [x] 2.1 En `app/features/butler/graph/state.py` añadir `world_context: dict | None` y `needs_world_context: bool` a `ButlerState`
- [x] 2.2 En `app/features/butler/service.py` añadir parámetro `world_context: dict | None = None` a `ButlerService.run()` y propagarlo al `graph.ainvoke(...)` como campo del estado inicial

## 3. Backend: nodos del grafo

- [x] 3.1 En `app/features/butler/graph/nodes.py` extender `IntentOutput` con `needs_world_context: bool = False`; actualizar el prompt del clasificador para que evalúe si la pregunta requiere contexto del mundo (inventario, cofres, animales, cultivos)
- [x] 3.2 En `classify_intent` retornar también `needs_world_context` en el dict de resultado
- [x] 3.3 Añadir función `format_world_context(ctx: dict) -> str` que genera el texto compacto: posición, top-10 inventario, top-5 por cofre, top-5 animales, cultivos; usa IDs de Minecraft tal cual
- [x] 3.4 En `speak_action`: si `state["needs_world_context"] and state.get("world_context")`, añadir el texto formateado al system prompt (sección separada tras `_MINECRAFT_SYSTEM_PROMPT`)
- [x] 3.5 En `answer_question`: mismo patrón que `speak_action` para inyectar el contexto cuando corresponda

## 4. Backend: router

- [x] 4.1 En `app/features/butler/router.py`, endpoint `ask`: pasar `req.world_context.model_dump() if req.world_context else None` a `service.run()`
- [x] 4.2 En endpoint `ask_voice`: añadir `world_context: str | None = Form(None)`; parsear con `json.loads(world_context)` en try/except, ignorar silenciosamente si falla (log warning); pasar a `service.run()`

## 5. Tests (OBLIGATORIO)

- [x] 5.1 Ampliar tests de integración en `tests/test_api.py` (tests de router world_context añadidos allí, donde viven el fixture `client` y los helpers de auth): caso con `world_context` válido en `/ask` (verificar 200), caso sin `world_context` (verificar retrocompatibilidad), caso con `world_context` inválido (verificar 422)
- [x] 5.2 Tests unitarios de `format_world_context` en `tests/features/butler/test_nodes.py`: verificar formato correcto, truncado a top-10/5, texto vacío cuando ctx es None o vacío
- [x] 5.3 `uv run pytest -q` en verde (89/89); informe guardado en `openspec/changes/world-context-integration/reports/2026-06-01-backend-tests.md`

## 6. Pruebas manuales con curl (OBLIGATORIO - EL AGENTE LO EJECUTA)

- [x] 6.1 Arrancar el backend: `uv run uvicorn app.main:app --reload`
- [x] 6.2 Autenticar y obtener token: `curl -X POST .../api/auth/login`
- [x] 6.3 `POST /api/butler/ask` sin `world_context` → 200 OK, retrocompatible ✓
- [x] 6.4 `POST /api/butler/ask` con `world_context` y "¿tengo hierro?" → Alfred usó el inventario ✓
- [x] 6.5 `POST /api/butler/ask` con `world_context` y "crafteo espada" → respuesta genérica, sin contexto ✓
- [x] 6.6 `POST /api/butler/ask-voice` con world_context válido → form field parseado ✓ (422 por audio silencioso, no por context)
- [x] 6.7 `POST /api/butler/ask-voice` con world_context malformado → 422 por audio, no 500, JSON ignorado ✓
- [x] 6.8 Informe guardado en `reports/2026-06-01-curl.md`

## 7. Cierre (OBLIGATORIO)

- [x] 7.1 Actualizar `docs/backend-standards.md`: contrato de world_context en ambos endpoints + sección World Context con formato, selección selectiva e instrucción de no persistir en Redis
- [ ] 7.2 PR con `gh pr create` usando la skill `write-pr-report`
