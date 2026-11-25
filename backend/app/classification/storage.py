import json
from pathlib import Path

from app.schemas.classification import ClassifiedDocumentResponse


def get_classified_file_path(extracted_root: Path, document_id: str) -> Path:
    """Return path to the Phase 3 classified JSON output for a document."""
    return extracted_root / "classified" / f"{document_id}.json"


def save_classified_document(
    extracted_root: Path,
    classified: ClassifiedDocumentResponse,
) -> Path:
    """Persist Phase 3 classified intermediate representation to extracted_data/classified/."""
    target = get_classified_file_path(extracted_root, classified.document_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(classified.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return target


def load_classified_document(
    extracted_root: Path,
    document_id: str,
) -> ClassifiedDocumentResponse:
    """Load persisted Phase 3 classified output for a document."""
    target = get_classified_file_path(extracted_root, document_id)
    if not target.is_file():
        raise FileNotFoundError(f"Classified output for document '{document_id}' not found.")

    raw = json.loads(target.read_text(encoding="utf-8"))
    return ClassifiedDocumentResponse.model_validate(raw)

