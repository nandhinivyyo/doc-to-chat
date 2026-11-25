from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ClassifiedTextItem(BaseModel):
    """Cleaned and classified text item ready for downstream chunking."""

    content_id: str
    document_id: str
    document_name: str
    page: int
    content_type: Literal["text"] = "text"
    text: str
    bbox: Optional[List[float]] = None
    section_heading: Optional[str] = None
    extraction_method: Literal["pymupdf", "ocr"] = "pymupdf"
    is_boilerplate: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ClassifiedTableItem(BaseModel):
    """Cleaned and structurally validated table item separated from prose text."""

    table_id: str
    content_id: str
    document_id: str
    document_name: str
    page: int
    content_type: Literal["table"] = "table"
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)
    structured_data: List[Dict[str, str]] = Field(default_factory=list)
    markdown: str = ""
    bbox: Optional[List[float]] = None
    extraction_method: Literal["pymupdf", "pdfplumber"] = "pymupdf"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ClassifiedImageItem(BaseModel):
    """Classified image item distinguishing meaningful figures from decorative logos."""

    image_id: str
    content_id: str
    document_id: str
    document_name: str
    page: int
    content_type: Literal["image"] = "image"
    image_path: str
    image_url: str
    image_format: str
    width: int
    height: int
    bbox: Optional[List[float]] = None
    ocr_text: Optional[str] = None
    is_decorative: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExcludedDuplicateItem(BaseModel):
    """Audit record of a raw text block excluded because it duplicates a table."""

    raw_content_id: str
    page: int
    matched_table_id: str
    overlap_ratio: float
    reason: str
    text_preview: str


class ClassificationStats(BaseModel):
    """Summary counts produced by Phase 3 content classification and cleanup."""

    raw_text_items: int
    classified_text_items: int
    clean_text_items: int
    boilerplate_text_items: int
    removed_table_duplicates: int
    raw_tables: int
    classified_tables: int
    refined_tables_count: int
    raw_images: int
    classified_images: int
    content_images: int
    decorative_images: int


class ClassifiedDocumentResponse(BaseModel):
    """Complete Phase 3 classified intermediate representation for a document."""

    document_id: str
    document_name: str
    total_pages: int
    created_at: datetime
    stats: ClassificationStats
    text: List[ClassifiedTextItem] = Field(default_factory=list)
    tables: List[ClassifiedTableItem] = Field(default_factory=list)
    images: List[ClassifiedImageItem] = Field(default_factory=list)
    excluded_duplicates: List[ExcludedDuplicateItem] = Field(default_factory=list)

