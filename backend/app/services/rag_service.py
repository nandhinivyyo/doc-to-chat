import logging

from app.core.config import Settings
from app.schemas.rag import RagChatRequest, RagChatResponse
from app.schemas.search import SemanticSearchRequest
from app.services.context_builder import (
    build_document_context,
    extract_source_references,
)
from app.services.gemini_service import generate_grounded_answer
from app.services.semantic_search import search_document

logger = logging.getLogger(__name__)

NO_RELEVANT_CONTEXT_MESSAGE = "No relevant information was found in the document."


def answer_document_question(
    document_id: str,
    request: RagChatRequest,
    settings: Settings,
) -> RagChatResponse:
    """Execute the Phase 8 RAG pipeline using Phase 7 retrieval and Gemini generation."""
    search_request = SemanticSearchRequest(
        query=request.query,
        top_k=request.top_k,
        chunking_method=request.chunking_method,
    )
    search_response = search_document(
        document_id=document_id,
        request=search_request,
        settings=settings,
    )

    non_empty_results = [item for item in search_response.results if item.text and item.text.strip()]
    if not non_empty_results:
        logger.info(
            "Phase 8 RAG for '%s': no relevant context retrieved; skipping Gemini call.",
            document_id,
        )
        return RagChatResponse(
            query=request.query,
            answer=NO_RELEVANT_CONTEXT_MESSAGE,
            sources=[],
            retrieved_chunks=0,
            model=settings.gemini_model,
        )

    document_context = build_document_context(non_empty_results)
    sources = extract_source_references(non_empty_results)

    answer = generate_grounded_answer(
        question=request.query,
        document_context=document_context,
        api_key=settings.gemini_api_key,
        model_name=settings.gemini_model,
        timeout_seconds=settings.gemini_timeout_seconds,
        fallback_models=settings.gemini_fallback_model_list,
    )

    logger.info(
        "Phase 8 RAG completed for '%s': retrieved=%d model='%s'",
        document_id,
        len(non_empty_results),
        settings.gemini_model,
    )

    return RagChatResponse(
        query=request.query,
        answer=answer,
        sources=sources,
        retrieved_chunks=len(non_empty_results),
        model=settings.gemini_model,
    )
