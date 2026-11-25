import json
from pathlib import Path

import pymupdf
from PIL import Image

from app.classification.boilerplate_detector import detect_boilerplate_text_items
from app.classification.classifier import classify_document
from app.classification.deduplicator import remove_table_duplicates_from_text
from app.classification.image_classifier import classify_images
from app.classification.table_refiner import score_table_quality
from app.core.config import Settings
from app.extraction.pdf_extractor import extract_pdf_document
from app.extraction.text_extractor import is_section_heading
from app.schemas.classification import ClassifiedTableItem
from app.schemas.document import ImageItem, PageMetadata, TextItem


def test_table_quality_scoring_prefers_clean_spacing():
    noisy_rows = [
        ["ProjectComponent", "ImplementationCosts", "AnnualCosts"],
        ["CapitalCostA", "$12500 ,", "–"],
        ["GasSavingsD", "–", "$104800 - ,"],
    ]
    clean_rows = [
        ["Project Component", "Implementation Costs", "Annual Costs"],
        ["Capital CostA", "$12,500", "–"],
        ["Gas SavingsD", "–", "-$104,800"],
    ]

    noisy_score, noisy_metrics = score_table_quality(noisy_rows)
    clean_score, clean_metrics = score_table_quality(clean_rows)

    assert clean_score > noisy_score
    assert noisy_metrics["merged_tokens"] > clean_metrics["merged_tokens"]
    assert noisy_metrics["split_punct"] > clean_metrics["split_punct"]


def test_remove_table_duplicates_from_text_preserves_captions_and_footnotes():
    table = ClassifiedTableItem(
        table_id="table_0001",
        content_id="table_0001",
        document_id="doc1",
        document_name="doc1.pdf",
        page=2,
        headers=["Configuration", "Status"],
        rows=[["Vented directly", "Unmitigated"], ["Routed to flare", "Mitigated"]],
        markdown="",
        bbox=[70.0, 100.0, 550.0, 300.0],
        extraction_method="pdfplumber",
    )

    raw_texts = [
        TextItem(
            content_id="text_0001",
            document="doc1.pdf",
            page=2,
            content="Table 1: Configurations",
            bbox=[180.0, 80.0, 420.0, 95.0],
        ),
        TextItem(
            content_id="text_0002",
            document="doc1.pdf",
            page=2,
            content="Vented directly\nUnmitigated",
            bbox=[90.0, 140.0, 500.0, 175.0],
        ),
        TextItem(
            content_id="text_0003",
            document="doc1.pdf",
            page=2,
            content="Note: Flare efficiency must be monitored regularly.",
            bbox=[70.0, 310.0, 540.0, 340.0],
        ),
    ]

    kept, excluded = remove_table_duplicates_from_text(raw_texts, [table])

    assert [t.content_id for t in kept] == ["text_0001", "text_0003"]
    assert len(excluded) == 1
    assert excluded[0].raw_content_id == "text_0002"
    assert excluded[0].matched_table_id == "table_0001"


