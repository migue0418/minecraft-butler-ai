# MinecraftButlerAI — Roadmap de portfolio AI Engineer

Estado actual y hoja de ruta técnica. Actualizar cuando se complete cada cambio.

---

## Estado del proyecto

Un mayordomo de Minecraft controlado por IA. Un mod Java/Fabric envía comandos del jugador
a un backend FastAPI; el backend ejecuta un grafo LangGraph que clasifica la intención,
recupera conocimiento (RAG) y devuelve acciones que el mod ejecuta en el juego.

```
Java Mod (Fabric) ──POST /api/butler/ask──▶ FastAPI (LangGraph brain)
                  ◀── [{ type, message, x, y, z }] ──────────────────
```

---

## Stack actual

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.14, FastAPI, SQLAlchemy async, Alembic, Pydantic Settings |
| Auth | JWT + pwdlib[argon2], roles |
| Agente | LangGraph, LangChain |
| LLMs | Anthropic (Haiku + Sonnet) — abstraídos via `llm-factory` |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (local, gratis) — abstraídos |
| Observabilidad | LangSmith (tracing básico activado) |
| Base de datos | PostgreSQL + asyncpg |
| Infraestructura | Docker Compose (postgres + backend) |
| Mod cliente | Java 25, Fabric 0.19.2, Minecraft 26.1.2 |

---

## Stack objetivo (portfolio completo)

| Capa | Tecnología | Notas |
|------|-----------|-------|
| Vector store | **Qdrant** (Docker) | RAG, hybrid search |
| Cache / Memoria | **Redis** (Docker) | LangGraph checkpointer, memoria multi-turn |
| Embeddings | sentence-transformers (default) / OpenAI | Ya abstraído en factory |
| Reranker | **FlashRank** (local, gratis) | Cross-encoder para RAG |
| LLMs | Anthropic + OpenAI | Ya abstraído en factory |
| Observabilidad | LangSmith profundo | Metadata, evaluación, feedback |

Docker compose final: `postgres` + `backend` + `qdrant` + `redis`

---

## Cambios completados ✅

### `init-butler-graph`
- Grafo LangGraph con clasificador de intención (Haiku) + nodos `answer_question`, `speak_action`, `move_action`
- Router `POST /api/butler/ask` protegido por JWT
- Integración LangSmith básica (tracing on/off)

### `llm-factory`
- Factory `get_llm(role)` → `BaseChatModel` (Anthropic o OpenAI, config-driven)
- Factory `get_embedding_model()` → `Embeddings` (HuggingFace o OpenAI, config-driven)
- `nodes.py` desacoplado de cualquier proveedor concreto
- Validación de API keys en Settings según proveedor activo
- 17 tests TDD del factory

---

## Roadmap pendiente

### Fase 1 — `rag-core` ⭐⭐⭐ (máximo impacto portfolio)

**Qué demuestra:** diseño de pipelines RAG de producción — hybrid search, reranking, ingesta.

Pipeline de recuperación:
```
Query
  └─ Query Rewriter          (mejora la query antes de buscar)
  └─ Hybrid Search           (Qdrant: dense vectors + sparse BM25)
       └─ RRF Fusion         (combina rankings)
  └─ Reranker                (FlashRank cross-encoder)
  └─ Top-K chunks ──────────▶ LLM context
```

Contenido del vector store:
- Recetas de crafteo (Minecraft data pack JSON — 2000+ recetas, ground truth exacto)
- Mecánicas y guía del juego (Minecraft Wiki)

Cambios en el grafo:
- Nuevo nodo `retrieve_context` entre `classify_intent` y `answer_question`
- Skip del nodo si intent es `move` o `speak` (no necesita RAG)
- Estado ampliado con `retrieved_docs: list[Document]`

Docker: añadir `qdrant` al compose.

---

### Fase 2 — `conversation-memory` ⭐⭐⭐

**Qué demuestra:** agentes multi-turn, LangGraph avanzado con checkpointing.

- Redis Checkpointer de LangGraph — historial persistido por `session_id`
- `session_id` en el request (= player UUID del mod Java)
- El butler recuerda el contexto entre turnos:
  ```
  Turno 1: "¿cómo fabrico una espada de diamante?"
  Turno 2: "¿y si no tengo suficientes materiales?"  ← recuerda el contexto
  ```

Docker: añadir `redis` al compose.

---

### Fase 3 — `chest-context` ⭐⭐ (diferenciador único)

**Qué demuestra:** integración real con estado del juego — el butler razona sobre el inventario.

El mod Java ya tiene un registro de cofres con contenido. Extender el request:
```json
{
  "message": "mueve los logs al horno",
  "session_id": "player-uuid",
  "chest_registry": [
    { "name": "storage", "items": ["oak_log x64", "birch_log x32"] },
    { "name": "furnace_input", "accepts": ["#minecraft:logs"] }
  ]
}
```

Nuevos action types en el grafo (y en el mod):
| Action type | Estado mod | Complejidad |
|---|---|---|
| `chest_move` | Parcial (`tryMoveAll` existe) | Baja |
| `chest_distribute` | Parcial (`distributeChest` existe) | Baja |
| `follow_player` | Parcial (flag `isFollowing`) | Muy baja |
| `stop_following` | Parcial | Muy baja |
| `move_to_player` | Parcial (`savedPosition`) | Baja |

---

### Fase 4 — `langsmith-depth` ⭐⭐

**Qué demuestra:** observabilidad de producción en sistemas LLM.

- Metadata por run: `user_id`, `session_id`, `intent`, `retrieved_docs_count`
- Dataset de evaluación: ~50 preguntas de Minecraft con respuestas esperadas
- Endpoint `POST /api/butler/feedback` → envía thumbs up/down a LangSmith
- Custom run names por nodo del grafo

---

### Fase 5 — `action-types-expansion` ⭐⭐

**Qué demuestra:** integración end-to-end con sistema real (Java mod ↔ FastAPI).

Coordinado con el mod: añadir los nuevos action types de la Fase 3 en el grafo y en el mod Java.
Requiere trabajo en ambos repositorios de forma coordinada.

---

### Fase 6 — `streaming` ⭐

**Qué demuestra:** async streaming — necesario en cualquier sistema LLM de producción.

- Endpoint `POST /api/butler/stream` con SSE
- LangGraph `.astream()` en lugar de `.ainvoke()`
- El mod Java recibe tokens progresivos (opcional, mejora UX del chat en Minecraft)

---

## Decisiones de arquitectura tomadas

| Decisión | Elección | Alternativa descartada | Motivo |
|---|---|---|---|
| Vector store | Qdrant | pgvector | Portfolio: servicio dedicado más visible |
| Reranker | FlashRank (gratis) | Cohere Rerank | Sin coste, modelo local |
| Embeddings default | HuggingFace all-MiniLM-L6-v2 | OpenAI ada-002 | Gratis, suficiente calidad |
| Memoria | Redis Checkpointer | In-memory | Persistencia real entre sesiones |
| Repositorios | Dos repos separados | Monorepo | Build tools incompatibles (Gradle vs uv) |
| LLM abstracción | Factory por rol semántico | Factory por nombre de modelo | El nodo no conoce modelos concretos |

---

## Próximo cambio sugerido

**`rag-core`** — máximo impacto para el portfolio, base técnica más compleja y visible.
Prerequisito: merge del PR de `llm-factory` y `/opsx:archive llm-factory`.
