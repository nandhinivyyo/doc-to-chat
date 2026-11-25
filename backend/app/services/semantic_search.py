import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

import faiss
import numpy as np

from app.core.config import Settings
from app.embeddings.embedder import embed_texts
from app.embeddings.pipeline import get_document_vector_dir
from app.schemas.embeddings import VectorMetadataItem
from app.schemas.search import (
    ALL_VECTOR_STORES,
    SEARCH_METHOD_ALIASES,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SemanticSearchResult,
)
from app.vectorstore.faiss_store import load_faiss_index_and_metadata

logger = logging.getLogger(__name__)

_OVERVIEW_QUERY_PATTERNS = (
    re.compile(
        r"\bwhat\s+is\s+(?:the\s+|this\s+)?(?:pdf|document|file|paper|report|guide|guidance|manual|text)\s+(?:overall\s+)?about\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwhat\s+(?:is|are)\s+the\s+(?:main|primary|overall|key)\s+(?:topic|topics|subject|subjects|purpose|scope|focus|theme)\s+of\s+(?:the\s+|this\s+)?(?:pdf|document|file|paper|report|guide|guidance|manual|text)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:give\s+me\s+|provide\s+|share\s+)?(?:a\s+|an\s+)?(?:brief\s+|short\s+|high[- ]level\s+|overall\s+)?(?:overview|summary|synopsis|abstract)\s+of\s+(?:the\s+|this\s+)?(?:pdf|document|file|paper|report|guide|guidance|manual|text)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:summarize|summarise)\s+(?:the\s+|this\s+)?(?:pdf|document|file|paper|report|guide|guidance|manual|text)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwhat\s+does\s+(?:the\s+|this\s+)?(?:pdf|document|file|paper|report|guide|guidance|manual|text)\s+(?:cover|discuss|explain|describe|talk\s+about)\b",
        re.IGNORECASE,
    ),
)

_OVERVIEW_SECTION_KEYWORDS = (
    "introduction",
    "overview",
    "abstract",
    "executive summary",
    "summary",
    "purpose",
    "scope",
    "background",
)


def is_document_overview_query(query: str) -> bool:
    """Detect generic whole-document overview questions without document-specific hardcoding."""
    return any(pattern.search(query) for pattern in _OVERVIEW_QUERY_PATTERNS)


def _overview_priority(item: VectorMetadataItem) -> Optional[int]:
    """Return tier (0 = explicit overview section, 1 = Page 1 opening prose, None = non-overview)."""
    text = item.text.strip()
    if len(text) < 80:
        return None
    # Exclude numbered footnote/citation lines (e.g. "1 For reporting purposes...")
    if re.match(r"^\s*\d+\s+[A-Z]", text):
        return None

    heading = (item.section_heading or "").strip().lower()
    if any(keyword in heading for keyword in _OVERVIEW_SECTION_KEYWORDS):
        return 0

    leading_lines = [line.strip().lower() for line in text.splitlines()[:4]]
    if any(
        line.startswith(keyword)
        for line in leading_lines
        for keyword in _OVERVIEW_SECTION_KEYWORDS
    ):
        return 0

    if item.page == 1 and item.content_type == "text":
        return 1

    return None


def embed_query(
    query: str,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
) -> Tuple[np.ndarray, int]:
    """Convert a search query into a L2-normalized float32 vector (shape 1 x dim).

    Reuses Phase 6 `embed_texts` so the query vector matches the stored FAISS indexes.
    """
    cleaned = query.strip() if isinstance(query, str) else ""
    if not cleaned:
        raise ValueError("Search query must not be empty or whitespace-only.")

    vectors, dim = embed_texts(
        texts=[cleaned],
        model_name=model_name,
        batch_size=1,
        normalize=True,
    )
    if vectors.shape[0] != 1 or dim <= 0:
        raise RuntimeError("Failed to generate query embedding vector.")

    return np.ascontiguousarray(vectors, dtype=np.float32), dim


def search_single_index(
    index: faiss.Index,
    metadata_items: List[VectorMetadataItem],
    query_vector: np.ndarray,
    top_k: int,
) -> List[Tuple[float, VectorMetadataItem]]:
    """Search one FAISS IndexFlatIP instance and map positions back to metadata.json items."""
    if int(index.ntotal) != len(metadata_items):
        raise ValueError(
            f"FAISS vector count ({index.ntotal}) does not match metadata count ({len(metadata_items)})."
        )

    if top_k <= 0:
        raise ValueError("top_k must be greater than 0.")

    if int(index.ntotal) == 0:
        return []

    query_arr = np.ascontiguousarray(query_vector, dtype=np.float32)
    if query_arr.ndim == 1:
        query_arr = query_arr.reshape(1, -1)
    if query_arr.shape[1] != int(index.d):
        raise ValueError(
            f"Query vector dimension ({query_arr.shape[1]}) does not match FAISS index dimension ({index.d})."
        )

    k = min(top_k, int(index.ntotal))
    scores, indices = index.search(query_arr, k)

    matches: List[Tuple[float, VectorMetadataItem]] = []
    for raw_score, raw_idx in zip(scores[0], indices[0]):
        idx = int(raw_idx)
        if idx < 0:
            continue
        if idx >= len(metadata_items):
            raise IndexError(
                f"FAISS returned out-of-range index {idx} for metadata length {len(metadata_items)}."
            )
        matches.append((float(raw_score), metadata_items[idx]))

    return matches


