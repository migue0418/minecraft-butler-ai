## MODIFIED Requirements

### Requirement: Dense vector search over Minecraft knowledge
The system SHALL retrieve the top-K documents by dense vector similarity over Qdrant's `dense` named vector, using the multilingual embedding model. Because the dense model is cross-lingual, Spanish-language queries SHALL retrieve the correct documents from the English-language corpus. The system SHALL NOT mix in the sparse BM42 branch nor a cross-encoder reranker at query time, because both are English-only lexical stages that degrade multilingual ranking (BM42 returns noise for Spanish queries; FlashRank rerankers do not reorder Spanish→English). The system SHALL discard retrieved documents whose similarity score is below a configurable threshold (`qdrant_score_threshold`, default `0.0`) before building the prompt context, so that irrelevant low-score documents do not waste tokens nor mislead the responder.

#### Scenario: Spanish query returns the correct entity
- **WHEN** the query `"¿Qué objetos dropea un caballo?"` is sent
- **THEN** the `Horse` mob document is returned as the top result

#### Scenario: Spanish query for cow returns the cow document
- **WHEN** the query `"¿Qué objetos dropea una vaca?"` is sent
- **THEN** the `Cow` mob document is returned as the top result

#### Scenario: English query keeps the entity above its spawn egg
- **WHEN** the query `"What items does a cow drop?"` is sent
- **THEN** the `Cow` mob document is ranked above the `Cow Spawn Egg` item document

#### Scenario: Metadata filter restricts search to correct document type
- **WHEN** `doc_type` is `"mob"` and dense search is executed
- **THEN** the Qdrant query applies a `query_filter` on `payload.doc_type == "mob"` and only mob documents are considered

#### Scenario: No filter applied for doc_type none
- **WHEN** `doc_type` is `"none"` or `None`
- **THEN** the Qdrant query is executed without a `query_filter`

#### Scenario: Documentos por debajo del umbral se descartan
- **WHEN** `qdrant_score_threshold` es `0.3` y la búsqueda devuelve documentos con scores `0.45, 0.32, 0.18, 0.10`
- **THEN** solo los documentos con score `0.45` y `0.32` se incluyen en el contexto; los de `0.18` y `0.10` se descartan

#### Scenario: Umbral por defecto no filtra
- **WHEN** `qdrant_score_threshold` es `0.0` (default)
- **THEN** todos los documentos top-K devueltos por Qdrant se incluyen, igual que el comportamiento previo
