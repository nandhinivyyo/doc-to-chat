import json
from pathlib import Path
from typing import List

from app.schemas.document import (
    DocumentExtractionResponse,
    DocumentSummary,
    ImageItem,
    PageMetadata,
    TableItem,
    TextItem,
)


def get_document_image_dir(extracted_root: Path, document_id: str) -> Path:
    """Return directory storing extracted images for a given document."""
    return extracted_root / "images" / document_id


def ensure_extraction_dirs(extracted_root: Path, document_id: str) -> None:
    """Create structured extracted_data subdirectories."""
    for sub in ("text", "tables", "images", "metadata"):
        (extracted_root / sub).mkdir(parents=True, exist_ok=True)
    get_document_image_dir(extracted_root, document_id).mkdir(parents=True, exist_ok=True)


def save_extraction_result(
    extracted_root: Path,
    result: DocumentExtractionResponse,
) -> None:
    """Persist extraction outputs across text/, tables/, images/, and metadata/."""
    doc_id = result.summary.document_id
    ensure_extraction_dirs(extracted_root, doc_id)

    text_file = extracted_root / "text" / f"{doc_id}.json"
    tables_file = extracted_root / "tables" / f"{doc_id}.json"
    images_file = extracted_root / "images" / f"{doc_id}.json"
    metadata_file = extracted_root / "metadata" / f"{doc_id}.json"

    text_file.write_text(
        json.dumps([item.model_dump(mode="json") for item in result.text], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    tables_file.write_text(
        json.dumps([item.model_dump(mode="json") for item in result.tables], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    images_file.write_text(
        json.dumps([item.model_dump(mode="json") for item in result.images], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    metadata_payload = {
        "summary": result.summary.model_dump(mode="json"),
        "pages": [page.model_dump(mode="json") for page in result.pages],
    }
    metadata_file.write_text(
        json.dumps(metadata_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_document_summary(extracted_root: Path, document_id: str) -> DocumentSummary:
    """Load document summary JSON for a processed document."""
    metadata_file = extracted_root / "metadata" / f"{document_id}.json"
    if not metadata_file.is_file():
        raise FileNotFoundError(f"Document '{document_id}' metadata not found.")

    raw = json.loads(metadata_file.read_text(encoding="utf-8"))
    return DocumentSummary.model_validate(raw["summary"])


def load_extraction_result(extracted_root: Path, document_id: str) -> DocumentExtractionResponse:
    """Load complete extracted content and metadata for a processed document."""
    metadata_file = extracted_root / "metadata" / f"{document_id}.json"
    if not metadata_file.is_file():
        raise FileNotFoundError(f"Document '{document_id}' extraction data not found.")

    metadata_raw = json.loads(metadata_file.read_text(encoding="utf-8"))
    summary = DocumentSummary.model_validate(metadata_raw["summary"])
    pages = [PageMetadata.model_validate(p) for p in metadata_raw.get("pages", [])]

    text_file = extracted_root / "text" / f"{document_id}.json"
    tables_file = extracted_root / "tables" / f"{document_id}.json"
    images_file = extracted_root / "images" / f"{document_id}.json"

    text_items: List[TextItem] = []
    if text_file.is_file():
        text_items = [TextItem.model_validate(x) for x in json.loads(text_file.read_text(encoding="utf-8"))]

    table_items: List[TableItem] = []
    if tables_file.is_file():
        table_items = [TableItem.model_validate(x) for x in json.loads(tables_file.read_text(encoding="utf-8"))]

    image_items: List[ImageItem] = []
    if images_file.is_file():
        image_items = [ImageItem.model_validate(x) for x in json.loads(images_file.read_text(encoding="utf-8"))]

    return DocumentExtractionResponse(
        summary=summary,
        pages=pages,
        text=text_items,
        tables=table_items,
        images=image_items,
    )


def list_document_summaries(extracted_root: Path) -> List[DocumentSummary]:
    """List all processed documents sorted newest first."""
    metadata_dir = extracted_root / "metadata"
    if not metadata_dir.is_dir():
        return []

    summaries: List[DocumentSummary] = []
    for path in metadata_dir.glob("*.json"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            summaries.append(DocumentSummary.model_validate(raw["summary"]))
        except Exception:
            continue

    summaries.sort(key=lambda item: item.created_at, reverse=True)
    return summaries

