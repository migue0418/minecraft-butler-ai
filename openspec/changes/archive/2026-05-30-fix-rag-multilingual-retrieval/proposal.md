## Why

Las consultas en español al butler devuelven resultados prácticamente aleatorios: preguntar "¿Qué objetos dropea un caballo?" no recupera el documento de Horse en una posición útil. El diagnóstico en vivo (`scripts/diag_rag.py` contra la colección real de 1665 puntos) demuestra que el retriever denso multilingüe funciona perfecto (ES: Horse 0.63, Cow 0.68 en el top-1), pero las dos etapas léxicas en inglés del pipeline —sparse BM42 y reranker FlashRank— no cruzan el idioma y **corrompen activamente** el ranking del denso. El corpus es 100% inglés y los usuarios preguntan en español, así que el pipeline debe ser multilingüe de extremo a extremo.

## What Changes

> Nota: el enfoque inicial considerado fue "híbrido multilingüe" (fusión dense-dominante + reranker multilingüe). La evidencia recogida durante la implementación lo descartó: el único reranker "multilingüe" de FlashRank (`ms-marco-MultiBERT-L-12`) **no reordena ES→EN** (devuelve scores ~0 / ruido para español), y la rama sparse BM42 es léxica solo-inglés. El denso multilingüe por sí solo ya devuelve el documento correcto en top-1 para ES y EN. Enfoque final: **dense-only**.

- **Recuperación dense-only**: `get_retriever()` devuelve directamente los top-K por similitud densa (named vector `dense`). Se elimina del flujo de consulta la rama sparse BM42 y la etapa de reranking FlashRank.
- **Sin filtro duro por `doc_type` en el grafo**: `retrieve_context` deja de filtrar por el `doc_type` que infiere el clasificador. Ese filtro excluía el documento correcto cuando el LLM erraba el tipo (p.ej. "¿qué items dropea una vaca?" → `item`, dejando fuera el doc del mob Cow). El denso elige el tipo correcto por semántica (verificado: la misma consulta sin filtro devuelve Cow en top-1).
- **Cobertura de tests**: tests del retriever que verifican que las consultas en español (Horse, Cow) y en inglés (Cow por encima de Cow Spawn Egg) devuelven el documento correcto, que se aplica el `query_filter` por `doc_type` y que el límite es `top_k`.
- Sin reingesta: la colección Qdrant y los embeddings densos no cambian. Solo cambia la ruta de consulta. La colección conserva los named vectors `dense` y `sparse`; el `sparse` simplemente deja de usarse en consulta.

## Capabilities

### New Capabilities
<!-- Ninguna capability nueva: se modifica el comportamiento de recuperación existente. -->

### Modified Capabilities
- `rag-pipeline`: el requisito de búsqueda pasa de híbrida (dense+sparse+RRF) a **dense-only** (renombrado), y se **elimina** el requisito de reranking con cross-encoder (degradaba la recuperación multilingüe).

## Impact

- **Slice afectado**: `app/features/butler/rag/` — `retriever.py` (reescrito a dense-only: `dense_search`, sin `_encode_sparse`/`rerank`/FlashRank).
- **Settings/.env**: sin cambios netos (no se añade configuración nueva; el enfoque final no necesita un modelo de reranker).
- **Dependencias**: ninguna nueva. FlashRank y la rama sparse dejan de usarse en consulta (siguen instalados; `scripts/ingest.py` aún usa el sparse al indexar).
- **Sin cambios de datos**: no toca el modelo de datos ni requiere migración Alembic ni reingesta de Qdrant.
- **Tests**: `tests/features/butler/test_rag_retriever.py`.
- **Docs**: `docs/` (descripción del pipeline RAG).
