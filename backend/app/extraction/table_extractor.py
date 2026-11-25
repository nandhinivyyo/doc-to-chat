import logging
import re
from typing import Any, List, Optional, Tuple

import pymupdf

from app.schemas.document import TableItem

logger = logging.getLogger(__name__)


def clean_table_rows(raw_rows: Optional[List[List[Any]]]) -> List[List[str]]:
    """Normalize cell values and remove completely empty rows."""
    if not raw_rows:
        return []

    cleaned_rows: List[List[str]] = []
    for row in raw_rows:
        if not row:
            continue
        cleaned_cells = [
            re.sub(r"\s+", " ", str(cell)).strip() if cell is not None else ""
            for cell in row
        ]
        if any(cell != "" for cell in cleaned_cells):
            cleaned_rows.append(cleaned_cells)

    if not cleaned_rows:
        return []

    max_cols = max(len(r) for r in cleaned_rows)
    normalized = [r + [""] * (max_cols - len(r)) for r in cleaned_rows]

    # Remove columns that are completely empty across all rows
    non_empty_col_indices = [
        col_idx
        for col_idx in range(max_cols)
        if any(row[col_idx] != "" for row in normalized)
    ]
    if not non_empty_col_indices:
        return []

    return [[row[idx] for idx in non_empty_col_indices] for row in normalized]


def is_valid_table(rows: List[List[str]]) -> bool:
    """Filter out single-cell or decorative layout boxes that are not real tables."""
    if len(rows) < 2:
        return False
    col_count = len(rows[0]) if rows else 0
    if col_count < 2:
        return False
    non_empty_cells = sum(1 for row in rows for cell in row if cell)
    return non_empty_cells >= 3


def table_to_markdown(rows: List[List[str]]) -> str:
    """Convert structured 2D table rows into a Markdown table representation."""
    if not rows:
        return ""
    headers = [cell.replace("|", "\\|") for cell in rows[0]]
    col_count = len(headers)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * col_count) + " |",
    ]
    for row in rows[1:]:
        escaped = [cell.replace("|", "\\|") for cell in row]
        lines.append("| " + " | ".join(escaped) + " |")
    return "\n".join(lines)


def _build_table_item(
    rows: List[List[str]],
    document_name: str,
    page_number: int,
    index: int,
    extractor: str,
    bbox: Optional[List[float]] = None,
) -> TableItem:
    return TableItem(
        content_id=f"table_{index:04d}",
        document=document_name,
        page=page_number,
        row_count=len(rows),
        col_count=len(rows[0]) if rows else 0,
        headers=rows[0] if rows else [],
        data=rows,
        markdown=table_to_markdown(rows),
        extractor=extractor,  # type: ignore[arg-type]
        bbox=bbox,
    )


def extract_page_tables(
    pymupdf_page: pymupdf.Page,
    plumber_page: Optional[Any],
    document_name: str,
    page_number: int,
    start_index: int = 1,
) -> Tuple[List[TableItem], List[str]]:
    """Extract tables from a page using PyMuPDF first and pdfplumber as fallback."""
    tables: List[TableItem] = []
    errors: List[str] = []
    next_idx = start_index
    pymupdf_failed = False

    # 1. Primary extractor: PyMuPDF find_tables()
    try:
        found = pymupdf_page.find_tables()
        for tbl in getattr(found, "tables", []):
            raw_rows = tbl.extract()
            cleaned = clean_table_rows(raw_rows)
            if not is_valid_table(cleaned):
                continue
            bbox = [round(float(v), 2) for v in tbl.bbox] if getattr(tbl, "bbox", None) else None
            tables.append(
                _build_table_item(
                    rows=cleaned,
                    document_name=document_name,
                    page_number=page_number,
                    index=next_idx,
                    extractor="pymupdf",
                    bbox=bbox,
                )
            )
            next_idx += 1
    except Exception as exc:
        pymupdf_failed = True
        msg = f"PyMuPDF table extraction failed on '{document_name}' page {page_number}: {exc}"
        logger.warning(msg)
        errors.append(msg)

    # 2. Fallback extractor: pdfplumber (when PyMuPDF found no valid tables or errored)
    if (not tables or pymupdf_failed) and plumber_page is not None:
        try:
            plumber_tables = plumber_page.extract_tables() or []
            for raw_rows in plumber_tables:
                cleaned = clean_table_rows(raw_rows)
                if not is_valid_table(cleaned):
                    continue
                tables.append(
                    _build_table_item(
                        rows=cleaned,
                        document_name=document_name,
                        page_number=page_number,
                        index=next_idx,
                        extractor="pdfplumber",
                        bbox=None,
                    )
                )
                next_idx += 1
            if tables:
                logger.info(
                    "pdfplumber fallback extracted %d table(s) on '%s' page %d",
                    len(tables),
                    document_name,
                    page_number,
                )
        except Exception as exc:
            msg = f"pdfplumber fallback failed on '{document_name}' page {page_number}: {exc}"
            logger.error(msg)
            errors.append(msg)

    return tables, errors

