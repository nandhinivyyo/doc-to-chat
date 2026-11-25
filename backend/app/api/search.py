from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.schemas.search import SemanticSearchRequest, SemanticSearchResponse
from app.services.semantic_search import search_document

router = APIRouter(prefix="/api/documents", tags=["search"])


@router.post("/{document_id}/search", response_model=SemanticSearchResponse)
def search_document_chunks(
    document_id: str,
    payload: SemanticSearchRequest,
    settings: Settings = Depends(get_settings),
) -> SemanticSearchResponse:
    """Run Phase 7 semantic similarity search over a document's Phase 6 FAISS indexes."""
    try:
        return search_document(
            document_id=document_id,
            request=payload,
            settings=settings,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
