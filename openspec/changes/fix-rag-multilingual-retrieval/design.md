## Context

El butler responde preguntas de Minecraft contra una base de conocimiento 100% en inglés (ítems, mobs, mecánicas de la wiki) almacenada en Qdrant (colección `minecraft_knowledge`, 1665 puntos, named vectors `dense` 384-dim Cosine + `sparse` BM42). Los usuarios preguntan en español.

El pipeline actual (`app/features/butler/rag/retriever.py`) es: `hybrid_search` (prefetch dense + sparse, fusión RRF de Qdrant) → `rerank` (FlashRank). Diagnóstico en vivo con `scripts/diag_rag.py`:

- **Dense solo** (multilingüe) es excelente y cross-lingual: ES "caballo" → Horse 0.63 top-1; ES "vaca" → Cow 0.68 top-1.
- **Sparse BM42 solo** es léxico solo-inglés: ES "caballo" → solo "Brewing" 0.02; ES "vaca" → vacío.
- **Híbrido RRF** corrompe el orden: la RRF de Qdrant usa k=2, así que el primer resultado de la rama sparse recibe score 0.5, empatando con el primero del denso → "caballo" pone "Brewing" empatado con Horse; EN "cow" pone "Cow Spawn Egg" (0.625) por encima de "Cow" (0.59).
- **Reranker** actual: `Ranker()` por defecto carga `ms-marco-TinyBERT-L-2-v2`, solo inglés → no sabe reordenar ES→EN, no rescata el orden.

Causa raíz: el denso multilingüe acierta, pero las dos etapas léxicas inglesas (sparse + reranker) lo corrompen. No es un problema de embeddings ni de espacio vectorial.

## Goals / Non-Goals

**Goals:**
- Que las consultas en español devuelvan el documento correcto en el top-K (Horse para "caballo", Cow para "vaca").
- Mantener el beneficio léxico del híbrido para consultas en inglés sin que degrade a las en español.
- Reranker multilingüe configurable por `Settings`.
- Sin reingesta: solo cambia la ruta de consulta.

**Non-Goals:**
- No se traduce el corpus al español ni se reindexa Qdrant.
- No se cambia el modelo de embeddings denso (ya funciona).
- No se añade traducción de la query (descartado por el usuario a favor del enfoque híbrido multilingüe).

## Decisions

### Decisión 1 — Reranker multilingüe: `ms-marco-MultiBERT-L-12` vía FlashRank
FlashRank ya trae `ms-marco-MultiBERT-L-12` (mMARCO, 11 idiomas incl. español) en su `model_file_map`. Se pasa el `model_name` al `Ranker(model_name=...)`, leyéndolo de `Settings.reranker_model` (default `ms-marco-MultiBERT-L-12`).

- **Por qué sobre `bge-reranker-v2-m3`**: bge-m3 es más potente pero requeriría `sentence-transformers`/`FlagEmbedding` y un modelo de ~2GB; MultiBERT no añade dependencia (FlashRank ya instalado) y es ONNX ligero. Se elige la opción de menor fricción que resuelve el problema; bge-m3 queda como mejora futura si la precisión no basta.
- El reranker es la **pieza clave**: aunque el híbrido entregue candidatos algo desordenados, un cross-encoder multilingüe sobre el top-N los reordena correctamente en ES y EN.

### Decisión 2 — Fusión dense-dominante
Para que el reranker reciba siempre los buenos candidatos densos, la rama sparse no debe expulsarlos del conjunto prefetch. Opciones evaluadas:
- **(elegida) Mantener prefetch dense + sparse pero subir `prefetch_limit` y dejar que el reranker decida.** El reranker multilingüe sobre un conjunto amplio (p. ej. 20–30 candidatos de cada rama unidos) recupera el orden. Es el cambio mínimo y robusto.
- **`Fusion.DBSF`** (distribution-based score fusion) normaliza scores por rama y penaliza ramas de baja señal; alternativa razonable a RRF. Se deja como opción a validar empíricamente en la implementación con `diag_rag.py`.
- Descartado: eliminar sparse (es el enfoque "dense-only" que el usuario no eligió).

La implementación validará con `scripts/diag_rag.py` cuál de RRF-con-reranker vs DBSF da mejor top-K en ES; el criterio de aceptación son los escenarios del spec.

### Decisión 3 — Fix BM42 query embedding
`_encode_sparse` usará `_sparse_model.query_embed([text])` en lugar de `.embed([text])`. BM42 distingue documento (atención) de query (IDF). Correcto aunque su aporte en ES sea bajo; evita un encoding inválido de la consulta.

### Capa por capa (backend)
- `app/features/butler/rag/retriever.py`: `_encode_sparse` (query_embed), `_get_ranker` (model_name desde config), `hybrid_search` (estrategia de fusión), `_get_config`/`RetrieverConfig` (nuevo campo reranker).
- `app/features/butler/rag/schemas.py`: añadir `reranker_model` a `RetrieverConfig`.
- `app/core/settings.py` + `.example.env`: `RERANKER_MODEL` (default `ms-marco-MultiBERT-L-12`).
- Sin modelos SQLAlchemy, sin migración Alembic, sin cambios en `import_model_modules`.

## Risks / Trade-offs

- **El modelo MultiBERT se descarga la primera vez (~latencia/red).** → Igual que el reranker actual; con `SSL_VERIFY=false` FlashRank descarga vía HF. Cachea tras la primera carga.
- **MultiBERT puede ser menos preciso que bge-m3 en consultas largas.** → Aceptable para el dominio (preguntas cortas de Minecraft); bge-m3 queda documentado como mejora futura.
- **Latencia de carga del nuevo modelo en primer request.** → Igual patrón que el `Ranker()` actual (lazy global). Sin regresión.
- **DBSF vs RRF**: si DBSF no mejora, se mantiene RRF + reranker. → Decidido empíricamente con `diag_rag.py` antes de cerrar.

## Migration Plan

1. Cambio solo en ruta de consulta; sin reingesta ni migración de datos.
2. Desplegar: nueva `RERANKER_MODEL` en `.env` (default ya en `Settings`). Primera consulta descarga el modelo.
3. Rollback: revertir el commit; la colección Qdrant no se ha tocado.

## Outcome (decisión final tras evidencia)

Durante la implementación se midió cada variante con `scripts/diag_rag.py` contra la colección real:

- **DBSF > RRF** para fusión (RRF empataba ruido sparse con el denso; DBSF normalizaba). Pero…
- **El reranker multilingüe no es viable**: `ms-marco-MultiBERT-L-12` da scores ~0 (ruido) para consultas en español y llegó a poner "gravel" por encima de "horse" para "caballo". Los rerankers de FlashRank no reordenan ES→EN.
- **El denso multilingüe solo** ya devuelve el documento correcto en top-1 para ES y EN, y cumple los 3 escenarios del spec.

Por tanto, la decisión final (confirmada con el usuario) es **dense-only**: se elimina del flujo de consulta tanto la rama sparse BM42 como el reranker. Las Decisiones 1–3 anteriores quedan **supersedidas** por este resultado; se conservan arriba como registro del razonamiento.

## Open Questions

- Ninguna. La elección RRF vs DBSF vs reranker quedó resuelta empíricamente a favor de dense-only.
- (Fuera de alcance) Cobertura de corpus: preguntas como "poción de fuerza" recuperan ruido porque ese contenido vive en la mecánica wiki "Brewing", no en items. Mejorar la cobertura/segmentación del corpus es un cambio aparte.
