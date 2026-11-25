from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.search import SemanticSearchRequest


class RagChatRequest(SemanticSearchRequest):
    """Request payload for Phase 8 RAG question answering.

    Inherits query validation (non-empty, non-whitespace) and top_k bounds (1..20, default 5)
    from Phase 7 SemanticSearchRequest.
    """


class RagSourceReference(BaseModel):
    """Grounded document source reference returned alongside a Gemini answer."""

    rank: int
    score: float
    page: int
    chunk_id: str
    content_type: Literal["text", "table"]
    chunking_method: str
    section_heading: Optional[str] = None


class RagChatResponse(BaseModel):
    """Response payload for Phase 8 RAG chatbot queries."""

    query: str
    answer: str
    sources: List[RagSourceReference] = Field(default_factory=list)
    retrieved_chunks: int
    model: str
