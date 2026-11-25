import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

from app.chunking.image_chunker import create_image_chunks
from app.chunking.stats import compute_method_stats
from app.chunking.storage import save_document_chunks
from app.chunking.table_chunker import create_table_chunks
from app.chunking.text_chunkers import (
    fixed_size_chunk,
    paragraph_based_chunk,
    recursive_chunk,
    semantic_chunk,
    sentence_based_chunk,
    sliding_window_chunk,
    structure_section_chunk,
    token_based_chunk,
)
from app.classification.classifier import classify_document
from app.classification.storage import load_classified_document
from app.core.config import Settings
from app.schemas.chunking import (
    ALL_CHUNKING_METHODS,
    ChunkItem,
    ChunkingParameters,
    DocumentChunkingResponse,
    MethodChunkStats,
)
from app.schemas.classification import ClassifiedDocumentResponse, ClassifiedTextItem

logger = logging.getLogger(__name__)


def _build_page_texts_with_spans(
    clean_items: List[ClassifiedTextItem],
) -> Dict[int, Tuple[str, List[Tuple[int, int, ClassifiedTextItem]]]]:
    """Combine clean text items per page while tracking character spans of each item."""
    by_page: Dict[int, List[ClassifiedTextItem]] = defaultdict(list)
    for item in clean_items:
        by_page[item.page].append(item)

    result: Dict[int, Tuple[str, List[Tuple[int, int, ClassifiedTextItem]]]] = {}
    for page_num in sorted(by_page):
        parts: List[str] = []
        spans: List[Tuple[int, int, ClassifiedTextItem]] = []
        cursor = 0
        for item in by_page[page_num]:
            text = item.text.strip()
            if not text:
                continue
            if parts:
                cursor += 2  # "\n\n" separator
            start = cursor
            end = start + len(text)
            parts.append(text)
            spans.append((start, end, item))
            cursor = end
        if parts:
            result[page_num] = ("\n\n".join(parts), spans)
    return result


def _resolve_span_metadata(
    start_pos: int,
    end_pos: int,
    spans: List[Tuple[int, int, ClassifiedTextItem]],
) -> Tuple[Optional[str], List[str]]:
    """Find overlapping source content IDs and primary section heading for a page span."""
    matched_ids: List[str] = []
    heading: Optional[str] = None

    for s_start, s_end, item in spans:
        if end_pos >= s_start and start_pos <= s_end:
            matched_ids.append(item.content_id)
            if item.section_heading and heading is None:
                heading = item.section_heading

    if heading is None and spans:
        heading = spans[0][2].section_heading
    return heading, matched_ids


def _run_page_based_chunker(
    method_name: str,
    chunk_fn: Callable[[str], List[dict]],
    page_data: Dict[int, Tuple[str, List[Tuple[int, int, ClassifiedTextItem]]]],
    document_id: str,
    document_name: str,
) -> List[ChunkItem]:
    """Run a text chunker page-by-page so every chunk preserves exact page & source metadata."""
    chunks: List[ChunkItem] = []
    counter = 1

    for page_num, (page_text, spans) in page_data.items():
        raw_chunks = chunk_fn(page_text)
        for raw in raw_chunks:
            start_pos = int(raw.get("start_pos", 0))
            end_pos = int(raw.get("end_pos", len(raw["content"])))
            heading, source_ids = _resolve_span_metadata(start_pos, end_pos, spans)

            extra_meta = {
                k: v
                for k, v in raw.items()
                if k not in ("content", "start_pos", "end_pos", "section_heading")
            }
            chunks.append(
                ChunkItem(
                    chunk_id=f"{method_name}_chunk_{counter:03d}",
                    document_id=document_id,
                    page=page_num,
                    content_type="text",
                    chunking_method=method_name,
                    content=raw["content"],
                    metadata={
                        "document_name": document_name,
                        "section_heading": raw.get("section_heading") or heading,
                        "source_content_ids": source_ids,
                        "start_pos": start_pos,
                        "end_pos": end_pos,
                        "char_count": len(raw["content"]),
                        **extra_meta,
                    },
                )
            )
            counter += 1

    return chunks


def _run_structure_section_chunker(
    clean_items: List[ClassifiedTextItem],
    document_id: str,
    document_name: str,
    max_chars: int,
    overlap_chars: int,
) -> List[ChunkItem]:
    """Group consecutive Phase 3 clean items sharing the same section_heading."""
    if not clean_items:
        return []

    sections: List[Dict[str, object]] = []
    for item in clean_items:
        heading = item.section_heading or "Untitled Section"
        if sections and sections[-1]["heading"] == heading:
            sections[-1]["items"].append(item)  # type: ignore[union-attr]
        else:
            sections.append({"heading": heading, "items": [item]})

    chunks: List[ChunkItem] = []
    counter = 1

    for sec in sections:
        heading = str(sec["heading"])
        items: List[ClassifiedTextItem] = sec["items"]  # type: ignore[assignment]
        combined_text = "\n\n".join(i.text.strip() for i in items if i.text.strip())
        if not combined_text:
            continue

        pages = sorted({i.page for i in items})
        source_ids = [i.content_id for i in items]
        sub_chunks = (
            [{"content": combined_text, "start_pos": 0, "end_pos": len(combined_text)}]
            if len(combined_text) <= max_chars
            else structure_section_chunk(combined_text, max_chars=max_chars, overlap_chars=overlap_chars)
        )

        for sub in sub_chunks:
            chunks.append(
                ChunkItem(
                    chunk_id=f"structure_section_chunk_{counter:03d}",
                    document_id=document_id,
                    page=pages[0],
                    content_type="text",
                    chunking_method="structure_section",
                    content=sub["content"],
                    metadata={
                        "document_name": document_name,
                        "section_heading": heading,
                        "pages": pages,
                        "source_content_ids": source_ids,
                        "start_pos": sub["start_pos"],
                        "end_pos": sub["end_pos"],
                        "char_count": len(sub["content"]),
                    },
                )
            )
            counter += 1

    return chunks


