import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pdfplumber

from app.extraction.table_extractor import clean_table_rows, is_valid_table, table_to_markdown
from app.schemas.classification import ClassifiedTableItem
from app.schemas.document import TableItem

logger = logging.getLogger(__name__)


def _normalize_cell_text(cell: str) -> str:
    """Normalize internal whitespace in a cell without altering numbers, units, or symbols."""
    return re.sub(r"\s+", " ", cell or "").strip()


def score_table_quality(rows: List[List[str]]) -> Tuple[float, Dict[str, int]]:
    """Compute a generic quality score for extracted table rows.

    Rewards clean word separation and well-formed numeric tokens; penalizes
    concatenated words (missing spaces) and split numeric punctuation.
    """
    if not rows:
        return 0.0, {"merged_tokens": 0, "split_punct": 0, "word_tokens": 0}

    merged_tokens = 0
    split_punct = 0
    word_tokens = 0
    non_empty_cells = 0

    for row in rows:
        for cell in row:
            if not cell:
                continue
            non_empty_cells += 1
            tokens = cell.split()
            word_tokens += len(tokens)

            for tok in tokens:
                if re.search(r"[a-z]{2,}[A-Z][a-z]+", tok):
                    merged_tokens += 1
                alpha_only = re.sub(r"[^A-Za-z]", "", tok)
                if len(alpha_only) >= 18:
                    merged_tokens += 1

            if re.search(r"\d\s+[,.-](?:\s|$)|-\s+,", cell):
                split_punct += 1

    score = (
        non_empty_cells * 1.0
        + word_tokens * 0.4
        - merged_tokens * 3.0
        - split_punct * 2.5
    )
    return round(score, 2), {
        "merged_tokens": merged_tokens,
        "split_punct": split_punct,
        "word_tokens": word_tokens,
    }


def _extract_plumber_candidates_by_page(
    pdf_path: Optional[Path],
    target_pages: set[int],
) -> Dict[int, List[Tuple[List[List[str]], Optional[List[float]]]]]:
    """Extract pdfplumber tables and bounding boxes for pages that contain raw tables."""
    if not pdf_path or not pdf_path.is_file() or not target_pages:
        return {}

    results: Dict[int, List[Tuple[List[List[str]], Optional[List[float]]]]] = {}
    try:
        with pdfplumber.open(str(pdf_path)) as plumber_doc:
            for page_num in sorted(target_pages):
                page_idx = page_num - 1
                if page_idx < 0 or page_idx >= len(plumber_doc.pages):
                    continue
                plumber_page = plumber_doc.pages[page_idx]
                page_candidates: List[Tuple[List[List[str]], Optional[List[float]]]] = []
                for found_tbl in plumber_page.find_tables() or []:
                    raw_rows = found_tbl.extract()
                    cleaned = clean_table_rows(raw_rows)
                    if not is_valid_table(cleaned):
                        continue
                    bbox = (
                        [round(float(v), 2) for v in found_tbl.bbox]
                        if getattr(found_tbl, "bbox", None)
                        else None
                    )
                    page_candidates.append((cleaned, bbox))
                if page_candidates:
                    results[page_num] = page_candidates
    except Exception as exc:
        logger.warning("pdfplumber table comparison failed for '%s': %s", pdf_path.name, exc)

    return results


