import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

from app.schemas.classification import ClassifiedImageItem
from app.schemas.document import ImageItem, PageMetadata


def _compute_file_sha256(file_path: Path) -> str:
    if not file_path.is_file():
        return ""
    hasher = hashlib.sha256()
    with file_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def classify_images(
    raw_images: List[ImageItem],
    pages: List[PageMetadata],
    extracted_root: Path,
    document_id: str,
    document_name: str,
) -> List[ClassifiedImageItem]:
    """Classify extracted images and conservatively flag repeated decorative logos."""
    page_height_map: Dict[int, float] = {p.page: p.height for p in pages}
    total_pages = len(pages) or max((img.page for img in raw_images), default=1)
    min_repeat_pages = max(3, int(total_pages * 0.4)) if total_pages >= 3 else 2

    hashes: Dict[str, str] = {}
    hash_pages: Dict[str, Set[int]] = defaultdict(set)

    for img in raw_images:
        digest = _compute_file_sha256(extracted_root / img.image_path)
        hashes[img.image_id] = digest
        if digest:
            hash_pages[digest].add(img.page)

    classified: List[ClassifiedImageItem] = []
    for img in raw_images:
        digest = hashes.get(img.image_id, "")
        occurrence_count = len(hash_pages.get(digest, set())) if digest else 1
        page_height = page_height_map.get(img.page, 792.0)

        in_header_or_footer = False
        if img.bbox and len(img.bbox) == 4 and page_height > 0:
            _, y0, _, y1 = img.bbox
            if y1 <= page_height * 0.16 or y0 >= page_height * 0.85:
                in_header_or_footer = True

        is_decorative = False
        decorative_reason = None

        if occurrence_count >= min_repeat_pages and in_header_or_footer:
            is_decorative = True
            decorative_reason = f"repeated_header_footer_logo(pages={occurrence_count}/{total_pages})"
        elif occurrence_count >= max(4, int(total_pages * 0.6)):
            is_decorative = True
            decorative_reason = f"repeated_identical_asset(pages={occurrence_count}/{total_pages})"
        elif img.width < 32 and img.height < 32:
            is_decorative = True
            decorative_reason = f"tiny_icon({img.width}x{img.height})"

        classified.append(
            ClassifiedImageItem(
                image_id=img.image_id,
                content_id=img.content_id,
                document_id=document_id,
                document_name=document_name,
                page=img.page,
                image_path=img.image_path,
                image_url=img.image_url,
                image_format=img.format,
                width=img.width,
                height=img.height,
                bbox=img.bbox,
                ocr_text=img.ocr_text,
                is_decorative=is_decorative,
                metadata={
                    "file_name": img.file_name,
                    "sha256": digest,
                    "occurrence_count": occurrence_count,
                    "decorative_reason": decorative_reason,
                },
            )
        )

    return classified