def _validate_parameters(params: ChunkingParameters) -> None:
    if params.fixed_overlap >= params.fixed_chunk_size:
        raise ValueError("fixed_overlap must be less than fixed_chunk_size.")
    if params.token_overlap >= params.token_max_tokens:
        raise ValueError("token_overlap must be less than token_max_tokens.")
    if params.sentence_overlap >= params.sentence_max_sentences:
        raise ValueError("sentence_overlap must be less than sentence_max_sentences.")
    if params.recursive_overlap >= params.recursive_chunk_size:
        raise ValueError("recursive_overlap must be less than recursive_chunk_size.")
    if params.sliding_step_size > params.sliding_window_size:
        raise ValueError("sliding_step_size must be <= sliding_window_size.")
    if params.section_overlap_chars >= params.section_max_chars:
        raise ValueError("section_overlap_chars must be less than section_max_chars.")


def chunk_document(
    document_id: str,
    settings: Settings,
    params: Optional[ChunkingParameters] = None,
) -> DocumentChunkingResponse:
    """Execute Phase 4 chunking across all 8 text methods plus table and image chunks."""
    cfg = params or ChunkingParameters()
    _validate_parameters(cfg)

    extracted_root = settings.extracted_storage_path
    try:
        classified: ClassifiedDocumentResponse = load_classified_document(extracted_root, document_id)
    except FileNotFoundError:
        classified = classify_document(document_id=document_id, settings=settings)

    logger.info("Running Phase 4 chunking for '%s' (%s)...", classified.document_name, document_id)

    clean_text = [
        item for item in classified.text if not item.is_boilerplate and item.text.strip()
    ]
    warnings: List[str] = []
    if not clean_text:
        msg = f"No clean non-boilerplate text items available for '{document_id}'."
        logger.warning(msg)
        warnings.append(msg)

    page_data = _build_page_texts_with_spans(clean_text)

    method_dispatch: Dict[str, Callable[[str], List[dict]]] = {
        "fixed_size": lambda t: fixed_size_chunk(
            t, chunk_size=cfg.fixed_chunk_size, overlap=cfg.fixed_overlap
        ),
        "token_based": lambda t: token_based_chunk(
            t, max_tokens=cfg.token_max_tokens, overlap_tokens=cfg.token_overlap
        ),
        "sentence_based": lambda t: sentence_based_chunk(
            t,
            max_sentences=cfg.sentence_max_sentences,
            overlap_sentences=cfg.sentence_overlap,
            max_chars=cfg.sentence_max_chars,
        ),
        "paragraph_based": lambda t: paragraph_based_chunk(
            t, max_paragraphs=cfg.paragraph_max_paragraphs, max_chars=cfg.paragraph_max_chars
        ),
        "recursive": lambda t: recursive_chunk(
            t, chunk_size=cfg.recursive_chunk_size, overlap=cfg.recursive_overlap
        ),
        "sliding_window": lambda t: sliding_window_chunk(
            t, window_size=cfg.sliding_window_size, step_size=cfg.sliding_step_size
        ),
        "semantic": lambda t: semantic_chunk(
            t,
            similarity_threshold=cfg.semantic_similarity_threshold,
            max_chars=cfg.semantic_max_chars,
            min_chars=cfg.semantic_min_chars,
        ),
    }

    text_chunks: Dict[str, List[ChunkItem]] = {}
    for method_name in ALL_CHUNKING_METHODS:
        if method_name == "structure_section":
            text_chunks[method_name] = _run_structure_section_chunker(
                clean_items=clean_text,
                document_id=document_id,
                document_name=classified.document_name,
                max_chars=cfg.section_max_chars,
                overlap_chars=cfg.section_overlap_chars,
            )
        else:
            text_chunks[method_name] = _run_page_based_chunker(
                method_name=method_name,
                chunk_fn=method_dispatch[method_name],
                page_data=page_data,
                document_id=document_id,
                document_name=classified.document_name,
            )

    table_chunks, table_warnings = create_table_chunks(
        tables=classified.tables,
        document_id=document_id,
        document_name=classified.document_name,
    )
    image_chunks, image_warnings = create_image_chunks(
        images=classified.images,
        clean_text_items=clean_text,
        extracted_root=extracted_root,
        document_id=document_id,
        document_name=classified.document_name,
    )
    warnings.extend(table_warnings)
    warnings.extend(image_warnings)

    method_stats: List[MethodChunkStats] = [
        compute_method_stats(method, text_chunks[method]) for method in ALL_CHUNKING_METHODS
    ]

    result = DocumentChunkingResponse(
        document_id=document_id,
        document_name=classified.document_name,
        total_pages=classified.total_pages,
        created_at=datetime.now(timezone.utc),
        parameters=cfg,
        method_stats=method_stats,
        table_chunks_count=len(table_chunks),
        image_chunks_count=len(image_chunks),
        warnings=warnings,
        text_chunks=text_chunks,
        table_chunks=table_chunks,
        image_chunks=image_chunks,
    )

    out_dir = save_document_chunks(settings.chunk_outputs_path, result)
    logger.info(
        "Phase 4 chunking completed for '%s': methods=%d, tables=%d, images=%d -> %s",
        classified.document_name,
        len(method_stats),
        len(table_chunks),
        len(image_chunks),
        out_dir,
    )
    return result
