import re
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from app.schemas.document import PageMetadata, TextItem

MAX_BOILERPLATE_CHARS = 250
TOP_BAND_RATIO = 0.14
BOTTOM_BAND_RATIO = 0.88
PAGE_NUMBER_RE = re.compile(r"^(?:page\s+)?\d+(?:\s*(?:of|/)\s*\d+)?$", re.IGNORECASE)


def _normalize_signature(text: str) -> str:
    """Normalize digits and whitespace so 'Page 1 of 10' and 'Page 2 of 10' share a signature."""
    collapsed = re.sub(r"\s+", " ", (text or "").strip().lower())
    return re.sub(r"\d+", "#", collapsed)


def _is_in_margin_band(
    bbox: Optional[List[float]],
    page_height: float,
) -> Tuple[bool, str]:
    if not bbox or len(bbox) != 4 or page_height <= 0:
        return False, ""
    _, y0, _, y1 = bbox
    if y1 <= page_height * TOP_BAND_RATIO:
        return True, "top_header_band"
    if y0 >= page_height * BOTTOM_BAND_RATIO:
        return True, "bottom_footer_band"
    return False, ""


def detect_boilerplate_text_items(
    text_items: List[TextItem],
    pages: List[PageMetadata],
) -> Dict[str, Optional[str]]:
    """Conservatively identify repeated headers, footers, and page numbering."""
    page_height_map: Dict[int, float] = {p.page: p.height for p in pages}
    total_pages = len(pages) or max((item.page for item in text_items), default=1)
    min_repeat_pages = max(3, int(total_pages * 0.4)) if total_pages >= 3 else 2

    signature_pages: Dict[str, Set[int]] = defaultdict(set)
    for item in text_items:
        cleaned = re.sub(r"\s+", " ", item.content).strip()
        if not cleaned or len(cleaned) > MAX_BOILERPLATE_CHARS:
            continue
        sig = _normalize_signature(cleaned)
        signature_pages[sig].add(item.page)

    reasons: Dict[str, Optional[str]] = {}
    for item in text_items:
        cleaned = re.sub(r"\s+", " ", item.content).strip()
        if not cleaned or len(cleaned) > MAX_BOILERPLATE_CHARS:
            reasons[item.content_id] = None
            continue

        sig = _normalize_signature(cleaned)
        repeat_count = len(signature_pages.get(sig, set()))
        page_height = page_height_map.get(item.page, 792.0)
        in_margin, band_name = _is_in_margin_band(item.bbox, page_height)

        if PAGE_NUMBER_RE.match(cleaned) and (in_margin or repeat_count >= 2):
            reasons[item.content_id] = f"repeated_page_number({band_name or 'pattern'}, pages={repeat_count})"
            continue

        if repeat_count >= min_repeat_pages and in_margin:
            reasons[item.content_id] = f"repeated_margin_boilerplate({band_name}, pages={repeat_count}/{total_pages})"
            continue

        reasons[item.content_id] = None

    return reasons

