import io
import logging
from pathlib import Path
from typing import List, Optional, Set, Tuple

import pymupdf
from PIL import Image

from app.schemas.document import ImageItem

logger = logging.getLogger(__name__)

MIN_IMAGE_DIMENSION_PX = 16


def extract_page_images(
    doc: pymupdf.Document,
    page: pymupdf.Page,
    document_id: str,
    document_name: str,
    page_number: int,
    images_dir: Path,
    start_index: int = 1,
) -> Tuple[List[ImageItem], List[str]]:
    """Extract embedded images from a PDF page and validate saved image files."""
    items: List[ImageItem] = []
    errors: List[str] = []
    next_idx = start_index
    seen_xrefs: Set[int] = set()

    images_dir.mkdir(parents=True, exist_ok=True)
    raw_images = page.get_images(full=True)

    for img_info in raw_images:
        xref = int(img_info[0])
        if xref in seen_xrefs:
            continue
        seen_xrefs.add(xref)

        try:
            extracted = doc.extract_image(xref)
            if not extracted or not extracted.get("image"):
                continue

            image_bytes: bytes = extracted["image"]
            orig_ext = str(extracted.get("ext", "png")).lower()

            # Validate image integrity using Pillow
            with Image.open(io.BytesIO(image_bytes)) as probe:
                probe.verify()

            with Image.open(io.BytesIO(image_bytes)) as pil_img:
                width, height = pil_img.size
                if width < MIN_IMAGE_DIMENSION_PX or height < MIN_IMAGE_DIMENSION_PX:
                    logger.debug(
                        "Skipping tiny image xref=%d (%dx%d) on '%s' page %d",
                        xref,
                        width,
                        height,
                        document_name,
                        page_number,
                    )
                    continue

                # Save web-friendly PNG or JPEG directly
                target_ext = "jpeg" if orig_ext in ("jpg", "jpeg") else "png"
                file_name = f"page_{page_number:03d}_img_{next_idx:04d}.{target_ext}"
                target_path = images_dir / file_name

                if target_ext == "jpeg":
                    rgb_img = pil_img.convert("RGB") if pil_img.mode not in ("RGB", "L") else pil_img
                    rgb_img.save(target_path, format="JPEG", quality=92)
                else:
                    out_img = pil_img.convert("RGBA") if pil_img.mode in ("CMYK", "P", "LA") else pil_img
                    out_img.save(target_path, format="PNG")

            rects = page.get_image_rects(xref)
            bbox: Optional[List[float]] = None
            if rects:
                r = rects[0]
                bbox = [round(float(r.x0), 2), round(float(r.y0), 2), round(float(r.x1), 2), round(float(r.y1), 2)]

            image_id = f"image_{next_idx:04d}"
            items.append(
                ImageItem(
                    content_id=image_id,
                    document=document_name,
                    page=page_number,
                    image_id=image_id,
                    image_path=f"images/{document_id}/{file_name}",
                    image_url=f"/api/documents/{document_id}/images/{file_name}",
                    file_name=file_name,
                    width=width,
                    height=height,
                    format=target_ext,
                    bbox=bbox,
                    ocr_text=None,
                )
            )
            next_idx += 1
        except Exception as exc:
            msg = f"Failed extracting image xref={xref} on '{document_name}' page {page_number}: {exc}"
            logger.error(msg)
            errors.append(msg)

    return items, errors