def _bbox_iou(box_a: Optional[List[float]], box_b: Optional[List[float]]) -> float:
    if not box_a or not box_b or len(box_a) != 4 or len(box_b) != 4:
        return 0.0
    x0 = max(box_a[0], box_b[0])
    y0 = max(box_a[1], box_b[1])
    x1 = min(box_a[2], box_b[2])
    y1 = min(box_a[3], box_b[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    inter = (x1 - x0) * (y1 - y0)
    area_a = max(0.0, box_a[2] - box_a[0]) * max(0.0, box_a[3] - box_a[1])
    area_b = max(0.0, box_b[2] - box_b[0]) * max(0.0, box_b[3] - box_b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _match_plumber_table(
    raw_table: TableItem,
    candidates: List[Tuple[List[List[str]], Optional[List[float]]]],
) -> Optional[Tuple[List[List[str]], Optional[List[float]]]]:
    """Find the matching pdfplumber table by bounding-box overlap or shape similarity."""
    if not candidates:
        return None

    best_candidate = None
    best_iou = 0.0
    for rows, bbox in candidates:
        iou = _bbox_iou(raw_table.bbox, bbox)
        if iou > best_iou:
            best_iou = iou
            best_candidate = (rows, bbox)

    if best_candidate is not None and best_iou >= 0.4:
        return best_candidate

    for rows, bbox in candidates:
        if len(rows) == raw_table.row_count and len(rows[0]) == raw_table.col_count:
            return (rows, bbox)

    return None


def _build_structured_rows(headers: List[str], data_rows: List[List[str]]) -> List[Dict[str, str]]:
    """Convert headers and data rows into list of key-value dicts with unique column keys."""
    seen: Dict[str, int] = {}
    unique_headers: List[str] = []
    for idx, hdr in enumerate(headers):
        base = hdr.strip() or f"column_{idx + 1}"
        count = seen.get(base, 0) + 1
        seen[base] = count
        unique_headers.append(base if count == 1 else f"{base}_{count}")

    structured: List[Dict[str, str]] = []
    for row in data_rows:
        record = {
            unique_headers[i]: (row[i] if i < len(row) else "")
            for i in range(len(unique_headers))
        }
        structured.append(record)
    return structured


def refine_tables(
    raw_tables: List[TableItem],
    document_id: str,
    document_name: str,
    pdf_path: Optional[Path] = None,
) -> Tuple[List[ClassifiedTableItem], int]:
    """Compare raw tables against pdfplumber and return cleaned ClassifiedTableItems."""
    target_pages = {tbl.page for tbl in raw_tables}
    plumber_by_page = _extract_plumber_candidates_by_page(pdf_path, target_pages)

    classified: List[ClassifiedTableItem] = []
    refined_count = 0

    for raw in raw_tables:
        raw_rows_norm = [[_normalize_cell_text(c) for c in row] for row in raw.data]
        raw_score, raw_metrics = score_table_quality(raw_rows_norm)

        chosen_rows = raw_rows_norm
        chosen_extractor = raw.extractor
        chosen_bbox = raw.bbox
        comparison_note = "kept_raw_extraction"

        matched = _match_plumber_table(raw, plumber_by_page.get(raw.page, []))
        if matched is not None:
            plumber_rows_raw, plumber_bbox = matched
            plumber_rows = [[_normalize_cell_text(c) for c in row] for row in plumber_rows_raw]
            plumber_score, _ = score_table_quality(plumber_rows)

            if plumber_score > raw_score:
                chosen_rows = plumber_rows
                chosen_extractor = "pdfplumber"
                chosen_bbox = raw.bbox or plumber_bbox
                refined_count += 1
                comparison_note = (
                    f"selected_pdfplumber_over_{raw.extractor}"
                    f"(plumber_score={plumber_score}, raw_score={raw_score})"
                )
                logger.info(
                    "Table '%s' on '%s' page %d refined using pdfplumber (%s)",
                    raw.content_id,
                    document_name,
                    raw.page,
                    comparison_note,
                )
            else:
                comparison_note = (
                    f"kept_{raw.extractor}"
                    f"(raw_score={raw_score}, plumber_score={plumber_score})"
                )

        headers = chosen_rows[0] if chosen_rows else []
        data_rows = chosen_rows[1:] if len(chosen_rows) > 1 else []
        structured_data = _build_structured_rows(headers, data_rows)
        markdown = table_to_markdown(chosen_rows)

        classified.append(
            ClassifiedTableItem(
                table_id=raw.content_id,
                content_id=raw.content_id,
                document_id=document_id,
                document_name=document_name,
                page=raw.page,
                headers=headers,
                rows=data_rows,
                structured_data=structured_data,
                markdown=markdown,
                bbox=chosen_bbox,
                extraction_method=chosen_extractor,
                metadata={
                    "row_count": len(chosen_rows),
                    "data_row_count": len(data_rows),
                    "col_count": len(headers),
                    "quality_score": score_table_quality(chosen_rows)[0],
                    "raw_quality_metrics": raw_metrics,
                    "comparison": comparison_note,
                },
            )
        )

    return classified, refined_count

