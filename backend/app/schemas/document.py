from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class TextItem(BaseModel):
    """Structured extracted text block from a PDF page."""

    content_id: str
    content_type: Literal["text"] = "text"
    document: str
    page: int
    content: str
    bbox: Optional[List[float]] = None
    section_heading: Optional[str] = None
    ocr_used: bool = False
    char_count: int = 0


class TableItem(BaseModel):
    """Structured extracted table preserving rows, columns, and markdown view."""

    content_id: str
    content_type: Literal["table"] = "table"
    document: str
    page: int
    row_count: int
    col_count: int
    headers: List[str] = Field(default_factory=list)
    data: List[List[str]] = Field(default_factory=list)
    markdown: str = ""
    extractor: Literal["pymupdf", "pdfplumber"] = "pymupdf"
    bbox: Optional[List[float]] = None


class ImageItem(BaseModel):
    """Structured extracted embedded image metadata."""

    content_id: str
    content_type: Literal["image"] = "image"
    document: str
    page: int
    image_id: str
    image_path: str
    image_url: str
    file_name: str
    width: int
    height: int
    format: str
    bbox: Optional[List[float]] = None
    ocr_text: Optional[str] = None


class PageMetadata(BaseModel):
    """Per-page extraction statistics and diagnostics."""

    page: int
    width: float
    height: float
    text_items_count: int = 0
    tables_count: int = 0
    images_count: int = 0
    ocr_used: bool = False
    ocr_reason: Optional[str] = None
    char_count: int = 0
    errors: List[str] = Field(default_factory=list)


class DocumentSummary(BaseModel):
    """Document-level summary generated after PDF extraction."""

    document_id: str
    document: str
    file_size_bytes: int
    total_pages: int
    text_items: int
    tables: int
    images: int
    ocr_pages: List[int] = Field(default_factory=list)
    ocr_used: bool = False
    status: Literal["completed", "completed_with_warnings", "failed"] = "completed"
    created_at: datetime
    errors: List[str] = Field(default_factory=list)


class DocumentExtractionResponse(BaseModel):
    """Complete extraction payload returned by GET /api/documents/{id}/extraction."""

    summary: DocumentSummary
    pages: List[PageMetadata] = Field(default_factory=list)
    text: List[TextItem] = Field(default_factory=list)
    tables: List[TableItem] = Field(default_factory=list)
    images: List[ImageItem] = Field(default_factory=list)


class DocumentListResponse(BaseModel):
    """List of processed documents."""

    documents: List[DocumentSummary] = Field(default_factory=list)

