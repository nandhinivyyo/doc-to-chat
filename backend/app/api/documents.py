import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.classification.classifier import classify_document
from app.classification.storage import load_classified_document
from app.core.config import Settings, get_settings
from app.extraction.pdf_extractor import PDFExtractionError, extract_pdf_document
from app.extraction.storage import (
    get_document_image_dir,
    list_document_summaries,
    load_document_summary,
    load_extraction_result,
)
from app.schemas.classification import ClassifiedDocumentResponse
from app.schemas.document import (
    DocumentExtractionResponse,
    DocumentListResponse,
    DocumentSummary,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])


def _sanitize_filename(filename: str) -> str:
    """Keep only safe filename characters while preserving extension."""
    base = Path(filename).name
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    return sanitized or "document.pdf"


@router.get("", response_model=DocumentListResponse)
def get_documents(settings: Settings = Depends(get_settings)) -> DocumentListResponse:
    """List all processed PDF documents."""
    summaries = list_document_summaries(settings.extracted_storage_path)
    return DocumentListResponse(documents=summaries)


@router.post("/upload", response_model=DocumentSummary, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
) -> DocumentSummary:
    """Upload a single PDF file and run multimodal content extraction."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file name provided.",
        )

    safe_name = _sanitize_filename(file.filename)
    if not safe_name.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type for '{safe_name}'. Only .pdf files are supported.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded file '{safe_name}' is empty.",
        )

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.max_upload_size_mb} MB.",
        )

    if not content.lstrip().startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File '{safe_name}' does not have a valid PDF header (%PDF-).",
        )

    stem = Path(safe_name).stem[:40]
    document_id = f"{stem}_{uuid.uuid4().hex[:8]}"

    pdf_dir = settings.pdf_storage_path
    pdf_dir.mkdir(parents=True, exist_ok=True)
    saved_pdf_path = pdf_dir / f"{document_id}.pdf"
    saved_pdf_path.write_bytes(content)

    logger.info("Uploaded PDF saved as '%s' (%d bytes)", saved_pdf_path.name, len(content))

    try:
        result = extract_pdf_document(
            pdf_path=saved_pdf_path,
            document_id=document_id,
            settings=settings,
            original_filename=safe_name,
        )
    except PDFExtractionError as exc:
        logger.error("Extraction failed for '%s': %s", safe_name, exc)
        if saved_pdf_path.exists():
            saved_pdf_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    try:
        classify_document(
            document_id=document_id,
            settings=settings,
            pdf_path=saved_pdf_path,
        )
    except Exception as exc:
        logger.error("Phase 3 classification failed after upload for '%s': %s", document_id, exc)

    return result.summary


@router.get("/{document_id}", response_model=DocumentSummary)
def get_document(
    document_id: str,
    settings: Settings = Depends(get_settings),
) -> DocumentSummary:
    """Retrieve document-level metadata and extraction counts."""
    try:
        return load_document_summary(settings.extracted_storage_path, document_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        ) from exc


@router.get("/{document_id}/extraction", response_model=DocumentExtractionResponse)
def get_document_extraction(
    document_id: str,
    settings: Settings = Depends(get_settings),
) -> DocumentExtractionResponse:
    """Retrieve full extracted text, tables, images, and page metadata."""
    try:
        return load_extraction_result(settings.extracted_storage_path, document_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction data for document '{document_id}' not found.",
        ) from exc


@router.post("/{document_id}/classify", response_model=ClassifiedDocumentResponse)
def run_document_classification(
    document_id: str,
    settings: Settings = Depends(get_settings),
) -> ClassifiedDocumentResponse:
    """Run or re-run Phase 3 content classification and cleanup for a document."""
    try:
        return classify_document(document_id=document_id, settings=settings)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction data for document '{document_id}' not found.",
        ) from exc


@router.get("/{document_id}/classification", response_model=ClassifiedDocumentResponse)
def get_document_classification(
    document_id: str,
    settings: Settings = Depends(get_settings),
) -> ClassifiedDocumentResponse:
    """Retrieve Phase 3 classified content, generating it on demand if not yet cached."""
    try:
        return load_classified_document(settings.extracted_storage_path, document_id)
    except FileNotFoundError:
        try:
            return classify_document(document_id=document_id, settings=settings)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document '{document_id}' not found.",
            ) from exc


@router.get("/{document_id}/images/{file_name}")
def get_extracted_image(
    document_id: str,
    file_name: str,
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    """Serve an extracted image file safely."""
    safe_file = Path(file_name).name
    if safe_file != file_name or ".." in document_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image path.")

    image_dir = get_document_image_dir(settings.extracted_storage_path, document_id).resolve()
    target = (image_dir / safe_file).resolve()
    if not str(target).startswith(str(image_dir)) or not target.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image '{safe_file}' not found for document '{document_id}'.",
        )

    media_type = "image/jpeg" if target.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    return FileResponse(target, media_type=media_type)

