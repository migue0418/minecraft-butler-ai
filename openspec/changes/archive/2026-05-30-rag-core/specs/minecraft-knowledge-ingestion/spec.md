## ADDED Requirements

### Requirement: Ingest script builds item-centric documents
The system SHALL build one document per Minecraft item combining recipe, stats, enchantments and repair info from `PrismarineJS/minecraft-data` and `misode/mcmeta` recipe JSON files.

#### Scenario: Item document contains recipe and stats
- **WHEN** the ingest script processes `diamond_sword`
- **THEN** the resulting document payload includes recipe ingredients, crafting pattern, damage, durability and applicable enchantments

#### Scenario: Item without recipe is still indexed
- **WHEN** an item has no crafting recipe (e.g. `nether_star`)
- **THEN** a document is still created with stats and drop/obtain info, with recipe field omitted

### Requirement: Ingest script builds mob-centric documents
The system SHALL build one document per Minecraft mob combining HP, attack damage, drops, spawn conditions and combat strategy.

#### Scenario: Mob document contains drops and spawn info
- **WHEN** the ingest script processes `creeper`
- **THEN** the resulting document includes HP, explosion damage, gunpowder drop, spawn biomes and strategy notes

### Requirement: Ingest script builds section-centric wiki documents with parent content
The system SHALL fetch Minecraft Wiki pages for core mechanics, split them by H2 section, index the chunk text, and store the full section as `parent_content` in the payload.

#### Scenario: Wiki section chunk stores parent content
- **WHEN** a wiki page is chunked by H2 section
- **THEN** each Qdrant point payload contains both `chunk_text` (indexed) and `parent_content` (full section, for retrieval)

#### Scenario: Wiki scraper respects rate limiting
- **WHEN** the ingest script fetches multiple wiki pages
- **THEN** a minimum 500ms delay is applied between API requests

### Requirement: All documents carry doc_type metadata
The system SHALL set a `type` field in every Qdrant point payload with value `"item"`, `"mob"` or `"mechanic"`, enabling metadata-filtered search.

#### Scenario: Item document has correct type
- **WHEN** a document for `iron_pickaxe` is indexed
- **THEN** its Qdrant payload contains `{"type": "item", "id": "iron_pickaxe"}`

### Requirement: Ingest uses the same embedding model as the runtime retriever
The system SHALL use `get_embedding_model()` from `app/features/butler/llm` to generate embeddings during ingestion, ensuring vector space consistency with the runtime query encoder.

#### Scenario: Model change requires re-ingestion
- **WHEN** `EMBEDDING_MODEL` setting is changed
- **THEN** the ingest script must be re-run to rebuild the collection with the new vector space