def test_boilerplate_and_decorative_image_detection(tmp_path: Path):
    pages = [
        PageMetadata(page=p, width=612.0, height=792.0)
        for p in range(1, 5)
    ]

    text_items = []
    idx = 1
    for p in range(1, 5):
        text_items.append(
            TextItem(
                content_id=f"text_{idx:04d}",
                document="tgd.pdf",
                page=p,
                content="CCAC OGMP Technical Guidance Document",
                bbox=[180.0, 35.0, 440.0, 60.0],
            )
        )
        idx += 1
        text_items.append(
            TextItem(
                content_id=f"text_{idx:04d}",
                document="tgd.pdf",
                page=p,
                content=f"Page {p} of 4",
                bbox=[480.0, 745.0, 540.0, 756.0],
            )
        )
        idx += 1
        text_items.append(
            TextItem(
                content_id=f"text_{idx:04d}",
                document="tgd.pdf",
                page=p,
                content=f"Unique technical guidance body paragraph on page {p}.",
                bbox=[72.0, 180.0, 540.0, 260.0],
            )
        )
        idx += 1

    reasons = detect_boilerplate_text_items(text_items, pages)
    for item in text_items:
        if "Unique technical guidance" in item.content:
            assert reasons[item.content_id] is None
        else:
            assert reasons[item.content_id] is not None

    img_dir = tmp_path / "images" / "doc_bp"
    img_dir.mkdir(parents=True, exist_ok=True)

    logo_path = img_dir / "logo.png"
    Image.new("RGB", (120, 60), color=(10, 40, 120)).save(logo_path)
    diagram_path = img_dir / "diagram.png"
    Image.new("RGB", (300, 200), color=(200, 100, 40)).save(diagram_path)

    raw_images = [
        ImageItem(
            content_id=f"image_{p:04d}",
            document="tgd.pdf",
            page=p,
            image_id=f"image_{p:04d}",
            image_path="images/doc_bp/logo.png",
            image_url="/api/documents/doc_bp/images/logo.png",
            file_name="logo.png",
            width=120,
            height=60,
            format="png",
            bbox=[45.0, 20.0, 175.0, 85.0],
        )
        for p in range(1, 5)
    ]
    raw_images.append(
        ImageItem(
            content_id="image_0005",
            document="tgd.pdf",
            page=3,
            image_id="image_0005",
            image_path="images/doc_bp/diagram.png",
            image_url="/api/documents/doc_bp/images/diagram.png",
            file_name="diagram.png",
            width=300,
            height=200,
            format="png",
            bbox=[100.0, 250.0, 400.0, 450.0],
        )
    )

    classified_imgs = classify_images(
        raw_images=raw_images,
        pages=pages,
        extracted_root=tmp_path,
        document_id="doc_bp",
        document_name="tgd.pdf",
    )

    assert sum(1 for i in classified_imgs if i.is_decorative) == 4
    assert sum(1 for i in classified_imgs if not i.is_decorative) == 1
    assert classified_imgs[-1].is_decorative is False


def test_classify_document_end_to_end(tmp_path: Path):
    settings = Settings(
        data_pdf_dir=str(tmp_path / "pdfs"),
        extracted_data_dir=str(tmp_path / "extracted"),
    )
    settings.pdf_storage_path.mkdir(parents=True, exist_ok=True)
    pdf_path = settings.pdf_storage_path / "doc_p3.pdf"

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 90), "Section 1: Overview", fontsize=14)
    page.insert_text(
        (72, 120),
        "Casinghead gas venting can be mitigated using vapor recovery units.",
        fontsize=11,
    )

    x_cols = [72, 240, 450]
    y_rows = [160, 190, 220, 250]
    for y in y_rows:
        page.draw_line((x_cols[0], y), (x_cols[-1], y))
    for x in x_cols:
        page.draw_line((x, y_rows[0]), (x, y_rows[-1]))

    rows = [
        ["Option", "Classification"],
        ["Direct Vent", "Unmitigated"],
        ["VRU Recovery", "Mitigated"],
    ]
    for r_idx, row in enumerate(rows):
        for c_idx, val in enumerate(row):
            page.insert_text((x_cols[c_idx] + 8, y_rows[r_idx] + 20), val, fontsize=10)

    doc.save(str(pdf_path))
    doc.close()

    extract_pdf_document(
        pdf_path=pdf_path,
        document_id="doc_p3",
        settings=settings,
        original_filename="doc_p3.pdf",
    )

    classified = classify_document(document_id="doc_p3", settings=settings, pdf_path=pdf_path)

    assert classified.document_id == "doc_p3"
    assert classified.stats.classified_tables == 1
    assert classified.tables[0].headers == ["Option", "Classification"]
    assert len(classified.tables[0].structured_data) == 2
    assert classified.stats.removed_table_duplicates >= 1
    assert all(t.section_heading not in ("Option", "Classification") for t in classified.text)

    classified_file = settings.extracted_storage_path / "classified" / "doc_p3.json"
    assert classified_file.is_file()
    parsed = json.loads(classified_file.read_text(encoding="utf-8"))
    assert parsed["document_id"] == "doc_p3"
    assert len(parsed["tables"]) == 1


def test_section_heading_filter_rejects_captions_and_fragments():
    assert is_section_heading("Introduction", 11.0, True) is True
    assert is_section_heading("Description of Source", 11.0, True) is True
    assert is_section_heading("Mitigation Option A – Install compressors/VRUs", 11.0, True) is True
    assert is_section_heading("Table 9.1: Configurations for Casinghead Gas Venting", 11.0, True) is False
    assert is_section_heading("Scenario)", 11.0, True) is False
    assert is_section_heading("(OPTION A)", 11.0, True) is False

