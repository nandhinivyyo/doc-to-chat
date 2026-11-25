import io
import json
from pathlib import Path

import pymupdf
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.config import Settings
from app.extraction.pdf_extractor import PDFExtractionError, extract_pdf_document
from app.extraction.table_extractor import clean_table_rows, is_valid_table, table_to_markdown
from app.extraction.text_extractor import assess_text_meaningfulness


def _build_test_settings(tmp_path: Path) -> Settings:
    return Settings(
        data_pdf_dir=str(tmp_path / "pdfs"),
        extracted_data_dir=str(tmp_path / "extracted"),
        min_meaningful_text_chars=30,
        min_alpha_chars=10,
        ocr_dpi=150,
        ocr_engine="auto",
    )


def _create_sample_pdf_with_text_table_image_and_ocr_page(pdf_path: Path) -> None:
    """Create a 2-page PDF: page 1 has text+table+image, page 2 is image-only for OCR."""
    doc = pymupdf.open()

    # Page 1: Heading, paragraph, drawn table, embedded PNG image
    page1 = doc.new_page(width=595, height=842)
    page1.insert_text((50, 60), "1. Methane Emissions Guidance", fontsize=16)
    page1.insert_text(
        (50, 95),
        "Pneumatic controllers actuated by natural gas are a significant source of methane emissions.",
        fontsize=11,
    )

    # Draw a 3x3 bordered table so PyMuPDF / pdfplumber can detect it
    x_cols = [50, 200, 350, 500]
    y_rows = [140, 170, 200, 230]
    for y in y_rows:
        page1.draw_line((x_cols[0], y), (x_cols[-1], y))
    for x in x_cols:
        page1.draw_line((x, y_rows[0]), (x, y_rows[-1]))

    table_cells = [
        ["Device Type", "Bleed Rate", "Mitigation"],
        ["Continuous High", "15 scfh", "Convert to air"],
        ["Intermittent", "2 scfh", "Retrofit valve"],
    ]
    for r_idx, row in enumerate(table_cells):
        for c_idx, val in enumerate(row):
            page1.insert_text((x_cols[c_idx] + 6, y_rows[r_idx] + 20), val, fontsize=10)

    # Create a valid PNG image and embed on page 1
    img = Image.new("RGB", (160, 100), color=(30, 90, 160))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 140, 80], outline=(255, 255, 255), width=3)
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    page1.insert_image(pymupdf.Rect(50, 280, 210, 380), stream=img_buf.getvalue())

    # Page 2: Scanned-like image-only page (no native text layer)
    page2 = doc.new_page(width=595, height=842)
    ocr_img = Image.new("RGB", (1000, 260), color=(255, 255, 255))
    ocr_draw = ImageDraw.Draw(ocr_img)
    ocr_font = ImageFont.load_default(size=32)
    ocr_draw.text((30, 80), "SCANNED APPENDIX: METHANE MONITORING LOG 2025", fill=(0, 0, 0), font=ocr_font)
    ocr_buf = io.BytesIO()
    ocr_img.save(ocr_buf, format="PNG")
    page2.insert_image(pymupdf.Rect(40, 60, 540, 200), stream=ocr_buf.getvalue())

    doc.save(str(pdf_path))
    doc.close()


def test_assess_text_meaningfulness():
    ok, _ = assess_text_meaningfulness("This is a clear technical paragraph about methane.")
    assert ok is True

    empty_ok, reason = assess_text_meaningfulness("   \n\t ")
    assert empty_ok is False
    assert reason == "no_extractable_text"

    short_ok, _ = assess_text_meaningfulness("12345")
    assert short_ok is False


def test_table_helpers():
    raw = [[" Header A ", None, "Header B"], [None, None, None], ["val 1", "", "val 2"]]
    cleaned = clean_table_rows(raw)
    assert cleaned == [["Header A", "Header B"], ["val 1", "val 2"]]
    assert is_valid_table(cleaned) is True
    md = table_to_markdown(cleaned)
    assert "| Header A | Header B |" in md
    assert "| val 1 | val 2 |" in md


def test_extract_pdf_document_full_pipeline(tmp_path: Path):
    settings = _build_test_settings(tmp_path)
    pdf_path = tmp_path / "sample_tgd.pdf"
    _create_sample_pdf_with_text_table_image_and_ocr_page(pdf_path)

    result = extract_pdf_document(
        pdf_path=pdf_path,
        document_id="sample_test_001",
        settings=settings,
        original_filename="sample_tgd.pdf",
    )

    assert result.summary.total_pages == 2
    assert result.summary.text_items >= 2
    assert result.summary.tables >= 1
    assert result.summary.images >= 2
    assert result.summary.ocr_used is True
    assert 2 in result.summary.ocr_pages
    assert result.pages[1].ocr_used is True
    assert result.pages[1].ocr_reason is not None

    # Verify structured JSON files exist and are valid JSON
    extracted_root = settings.extracted_storage_path
    for sub in ("text", "tables", "images", "metadata"):
        json_file = extracted_root / sub / "sample_test_001.json"
        assert json_file.is_file()
        parsed = json.loads(json_file.read_text(encoding="utf-8"))
        assert parsed is not None

    # Verify extracted image files open cleanly with Pillow
    for img_item in result.images:
        img_file = extracted_root / img_item.image_path
        assert img_file.is_file()
        with Image.open(img_file) as opened:
            opened.verify()


def test_extract_invalid_and_missing_pdfs(tmp_path: Path):
    settings = _build_test_settings(tmp_path)

    with pytest.raises(PDFExtractionError, match="not found"):
        extract_pdf_document(tmp_path / "missing.pdf", "missing_1", settings)

    empty_pdf = tmp_path / "empty.pdf"
    empty_pdf.write_bytes(b"")
    with pytest.raises(PDFExtractionError, match="empty"):
        extract_pdf_document(empty_pdf, "empty_1", settings)

    corrupt_pdf = tmp_path / "corrupt.pdf"
    corrupt_pdf.write_bytes(b"%PDF-1.4 corrupted binary garbage")
    with pytest.raises(PDFExtractionError, match="Failed to open"):
        extract_pdf_document(corrupt_pdf, "corrupt_1", settings)

