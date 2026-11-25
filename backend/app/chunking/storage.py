import json
from pathlib import Path
from typing import Dict, List

from app.schemas.chunking import (
    ALL_CHUNKING_METHODS,
    ChunkItem,
    ChunkSummaryResponse,
    ChunkingParameters,
    DocumentChunkingResponse,
    ImageChunksResponse,
    MethodChunkStats,
    MethodChunksResponse,
    TableChunksResponse,
)


def get_document_chunk_dir(chunk_outputs_root: Path, document_id: str) -> Path:
    """Return directory storing Phase 4 chunk outputs for a document."""
    return chunk_outputs_root / document_id


def save_document_chunks(
    chunk_outputs_root: Path,
    result: DocumentChunkingResponse,
) -> Path:
    """Save summary, tables, images, and per-method text chunks to chunk_outputs/<document_id>/."""
    doc_dir = get_document_chunk_dir(chunk_outputs_root, result.document_id)
    methods_dir = doc_dir / "methods"
    methods_dir.mkdir(parents=True, exist_ok=True)

    summary_payload = {
        "document_id": result.document_id,
        "document_name": result.document_name,
        "total_pages": result.total_pages,
        "created_at": result.created_at.isoformat(),
        "parameters": result.parameters.model_dump(mode="json"),
        "method_stats": [s.model_dump(mode="json") for s in result.method_stats],
        "table_chunks_count": result.table_chunks_count,
        "image_chunks_count": result.image_chunks_count,
        "warnings": result.warnings,
    }
    (doc_dir / "summary.json").write_text(
        json.dumps(summary_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    (doc_dir / "tables.json").write_text(
        json.dumps([c.model_dump(mode="json") for c in result.table_chunks], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (doc_dir / "images.json").write_text(
        json.dumps([c.model_dump(mode="json") for c in result.image_chunks], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    for method, chunks in result.text_chunks.items():
        (methods_dir / f"{method}.json").write_text(
            json.dumps([c.model_dump(mode="json") for c in chunks], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return doc_dir


def load_document_chunks(
    chunk_outputs_root: Path,
    document_id: str,
) -> DocumentChunkingResponse:
    """Load persisted Phase 4 chunking outputs for a document."""
    doc_dir = get_document_chunk_dir(chunk_outputs_root, document_id)
    summary_file = doc_dir / "summary.json"
    if not summary_file.is_file():
        raise FileNotFoundError(f"Chunk outputs for document '{document_id}' not found.")

    summary_raw = json.loads(summary_file.read_text(encoding="utf-8"))
    tables_raw = json.loads((doc_dir / "tables.json").read_text(encoding="utf-8"))
    images_raw = json.loads((doc_dir / "images.json").read_text(encoding="utf-8"))

    text_chunks: Dict[str, List[ChunkItem]] = {}
    methods_dir = doc_dir / "methods"
    for method in ALL_CHUNKING_METHODS:
        method_file = methods_dir / f"{method}.json"
        if method_file.is_file():
            raw_list = json.loads(method_file.read_text(encoding="utf-8"))
            text_chunks[method] = [ChunkItem.model_validate(item) for item in raw_list]
        else:
            text_chunks[method] = []

    return DocumentChunkingResponse(
        document_id=summary_raw["document_id"],
        document_name=summary_raw["document_name"],
        total_pages=summary_raw["total_pages"],
        created_at=summary_raw["created_at"],
        parameters=ChunkingParameters.model_validate(summary_raw["parameters"]),
        method_stats=[MethodChunkStats.model_validate(s) for s in summary_raw["method_stats"]],
        table_chunks_count=summary_raw["table_chunks_count"],
        image_chunks_count=summary_raw["image_chunks_count"],
        warnings=summary_raw.get("warnings", []),
        text_chunks=text_chunks,
        table_chunks=[ChunkItem.model_validate(item) for item in tables_raw],
        image_chunks=[ChunkItem.model_validate(item) for item in images_raw],
    )


def load_method_chunks(
    chunk_outputs_root: Path,
    document_id: str,
    method: str,
) -> MethodChunksResponse:
    """Load chunks and statistics for a single text chunking method."""
    summary = load_chunk_summary(chunk_outputs_root, document_id)
    if method not in ALL_CHUNKING_METHODS:
        raise ValueError(f"Unknown chunking method '{method}'.")

    method_file = get_document_chunk_dir(chunk_outputs_root, document_id) / "methods" / f"{method}.json"
    if not method_file.is_file():
        raise FileNotFoundError(f"Chunks for method '{method}' not found for '{document_id}'.")

    raw_list = json.loads(method_file.read_text(encoding="utf-8"))
    chunks = [ChunkItem.model_validate(item) for item in raw_list]
    stats = next(s for s in summary.method_stats if s.method == method)
    return MethodChunksResponse(
        document_id=summary.document_id,
        document_name=summary.document_name,
        method=method,
        stats=stats,
        chunks=chunks,
    )


def load_chunk_summary(
    chunk_outputs_root: Path,
    document_id: str,
) -> ChunkSummaryResponse:
    """Load summary.json metadata and 8-method statistics without reading all chunk files."""
    summary_file = get_document_chunk_dir(chunk_outputs_root, document_id) / "summary.json"
    if not summary_file.is_file():
        raise FileNotFoundError(f"Chunk summary for document '{document_id}' not found.")

    raw = json.loads(summary_file.read_text(encoding="utf-8"))
    return ChunkSummaryResponse(
        document_id=raw["document_id"],
        document_name=raw["document_name"],
        total_pages=raw["total_pages"],
        created_at=raw["created_at"],
        parameters=ChunkingParameters.model_validate(raw["parameters"]),
        method_stats=[MethodChunkStats.model_validate(s) for s in raw["method_stats"]],
        table_chunks_count=raw["table_chunks_count"],
        image_chunks_count=raw["image_chunks_count"],
        warnings=raw.get("warnings", []),
    )


def load_table_chunks(
    chunk_outputs_root: Path,
    document_id: str,
) -> TableChunksResponse:
    """Load persisted table chunks for a document."""
    summary = load_chunk_summary(chunk_outputs_root, document_id)
    tables_file = get_document_chunk_dir(chunk_outputs_root, document_id) / "tables.json"
    if not tables_file.is_file():
        raise FileNotFoundError(f"Table chunks for document '{document_id}' not found.")

    raw_list = json.loads(tables_file.read_text(encoding="utf-8"))
    tables = [ChunkItem.model_validate(item) for item in raw_list]
    return TableChunksResponse(
        document_id=summary.document_id,
        document_name=summary.document_name,
        table_chunks_count=len(tables),
        tables=tables,
    )


def load_image_chunks(
    chunk_outputs_root: Path,
    document_id: str,
) -> ImageChunksResponse:
    """Load persisted meaningful image chunks for a document."""
    summary = load_chunk_summary(chunk_outputs_root, document_id)
    images_file = get_document_chunk_dir(chunk_outputs_root, document_id) / "images.json"
    if not images_file.is_file():
        raise FileNotFoundError(f"Image chunks for document '{document_id}' not found.")

    raw_list = json.loads(images_file.read_text(encoding="utf-8"))
    images = [ChunkItem.model_validate(item) for item in raw_list]
    return ImageChunksResponse(
        document_id=summary.document_id,
        document_name=summary.document_name,
        image_chunks_count=len(images),
        images=images,
    )
