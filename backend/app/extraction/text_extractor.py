import logging
import re
from typing import List, Optional, Tuple

import pymupdf

from app.schemas.document import TextItem

logger = logging.getLogger(__name__)

_CAPTION_RE = re.compile(r"^(?:table|figure|fig\.)\s+\d+", re.IGNORECASE)
_BULLET_RE = re.compile(r"^(?:[\u2022\uf0b7\-*]|\d+\.)\s+")
_SINGLE_WORD_ALLOWED_HEADINGS = {
    "introduction",
    "overview",
    "background",
    "summary",
    "conclusion",
    "conclusions",
    "references",
    "appendix",
    "methodology",
}


def assess_text_meaningfulness(
    text: str,
    min_chars: int = 40,
    min_alpha: int = 15,
) -> Tuple[bool, str]:
    """Determine whether extracted page text is meaningful or requires OCR."""
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return False, "no_extractable_text"

    alpha_count = sum(1 for ch in cleaned if ch.isalpha())
    if len(cleaned) < min_chars or alpha_count < min_alpha:
        return (
            False,
            f"insufficient_text(chars={len(cleaned)}, alpha={alpha_count})",
        )

    return True, "meaningful_text"


def is_section_heading(text: str, max_font_size: float, is_bold: bool) -> bool:
    """Heuristic check for true document section headings (excluding captions/fragments)."""
    normalized = re.sub(r"\s+", " ", (text or "")).strip()
    if not normalized or len(normalized) > 140 or "\n" in (text or "").strip():
        return False
    if _CAPTION_RE.match(normalized) or _BULLET_RE.match(normalized):
        return False
    # Reject unbalanced parenthesis fragments such as wrapped caption tail 'Scenario)'
    if normalized.count("(") != normalized.count(")"):
        return False
    # Reject wrapped parenthetical tags or footnote markers
    if normalized.startswith("(") and normalized.endswith(")"):
        return False
    if normalized.endswith((",", ";")):
        return False

    alpha_chars = sum(1 for ch in normalized if ch.isalpha())
    if alpha_chars < 4:
        return False

    words = normalized.split()
    if len(words) == 1 and normalized.rstrip(":").lower() not in _SINGLE_WORD_ALLOWED_HEADINGS:
        return False

    if max_font_size >= 13.0:
        return True
    if is_bold and max_font_size >= 10.5 and len(words) <= 16:
        return True
    return False


def _merge_bboxes(bboxes: List[List[float]]) -> Optional[List[float]]:
    if not bboxes:
        return None
    return [
        round(min(b[0] for b in bboxes), 2),
        round(min(b[1] for b in bboxes), 2),
        round(max(b[2] for b in bboxes), 2),
        round(max(b[3] for b in bboxes), 2),
    ]


def extract_page_text_blocks(
    page: pymupdf.Page,
    document_name: str,
    page_number: int,
    start_index: int = 1,
    active_heading: Optional[str] = None,
) -> Tuple[List[TextItem], str, Optional[str]]:
    """Extract structured text blocks from a PDF page using PyMuPDF.

    Splits blocks when a standalone bold/large section heading line appears inside
    a multi-line block so each section keeps an accurate section_heading.
    """
    items: List[TextItem] = []
    combined_parts: List[str] = []
    current_heading = active_heading
    next_idx = start_index

    page_dict = page.get_text("dict")
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue

        segment_lines: List[str] = []
        segment_bboxes: List[List[float]] = []

        def flush_segment() -> None:
            nonlocal next_idx
            seg_text = "\n".join(segment_lines).strip()
            if not seg_text:
                segment_lines.clear()
                segment_bboxes.clear()
                return
            seg_bbox = _merge_bboxes(segment_bboxes) or (
                [round(float(v), 2) for v in block["bbox"]] if block.get("bbox") else None
            )
            items.append(
                TextItem(
                    content_id=f"text_{next_idx:04d}",
                    document=document_name,
                    page=page_number,
                    content=seg_text,
                    bbox=seg_bbox,
                    section_heading=current_heading,
                    ocr_used=False,
                    char_count=len(seg_text),
                )
            )
            combined_parts.append(seg_text)
            next_idx += 1
            segment_lines.clear()
            segment_bboxes.clear()

        for line in block.get("lines", []):
            span_texts: List[str] = []
            line_max_size = 0.0
            non_empty_spans = 0
            bold_spans = 0

            for span in line.get("spans", []):
                span_str = span.get("text", "")
                if span_str:
                    span_texts.append(span_str)
                    if span_str.strip():
                        non_empty_spans += 1
                        size = float(span.get("size", 0.0))
                        line_max_size = max(line_max_size, size)
                        flags = int(span.get("flags", 0))
                        if flags & 16 or "bold" in str(span.get("font", "")).lower():
                            bold_spans += 1

            joined_line = "".join(span_texts).strip()
            if not joined_line:
                continue

            line_all_bold = non_empty_spans > 0 and bold_spans == non_empty_spans
            raw_line_bbox = line.get("bbox")
            line_bbox = [float(v) for v in raw_line_bbox] if raw_line_bbox else None

            if is_section_heading(joined_line, line_max_size, line_all_bold):
                flush_segment()
                current_heading = re.sub(r"\s+", " ", joined_line).strip()
                segment_lines.append(joined_line)
                if line_bbox:
                    segment_bboxes.append(line_bbox)
            else:
                segment_lines.append(joined_line)
                if line_bbox:
                    segment_bboxes.append(line_bbox)

        flush_segment()

    return items, "\n\n".join(combined_parts), current_heading
