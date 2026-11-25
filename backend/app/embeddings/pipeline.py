import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.chunking.stats import METHOD_LABELS
from app.chunking.storage import load_document_chunks
from app.core.config import Settings
from app.embeddings.embedder import embed_texts, format_table_for_embedding
from app.schemas.chunking import ALL_CHUNKING_METHODS, ChunkItem
from app.schemas.embeddings import (
    EmbeddingSummaryResponse,
    MethodVectorStats,
    VectorMetadataItem,
)
from app.vectorstore.faiss_store import build_and_save_faiss_index

logger = logging.getLogger(__name__)


def get_document_vector_dir(vector_store_root: Path, document_id: str) -> Path:
    """Return directory storing FAISS indexes and metadata for a document."""
    return vector_store_root / document_id


def _build_metadata_items(
    chunks: List[ChunkItem],
    texts: List[str],
    content_type: str,
    chunking_method: str,
    model_name: str,
    dimension: int,
    seen_ids: set[str],
) -> List[VectorMetadataItem]:
    items: List[VectorMetadataItem] = []
    for vec_idx, (chunk, text) in enumerate(zip(chunks, texts)):
        embedding_id = f"emb_{chunk.chunk_id}"
        if embedding_id in seen_ids:
            raise ValueError(f"Duplicate embedding_id detected: '{embedding_id}'.")
        seen_ids.add(embedding_id)

        section_heading = chunk.metadata.get("section_heading")
        items.append(
            VectorMetadataItem(
                vector_index=vec_idx,
                embedding_id=embedding_id,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                content_type=content_type,  # type: ignore[arg-type]
                chunking_method=chunking_method,
                page=chunk.page,
                section_heading=str(section_heading) if section_heading else None,
                text=text,
                embedding_model=model_name,
                embedding_dimension=dimension,
                metadata=chunk.metadata,
            )
        )
    return items


def generate_document_embeddings(
    document_id: str,
    settings: Settings,
    batch_size: Optional[int] = None,
) -> EmbeddingSummaryResponse:
    """Generate embeddings for Phase 4 chunks and store FAISS indexes + metadata."""
    effective_batch = batch_size or settings.embedding_batch_size
    if effective_batch <= 0:
        raise ValueError("batch_size must be greater than 0.")

    chunk_data = load_document_chunks(settings.chunk_outputs_path, document_id)
    doc_vector_dir = get_document_vector_dir(settings.vector_store_path, document_id)
    doc_vector_dir.mkdir(parents=True, exist_ok=True)

    model_name = settings.embedding_model_name
    seen_embedding_ids: set[str] = set()
    method_stats: List[MethodVectorStats] = []
    method_counts: Dict[str, int] = {}
    text_vectors_total = 0
    detected_dimension = 0

    logger.info(
        "Generating Phase 6 embeddings for '%s' (%s) using '%s' (batch_size=%d)...",
        chunk_data.document_name,
        document_id,
        model_name,
        effective_batch,
    )

    # 1. Embed each of the 8 text chunking methods separately
    for method in ALL_CHUNKING_METHODS:
        raw_chunks = chunk_data.text_chunks.get(method, [])
        valid_pairs = [(c, c.content.strip()) for c in raw_chunks if c.content and c.content.strip()]
        valid_chunks = [p[0] for p in valid_pairs]
        texts = [p[1] for p in valid_pairs]

        vectors, dim = embed_texts(
            texts=texts,
            model_name=model_name,
            batch_size=effective_batch,
            normalize=True,
        )
        if dim > 0:
            detected_dimension = dim

        meta_items = _build_metadata_items(
            chunks=valid_chunks,
            texts=texts,
            content_type="text",
            chunking_method=method,
            model_name=model_name,
            dimension=dim,
            seen_ids=seen_embedding_ids,
        )

        method_dir = doc_vector_dir / method
        index_path, metadata_path = build_and_save_faiss_index(vectors, meta_items, method_dir)

        count = len(meta_items)
        text_vectors_total += count
        method_counts[method] = count
        method_stats.append(
            MethodVectorStats(
                method=method,
                label=METHOD_LABELS.get(method, method),
                vector_count=count,
                dimension=dim,
                index_path=str(index_path.relative_to(settings.vector_store_path)),
                metadata_path=str(metadata_path.relative_to(settings.vector_store_path)),
            )
        )

    # 2. Embed table chunks from clean textual representations
    table_chunks = chunk_data.table_chunks
    table_texts = [format_table_for_embedding(tc) for tc in table_chunks]
    table_vectors, table_dim = embed_texts(
        texts=table_texts,
        model_name=model_name,
        batch_size=effective_batch,
        normalize=True,
    )
    if table_dim > 0 and detected_dimension == 0:
        detected_dimension = table_dim

    table_meta = _build_metadata_items(
        chunks=table_chunks,
        texts=table_texts,
        content_type="table",
        chunking_method="table",
        model_name=model_name,
        dimension=table_dim,
        seen_ids=seen_embedding_ids,
    )
    table_dir = doc_vector_dir / "tables"
    tbl_idx_path, tbl_meta_path = build_and_save_faiss_index(table_vectors, table_meta, table_dir)
    table_stats = MethodVectorStats(
        method="table",
        label="Structured Tables",
        vector_count=len(table_meta),
        dimension=table_dim,
        index_path=str(tbl_idx_path.relative_to(settings.vector_store_path)),
        metadata_path=str(tbl_meta_path.relative_to(settings.vector_store_path)),
    )

    # 3. Store image metadata separately (image embeddings are NOT implemented in Phase 6)
    images_dir = doc_vector_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    image_metadata_file = images_dir / "metadata.json"
    image_metadata_payload = {
        "document_id": document_id,
        "image_embeddings_status": "Not implemented in Phase 6",
        "image_vectors": 0,
        "images": [ic.model_dump(mode="json") for ic in chunk_data.image_chunks],
    }
    image_metadata_file.write_text(
        json.dumps(image_metadata_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    summary = EmbeddingSummaryResponse(
        document_id=document_id,
        document_name=chunk_data.document_name,
        model=model_name,
        dimension=detected_dimension,
        normalization="L2-normalized (cosine similarity via IndexFlatIP)",
        methods_processed=len(method_stats),
        text_vectors=text_vectors_total,
        table_vectors=len(table_meta),
        image_vectors=0,
        image_embeddings_status="Not implemented in Phase 6",
        total_vectors=text_vectors_total + len(table_meta),
        method_counts=method_counts,
        method_stats=method_stats,
        table_stats=table_stats,
        image_metadata_path=str(image_metadata_file.relative_to(settings.vector_store_path)),
        storage_location=str(doc_vector_dir),
        status="completed",
        created_at=datetime.now(timezone.utc),
    )

    (doc_vector_dir / "summary.json").write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(
        "Phase 6 completed for '%s': text_vectors=%d, table_vectors=%d, image_vectors=0, total=%d (dim=%d)",
        chunk_data.document_name,
        summary.text_vectors,
        summary.table_vectors,
        summary.total_vectors,
        summary.dimension,
    )
    return summary


def load_embedding_summary(
    vector_store_root: Path,
    document_id: str,
) -> EmbeddingSummaryResponse:
    """Load persisted Phase 6 embedding summary for a document."""
    summary_file = get_document_vector_dir(vector_store_root, document_id) / "summary.json"
    if not summary_file.is_file():
        raise FileNotFoundError(f"Embedding summary for document '{document_id}' not found.")

    raw = json.loads(summary_file.read_text(encoding="utf-8"))
    return EmbeddingSummaryResponse.model_validate(raw)
