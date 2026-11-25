from typing import Dict, List

from app.schemas.chunking import ChunkItem, MethodChunkStats

METHOD_LABELS: Dict[str, str] = {
    "fixed_size": "Fixed-Size Chunking",
    "token_based": "Token-Based Chunking",
    "sentence_based": "Sentence-Based Chunking",
    "paragraph_based": "Paragraph-Based Chunking",
    "recursive": "Recursive Chunking",
    "sliding_window": "Sliding-Window Chunking",
    "semantic": "Semantic Chunking",
    "structure_section": "Structure / Section-Based Chunking",
}


def compute_method_stats(method: str, chunks: List[ChunkItem]) -> MethodChunkStats:
    """Compute basic length and count statistics for one chunking method."""
    label = METHOD_LABELS.get(method, method)
    if not chunks:
        return MethodChunkStats(
            method=method,
            label=label,
            chunk_count=0,
            avg_chunk_length=0.0,
            min_chunk_length=0,
            max_chunk_length=0,
            total_characters=0,
            total_words=0,
        )

    lengths = [len(c.content) for c in chunks]
    total_chars = sum(lengths)
    total_words = sum(len(c.content.split()) for c in chunks)

    return MethodChunkStats(
        method=method,
        label=label,
        chunk_count=len(chunks),
        avg_chunk_length=round(total_chars / len(chunks), 2),
        min_chunk_length=min(lengths),
        max_chunk_length=max(lengths),
        total_characters=total_chars,
        total_words=total_words,
    )
