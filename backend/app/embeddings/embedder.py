import logging
from typing import Dict, List, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer

from app.schemas.chunking import ChunkItem

logger = logging.getLogger(__name__)

_MODEL_CACHE: Dict[str, SentenceTransformer] = {}


def get_embedding_model(model_name: str) -> SentenceTransformer:
    """Load and cache the configured SentenceTransformer model."""
    if model_name not in _MODEL_CACHE:
        logger.info("Loading embedding model '%s'...", model_name)
        _MODEL_CACHE[model_name] = SentenceTransformer(model_name)
    return _MODEL_CACHE[model_name]


def embed_texts(
    texts: List[str],
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    batch_size: int = 32,
    normalize: bool = True,
) -> Tuple[np.ndarray, int]:
    """Convert a list of texts into L2-normalized float32 embeddings in batches.

    Returns:
        (vectors_array, embedding_dimension)
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0.")

    model = get_embedding_model(model_name)
    dim_fn = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
    model_dim = int(dim_fn() or 0)

    cleaned_texts = [t.strip() for t in texts if t and t.strip()]
    if not cleaned_texts:
        return np.empty((0, model_dim), dtype=np.float32), model_dim

    encoded = model.encode(
        cleaned_texts,
        batch_size=batch_size,
        normalize_embeddings=normalize,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    vectors = np.asarray(encoded, dtype=np.float32)
    if vectors.ndim == 1:
        vectors = vectors.reshape(1, -1)

    actual_dim = int(vectors.shape[1])
    return np.ascontiguousarray(vectors, dtype=np.float32), actual_dim


def format_table_for_embedding(table_chunk: ChunkItem) -> str:
    """Convert a structured Phase 4 table chunk into a clean textual representation."""
    table_id = str(table_chunk.metadata.get("table_id", table_chunk.chunk_id))
    headers = table_chunk.metadata.get("headers") or []
    rows = table_chunk.metadata.get("rows") or []

    lines: List[str] = [f"Table: {table_id}"]
    if headers:
        lines.append("Headers:")
        lines.append(" | ".join(str(h) for h in headers))
    if rows:
        lines.append("Rows:")
        for row in rows:
            lines.append(" | ".join(str(cell) for cell in row))

    if len(lines) == 1 and table_chunk.content.strip():
        return table_chunk.content.strip()
    return "\n".join(lines)
