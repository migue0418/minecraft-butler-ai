## Why

El endpoint `/api/butler/ask` usa una lógica provisional de regex para detectar coordenadas. Para soportar múltiples tipos de acción de forma extensible (preguntas, movimiento, organización de cofres, cultivos, RAG, STT…) se necesita un grafo de agente real. El momento es ahora porque es la pieza central del proyecto y todo lo demás (RAG, GraphRAG, STT, más nodos) se añadirá encima.

## What Changes

- **Nuevo módulo de grafo**: `app/features/butler/graph/` con la definición del grafo LangGraph, los nodos, el estado y la configuración.
- **Dos nodos iniciales**:
  - `classify_intent` — clasifica el mensaje del usuario en una intención (`question`, `move`, `speak`…) usando Claude via LangChain. Es la puerta de entrada al grafo.
  - `answer_question` — responde preguntas sobre Minecraft usando Claude; diseñado para recibir contexto RAG en el futuro.
- **Routing condicional**: desde `classify_intent` hacia el nodo adecuado según la intención detectada.
- **Observabilidad**: integración con LangSmith (tracing automático via `LANGSMITH_API_KEY` + `LANGCHAIN_TRACING_V2`).
- **Configuración**: nuevas variables de entorno en `Settings` y `.example.env` (`ANTHROPIC_API_KEY`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`).
- **Refactor del router**: `butler/router.py` llama al grafo en lugar del stub de regex; la interfaz pública (`POST /api/butler/ask` → `list[ButlerAction]`) no cambia.
- **Sin cambios de modelo de datos**: no hay migración Alembic.

## Capabilities

### New Capabilities
- `butler-graph`: Grafo LangGraph del agente butler con clasificación de intención y respuesta a preguntas, observable desde LangSmith.

### Modified Capabilities
- `butler`: El endpoint `/api/butler/ask` ahora delega en el grafo en lugar de la lógica hardcoded.

## Impact

- **Slices afectados**: `app/features/butler/` (router, schemas, nuevo módulo `graph/`), `app/core/settings.py`.
- **Dependencias nuevas**: `langgraph`, `langchain-anthropic`, `langchain-core`, `langsmith`.
- **Sin migración Alembic**: no hay cambios de schema de base de datos.
- **Variables de entorno**: requiere `ANTHROPIC_API_KEY`; `LANGSMITH_API_KEY` y `LANGSMITH_PROJECT` opcionales para tracing.
