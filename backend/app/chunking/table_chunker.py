import logging
from typing import List, Tuple

from app.schemas.chunking import ChunkItem
from app.schemas.classification import ClassifiedTableItem

logger = logging.getLogger(__name__)


def format_table_chunk_text(table: ClassifiedTableItem) -> str:
    """Format a structured table into a simple, readable text representation."""
    lines: List[str] = [f"Table {table.table_id} (Page {table.page})"]
    if table.headers:
        lines.append("Headers: " + " | ".join(table.headers))
    for row_idx, row in enumerate(table.rows, start=1):
        lines.append(f"Row {row_idx}: " + " | ".join(row))
    return "\n".join(lines)


def create_table_chunks(
    tables: List[ClassifiedTableItem],
    document_id: str,
    document_name: str,
) -> Tuple[List[ChunkItem], List[str]]:
    """Create one intact table-aware chunk per validated Phase 3 table."""
    chunks: List[ChunkItem] = []
    warnings: List[str] = []

    for idx, table in enumerate(tables, start=1):
        if not table.headers and not table.rows:
            msg = f"Skipped empty table '{table.table_id}' on page {table.page}."
            logger.warning(msg)
            warnings.append(msg)
            continue

        content = format_table_chunk_text(table)
        chunks.append(
            ChunkItem(
                chunk_id=f"table_chunk_{idx:03d}",
                document_id=document_id,
                page=table.page,
                content_type="table",
                chunking_method="table_structured",
                content=content,
                metadata={
                    "document_name": document_name,
                    "table_id": table.table_id,
                    "headers": table.headers,
                    "rows": table.rows,
                    "structured_data": table.structured_data,
                    "markdown": table.markdown,
                    "bbox": table.bbox,
                    "extraction_method": table.extraction_method,
                    "row_count": len(table.rows),
                    "col_count": len(table.headers),
                },
            )
        )

    return chunks, warnings
