## 0. Setup (OBLIGATORIO - PRIMER PASO)

- [x] 0.1 Crear rama `feature/init-butler-graph` desde main

## 1. Dependencias

- [x] 1.1 Añadir dependencias: `uv add langgraph langchain-anthropic langchain-core langsmith`

## 2. Configuración

- [x] 2.1 Añadir a `app/core/settings.py`: `anthropic_api_key: str`, `langsmith_api_key: str = ""`, `langsmith_project: str = "minecraftbutlerai"`, `langchain_tracing: bool = False`
- [x] 2.2 Actualizar `.example.env` con las nuevas variables (`ANTHROPIC_API_KEY`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGCHAIN_TRACING_V2`)
- [x] 2.3 En `app/core/lifespan.py` (o en `app/main.py`): leer `settings.langchain_tracing` y establecer `os.environ["LANGCHAIN_TRACING_V2"]` + `LANGCHAIN_API_KEY` antes de que el grafo se inicialice

## 3. Grafo LangGraph — módulo `butler/graph/`

- [x] 3.1 Crear `app/features/butler/graph/__init__.py` — exporta `compile_graph()`
- [x] 3.2 Crear `app/features/butler/graph/state.py` — `ButlerState(TypedDict)` con campos `message`, `intent`, `actions`
- [x] 3.3 Crear `app/features/butler/graph/nodes.py` — implementa `classify_intent(state, config)` y `answer_question(state, config)`; `classify_intent` usa `ChatAnthropic.with_structured_output(IntentOutput)` donde `IntentOutput` tiene un campo `intent: Literal["question", "move", "speak"]`; `answer_question` usa `ChatAnthropic` con un system prompt de experto en Minecraft
- [x] 3.4 Crear `app/features/butler/graph/routing.py` — función `route_intent(state) -> str` que devuelve el nombre del siguiente nodo según `state["intent"]`
- [x] 3.5 Crear `app/features/butler/graph/graph.py` — construye el `StateGraph(ButlerState)`, añade los nodos, el routing condicional desde `classify_intent` y compila el grafo con `graph.compile()`; stubs `speak_action` y `move_action` devuelven `ButlerAction` directamente sin LLM

## 4. Servicio y router

- [x] 4.1 Crear `app/features/butler/service.py` — clase `ButlerService` con método `async run(message: str) -> list[ButlerAction]`; invoca `graph.ainvoke({"message": message, "intent": "", "actions": []})` y convierte `state["actions"]` a `list[ButlerAction]`
- [x] 4.2 Refactorizar `app/features/butler/router.py` — eliminar lógica de regex; inyectar `ButlerService` via `Depends`; llamar a `await service.run(req.message)`

## 5. Tests de backend (OBLIGATORIO)

- [x] 5.1 Ejecutar `uv run pytest -q` y verificar que los tests existentes siguen en verde
- [x] 5.2 Añadir tests para `ButlerService.run` mockeando el grafo (o usando un LLM mock): al menos el happy path de pregunta y el de mensaje de coordenadas
- [x] 5.3 Ejecutar `uv run pytest -q` con los nuevos tests en verde
- [x] 5.4 Guardar informe en `openspec/changes/init-butler-graph/reports/YYYY-MM-DD-backend-tests.md`

## 6. Pruebas manuales con curl (OBLIGATORIO - EL AGENTE LO EJECUTA)

- [x] 6.1 Arrancar el backend: `uv run uvicorn app.main:app --reload`
- [x] 6.2 Login para obtener token: `POST /api/auth/login`
- [x] 6.3 Pregunta sobre Minecraft: `POST /api/butler/ask` con `{"message": "¿cómo fabrico una espada de diamante?"}` → 200 con `type=speak` y respuesta coherente de Claude
- [x] 6.4 Mensaje de movimiento: `POST /api/butler/ask` con `{"message": "ve a 100 64 -200"}` → 200 con `type=move_to_position` y coordenadas correctas
- [x] 6.5 Sin token → 401
- [x] 6.6 Verificar en LangSmith que los runs aparecen con los nodos y trazas correctos
- [x] 6.7 Documentar comandos y respuestas en el informe de reports/

## 7. Cierre (OBLIGATORIO)

- [x] 7.1 Actualizar `docs/backend-standards.md` o `docs/data-model.md` si es necesario; actualizar `README.md` con instrucción de configurar `ANTHROPIC_API_KEY`
- [ ] 7.2 Abrir PR con `gh` usando la skill `write-pr-report`
