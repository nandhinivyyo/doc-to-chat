import io
import logging
import os
import shutil
from typing import Optional, Tuple

import pymupdf
from PIL import Image

logger = logging.getLogger(__name__)

_RAPIDOCR_INSTANCE = None


def _find_tesseract_cmd() -> Optional[str]:
    """Locate tesseract executable if installed on the host."""
    in_path = shutil.which("tesseract")
    if in_path:
        return in_path

    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(os.path.join(local_app_data, "Programs", "Tesseract-OCR", "tesseract.exe"))

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def _get_rapidocr():
    """Lazily initialize RapidOCR engine if installed."""
    global _RAPIDOCR_INSTANCE
    if _RAPIDOCR_INSTANCE is None:
        from rapidocr import RapidOCR

        _RAPIDOCR_INSTANCE = RapidOCR()
    return _RAPIDOCR_INSTANCE


def _run_pytesseract(pil_image: Image.Image) -> str:
    import pytesseract

    tesseract_cmd = _find_tesseract_cmd()
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    return pytesseract.image_to_string(pil_image).strip()


def _run_rapidocr(image_bytes: bytes) -> str:
    engine = _get_rapidocr()
    result = engine(image_bytes)
    txts = getattr(result, "txts", None)
    if not txts:
        return ""
    lines = [str(line).strip() for line in txts if str(line).strip()]
    return "\n".join(lines).strip()


def resolve_ocr_engine(preferred: str = "auto") -> str:
    """Resolve which OCR backend should be used."""
    pref = (preferred or "auto").lower().strip()
    if pref == "tesseract":
        return "tesseract"
    if pref == "rapidocr":
        return "rapidocr"

    if _find_tesseract_cmd():
        return "tesseract"
    try:
        import rapidocr  # noqa: F401

        return "rapidocr"
    except ImportError:
        return "tesseract"


def ocr_image_bytes(
    image_bytes: bytes,
    preferred_engine: str = "auto",
) -> Tuple[str, str, Optional[str]]:
    """Run OCR on raw image bytes, returning (text, engine_used, error_message)."""
    engine_name = resolve_ocr_engine(preferred_engine)

    try:
        if engine_name == "rapidocr":
            text = _run_rapidocr(image_bytes)
            return text, "rapidocr", None

        with Image.open(io.BytesIO(image_bytes)) as img:
            text = _run_pytesseract(img)
        return text, "tesseract", None
    except Exception as exc:
        logger.warning("Primary OCR engine '%s' failed: %s", engine_name, exc)
        # Try fallback engine if auto mode was requested
        if preferred_engine.lower().strip() == "auto":
            fallback = "rapidocr" if engine_name == "tesseract" else "tesseract"
            try:
                if fallback == "rapidocr":
                    text = _run_rapidocr(image_bytes)
                    return text, "rapidocr", None
                with Image.open(io.BytesIO(image_bytes)) as img:
                    text = _run_pytesseract(img)
                return text, "tesseract", None
            except Exception as fallback_exc:
                return "", f"{engine_name}+{fallback}", f"{exc}; fallback failed: {fallback_exc}"

        return "", engine_name, str(exc)


def ocr_pdf_page(
    page: pymupdf.Page,
    document_name: str,
    page_number: int,
    dpi: int = 200,
    preferred_engine: str = "auto",
) -> Tuple[str, str, Optional[str]]:
    """Render a PDF page to an image and run OCR on it."""
    try:
        pixmap = page.get_pixmap(dpi=dpi)
        png_bytes = pixmap.tobytes("png")
    except Exception as exc:
        err = f"Failed to render page {page_number} of '{document_name}' for OCR: {exc}"
        logger.error(err)
        return "", "none", err

    text, engine_used, error_msg = ocr_image_bytes(png_bytes, preferred_engine=preferred_engine)
    if error_msg:
        logger.error(
            "OCR failed for document '%s' page %d (engine=%s): %s",
            document_name,
            page_number,
            engine_used,
            error_msg,
        )
    else:
        logger.info(
            "OCR completed for document '%s' page %d using '%s' (%d chars)",
            document_name,
            page_number,
            engine_used,
            len(text),
        )
    return text, engine_used, error_msg

