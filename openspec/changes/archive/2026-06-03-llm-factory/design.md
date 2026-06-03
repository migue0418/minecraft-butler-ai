## Context

El slice `butler` instancia `ChatAnthropic` directamente en `nodes.py` con modelos hardcodeados (`claude-haiku-4-5-20251001`, `claude-sonnet-4-6`). No hay soporte para OpenAI ni forma de cambiar proveedor/modelo sin tocar código. El factory de embeddings tampoco existe — se necesita antes del cambio `rag-core`.

LangChain abstrae proveedores vía `BaseChatModel` (chat) y `Embeddings` (embeddings), lo que hace posible un factory limpio sin añadir interfaces propias.

## Goals / Non-Goals

**Goals:**
- Factory `get_llm(role)` → `BaseChatModel` configurable desde `Settings` (proveedor + modelo por rol).
- Factory `get_embedding_model()` → `Embeddings` configurable desde `Settings`.
- `nodes.py` completamente desacoplado del proveedor concreto.
- Soporte Anthropic y OpenAI desde el primer día; extensible a otros sin cambiar el factory.
- Tests unitarios del factory que verifiquen la instancia correcta por configuración.

**Non-Goals:**
- Soporte de más de dos proveedores en esta iteración.
- Streaming de respuestas (será otro cambio).
- Middleware de retry/fallback entre proveedores.
- Caching de instancias LLM (premature optimization).

## Decisions

### 1. Módulo `app/features/butler/llm/` (no `app/core/`)

El factory vive dentro del slice `butler`, no en `core`, porque es lógica específica del dominio AI. Si en el futuro otro slice necesita LLMs, se promueve a `core`. Mantener en `butler` evita coupling prematuro.

### 2. `get_llm(role: Literal["classifier", "responder"]) → BaseChatModel`

Firma por "rol semántico" en lugar de por nombre de modelo. Ventajas:
- El router/nodo no conoce nombres de modelos.
- Cambiar el modelo del clasificador no afecta al código que lo usa, solo a `Settings`.
- Alternativa considerada: `get_llm(model: str)` — rechazada porque filtra los nombres de modelo a las capas superiores.

### 3. Settings: campos explícitos, no dict libre

```python
llm_provider: Literal["anthropic", "openai"] = "anthropic"
classifier_model: str = "claude-haiku-4-5-20251001"
responder_model: str = "claude-sonnet-4-6"
embedding_provider: Literal["openai", "huggingface"] = "huggingface"
embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
openai_api_key: str = ""
```

Alternativa considerada: un dict `llm_config: dict`. Rechazada — no hay validación, peor autocompletado, más difícil de documentar.

### 4. Embeddings: `huggingface` como default (gratis)

`sentence-transformers/all-MiniLM-L6-v2` via `langchain-huggingface` no requiere API key y es suficiente para el RAG de Minecraft. OpenAI `text-embedding-3-small` como alternativa de pago. El factory instancia `HuggingFaceEmbeddings` o `OpenAIEmbeddings` según config.

### 5. Estructura de archivos

```
app/features/butler/llm/
├── __init__.py      # exporta get_llm, get_embedding_model
└── factory.py       # implementación del factory
```

Un solo archivo `factory.py` es suficiente. Si crece (retry logic, caching), se parte entonces.

## Risks / Trade-offs

- **[Riesgo] `langchain-huggingface` descarga modelos en runtime** → Mitigation: en Docker, pre-descargar en el build o montar un volumen de caché de Hugging Face. Para desarrollo local, la primera ejecución tarda ~30s (descarga del modelo).
- **[Riesgo] Incompatibilidad de versiones entre `langchain-anthropic`, `langchain-openai` y `langchain-core`** → Mitigation: fijar versiones en `pyproject.toml` con `uv lock`.
- **[Trade-off] El factory no cachea instancias** → Cada llamada a `get_llm()` crea una nueva instancia. Aceptable por ahora; `ChatAnthropic`/`ChatOpenAI` son ligeros de instanciar.
