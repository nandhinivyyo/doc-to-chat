from typing import List

from app.schemas.rag import RagSourceReference
from app.schemas.search import SemanticSearchResult


def build_document_context(results: List[SemanticSearchResult]) -> str:
    """Format Phase 7 retrieved chunks into a clean, clearly separated context block for Gemini."""
    if not results:
        return ""

    blocks: List[str] = ["DOCUMENT CONTEXT"]
    for idx, item in enumerate(results, start=1):
        content_label = "Table" if item.content_type == "table" else "Text"
        header_lines = [
            f"SOURCE {idx}",
            f"Page: {item.page}",
            f"Content Type: {content_label}",
            f"Method: {item.chunking_method}",
            f"Chunk ID: {item.chunk_id}",
        ]
        if item.section_heading:
            header_lines.append(f"Section: {item.section_heading}")

        body = item.text.strip()
        blocks.append("\n".join(header_lines) + "\n\n" + body)

    return "\n\n---\n\n".join(blocks)


def extract_source_references(results: List[SemanticSearchResult]) -> List[RagSourceReference]:
    """Preserve factual source metadata from Phase 7 semantic search results."""
    return [
        RagSourceReference(
            rank=item.rank,
            score=item.score,
            page=item.page,
            chunk_id=item.chunk_id,
            content_type=item.content_type,
            chunking_method=item.chunking_method,
            section_heading=item.section_heading,
        )
        for item in results
    ]
