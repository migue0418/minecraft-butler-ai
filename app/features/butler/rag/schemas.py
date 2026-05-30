from pydantic import BaseModel


class RetrievedDoc(BaseModel):
    id: str
    content: str
    doc_type: str
    score: float
    metadata: dict = {}


class RetrieverConfig(BaseModel):
    qdrant_url: str
    collection: str
    api_key: str
    top_k: int
    prefetch_limit: int
    embedding_model: str
