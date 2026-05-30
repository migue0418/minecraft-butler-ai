## 0. Setup (OBLIGATORIO - PRIMER PASO)

- [x] 0.1 Crear rama `feature/rag-core` desde main

## 1. Infraestructura

- [x] 1.1 Añadir servicio `qdrant` a `docker-compose.yml` (imagen `qdrant/qdrant`, puerto 6333, volumen persistente)
- [x] 1.2 Añadir `QDRANT_URL` a `app/core/settings.py` (default `http://localhost:6333`) y a `.example.env`
- [x] 1.3 Cambiar default de `embedding_model` en `Settings` a `paraphrase-multilingual-MiniLM-L12-v2` y `embedding_provider` a `huggingface`
- [x] 1.4 `uv add qdrant-client fastembed flashrank langchain-qdrant --native-tls`

## 2. Módulo RAG (TDD)

- [x] 2.1 Crear `app/features/butler/rag/__init__.py`, `client.py`, `schemas.py`, `retriever.py`
- [x] 2.2 `client.py`: singleton `QdrantClient` que lee `settings.qdrant_url`
- [x] 2.3 `schemas.py`: `RetrievedDoc(content, doc_type, doc_id, score)`
- [x] 2.4 Escribir tests TDD para `retriever.py`: mock de Qdrant — hybrid search retorna docs filtrados por `doc_type`; reranker reduce a top-3; doc_type `"none"` retorna lista vacía; parent content reemplaza chunk en mecánicas
- [x] 2.5 `retriever.py`: `async retrieve(query, doc_type) -> list[RetrievedDoc]` con hybrid search (dense + sparse prefetch + RRF), FlashRank reranking y parent document retrieval para mecánicas
- [x] 2.6 Verificar que los tests del retriever pasan

## 3. Script de ingesta

- [x] 3.1 Crear `scripts/__init__.py` (vacío) y `scripts/ingest.py`
- [x] 3.2 Función `build_item_documents()`: descarga items + recipes de `PrismarineJS/minecraft-data` (1.21), construye documentos item-centric con receta, stats, enchantments
- [x] 3.3 Función `build_mob_documents()`: descarga entities JSON, construye documentos mob-centric con HP, drops, spawn, estrategia
- [x] 3.4 Función `build_mechanic_documents()`: scrapa Minecraft Wiki via MediaWiki API (páginas: Crafting, Enchanting, Brewing, Combat, Farming, Redstone), split por H2, almacena `parent_content` en payload
- [x] 3.5 Función `ingest_all()`: crea colección `minecraft_knowledge` con vectores named (`dense` 384-dim, `sparse` BM42); comprueba si ya existe con datos (idempotente); indexa todos los documentos en batches de 100
- [x] 3.6 Verificar script manualmente: `uv run python scripts/ingest.py` — sin errores, colección creada en Qdrant (verificar en `http://localhost:6333/dashboard`)

## 4. Grafo LangGraph: extensión de `classify_intent` y nuevo nodo

- [x] 4.1 Ampliar `IntentOutput` en `nodes.py` con `doc_type: Literal["item", "mob", "mechanic", "none"]`
- [x] 4.2 Actualizar system prompt de `classify_intent` para que también clasifique `doc_type`
- [x] 4.3 Ampliar `ButlerState` en `state.py` con `doc_type: str` y `retrieved_docs: list[dict]`
- [x] 4.4 Crear nodo `retrieve_context(state) -> dict` en `nodes.py` que llama a `retriever.retrieve()`
- [x] 4.5 Actualizar `answer_question` para incluir los `retrieved_docs` en el prompt cuando existan
- [x] 4.6 Actualizar `graph.py`: insertar nodo `retrieve_context` entre `classify_intent` y `answer_question`; ajustar routing condicional para que `move` y `speak` sigan saltando `retrieve_context`

## 5. Tests de backend (OBLIGATORIO)

- [x] 5.1 Actualizar tests existentes de `ButlerService` y `nodes` para que pasen con el nuevo estado (`doc_type`, `retrieved_docs`)
- [x] 5.2 Añadir tests para `classify_intent` con `doc_type`: pregunta de ítem → `doc_type="item"`; pregunta de mob → `doc_type="mob"`; movimiento → `doc_type="none"`
- [x] 5.3 Ejecutar `uv run pytest -q` — suite completa en verde
- [x] 5.4 Guardar informe en `openspec/changes/rag-core/reports/YYYY-MM-DD-backend-tests.md`

## 6. Pruebas manuales con curl (OBLIGATORIO - EL AGENTE LO EJECUTA)

- [x] 6.1 Levantar servicios: `docker compose up -d qdrant` y arrancar backend
- [x] 6.2 Ejecutar ingesta: `uv run python scripts/ingest.py`
- [x] 6.3 Login: `POST /api/auth/login` → obtener token
- [x] 6.4 Pregunta de receta: `POST /api/butler/ask` con `{"message": "¿cómo fabrico una espada de diamante?"}` → 200, respuesta con ingredientes correctos, sin alucinaciones
- [x] 6.5 Pregunta de mob: `POST /api/butler/ask` con `{"message": "¿qué dropea un creeper?"}` → 200, respuesta con gunpowder y music disc
- [x] 6.6 Pregunta de mecánica: `POST /api/butler/ask` con `{"message": "¿cómo funciona el encantamiento?"}` → 200, respuesta coherente con contexto wiki
- [x] 6.7 Movimiento (sin RAG): `POST /api/butler/ask` con `{"message": "ve a 100 64 -200"}` → 200, `move_to_position`, sin llamada a Qdrant
- [x] 6.8 Sin token → 401
- [x] 6.9 Verificar en LangSmith que las trazas muestran el nodo `retrieve_context` y los documentos recuperados
- [x] 6.10 Documentar comandos y respuestas en el informe de reports/

## 7. Cierre (OBLIGATORIO)

- [x] 7.1 Actualizar `docs/backend-standards.md` con sección RAG (cómo añadir nuevos tipos de documento, cómo re-indexar)
- [x] 7.2 Actualizar `docs/roadmap.md`: marcar `rag-core` como completado
- [x] 7.3 Actualizar `README.md`: añadir paso de ingesta a las instrucciones de setup
- [ ] 7.4 PR con `gh` usando la skill `write-pr-report`
