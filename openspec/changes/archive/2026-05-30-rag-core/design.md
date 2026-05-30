## Context

El grafo LangGraph actual invoca el LLM directamente sin ningún contexto recuperado. El estado `ButlerState` solo contiene `message`, `intent` y `actions`. No existe ninguna infraestructura de vector store ni pipeline de recuperación. El embedding model ya está abstraído en `get_embedding_model()` (llm-factory), pero aún no se usa.

## Goals / Non-Goals

**Goals:**
- Pipeline RAG completo: ingesta → indexación → hybrid search → reranking → generación con contexto.
- Granularidad correcta por tipo: item-centric, mob-centric, section-centric (wiki).
- Hybrid search: dense (multilingual embeddings) + sparse (BM25 via fastembed) con RRF fusion en Qdrant.
- Reranking con FlashRank (cross-encoder local, sin coste).
- Parent document retrieval para wiki: índice de chunks pequeños, recuperación del doc padre.
- Metadata filtering: `doc_type` en cada documento permite filtrar antes del vector search.
- Embeddings multilingues (`paraphrase-multilingual-MiniLM-L12-v2`): queries en español, corpus en inglés.

**Non-Goals:**
- Streaming de respuestas (cambio separado).
- GraphRAG / traversal de grafo de crafteo (cambio futuro).
- Endpoint de re-ingesta (cambio futuro `chest-context`).
- Soporte de versiones snapshot (solo Minecraft estable 1.21.x).

## Decisions

### 1. Colección Qdrant con vectores nombrados (dense + sparse)

Qdrant ≥ 1.7 permite múltiples vectores nombrados por punto. Se usa una única colección `minecraft_knowledge` con:
- `dense`: embeddings de `paraphrase-multilingual-MiniLM-L12-v2` (384 dims)
- `sparse`: BM25 via `fastembed` sparse model (`Qdrant/bm42-all-minilm-l6-v2-attentions`)

El hybrid search fusiona ambos rankings con RRF directamente en Qdrant (query con `prefetch` + `fusion=rrf`). Alternativa descartada: dos colecciones separadas — más operacional, sin ventaja de calidad.

### 2. Granularidad de documentos

```
TIPO         FUENTE                  TAMAÑO APROX   METADATA
──────────── ───────────────────────────────────── ──────────────────────────────
item         minecraft-data JSON     ~250-400 tok   {type:"item", id:"diamond_sword"}
mob          minecraft-data JSON     ~300-500 tok   {type:"mob", id:"creeper"}
mechanic     Minecraft Wiki          ~500-800 tok   {type:"mechanic", page, section}
  └─ parent  (doc padre completo)    guardado en payload, no indexado aparte
```

Los documentos de ítems y mobs se construyen programáticamente desde los JSON de `PrismarineJS/minecraft-data` + recetas de `misode/mcmeta`. Los documentos de mecánicas se scrapean de la Minecraft Wiki por secciones H2.

### 3. Parent Document Retrieval (solo para mecánicas wiki)

Los chunks de wiki se indexan en Qdrant. El payload de cada chunk incluye el campo `parent_content` con el texto completo de la sección padre. Al recuperar, se retorna `parent_content` al LLM, no el chunk. Para ítems y mobs no se necesita — el documento completo ya es el tamaño correcto.

### 4. Metadata filtering en `classify_intent`

`classify_intent` pasa de producir solo `intent` a producir también `doc_type`:

```python
class IntentOutput(BaseModel):
    intent: Literal["question", "move", "speak"]
    doc_type: Literal["item", "mob", "mechanic", "none"]
```

`doc_type: "none"` cuando `intent` no es `question`. El nodo `retrieve_context` usa `doc_type` para construir el filtro de Qdrant antes del search.

### 5. Nodo `retrieve_context` — posición y skip logic

```
START → classify_intent → [conditional] → retrieve_context → answer_question → END
                               │
                               └─ (move / speak) → move_action / speak_action → END
```

El routing existente ya salta `answer_question` para `move` y `speak`. `retrieve_context` se añade solo en el path de `question`. No modifica el routing de los otros intents.

### 6. Embedding model en Settings

`get_embedding_model()` ya lee `settings.embedding_model`. Se cambia el default a `paraphrase-multilingual-MiniLM-L12-v2` en `settings.py`. La ingesta y el retriever usan el mismo factory, garantizando consistencia.

### 7. Módulo `app/features/butler/rag/`

```
app/features/butler/rag/
├── __init__.py          # exporta get_retriever()
├── client.py            # QdrantClient singleton desde Settings
├── retriever.py         # hybrid_search() + rerank() + build_context()
└── schemas.py           # RetrievedDoc, RetrieverConfig
```

`get_retriever()` devuelve un objeto `Retriever` con método `async retrieve(query, doc_type) -> list[RetrievedDoc]`. El nodo `retrieve_context` lo llama con el mensaje y el `doc_type` del estado.

### 8. Script de ingesta `scripts/ingest.py`

Descarga datos de:
- `https://raw.githubusercontent.com/PrismarineJS/minecraft-data/master/data/pc/1.21/` (items, blocks, recipes, entities JSON)
- `https://minecraft.wiki/api.php` (MediaWiki API, páginas de mecánicas)

Construye documentos, genera embeddings con el mismo `get_embedding_model()` de la app, y los sube a Qdrant. Idempotente: comprueba si la colección ya existe con datos antes de indexar.

## Risks / Trade-offs

- **[Riesgo] fastembed descarga modelos en primera ejecución** → Mitigation: igual que HuggingFace, se cachea. Documentar en README que la primera ejecución del script es más lenta.
- **[Riesgo] Minecraft Wiki rate limiting** → Mitigation: `time.sleep(0.5)` entre peticiones en el scraper; cachear las páginas localmente en `data/wiki_cache/`.
- **[Riesgo] `paraphrase-multilingual-MiniLM-L12-v2` es más lento que all-MiniLM** → ~150ms vs ~80ms en encoding. Aceptable para RAG offline (ingesta); en runtime el retriever llama al modelo una sola vez por request.
- **[Trade-off] Parent content duplicado en payload** → Cada chunk de wiki guarda el texto completo del padre en su payload. Para 200-300 chunks de ~800 tokens esto son ~240KB de payload total. Negligible.
- **[Trade-off] `doc_type` en classify_intent añade un campo al structured output** → Haiku maneja bien el structured output extendido; no se espera degradación de calidad.
