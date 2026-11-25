from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.chunking import ALL_CHUNKING_METHODS

DEFAULT_TOP_K = 5
MAX_TOP_K = 20

# Vector store directory names generated in Phase 6
ALL_VECTOR_STORES: List[str] = [*ALL_CHUNKING_METHODS, "tables"]

# Mapping accepted request filter names to Phase 6 directory names
SEARCH_METHOD_ALIASES: Dict[str, str] = {
    **{method: method for method in ALL_CHUNKING_METHODS},
    "tables": "tables",
    "table": "tables",
}


class SemanticSearchRequest(BaseModel):
    """Request payload for Phase 7 FAISS semantic search."""

    query: str
    top_k: int = Field(default=DEFAULT_TOP_K)
    chunking_method: Optional[str] = Field(default=None)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        cleaned = value.strip() if isinstance(value, str) else ""
        if not cleaned:
            raise ValueError("Search query must not be empty or whitespace-only.")
        return cleaned

    @field_validator("top_k")
    @classmethod
    def validate_top_k(cls, value: int) -> int:
        if value <= 0 or value > MAX_TOP_K:
            raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}.")
        return value

    @field_validator("chunking_method")
    @classmethod
    def validate_chunking_method(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned or cleaned.lower() in {"all", "all_methods"}:
            return None
        resolved = SEARCH_METHOD_ALIASES.get(cleaned)
        if not resolved:
            allowed = ", ".join(ALL_VECTOR_STORES)
            raise ValueError(
                f"Unsupported chunking_method '{value}'. Choose one of: {allowed}."
            )
        return resolved


class SemanticSearchResult(BaseModel):
    """Single ranked chunk returned by Phase 7 semantic search."""

    rank: int
    score: float
    chunk_id: str
    document_id: str
    content_type: Literal["text", "table"]
    chunking_method: str
    page: int
    section_heading: Optional[str] = None
    text: str


class SemanticSearchResponse(BaseModel):
    """Ranked semantic search response without LLM generation."""

    query: str
    top_k: int
    document_id: str
    chunking_method: Optional[str] = None
    model: str
    searched_stores: List[str] = Field(default_factory=list)
    total_candidates: int = 0
    results: List[SemanticSearchResult] = Field(default_factory=list)
