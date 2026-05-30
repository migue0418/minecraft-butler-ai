## Why

El butler responde preguntas de Minecraft basándose únicamente en el conocimiento del LLM, lo que produce alucinaciones en recetas, stats y mecánicas. Añadir un pipeline RAG con datos oficiales de Minecraft como fuente de verdad elimina las alucinaciones en el dominio factual y mejora drásticamente la calidad de respuestas sobre crafteo, mobs y mecánicas del juego.

## What Changes

- Qdrant añadido al `docker-compose.yml` como vector store dedicado.
- Script de ingesta `scripts/ingest.py` que descarga datos oficiales de Minecraft (ítems, recetas, mobs, mecánicas wiki), construye documentos con granularidad item-centric / mob-centric / section-centric y los indexa en Qdrant con embeddings multilingues.
- Nuevo módulo `app/features/butler/rag/` con: cliente Qdrant, lógica de hybrid search (dense + sparse BM25), reranker FlashRank y parent document retrieval para wiki.
- `classify_intent` extendido para producir además `doc_type` (`item`, `mob`, `mechanic`, `none`), usado como filtro de metadata en Qdrant.
- Nuevo nodo `retrieve_context` en el grafo LangGraph, ejecutado después de `classify_intent` y antes de `answer_question`; saltado si `intent` es `move` o `speak`.
- `ButlerState` ampliado con `retrieved_docs: list[Document]`.
- `answer_question` reformula su prompt para incluir los documentos recuperados cuando existen.

## Capabilities

### New Capabilities
- `rag-pipeline`: Indexación de conocimiento de Minecraft en Qdrant y recuperación mediante hybrid search + reranking + parent document retrieval, con metadata filtering por tipo de documento.
- `minecraft-knowledge-ingestion`: Script de ingesta que construye el corpus desde fuentes oficiales (`PrismarineJS/minecraft-data`, Minecraft Wiki) y lo indexa en Qdrant.

### Modified Capabilities
- `butler`: El nodo `classify_intent` produce ahora también `doc_type`; el grafo añade el nodo `retrieve_context`; `answer_question` incorpora contexto recuperado en el prompt. No cambia el contrato HTTP.

## Impact

- **Slices afectados**: `app/features/butler/` (graph, nuevo módulo `rag/`), `app/core/settings.py` (URL de Qdrant).
- **Infraestructura**: `docker-compose.yml` añade el servicio `qdrant` (puerto 6333).
- **Sin cambios de BD**: no hay migraciones Alembic.
- **Dependencias nuevas**: `qdrant-client`, `fastembed` (sparse vectors), `flashrank`, `langchain-qdrant`, `httpx` (para ingesta wiki).
- **Script nuevo**: `scripts/ingest.py` — ejecutar una vez antes de usar el butler.
