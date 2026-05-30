## RENAMED Requirements

- FROM: `### Requirement: Hybrid search over Minecraft knowledge`
- TO: `### Requirement: Dense vector search over Minecraft knowledge`

## MODIFIED Requirements

### Requirement: Dense vector search over Minecraft knowledge
The system SHALL retrieve the top-K documents by dense vector similarity over Qdrant's `dense` named vector, using the multilingual embedding model. Because the dense model is cross-lingual, Spanish-language queries SHALL retrieve the correct documents from the English-language corpus. The system SHALL NOT mix in the sparse BM42 branch nor a cross-encoder reranker at query time, because both are English-only lexical stages that degrade multilingual ranking (BM42 returns noise for Spanish queries; FlashRank rerankers do not reorder Spanish→English).

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

## REMOVED Requirements

### Requirement: Cross-encoder reranking with FlashRank
**Reason**: FlashRank's rerankers are English-only at the cross-lingual level. The "multilingual" `ms-marco-MultiBERT-L-12` produces near-zero noise scores for Spanish queries (it ranked an irrelevant document above the relevant one in tests), and the English models score Spanish at 0. Reranking therefore degraded, rather than improved, Spanish retrieval. The cross-lingual dense retriever already returns the correct document at top-1 for both Spanish and English, so the reranking stage is removed.
**Migration**: No data migration. The query pipeline no longer calls a reranker; `get_retriever()` returns dense-search results directly. The Qdrant collection is unchanged (no re-ingestion).
