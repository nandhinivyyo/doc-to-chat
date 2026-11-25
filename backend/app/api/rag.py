from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.schemas.rag import RagChatRequest, RagChatResponse
from app.services.gemini_service import (
    GeminiConfigurationError,
    GeminiServiceError,
)
from app.services.rag_service import answer_document_question

router = APIRouter(prefix="/api/documents", tags=["rag"])


@router.post("/{document_id}/chat", response_model=RagChatResponse)
def chat_with_document(
    document_id: str,
    payload: RagChatRequest,
    settings: Settings = Depends(get_settings),
) -> RagChatResponse:
    """Answer a question about a document using Phase 7 retrieval + Gemini generation."""
    try:
        return answer_document_question(
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
    except GeminiConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except GeminiServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
