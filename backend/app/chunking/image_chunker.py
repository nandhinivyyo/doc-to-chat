import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.schemas.chunking import ChunkItem
from app.schemas.classification import ClassifiedImageItem, ClassifiedTextItem

logger = logging.getLogger(__name__)


def _collect_page_context(clean_text_items: List[ClassifiedTextItem]) -> Dict[int, Dict[str, Optional[str]]]:
    """Collect existing section headings and exhibit captions per page from clean text."""
    page_info: Dict[int, Dict[str, Optional[str]]] = {}
    for item in clean_text_items:
        entry = page_info.setdefault(item.page, {"section_heading": None, "caption": None})
        if item.section_heading and entry["section_heading"] is None:
            entry["section_heading"] = item.section_heading
        first_line = item.text.splitlines()[0].strip() if item.text else ""
        if first_line.lower().startswith(("exhibit ", "figure ", "fig.")):
            existing = entry["caption"]
            entry["caption"] = f"{existing} | {first_line}" if existing else first_line
    return page_info


def create_image_chunks(
    images: List[ClassifiedImageItem],
    clean_text_items: List[ClassifiedTextItem],
    extracted_root: Path,
    document_id: str,
    document_name: str,
) -> Tuple[List[ChunkItem], List[str]]:
    """Create image chunks exclusively for meaningful non-decorative Phase 3 images."""
    chunks: List[ChunkItem] = []
    warnings: List[str] = []
    page_context = _collect_page_context(clean_text_items)
    chunk_num = 1

    for img in images:
        if img.is_decorative:
            continue

        image_file = extracted_root / img.image_path
        if not image_file.is_file():
            msg = f"Skipped missing image file '{img.image_path}' ({img.image_id}, page {img.page})."
            logger.warning(msg)
            warnings.append(msg)
            continue

        ctx = page_context.get(img.page, {})
        section_heading = ctx.get("section_heading")
        caption = ctx.get("caption")

        lines = [
            f"Image {img.image_id} (Page {img.page})",
            f"Source: {document_name}",
            f"File: {img.image_path} ({img.width}x{img.height} {img.image_format})",
        ]
        if section_heading:
            lines.append(f"Section: {section_heading}")
        if caption and caption != section_heading:
            lines.append(f"Page Exhibits/Captions: {caption}")
        if img.ocr_text:
            lines.append(f"OCR Text: {img.ocr_text}")

        chunks.append(
            ChunkItem(
                chunk_id=f"image_chunk_{chunk_num:03d}",
                document_id=document_id,
                page=img.page,
                content_type="image",
                chunking_method="image_metadata",
                content="\n".join(lines),
                metadata={
                    "document_name": document_name,
                    "image_id": img.image_id,
                    "image_path": img.image_path,
                    "image_url": img.image_url,
                    "image_format": img.image_format,
                    "width": img.width,
                    "height": img.height,
                    "bbox": img.bbox,
                    "section_heading": section_heading,
                    "caption_context": caption,
                    "ocr_text": img.ocr_text,
                },
            )
        )
        chunk_num += 1

    return chunks, warnings
