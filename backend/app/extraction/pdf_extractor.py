import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import pdfplumber
import pymupdf

from app.core.config import Settings
from app.extraction.image_extractor import extract_page_images
from app.extraction.ocr_processor import ocr_pdf_page
from app.extraction.storage import (
    ensure_extraction_dirs,
    get_document_image_dir,
    save_extraction_result,
)
from app.extraction.table_extractor import extract_page_tables
from app.extraction.text_extractor import assess_text_meaningfulness, extract_page_text_blocks
from app.schemas.document import (
    DocumentExtractionResponse,
    DocumentSummary,
    ImageItem,
    PageMetadata,
    TableItem,
    TextItem,
)

logger = logging.getLogger(__name__)


class PDFExtractionError(Exception):
    """Raised when a PDF file cannot be opened or validated."""


def extract_pdf_document(
    pdf_path: Path,
    document_id: str,
    settings: Settings,
    original_filename: Optional[str] = None,
) -> DocumentExtractionResponse:
    """Run the full Phase 2 multimodal extraction pipeline on a single PDF file."""
    if not pdf_path.is_file():
        raise PDFExtractionError(f"PDF file not found: {pdf_path}")

    file_size = pdf_path.stat().st_size
    if file_size == 0:
        raise PDFExtractionError(f"PDF file is empty (0 bytes): {pdf_path.name}")

    doc_name = original_filename or pdf_path.name
    logger.info("Loading PDF '%s' (document_id=%s, size=%d bytes)...", doc_name, document_id, file_size)

    try:
        pymupdf_doc = pymupdf.open(str(pdf_path))
    except Exception as exc:
        raise PDFExtractionError(f"Failed to open PDF '{doc_name}': {exc}") from exc

    if pymupdf_doc.needs_pass:
        pymupdf_doc.close()
        raise PDFExtractionError(f"PDF '{doc_name}' is password-protected and cannot be processed.")

    total_pages = len(pymupdf_doc)
    if total_pages == 0:
        pymupdf_doc.close()
        raise PDFExtractionError(f"PDF '{doc_name}' contains 0 pages.")

    logger.info("Total pages: %d (%s)", total_pages, doc_name)

    extracted_root = settings.extracted_storage_path
    ensure_extraction_dirs(extracted_root, document_id)
    images_dir = get_document_image_dir(extracted_root, document_id)

    plumber_doc = None
    doc_errors: List[str] = []
    try:
        plumber_doc = pdfplumber.open(str(pdf_path))
    except Exception as exc:
        msg = f"pdfplumber could not open '{doc_name}' (table fallback disabled): {exc}"
        logger.warning(msg)
        doc_errors.append(msg)

    all_text: List[TextItem] = []
    all_tables: List[TableItem] = []
    all_images: List[ImageItem] = []
    page_metadata_list: List[PageMetadata] = []
    ocr_pages: List[int] = []

    text_counter = 1
    table_counter = 1
    image_counter = 1
    active_heading: Optional[str] = None

    try:
        for page_idx in range(total_pages):
            page_num = page_idx + 1
            page_errors: List[str] = []
            page = pymupdf_doc[page_idx]
            rect = page.rect

            # 1. Text extraction
            logger.debug("Extracting text from '%s' page %d...", doc_name, page_num)
            page_text_items, combined_text, active_heading = extract_page_text_blocks(
                page=page,
                document_name=doc_name,
                page_number=page_num,
                start_index=text_counter,
                active_heading=active_heading,
            )

            meaningful, reason = assess_text_meaningfulness(
                combined_text,
                min_chars=settings.min_meaningful_text_chars,
                min_alpha=settings.min_alpha_chars,
            )

            ocr_used = False
            ocr_reason: Optional[str] = None
            if not meaningful:
                logger.info("OCR required for page %d of '%s' (%s)", page_num, doc_name, reason)
                ocr_text, ocr_engine, ocr_error = ocr_pdf_page(
                    page=page,
                    document_name=doc_name,
                    page_number=page_num,
                    dpi=settings.ocr_dpi,
                    preferred_engine=settings.ocr_engine,
                )
                ocr_reason = reason
                if ocr_error:
                    page_errors.append(f"OCR error on page {page_num}: {ocr_error}")
                if ocr_text.strip():
                    ocr_used = True
                    ocr_pages.append(page_num)
                    page_text_items = [
                        TextItem(
                            content_id=f"text_{text_counter:04d}",
                            document=doc_name,
                            page=page_num,
                            content=ocr_text.strip(),
                            bbox=[0.0, 0.0, round(float(rect.width), 2), round(float(rect.height), 2)],
                            section_heading=active_heading,
                            ocr_used=True,
                            char_count=len(ocr_text.strip()),
                        )
                    ]
                    combined_text = ocr_text.strip()
                elif not page_text_items:
                    msg = f"Page {page_num} of '{doc_name}' yielded no extractable text (reason={reason})."
                    logger.warning(msg)
                    page_errors.append(msg)

            all_text.extend(page_text_items)
            text_counter += len(page_text_items)

            # 2. Table extraction (PyMuPDF primary, pdfplumber fallback)
            plumber_page = plumber_doc.pages[page_idx] if plumber_doc and page_idx < len(plumber_doc.pages) else None
            page_tables, table_errors = extract_page_tables(
                pymupdf_page=page,
                plumber_page=plumber_page,
                document_name=doc_name,
                page_number=page_num,
                start_index=table_counter,
            )
            all_tables.extend(page_tables)
            table_counter += len(page_tables)
            page_errors.extend(table_errors)

            # 3. Embedded image extraction
            page_images, image_errors = extract_page_images(
                doc=pymupdf_doc,
                page=page,
                document_id=document_id,
                document_name=doc_name,
                page_number=page_num,
                images_dir=images_dir,
                start_index=image_counter,
            )
            all_images.extend(page_images)
            image_counter += len(page_images)
            page_errors.extend(image_errors)

            doc_errors.extend(page_errors)
            page_metadata_list.append(
                PageMetadata(
                    page=page_num,
                    width=round(float(rect.width), 2),
                    height=round(float(rect.height), 2),
                    text_items_count=len(page_text_items),
                    tables_count=len(page_tables),
                    images_count=len(page_images),
                    ocr_used=ocr_used,
                    ocr_reason=ocr_reason,
                    char_count=len(combined_text),
                    errors=page_errors,
                )
            )
    finally:
        pymupdf_doc.close()
        if plumber_doc is not None:
            plumber_doc.close()

    logger.info("Text items extracted: %d (%s)", len(all_text), doc_name)
    logger.info("Tables detected: %d (%s)", len(all_tables), doc_name)
    logger.info("Images extracted: %d (%s)", len(all_images), doc_name)
    if ocr_pages:
        logger.info("OCR used on pages: %s (%s)", ocr_pages, doc_name)
    logger.info("Extraction completed for '%s'", doc_name)

    summary = DocumentSummary(
        document_id=document_id,
        document=doc_name,
        file_size_bytes=file_size,
        total_pages=total_pages,
        text_items=len(all_text),
        tables=len(all_tables),
        images=len(all_images),
        ocr_pages=ocr_pages,
        ocr_used=len(ocr_pages) > 0,
        status="completed_with_warnings" if doc_errors else "completed",
        created_at=datetime.now(timezone.utc),
        errors=doc_errors,
    )

    result = DocumentExtractionResponse(
        summary=summary,
        pages=page_metadata_list,
        text=all_text,
        tables=all_tables,
        images=all_images,
    )
    save_extraction_result(extracted_root, result)
    return result

