from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import Settings, get_settings
from app.embeddings.pipeline import generate_document_embeddings, load_embedding_summary
from app.schemas.embeddings import EmbeddingSummaryResponse

router = APIRouter(prefix="/api/documents", tags=["embeddings"])


@router.post("/{document_id}/embeddings/generate", response_model=EmbeddingSummaryResponse)
def generate_embeddings(
    document_id: str,
    batch_size: Optional[int] = Query(default=None, gt=0),
    settings: Settings = Depends(get_settings),
) -> EmbeddingSummaryResponse:
    """Generate embeddings for Phase 4 chunks and store FAISS indexes + metadata."""
    try:
        return generate_document_embeddings(
            document_id=document_id,
            settings=settings,
            batch_size=batch_size,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Phase 4 chunk outputs for document '{document_id}' not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/{document_id}/embeddings/summary", response_model=EmbeddingSummaryResponse)
def get_embeddings_summary(
    document_id: str,
    settings: Settings = Depends(get_settings),
) -> EmbeddingSummaryResponse:
    """Retrieve Phase 6 embedding & FAISS storage summary for a document."""
    try:
        return load_embedding_summary(settings.vector_store_path, document_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Embeddings for document '{document_id}' have not been generated yet.",
        ) from exc
