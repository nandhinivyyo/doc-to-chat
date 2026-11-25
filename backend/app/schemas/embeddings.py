from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class EmbeddingRecord(BaseModel):
    """Common embedding record linking a chunk to its numerical vector."""

    embedding_id: str
    chunk_id: str
    document_id: str
    content_type: Literal["text", "table"]
    chunking_method: str
    page: int
    section_heading: Optional[str] = None
    text: str
    embedding_model: str
    embedding_dimension: int
    vector: List[float] = Field(default_factory=list)


class VectorMetadataItem(BaseModel):
    """Metadata stored alongside a FAISS index linking vector_index to its source chunk."""

    vector_index: int
    embedding_id: str
    chunk_id: str
    document_id: str
    content_type: Literal["text", "table"]
    chunking_method: str
    page: int
    section_heading: Optional[str] = None
    text: str
    embedding_model: str
    embedding_dimension: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MethodVectorStats(BaseModel):
    """Vector count and storage paths for one FAISS index."""

    method: str
    label: str
    vector_count: int
    dimension: int
    index_path: str
    metadata_path: str


class EmbeddingSummaryResponse(BaseModel):
    """Summary of Phase 6 embedding generation and FAISS storage for a document."""

    document_id: str
    document_name: str
    model: str
    dimension: int
    normalization: str
    methods_processed: int
    text_vectors: int
    table_vectors: int
    image_vectors: int = 0
    image_embeddings_status: str = "Not implemented in Phase 6"
    total_vectors: int
    method_counts: Dict[str, int] = Field(default_factory=dict)
    method_stats: List[MethodVectorStats] = Field(default_factory=list)
    table_stats: Optional[MethodVectorStats] = None
    image_metadata_path: Optional[str] = None
    storage_location: str
    status: Literal["completed"] = "completed"
    created_at: datetime
