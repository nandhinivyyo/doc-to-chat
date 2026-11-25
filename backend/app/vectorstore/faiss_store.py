import json
from pathlib import Path
from typing import List, Tuple

import faiss
import numpy as np

from app.schemas.embeddings import VectorMetadataItem


def build_and_save_faiss_index(
    vectors: np.ndarray,
    metadata_items: List[VectorMetadataItem],
    index_dir: Path,
) -> Tuple[Path, Path]:
    """Create a FAISS IndexFlatIP from normalized vectors and persist index + metadata.

    Using L2-normalized vectors with IndexFlatIP computes exact cosine similarity.
    """
    if len(vectors) != len(metadata_items):
        raise ValueError(
            f"Vector count ({len(vectors)}) does not match metadata count ({len(metadata_items)})."
        )
    if vectors.ndim != 2 or vectors.shape[1] <= 0:
        raise ValueError("Vectors array must be 2D with non-zero embedding dimension.")

    index_dir.mkdir(parents=True, exist_ok=True)
    dim = int(vectors.shape[1])
    contiguous = np.ascontiguousarray(vectors, dtype=np.float32)

    index = faiss.IndexFlatIP(dim)
    if len(contiguous) > 0:
        index.add(contiguous)

    index_path = index_dir / "index.faiss"
    metadata_path = index_dir / "metadata.json"

    faiss.write_index(index, str(index_path))
    metadata_path.write_text(
        json.dumps([item.model_dump(mode="json") for item in metadata_items], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return index_path, metadata_path


def load_faiss_index_and_metadata(
    index_dir: Path,
) -> Tuple[faiss.Index, List[VectorMetadataItem]]:
    """Load a saved FAISS index and verify its vector count matches metadata.json."""
    index_path = index_dir / "index.faiss"
    metadata_path = index_dir / "metadata.json"
    if not index_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError(f"FAISS index or metadata not found in '{index_dir}'.")

    index = faiss.read_index(str(index_path))
    raw_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata_items = [VectorMetadataItem.model_validate(item) for item in raw_meta]

    if int(index.ntotal) != len(metadata_items):
        raise ValueError(
            f"FAISS vector count ({index.ntotal}) does not match metadata count ({len(metadata_items)})."
        )

    return index, metadata_items