def _resolve_target_stores(
    doc_vector_dir: Path,
    chunking_method: Optional[str],
) -> List[str]:
    """Determine which Phase 6 FAISS vector store directories should be searched."""
    if not doc_vector_dir.is_dir():
        raise FileNotFoundError(
            f"Vector store for document '{doc_vector_dir.name}' was not found. "
            "Generate Phase 6 embeddings before searching."
        )

    if chunking_method is not None:
        store_name = SEARCH_METHOD_ALIASES.get(chunking_method)
        if not store_name:
            raise ValueError(f"Unsupported chunking_method '{chunking_method}'.")
        store_dir = doc_vector_dir / store_name
        if not (store_dir / "index.faiss").is_file():
            raise FileNotFoundError(
                f"Vector store '{store_name}' not found for document '{doc_vector_dir.name}'."
            )
        return [store_name]

    available_stores = [
        name for name in ALL_VECTOR_STORES if (doc_vector_dir / name / "index.faiss").is_file()
    ]
    if not available_stores:
        raise FileNotFoundError(
            f"No FAISS indexes found in '{doc_vector_dir}'. Generate Phase 6 embeddings first."
        )
    return available_stores


def search_document(
    document_id: str,
    request: SemanticSearchRequest,
    settings: Settings,
) -> SemanticSearchResponse:
    """Execute Phase 7 semantic search across Phase 6 FAISS indexes for a document."""
    doc_vector_dir = get_document_vector_dir(settings.vector_store_path, document_id)
    target_stores = _resolve_target_stores(doc_vector_dir, request.chunking_method)

    overview_mode = is_document_overview_query(request.query)
    retrieval_query = (
        f"{request.query} Introduction overview document purpose topic summary scope"
        if overview_mode
        else request.query
    )

    query_vector, query_dim = embed_query(
        query=retrieval_query,
        model_name=settings.embedding_model_name,
    )

    candidates: List[Tuple[float, VectorMetadataItem]] = []
    for store_name in target_stores:
        store_dir = doc_vector_dir / store_name
        index, metadata_items = load_faiss_index_and_metadata(store_dir)
        per_store_k = int(index.ntotal) if overview_mode else request.top_k
        store_matches = search_single_index(
            index=index,
            metadata_items=metadata_items,
            query_vector=query_vector,
            top_k=per_store_k,
        )
        candidates.extend(store_matches)

    # Sort descending by cosine similarity score; deterministic tie-breaker by method + chunk_id
    candidates.sort(key=lambda pair: (-pair[0], pair[1].chunking_method, pair[1].chunk_id))

    # Deduplicate identical (chunking_method, chunk_id) records while preserving method comparisons
    deduped: List[Tuple[float, VectorMetadataItem]] = []
    seen_keys: set[tuple[str, str]] = set()
    for score, item in candidates:
        key = (item.chunking_method, item.chunk_id)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append((score, item))

    if overview_mode:
        # For broad overview queries, prioritize explicit Introduction / Overview section chunks
        # (tier 0), then substantive Page 1 opening prose (tier 1), deduplicating identical text
        # across chunking methods while keeping authentic FAISS cosine similarity scores.
        tier0_hits: List[Tuple[float, VectorMetadataItem]] = []
        tier1_hits: List[Tuple[float, VectorMetadataItem]] = []
        fallback_hits: List[Tuple[float, VectorMetadataItem]] = []
        seen_norm_texts: set[str] = set()
        for score, item in deduped:
            norm_text = re.sub(r"\s+", " ", item.text.strip().lower())
            if norm_text in seen_norm_texts:
                continue
            seen_norm_texts.add(norm_text)
            tier = _overview_priority(item)
            if tier == 0:
                tier0_hits.append((score, item))
            elif tier == 1:
                tier1_hits.append((score, item))
            else:
                fallback_hits.append((score, item))
        top_matches = (tier0_hits + tier1_hits + fallback_hits)[: request.top_k]
    else:
        top_matches = deduped[: request.top_k]
    results = [
        SemanticSearchResult(
            rank=rank,
            score=round(float(score), 6),
            chunk_id=item.chunk_id,
            document_id=item.document_id,
            content_type=item.content_type,
            chunking_method=item.chunking_method,
            page=item.page,
            section_heading=item.section_heading,
            text=item.text,
        )
        for rank, (score, item) in enumerate(top_matches, start=1)
    ]

    logger.info(
        "Phase 7 search for '%s' (query_dim=%d, stores=%d, top_k=%d) -> candidates=%d, returned=%d",
        document_id,
        query_dim,
        len(target_stores),
        request.top_k,
        len(deduped),
        len(results),
    )

    return SemanticSearchResponse(
        query=request.query,
        top_k=request.top_k,
        document_id=document_id,
        chunking_method=request.chunking_method,
        model=settings.embedding_model_name,
        searched_stores=target_stores,
        total_candidates=len(deduped),
        results=results,
    )
