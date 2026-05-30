# Informe de verificación — fix-rag-multilingual-retrieval

Fecha: 2026-05-31

## Diagnóstico (causa raíz)

Diagnóstico en vivo con `scripts/diag_rag.py` contra la colección real `minecraft_knowledge` (1665 puntos):

- El retriever **denso** (`paraphrase-multilingual-MiniLM-L12-v2`) es cross-lingual y recupera perfecto en ES y EN.
- La rama **sparse BM42** (`Qdrant/bm42-all-minilm-l6-v2-attentions`) es léxica solo-inglés: en español devuelve ruido o nada, y la fusión RRF de Qdrant (k=2) le daba peso igual al denso, corrompiendo el ranking.
- Los **rerankers de FlashRank** no reordenan ES→EN. Test horse vs gravel:
  - `ms-marco-MultiBERT-L-12` ("multilingüe"): EN horse 0.987 > gravel 0.961 ✅; **ES gravel 0.002 > horse 0.001 ❌** (ruido).
  - `ms-marco-MiniLM-L-12-v2` (inglés): EN horse 0.997 > gravel 0.0 ✅; ES ambos 0.0 ❌.

Conclusión: las etapas léxicas (sparse + reranker) son solo-inglés y degradan el denso multilingüe. **Decisión: dense-only.**

## Evaluación de recuperación (dense-only, ruta de producción)

`uv run python scripts/diag_rag.py`:

| Consulta | Top-1 | OK |
|---|---|---|
| ES "¿Qué objetos dropea un caballo?" | mob Horse (0.633) | ✅ |
| ES "¿Qué objetos dropea una vaca?" | mob Cow (0.681) | ✅ |
| EN "What items does a cow drop?" | mob Cow (0.636), por encima de Cow Spawn Egg | ✅ |
| ES "¿Cómo encanto una espada?" | item Diamond Sword (0.664) y demás espadas | ✅ |

Cumple los 3 escenarios del spec `rag-pipeline`.

## Tests de backend

`uv run pytest -q` → **52 passed, 3 warnings** (warnings de SlowAPI, ajenas al cambio).
`tests/features/butler/test_rag_retriever.py` → 15 passed (reescritos a dense-only).

## Estado de BD / Qdrant

- Sin reingesta. Colección `minecraft_knowledge`: **1665 puntos antes y después** (`GET /collections/minecraft_knowledge`).
- El cambio no muta la BD relacional ni la colección vectorial; solo la ruta de consulta.

## Prueba del endpoint (live server, POST /api/butler/ask, autenticado)

| Mensaje | HTTP | Respuesta |
|---|---|---|
| EN "What items does a cow drop?" | 200 | carne de res, cuero, leche ✅ |
| ES "¿Qué objetos dropea un caballo?" | 200 | cuero, silla de montar, armadura de caballo ✅ |
| ES "¿Qué objetos dropea una vaca?" | 200 | respuesta correcta ✅ |

(El body con caracteres no-ASCII se envió vía httpx por encoding del shell; el endpoint responde 200 y con el contexto correcto.)

## Filtro duro por doc_type (arreglo adicional)

Tras el fix dense-only, se detectó un segundo problema independiente del retriever: `retrieve_context` filtraba por el `doc_type` que infiere el clasificador. Para "¿qué items dropea una vaca?" el clasificador devolvía `item`, y el filtro excluía el documento del mob Cow → el LLM caía a conocimiento general.

- Verificación: `dense_search("¿Qué items dropea una vaca?")` **sin filtro** → Cow top-1 (0.638); "¿qué dropea el mineral de hierro?" → Iron Ore top-1 (el denso acierta el tipo por semántica).
- Fix: `retrieve_context` deja de pasar `doc_type` como filtro. Test `test_retrieve_context_does_not_hard_filter_by_doc_type`.
- HTTP `POST /api/butler/ask` "¿Qué items dropea una vaca?" → 200, respuesta fundamentada ("Según la información oficial, una vaca dropea... carne, cuero, leche").
- Suite: **53 passed**.

## Resultado

El butler responde correctamente preguntas en español: la recuperación deja de ser aleatoria, y las preguntas de drops ya no se rompen por la palabra usada ("items" vs "objetos"). No requiere reingesta ni cambios de datos.
