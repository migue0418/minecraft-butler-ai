## Why

`nodes.py` instancia `ChatAnthropic` de forma hardcodeada, acoplando el grafo a un único proveedor y modelo. Para un portfolio de AI Engineer es crítico demostrar abstracción limpia del proveedor LLM, configuración externa y soporte multi-proveedor (Anthropic y OpenAI), además de preparar el terreno para el modelo de embeddings que necesitará el RAG.

## What Changes

- Nuevo módulo `app/features/butler/llm/` con un factory `get_llm(role)` que devuelve `BaseChatModel` según `Settings`.
- Nuevo factory `get_embedding_model()` que devuelve `Embeddings` según `Settings`.
- `Settings` amplía con campos: `llm_provider`, `classifier_model`, `responder_model`, `embedding_model`, `openai_api_key`.
- `nodes.py` elimina toda instanciación directa de `ChatAnthropic`; usa el factory.
- `.example.env` actualizado con las nuevas variables.

## Capabilities

### New Capabilities
- `llm-factory`: Factory functions config-driven para instanciar `BaseChatModel` y `Embeddings` por rol, soportando proveedores Anthropic y OpenAI de forma intercambiable.

### Modified Capabilities
- `butler`: El slice butler cambia su implementación interna de nodos (ya no acopla a un proveedor concreto). No cambian los contratos HTTP ni el comportamiento observable.

## Impact

- **Slices afectados**: `app/features/butler/` (nodes.py, nuevo módulo llm/).
- **Settings**: `app/core/settings.py` añade campos nuevos opcionales; sin migración Alembic (no toca BD).
- **Dependencias nuevas**: `langchain-openai` (uv add).
- **Tests**: los tests de butler existentes usan mocks del grafo, no se rompen; se añaden tests del factory.
