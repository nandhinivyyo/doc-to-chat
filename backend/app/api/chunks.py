from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.chunking.pipeline import chunk_document
from app.chunking.storage import (
    load_chunk_summary,
    load_document_chunks,
    load_image_chunks,
    load_method_chunks,
    load_table_chunks,
)
from app.core.config import Settings, get_settings
from app.schemas.chunking import (
    ALL_CHUNKING_METHODS,
    ChunkSummaryResponse,
    ChunkingParameters,
    DocumentChunkingResponse,
    ImageChunksResponse,
    MethodChunksResponse,
    TableChunksResponse,
)

router = APIRouter(prefix="/api/documents", tags=["chunks"])


@router.post("/{document_id}/chunk", response_model=DocumentChunkingResponse)
def run_document_chunking(
    document_id: str,
    params: Optional[ChunkingParameters] = Body(default=None),
    settings: Settings = Depends(get_settings),
) -> DocumentChunkingResponse:
    """Run Phase 4 chunking across all 8 text methods plus table and image chunks."""
    try:
        return chunk_document(document_id=document_id, settings=settings, params=params)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/{document_id}/chunks", response_model=DocumentChunkingResponse)
def get_document_chunks(
    document_id: str,
    settings: Settings = Depends(get_settings),
) -> DocumentChunkingResponse:
    """Retrieve Phase 4 chunking output, generating it on demand if not yet cached."""
    try:
        return load_document_chunks(settings.chunk_outputs_path, document_id)
    except FileNotFoundError:
        try:
            return chunk_document(document_id=document_id, settings=settings)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document '{document_id}' not found.",
            ) from exc


@router.get("/{document_id}/chunks/summary", response_model=ChunkSummaryResponse)
def get_chunks_summary(
    document_id: str,
    settings: Settings = Depends(get_settings),
) -> ChunkSummaryResponse:
    """Read-only summary and statistics across all 8 chunking methods, tables, and images."""
    try:
        return load_chunk_summary(settings.chunk_outputs_path, document_id)
    except FileNotFoundError:
        try:
            chunk_document(document_id=document_id, settings=settings)
            return load_chunk_summary(settings.chunk_outputs_path, document_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document '{document_id}' not found.",
            ) from exc


@router.get("/{document_id}/chunks/tables", response_model=TableChunksResponse)
def get_table_chunks(
    document_id: str,
    settings: Settings = Depends(get_settings),
) -> TableChunksResponse:
    """Read-only endpoint returning structured table chunks."""
    try:
        return load_table_chunks(settings.chunk_outputs_path, document_id)
    except FileNotFoundError:
        try:
            chunk_document(document_id=document_id, settings=settings)
            return load_table_chunks(settings.chunk_outputs_path, document_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document '{document_id}' not found.",
            ) from exc


@router.get("/{document_id}/chunks/images", response_model=ImageChunksResponse)
def get_image_chunks(
    document_id: str,
    settings: Settings = Depends(get_settings),
) -> ImageChunksResponse:
    """Read-only endpoint returning non-decorative content image chunks."""
    try:
        return load_image_chunks(settings.chunk_outputs_path, document_id)
    except FileNotFoundError:
        try:
            chunk_document(document_id=document_id, settings=settings)
            return load_image_chunks(settings.chunk_outputs_path, document_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document '{document_id}' not found.",
            ) from exc


@router.get("/{document_id}/chunks/{method}", response_model=MethodChunksResponse)
def get_method_chunks(
    document_id: str,
    method: str,
    settings: Settings = Depends(get_settings),
) -> MethodChunksResponse:
    """Retrieve text chunks and statistics for one specific chunking method."""
    if method not in ALL_CHUNKING_METHODS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported chunking method '{method}'. Expected one of: {', '.join(ALL_CHUNKING_METHODS)}.",
        )

    try:
        return load_method_chunks(settings.chunk_outputs_path, document_id, method)
    except FileNotFoundError:
        try:
            chunk_document(document_id=document_id, settings=settings)
            return load_method_chunks(settings.chunk_outputs_path, document_id, method)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document '{document_id}' not found.",
            ) from exc
