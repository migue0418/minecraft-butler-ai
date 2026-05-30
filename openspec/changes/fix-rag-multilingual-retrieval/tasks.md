## 0. Setup (OBLIGATORIO - PRIMER PASO)
- [x] 0.1 Trabajo sobre rama `feature/rag-core` (decisión del usuario: ambas features van juntas a main; el código RAG solo existe en rag-core). WIP previo commiteado antes de empezar.
- [x] 0.2 Plan técnico en `.claude/doc/fix-rag-multilingual-retrieval/backend.md` (leído antes de implementar)

## 1. Implementación (dense-only) — TDD
- [x] 1.1 Tests TDD en `tests/features/butler/test_rag_retriever.py` (dense_search: using="dense", query_filter por doc_type, limit=top_k, parent_content, pipeline)
- [x] 1.2 `retriever.py` reescrito a dense-only: `dense_search()` + `build_context()` + `get_retriever()`; eliminadas rama sparse BM42 y reranker FlashRank
- [x] 1.3 Revertidas adiciones de reranker (Settings/.env/RetrieverConfig) al descartarse el enfoque híbrido

## 2. Verificación de recuperación con diag_rag.py (OBLIGATORIO - EL AGENTE LO EJECUTA)
- [x] 2.1 `uv run python scripts/diag_rag.py`: ES caballo→Horse, ES vaca→Cow, EN cow→Cow (top-1) ✓
- [x] 2.2 Informe en `reports/2026-05-31-verification.md` (incluye la evidencia que descartó sparse+reranker)

## 3. Backend: tests y estado de BD (OBLIGATORIO - EL AGENTE LO EJECUTA)
- [x] 3.1 `uv run pytest -q`: **52 passed**
- [x] 3.2 Colección `minecraft_knowledge` intacta: **1665 puntos** antes y después (sin reingesta)

## 4. Backend: endpoint del butler (OBLIGATORIO - EL AGENTE LO EJECUTA)
- [x] 4.1 `POST /api/butler/ask` autenticado: ES "caballo" → 200 (cuero, silla, armadura); ES "vaca" → 200; EN "cow" → 200 (carne, cuero, leche)

## 5. Cierre (OBLIGATORIO)
- [ ] 5.1 Actualizar `docs/` (pipeline RAG dense-only)
- [ ] 5.2 PR con `gh` usando la skill `write-pr-report`
