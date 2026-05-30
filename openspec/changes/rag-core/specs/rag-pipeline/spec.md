## ADDED Requirements

### Requirement: Hybrid search over Minecraft knowledge
The system SHALL perform hybrid search combining dense vector similarity and sparse BM25 keyword matching, fusing results with Reciprocal Rank Fusion (RRF) via Qdrant's native prefetch mechanism.

#### Scenario: Dense + sparse fusion returns relevant item document
- **WHEN** a query `"cómo fabrico espada de diamante"` is sent with `doc_type="item"`
- **THEN** the hybrid search returns the `diamond_sword` item document in the top-3 results

#### Scenario: Metadata filter restricts search to correct document type
- **WHEN** `doc_type` is `"mob"` and hybrid search is executed
- **THEN** only documents with `payload.type == "mob"` are considered, regardless of relevance of other types

#### Scenario: No filter applied for doc_type none
- **WHEN** `doc_type` is `"none"`
- **THEN** the retriever returns an empty list without querying Qdrant

### Requirement: Cross-encoder reranking with FlashRank
The system SHALL rerank the top-20 candidates from hybrid search using FlashRank's cross-encoder before returning the final top-K documents to the LLM.

#### Scenario: Reranker improves precision over raw vector search
- **WHEN** hybrid search returns 20 candidates for a query
- **THEN** FlashRank reranks them and the system returns only the top-3 to the LLM context

#### Scenario: Reranker falls back gracefully on empty candidates
- **WHEN** hybrid search returns 0 candidates
- **THEN** the retriever returns an empty list without calling the reranker

### Requirement: Parent document retrieval for wiki mechanics
The system SHALL return the full parent section content for wiki mechanic documents, not the indexed chunk.

#### Scenario: Wiki chunk returns parent content to LLM
- **WHEN** a retrieved document has `doc_type="mechanic"` and a `parent_content` payload field
- **THEN** the `content` field exposed to the LLM is `parent_content`, not the chunk text

#### Scenario: Item and mob documents return their own content
- **WHEN** a retrieved document has `doc_type="item"` or `doc_type="mob"`
- **THEN** the full document text is returned as-is (no parent lookup needed)

### Requirement: Qdrant collection uses named dense and sparse vectors
The system SHALL maintain a single Qdrant collection `minecraft_knowledge` with named vectors `dense` (384-dim float) and `sparse` (BM42), enabling native hybrid search without client-side merging.

#### Scenario: Collection created with correct vector config
- **WHEN** `scripts/ingest.py` runs against an empty Qdrant instance
- **THEN** the collection `minecraft_knowledge` is created with `dense` and `sparse` named vectors

#### Scenario: Re-running ingest on non-empty collection skips re-indexing
- **WHEN** the collection already contains documents and `ingest.py` is run again
- **THEN** the script detects existing data and exits without re-indexing
