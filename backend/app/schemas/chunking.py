from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

ChunkMethodName = Literal[
    "fixed_size",
    "token_based",
    "sentence_based",
    "paragraph_based",
    "recursive",
    "sliding_window",
    "semantic",
    "structure_section",
]

ALL_CHUNKING_METHODS: List[ChunkMethodName] = [
    "fixed_size",
    "token_based",
    "sentence_based",
    "paragraph_based",
    "recursive",
    "sliding_window",
    "semantic",
    "structure_section",
]


class ChunkingParameters(BaseModel):
    """Configurable default parameters for the 8 Phase 4 text chunking methods."""

    fixed_chunk_size: int = Field(default=500, gt=0)
    fixed_overlap: int = Field(default=50, ge=0)

    token_max_tokens: int = Field(default=100, gt=0)
    token_overlap: int = Field(default=15, ge=0)

    sentence_max_sentences: int = Field(default=4, gt=0)
    sentence_overlap: int = Field(default=1, ge=0)
    sentence_max_chars: int = Field(default=1000, gt=0)

    paragraph_max_paragraphs: int = Field(default=2, gt=0)
    paragraph_max_chars: int = Field(default=1000, gt=0)

    recursive_chunk_size: int = Field(default=600, gt=0)
    recursive_overlap: int = Field(default=60, ge=0)

    sliding_window_size: int = Field(default=400, gt=0)
    sliding_step_size: int = Field(default=200, gt=0)

    semantic_similarity_threshold: float = Field(default=0.12, ge=0.0, le=1.0)
    semantic_max_chars: int = Field(default=900, gt=0)
    semantic_min_chars: int = Field(default=120, ge=0)

    section_max_chars: int = Field(default=1200, gt=0)
    section_overlap_chars: int = Field(default=0, ge=0)


class ChunkItem(BaseModel):
    """Common chunk representation shared across text, table, and image chunks."""

    chunk_id: str
    document_id: str
    page: int
    content_type: Literal["text", "table", "image"]
    chunking_method: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MethodChunkStats(BaseModel):
    """Simple statistical summary for a single chunking method."""

    method: str
    label: str
    chunk_count: int
    avg_chunk_length: float
    min_chunk_length: int
    max_chunk_length: int
    total_characters: int
    total_words: int


class DocumentChunkingResponse(BaseModel):
    """Complete Phase 4 chunking output for a document across all 8 methods."""

    document_id: str
    document_name: str
    total_pages: int
    created_at: datetime
    parameters: ChunkingParameters
    method_stats: List[MethodChunkStats] = Field(default_factory=list)
    table_chunks_count: int
    image_chunks_count: int
    warnings: List[str] = Field(default_factory=list)
    text_chunks: Dict[str, List[ChunkItem]] = Field(default_factory=dict)
    table_chunks: List[ChunkItem] = Field(default_factory=list)
    image_chunks: List[ChunkItem] = Field(default_factory=list)


class MethodChunksResponse(BaseModel):
    """Chunks and statistics for a single requested text chunking method."""

    document_id: str
    document_name: str
    method: str
    stats: MethodChunkStats
    chunks: List[ChunkItem] = Field(default_factory=list)


class ChunkSummaryResponse(BaseModel):
    """Read-only summary and statistics across all chunk types and 8 methods."""

    document_id: str
    document_name: str
    total_pages: int
    created_at: datetime
    parameters: ChunkingParameters
    method_stats: List[MethodChunkStats] = Field(default_factory=list)
    table_chunks_count: int
    image_chunks_count: int
    warnings: List[str] = Field(default_factory=list)


class TableChunksResponse(BaseModel):
    """Read-only response containing structured table chunks for visualization."""

    document_id: str
    document_name: str
    table_chunks_count: int
    tables: List[ChunkItem] = Field(default_factory=list)


class ImageChunksResponse(BaseModel):
    """Read-only response containing meaningful non-decorative image chunks."""

    document_id: str
    document_name: str
    image_chunks_count: int
    images: List[ChunkItem] = Field(default_factory=list)
