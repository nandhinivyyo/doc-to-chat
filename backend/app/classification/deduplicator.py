import logging
import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from app.schemas.classification import ClassifiedTableItem, ExcludedDuplicateItem
from app.schemas.document import TextItem

logger = logging.getLogger(__name__)


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\W+", "", (text or "").lower())


def _box_overlap_ratio(text_bbox: Optional[List[float]], table_bbox: Optional[List[float]]) -> float:
    """Return fraction of text_bbox area that lies inside table_bbox."""
    if not text_bbox or not table_bbox or len(text_bbox) != 4 or len(table_bbox) != 4:
        return 0.0

    tx0, ty0, tx1, ty1 = text_bbox
    bx0, by0, bx1, by1 = table_bbox

    text_area = max(0.0, tx1 - tx0) * max(0.0, ty1 - ty0)
    if text_area <= 0.0:
        return 0.0

    ix0 = max(tx0, bx0)
    iy0 = max(ty0, by0)
    ix1 = min(tx1, bx1)
    iy1 = min(ty1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0

    inter_area = (ix1 - ix0) * (iy1 - iy0)
    return inter_area / text_area


def _text_matches_table_content(text: str, table: ClassifiedTableItem) -> bool:
    """Verify a geometrically overlapping block actually represents table content."""
    norm_text = _normalize_for_match(text)
    if not norm_text:
        return False

    table_flat = _normalize_for_match(
        " ".join(table.headers + [cell for row in table.rows for cell in row])
    )
    if not table_flat:
        return False

    if norm_text in table_flat:
        return True

    lines = [_normalize_for_match(line) for line in text.splitlines() if line.strip()]
    if lines and all(line in table_flat for line in lines):
        return True

    return False


def remove_table_duplicates_from_text(
    raw_text_items: List[TextItem],
    tables: List[ClassifiedTableItem],
    overlap_threshold: float = 0.60,
) -> Tuple[List[TextItem], List[ExcludedDuplicateItem]]:
    """Filter out text blocks that duplicate detected tables using bbox + content checks."""
    tables_by_page: Dict[int, List[ClassifiedTableItem]] = defaultdict(list)
    for tbl in tables:
        tables_by_page[tbl.page].append(tbl)

    kept_text: List[TextItem] = []
    excluded: List[ExcludedDuplicateItem] = []

    for item in raw_text_items:
        if item.ocr_used:
            kept_text.append(item)
            continue

        page_tables = tables_by_page.get(item.page, [])
        if not page_tables:
            kept_text.append(item)
            continue

        matched_table: Optional[ClassifiedTableItem] = None
        matched_overlap = 0.0
        matched_reason = ""

        for tbl in page_tables:
            overlap = _box_overlap_ratio(item.bbox, tbl.bbox)
            if overlap >= overlap_threshold and _text_matches_table_content(item.content, tbl):
                matched_table = tbl
                matched_overlap = round(overlap, 3)
                matched_reason = "bbox_inside_table_and_content_match"
                break

            if tbl.bbox is None and _text_matches_table_content(item.content, tbl):
                matched_table = tbl
                matched_overlap = 0.0
                matched_reason = "exact_table_cell_text_match_no_bbox"
                break

        if matched_table is not None:
            preview = re.sub(r"\s+", " ", item.content).strip()[:120]
            excluded.append(
                ExcludedDuplicateItem(
                    raw_content_id=item.content_id,
                    page=item.page,
                    matched_table_id=matched_table.table_id,
                    overlap_ratio=matched_overlap,
                    reason=matched_reason,
                    text_preview=preview,
                )
            )
        else:
            kept_text.append(item)

    if excluded:
        logger.info("Removed %d table-duplicate text block(s) during classification.", len(excluded))

    return kept_text, excluded

