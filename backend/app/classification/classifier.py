import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from app.classification.boilerplate_detector import detect_boilerplate_text_items
from app.classification.deduplicator import remove_table_duplicates_from_text
from app.classification.image_classifier import classify_images
from app.classification.storage import save_classified_document
from app.classification.table_refiner import refine_tables
from app.core.config import Settings
from app.extraction.storage import load_extraction_result
from app.schemas.classification import (
    ClassificationStats,
    ClassifiedDocumentResponse,
    ClassifiedTextItem,
)

logger = logging.getLogger(__name__)


def _clean_prose_text(text: str) -> str:
    """Normalize line-level trailing spaces while preserving paragraph breaks."""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in (text or "").splitlines()]
    return "\n".join(line for line in lines if line).strip()


def classify_document(
    document_id: str,
    settings: Settings,
    pdf_path: Optional[Path] = None,
) -> ClassifiedDocumentResponse:
    """Run Phase 3 classification and cleanup over a document's raw extraction."""
    extracted_root = settings.extracted_storage_path
    raw_extraction = load_extraction_result(extracted_root, document_id)
    summary = raw_extraction.summary

    resolved_pdf_path = pdf_path
    if resolved_pdf_path is None:
        candidate = settings.pdf_storage_path / f"{document_id}.pdf"
        if candidate.is_file():
            resolved_pdf_path = candidate

    logger.info("Running Phase 3 classification for '%s' (%s)...", summary.document, document_id)

    classified_tables, refined_tables_count = refine_tables(
        raw_tables=raw_extraction.tables,
        document_id=document_id,
        document_name=summary.document,
        pdf_path=resolved_pdf_path,
    )

    non_duplicate_text, excluded_duplicates = remove_table_duplicates_from_text(
        raw_text_items=raw_extraction.text,
        tables=classified_tables,
    )

    boilerplate_reasons = detect_boilerplate_text_items(
        text_items=non_duplicate_text,
        pages=raw_extraction.pages,
    )

    classified_text: List[ClassifiedTextItem] = []
    boilerplate_count = 0
    active_clean_heading: Optional[str] = None
    for idx, item in enumerate(non_duplicate_text, start=1):
        reason = boilerplate_reasons.get(item.content_id)
        is_boilerplate = reason is not None
        if is_boilerplate:
            boilerplate_count += 1
        elif (
            item.section_heading
            and item.section_heading in re.sub(r"\s+", " ", item.content)
            and not re.match(r"^(?:table|figure|fig\.)\s+\d+", item.section_heading, re.I)
        ):
            active_clean_heading = item.section_heading

        cleaned_content = _clean_prose_text(item.content)
        classified_text.append(
            ClassifiedTextItem(
                content_id=f"text_{idx:04d}",
                document_id=document_id,
                document_name=summary.document,
                page=item.page,
                text=cleaned_content,
                bbox=item.bbox,
                section_heading=None if is_boilerplate else active_clean_heading,
                extraction_method="ocr" if item.ocr_used else "pymupdf",
                is_boilerplate=is_boilerplate,
                metadata={
                    "raw_content_id": item.content_id,
                    "char_count": len(cleaned_content),
                    "ocr_used": item.ocr_used,
                    "boilerplate_reason": reason,
                },
            )
        )

    classified_images = classify_images(
        raw_images=raw_extraction.images,
        pages=raw_extraction.pages,
        extracted_root=extracted_root,
        document_id=document_id,
        document_name=summary.document,
    )

    decorative_count = sum(1 for img in classified_images if img.is_decorative)
    content_image_count = len(classified_images) - decorative_count
    clean_text_count = len(classified_text) - boilerplate_count

    stats = ClassificationStats(
        raw_text_items=len(raw_extraction.text),
        classified_text_items=len(classified_text),
        clean_text_items=clean_text_count,
        boilerplate_text_items=boilerplate_count,
        removed_table_duplicates=len(excluded_duplicates),
        raw_tables=len(raw_extraction.tables),
        classified_tables=len(classified_tables),
        refined_tables_count=refined_tables_count,
        raw_images=len(raw_extraction.images),
        classified_images=len(classified_images),
        content_images=content_image_count,
        decorative_images=decorative_count,
    )

    result = ClassifiedDocumentResponse(
        document_id=document_id,
        document_name=summary.document,
        total_pages=summary.total_pages,
        created_at=datetime.now(timezone.utc),
        stats=stats,
        text=classified_text,
        tables=classified_tables,
        images=classified_images,
        excluded_duplicates=excluded_duplicates,
    )

    output_path = save_classified_document(extracted_root, result)
    logger.info(
        "Phase 3 classification completed for '%s': text=%d (clean=%d, boilerplate=%d, table_dupes_removed=%d), tables=%d (refined=%d), images=%d (content=%d, decorative=%d) -> %s",
        summary.document,
        stats.classified_text_items,
        stats.clean_text_items,
        stats.boilerplate_text_items,
        stats.removed_table_duplicates,
        stats.classified_tables,
        stats.refined_tables_count,
        stats.classified_images,
        stats.content_images,
        stats.decorative_images,
        output_path,
    )
    return result

