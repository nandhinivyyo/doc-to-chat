import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional

import numpy as np

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")
_HEADING_LINE_RE = re.compile(
    r"^(?:#{1,6}\s+.+|(?:Section|Chapter|Exhibit|Appendix)\s+[A-Za-z0-9].*|[A-Z][A-Za-z0-9\s,&/\-–:]{2,80})$"
)


def _normalize_input(text: str) -> str:
    return (text or "").strip()


def split_sentences(text: str) -> List[str]:
    """Split text into sentences using simple punctuation and capitalization cues."""
    cleaned = re.sub(r"\s+", " ", (text or "")).strip()
    if not cleaned:
        return []
    parts = [part.strip() for part in _SENTENCE_SPLIT_RE.split(cleaned) if part.strip()]
    return parts if parts else [cleaned]


def split_paragraphs(text: str) -> List[str]:
    """Split text into non-empty paragraphs separated by blank lines or line breaks."""
    raw = (text or "").strip()
    if not raw:
        return []
    blocks = [re.sub(r"[ \t]+", " ", p).strip() for p in re.split(r"\n\s*\n+", raw)]
    blocks = [b for b in blocks if b]
    if len(blocks) == 1 and "\n" in raw:
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if len(lines) > 1:
            return lines
    return blocks


def fixed_size_chunk(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> List[Dict[str, Any]]:
    """Split text into fixed-length character chunks with optional overlap."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0.")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and strictly less than chunk_size.")

    cleaned = _normalize_input(text)
    if not cleaned:
        return []

    if len(cleaned) <= chunk_size:
        return [{"content": cleaned, "start_pos": 0, "end_pos": len(cleaned)}]

    chunks: List[Dict[str, Any]] = []
    step = chunk_size - overlap
    start = 0
    length = len(cleaned)

    while start < length:
        end = min(start + chunk_size, length)
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append({"content": piece, "start_pos": start, "end_pos": end})
        if end >= length:
            break
        start += step

    return chunks


def token_based_chunk(
    text: str,
    max_tokens: int = 100,
    overlap_tokens: int = 15,
) -> List[Dict[str, Any]]:
    """Split text into chunks by whitespace-delimited token count with optional overlap."""
    if max_tokens <= 0:
        raise ValueError("max_tokens must be greater than 0.")
    if overlap_tokens < 0 or overlap_tokens >= max_tokens:
        raise ValueError("overlap_tokens must be >= 0 and strictly less than max_tokens.")

    cleaned = _normalize_input(text)
    if not cleaned:
        return []

    token_matches = list(re.finditer(r"\S+", cleaned))
    if not token_matches:
        return []

    if len(token_matches) <= max_tokens:
        return [
            {
                "content": cleaned,
                "start_pos": token_matches[0].start(),
                "end_pos": token_matches[-1].end(),
                "token_count": len(token_matches),
            }
        ]

    chunks: List[Dict[str, Any]] = []
    step = max_tokens - overlap_tokens
    idx = 0
    total = len(token_matches)

    while idx < total:
        end_idx = min(idx + max_tokens, total)
        window = token_matches[idx:end_idx]
        chunk_text = " ".join(m.group(0) for m in window)
        chunks.append(
            {
                "content": chunk_text,
                "start_pos": window[0].start(),
                "end_pos": window[-1].end(),
                "token_count": len(window),
            }
        )
        if end_idx >= total:
            break
        idx += step

    return chunks


def sentence_based_chunk(
    text: str,
    max_sentences: int = 4,
    overlap_sentences: int = 1,
    max_chars: int = 1000,
) -> List[Dict[str, Any]]:
    """Group consecutive sentences into chunks with optional sentence overlap."""
    if max_sentences <= 0:
        raise ValueError("max_sentences must be greater than 0.")
    if overlap_sentences < 0 or overlap_sentences >= max_sentences:
        raise ValueError("overlap_sentences must be >= 0 and less than max_sentences.")
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than 0.")

    cleaned = _normalize_input(text)
    if not cleaned:
        return []

    sentences = split_sentences(cleaned)
    if not sentences:
        return []

    chunks: List[Dict[str, Any]] = []
    idx = 0
    total = len(sentences)

    while idx < total:
        group: List[str] = []
        current_len = 0
        end_idx = idx

        while end_idx < total and len(group) < max_sentences:
            sent = sentences[end_idx]
            added_len = len(sent) + (1 if group else 0)
            if group and current_len + added_len > max_chars:
                break
            group.append(sent)
            current_len += added_len
            end_idx += 1

        chunk_text = " ".join(group)
        start_pos = cleaned.find(group[0]) if group else 0
        end_pos = start_pos + len(chunk_text) if start_pos >= 0 else len(chunk_text)
        chunks.append(
            {
                "content": chunk_text,
                "start_pos": max(0, start_pos),
                "end_pos": max(0, end_pos),
                "sentence_count": len(group),
            }
        )

        if end_idx >= total:
            break

        advance = max(1, len(group) - overlap_sentences)
        idx += advance

    return chunks


def paragraph_based_chunk(
    text: str,
    max_paragraphs: int = 2,
    max_chars: int = 1000,
) -> List[Dict[str, Any]]:
    """Group consecutive paragraphs into chunks while preserving paragraph boundaries."""
    if max_paragraphs <= 0:
        raise ValueError("max_paragraphs must be greater than 0.")
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than 0.")

    cleaned = _normalize_input(text)
    if not cleaned:
        return []

    paragraphs = split_paragraphs(cleaned)
    if not paragraphs:
        return []

    chunks: List[Dict[str, Any]] = []
    current_group: List[str] = []
    current_len = 0
    cursor = 0

    def flush_group() -> None:
        nonlocal cursor
        if not current_group:
            return
        chunk_text = "\n\n".join(current_group)
        pos = cleaned.find(current_group[0], cursor)
        start_pos = pos if pos >= 0 else cursor
        end_pos = min(len(cleaned), start_pos + len(chunk_text))
        chunks.append(
            {
                "content": chunk_text,
                "start_pos": start_pos,
                "end_pos": end_pos,
                "paragraph_count": len(current_group),
            }
        )
        cursor = end_pos
        current_group.clear()

    for para in paragraphs:
        added_len = len(para) + (2 if current_group else 0)
        if current_group and (
            len(current_group) >= max_paragraphs or current_len + added_len > max_chars
        ):
            flush_group()
            current_len = 0

        current_group.append(para)
        current_len += len(para) + (2 if len(current_group) > 1 else 0)

    flush_group()
    return chunks


def _recursive_split_pieces(text: str, chunk_size: int, separators: List[str]) -> List[str]:
    """Recursively split text using progressively finer separators."""
    if len(text) <= chunk_size:
        return [text]

    if not separators:
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    sep = separators[0]
    remaining_seps = separators[1:]

    if sep == "":
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    if sep not in text:
        return _recursive_split_pieces(text, chunk_size, remaining_seps)

    raw_parts = [p.strip() for p in text.split(sep) if p.strip()]
    pieces: List[str] = []
    for part in raw_parts:
        if len(part) <= chunk_size:
            pieces.append(part)
        else:
            pieces.extend(_recursive_split_pieces(part, chunk_size, remaining_seps))
    return pieces


def recursive_chunk(
    text: str,
    chunk_size: int = 600,
    overlap: int = 60,
    separators: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Split text recursively from paragraph to sentence/word boundaries with optional overlap."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0.")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and strictly less than chunk_size.")

    cleaned = _normalize_input(text)
    if not cleaned:
        return []

    seps = separators if separators is not None else ["\n\n", "\n", ". ", " ", ""]
    pieces = _recursive_split_pieces(cleaned, chunk_size, seps)

    merged: List[str] = []
    current = ""

    for piece in pieces:
        candidate = f"{current}\n{piece}".strip() if current else piece
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                merged.append(current)
                if overlap > 0:
                    tail = current[-overlap:].lstrip()
                    current = f"{tail} {piece}".strip() if tail and len(tail) + len(piece) + 1 <= chunk_size else piece
                else:
                    current = piece
            else:
                merged.append(piece)
                current = ""

    if current:
        merged.append(current)

    chunks: List[Dict[str, Any]] = []
    cursor = 0
    for piece in merged:
        probe = piece[:40]
        found = cleaned.find(probe, max(0, cursor - overlap))
        start_pos = found if found >= 0 else cursor
        end_pos = min(len(cleaned), start_pos + len(piece))
        chunks.append({"content": piece, "start_pos": start_pos, "end_pos": end_pos})
        cursor = end_pos

    return chunks


def sliding_window_chunk(
    text: str,
    window_size: int = 400,
    step_size: int = 200,
) -> List[Dict[str, Any]]:
    """Slide a fixed-length character window across text by step_size."""
    if window_size <= 0:
        raise ValueError("window_size must be greater than 0.")
    if step_size <= 0 or step_size > window_size:
        raise ValueError("step_size must be > 0 and <= window_size.")

    cleaned = _normalize_input(text)
    if not cleaned:
        return []

    if len(cleaned) <= window_size:
        return [{"content": cleaned, "start_pos": 0, "end_pos": len(cleaned)}]

    chunks: List[Dict[str, Any]] = []
    start = 0
    length = len(cleaned)

    while start < length:
        end = min(start + window_size, length)
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(
                {
                    "content": piece,
                    "start_pos": start,
                    "end_pos": end,
                    "overlap_chars": window_size - step_size,
                }
            )
        if end >= length:
            break
        start += step_size

    return chunks


def _compute_tfidf_vectors(sentences: List[str]) -> np.ndarray:
    """Build lightweight TF-IDF vectors for a list of sentences using NumPy."""
    tokenized = [re.findall(r"[a-z0-9]+", s.lower()) for s in sentences]
    vocab: Dict[str, int] = {}
    doc_freq: Counter[str] = Counter()

    for tokens in tokenized:
        for tok in set(tokens):
            doc_freq[tok] += 1
            if tok not in vocab:
                vocab[tok] = len(vocab)

    if not vocab:
        return np.zeros((len(sentences), 1), dtype=float)

    num_docs = len(sentences)
    matrix = np.zeros((num_docs, len(vocab)), dtype=float)

    for row_idx, tokens in enumerate(tokenized):
        if not tokens:
            continue
        counts = Counter(tokens)
        total_toks = len(tokens)
        for tok, cnt in counts.items():
            col_idx = vocab[tok]
            tf = cnt / total_toks
            idf = math.log((1 + num_docs) / (1 + doc_freq[tok])) + 1.0
            matrix[row_idx, col_idx] = tf * idf

    return matrix


def _cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    norm_a = float(np.linalg.norm(vec_a))
    norm_b = float(np.linalg.norm(vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


def semantic_chunk(
    text: str,
    similarity_threshold: float = 0.12,
    max_chars: int = 900,
    min_chars: int = 120,
) -> List[Dict[str, Any]]:
    """Group sentences with similar meaning together based on TF-IDF cosine similarity."""
    if not (0.0 <= similarity_threshold <= 1.0):
        raise ValueError("similarity_threshold must be between 0.0 and 1.0.")
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than 0.")
    if min_chars < 0:
        raise ValueError("min_chars must be >= 0.")

    cleaned = _normalize_input(text)
    if not cleaned:
        return []

    sentences = split_sentences(cleaned)
    if len(sentences) == 1:
        return [{"content": sentences[0], "start_pos": 0, "end_pos": len(sentences[0])}]

    vectors = _compute_tfidf_vectors(sentences)
    chunks: List[Dict[str, Any]] = []

    group_sentences = [sentences[0]]
    group_vec = vectors[0].copy()
    group_len = len(sentences[0])
    cursor = 0

    for idx in range(1, len(sentences)):
        next_sent = sentences[idx]
        next_vec = vectors[idx]
        sim = _cosine_similarity(group_vec, next_vec)

        exceeds_max = group_len + 1 + len(next_sent) > max_chars
        topic_shift = sim < similarity_threshold and group_len >= min_chars

        if exceeds_max or topic_shift:
            chunk_text = " ".join(group_sentences)
            pos = cleaned.find(group_sentences[0], cursor)
            start_pos = pos if pos >= 0 else cursor
            end_pos = min(len(cleaned), start_pos + len(chunk_text))
            chunks.append(
                {
                    "content": chunk_text,
                    "start_pos": start_pos,
                    "end_pos": end_pos,
                    "sentence_count": len(group_sentences),
                }
            )
            cursor = end_pos
            group_sentences = [next_sent]
            group_vec = next_vec.copy()
            group_len = len(next_sent)
        else:
            group_sentences.append(next_sent)
            group_vec = group_vec + next_vec
            group_len += 1 + len(next_sent)

    if group_sentences:
        chunk_text = " ".join(group_sentences)
        pos = cleaned.find(group_sentences[0], cursor)
        start_pos = pos if pos >= 0 else cursor
        end_pos = min(len(cleaned), start_pos + len(chunk_text))
        chunks.append(
            {
                "content": chunk_text,
                "start_pos": start_pos,
                "end_pos": end_pos,
                "sentence_count": len(group_sentences),
            }
        )

    return chunks


def structure_section_chunk(
    text: str,
    max_chars: int = 1200,
    overlap_chars: int = 0,
) -> List[Dict[str, Any]]:
    """Split raw text along heading/section lines, keeping each section grouped together."""
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than 0.")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be >= 0 and strictly less than max_chars.")

    cleaned = _normalize_input(text)
    if not cleaned:
        return []

    sections: List[Dict[str, Any]] = []
    current_heading: Optional[str] = None
    current_lines: List[str] = []

    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped:
            if current_lines and current_lines[-1] != "":
                current_lines.append("")
            continue

        is_heading = (
            stripped.startswith("#")
            or (
                bool(_HEADING_LINE_RE.match(stripped))
                and len(stripped.split()) <= 10
                and not stripped.endswith(".")
            )
        )
        if is_heading and current_lines:
            section_text = "\n".join(current_lines).strip()
            if section_text:
                sections.append({"section_heading": current_heading, "text": section_text})
            current_heading = stripped.lstrip("#").strip()
            current_lines = [stripped]
        else:
            if is_heading and current_heading is None:
                current_heading = stripped.lstrip("#").strip()
            current_lines.append(stripped)

    if current_lines:
        section_text = "\n".join(current_lines).strip()
        if section_text:
            sections.append({"section_heading": current_heading, "text": section_text})

    chunks: List[Dict[str, Any]] = []
    cursor = 0
    for sec in sections:
        sec_text = sec["text"]
        heading = sec["section_heading"]
        if len(sec_text) <= max_chars:
            pos = cleaned.find(sec_text[:40], cursor)
            start_pos = pos if pos >= 0 else cursor
            end_pos = min(len(cleaned), start_pos + len(sec_text))
            chunks.append(
                {
                    "content": sec_text,
                    "start_pos": start_pos,
                    "end_pos": end_pos,
                    "section_heading": heading,
                }
            )
            cursor = end_pos
        else:
            sub_chunks = recursive_chunk(sec_text, chunk_size=max_chars, overlap=overlap_chars)
            for sub in sub_chunks:
                chunks.append(
                    {
                        "content": sub["content"],
                        "start_pos": cursor + sub["start_pos"],
                        "end_pos": cursor + sub["end_pos"],
                        "section_heading": heading,
                    }
                )
            cursor += len(sec_text)

    return chunks
