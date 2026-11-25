import json
from pathlib import Path

import pytest
from PIL import Image

from app.chunking.image_chunker import create_image_chunks
from app.chunking.pipeline import chunk_document
from app.chunking.stats import compute_method_stats
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
from app.classification.storage import save_classified_document
from app.core.config import Settings
from app.schemas.chunking import ALL_CHUNKING_METHODS, ChunkingParameters
from app.schemas.classification import (
    ClassificationStats,
    ClassifiedDocumentResponse,
    ClassifiedImageItem,
    ClassifiedTableItem,
    ClassifiedTextItem,
)

SAMPLE_LONG_TEXT = (
    "# Introduction\n"
    "Casinghead gas collects in the annular space between the casing and tubing in an oil well. "
    "When pressure builds up, it can vapor lock a beam pump or electric submersible pump. "
    "Operators remove casinghead gas pressure to maintain steady oil production. "
    "Venting this gas directly to the atmosphere causes significant methane emissions.\n\n"
    "# Mitigation Options\n"
    "Vapor recovery units compress casinghead gas and route it into gathering pipelines for sales. "
    "Wellhead compressors can also capture gas for onsite fuel usage or reinjection. "
    "When gas recovery is not feasible, routing gas to an enclosed flare reduces methane venting. "
    "Operators should inspect compressors and flare pilots regularly to verify high destruction efficiency."
)


@pytest.mark.parametrize(
    "chunk_fn",
    [
        fixed_size_chunk,
        token_based_chunk,
        sentence_based_chunk,
        paragraph_based_chunk,
        recursive_chunk,
        sliding_window_chunk,
        semantic_chunk,
        structure_section_chunk,
    ],
)
def test_all_methods_handle_empty_and_short_text(chunk_fn):
    assert chunk_fn("") == []
    assert chunk_fn("   \n\t  ") == []

    short = "Methane monitoring guidance."
    res = chunk_fn(short)
    assert len(res) == 1
    assert res[0]["content"] == short


def test_fixed_size_and_sliding_window_overlap():
    text = "A" * 100 + "B" * 100 + "C" * 50  # 250 chars
    fixed = fixed_size_chunk(text, chunk_size=100, overlap=20)
    assert len(fixed) == 3
    assert fixed[0]["start_pos"] == 0 and fixed[0]["end_pos"] == 100
    assert fixed[1]["start_pos"] == 80 and fixed[1]["end_pos"] == 180
    assert fixed[0]["content"][-20:] == fixed[1]["content"][:20]

    sw = sliding_window_chunk(text, window_size=100, step_size=50)
    assert len(sw) == 4
    assert sw[1]["start_pos"] == 50
    assert sw[0]["content"][50:] == sw[1]["content"][:50]


def test_token_sentence_paragraph_recursive_semantic_and_section_chunkers():
    tokens = token_based_chunk(SAMPLE_LONG_TEXT, max_tokens=30, overlap_tokens=5)
    assert len(tokens) >= 3
    assert tokens[0]["content"].split()[-5:] == tokens[1]["content"].split()[:5]

    sents = sentence_based_chunk(SAMPLE_LONG_TEXT, max_sentences=2, overlap_sentences=1, max_chars=500)
    assert len(sents) >= 4
    assert sents[0]["sentence_count"] <= 2

    paras = paragraph_based_chunk(SAMPLE_LONG_TEXT, max_paragraphs=1, max_chars=600)
    assert len(paras) == 2
    assert "Introduction" in paras[0]["content"]
    assert "Mitigation Options" in paras[1]["content"]

    rec = recursive_chunk(SAMPLE_LONG_TEXT, chunk_size=260, overlap=30)
    assert len(rec) >= 3
    assert all(len(c["content"]) <= 260 for c in rec)

    sem = semantic_chunk(SAMPLE_LONG_TEXT, similarity_threshold=0.25, max_chars=350, min_chars=80)
    assert len(sem) >= 2

    sec = structure_section_chunk(SAMPLE_LONG_TEXT, max_chars=500)
    assert len(sec) == 2
    assert sec[0]["section_heading"] == "Introduction"
    assert sec[1]["section_heading"] == "Mitigation Options"


def test_invalid_chunk_parameters_raise_value_error():
    with pytest.raises(ValueError):
        fixed_size_chunk("hello", chunk_size=0, overlap=0)
    with pytest.raises(ValueError):
        fixed_size_chunk("hello", chunk_size=50, overlap=50)
    with pytest.raises(ValueError):
        token_based_chunk("hello", max_tokens=10, overlap_tokens=10)
    with pytest.raises(ValueError):
        sentence_based_chunk("hello", max_sentences=2, overlap_sentences=2)
    with pytest.raises(ValueError):
        sliding_window_chunk("hello", window_size=100, step_size=120)
    with pytest.raises(ValueError):
        semantic_chunk("hello", similarity_threshold=1.5)


def test_table_and_image_chunk_creation_and_missing_assets(tmp_path: Path):
    tables = [
        ClassifiedTableItem(
            table_id="table_0001",
            content_id="table_0001",
            document_id="doc1",
            document_name="doc1.pdf",
            page=2,
            headers=["Configuration", "Status"],
            rows=[["Direct Vent", "Unmitigated"], ["VRU", "Mitigated"]],
            structured_data=[{"Configuration": "Direct Vent", "Status": "Unmitigated"}],
            markdown="| Configuration | Status |\n| --- | --- |",
            extraction_method="pdfplumber",
        ),
        ClassifiedTableItem(
            table_id="table_empty",
            content_id="table_empty",
            document_id="doc1",
            document_name="doc1.pdf",
            page=3,
            headers=[],
            rows=[],
        ),
    ]
    tbl_chunks, tbl_warnings = create_table_chunks(tables, "doc1", "doc1.pdf")
    assert len(tbl_chunks) == 1
    assert len(tbl_warnings) == 1
    assert tbl_chunks[0].content_type == "table"
    assert tbl_chunks[0].page == 2
    assert "Headers: Configuration | Status" in tbl_chunks[0].content
    assert "Row 1: Direct Vent | Unmitigated" in tbl_chunks[0].content

    extracted_root = tmp_path / "extracted"
    img_dir = extracted_root / "images" / "doc1"
    img_dir.mkdir(parents=True, exist_ok=True)
    real_img_path = img_dir / "exhibit_a.jpeg"
    Image.new("RGB", (320, 240), color=(40, 120, 180)).save(real_img_path)

    images = [
        ClassifiedImageItem(
            image_id="image_0001",
            content_id="image_0001",
            document_id="doc1",
            document_name="doc1.pdf",
            page=1,
            image_path="images/doc1/logo.png",
            image_url="/api/documents/doc1/images/logo.png",
            image_format="png",
            width=404,
            height=201,
            is_decorative=True,
        ),
        ClassifiedImageItem(
            image_id="image_0002",
            content_id="image_0002",
            document_id="doc1",
            document_name="doc1.pdf",
            page=9,
            image_path="images/doc1/exhibit_a.jpeg",
            image_url="/api/documents/doc1/images/exhibit_a.jpeg",
            image_format="jpeg",
            width=320,
            height=240,
            is_decorative=False,
        ),
        ClassifiedImageItem(
            image_id="image_0003",
            content_id="image_0003",
            document_id="doc1",
            document_name="doc1.pdf",
            page=10,
            image_path="images/doc1/missing.png",
            image_url="/api/documents/doc1/images/missing.png",
            image_format="png",
            width=300,
            height=200,
            is_decorative=False,
        ),
    ]
    clean_texts = [
        ClassifiedTextItem(
            content_id="text_0001",
            document_id="doc1",
            document_name="doc1.pdf",
            page=9,
            text="Exhibit A – Manually Venting Casinghead Gas",
            section_heading="Exhibit A – Manually Venting Casinghead Gas",
            is_boilerplate=False,
        )
    ]

    img_chunks, img_warnings = create_image_chunks(images, clean_texts, extracted_root, "doc1", "doc1.pdf")
    assert len(img_chunks) == 1
    assert len(img_warnings) == 1
    assert img_chunks[0].content_type == "image"
    assert img_chunks[0].page == 9
    assert img_chunks[0].metadata["image_id"] == "image_0002"
    assert img_chunks[0].metadata["section_heading"] == "Exhibit A – Manually Venting Casinghead Gas"


def test_chunk_document_pipeline_persists_all_8_methods_and_stats(tmp_path: Path):
    settings = Settings(
        data_pdf_dir=str(tmp_path / "pdfs"),
        extracted_data_dir=str(tmp_path / "extracted"),
        chunk_outputs_dir=str(tmp_path / "chunks"),
    )
    img_dir = settings.extracted_storage_path / "images" / "doc_full"
    img_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (200, 150), color=(20, 80, 140)).save(img_dir / "fig1.png")

    classified = ClassifiedDocumentResponse(
        document_id="doc_full",
        document_name="sample_ogmp.pdf",
        total_pages=2,
        created_at="2026-11-25T12:00:00Z",
        stats=ClassificationStats(
            raw_text_items=4,
            classified_text_items=4,
            clean_text_items=3,
            boilerplate_text_items=1,
            removed_table_duplicates=0,
            raw_tables=1,
            classified_tables=1,
            refined_tables_count=0,
            raw_images=2,
            classified_images=2,
            content_images=1,
            decorative_images=1,
        ),
        text=[
            ClassifiedTextItem(
                content_id="text_0001",
                document_id="doc_full",
                document_name="sample_ogmp.pdf",
                page=1,
                text="CCAC OGMP Banner",
                is_boilerplate=True,
            ),
            ClassifiedTextItem(
                content_id="text_0002",
                document_id="doc_full",
                document_name="sample_ogmp.pdf",
                page=1,
                text="Introduction\n" + ("Casinghead gas recovery reduces methane emissions. " * 14),
                section_heading="Introduction",
                is_boilerplate=False,
            ),
            ClassifiedTextItem(
                content_id="text_0003",
                document_id="doc_full",
                document_name="sample_ogmp.pdf",
                page=2,
                text="Mitigation Option A\n" + ("Install wellhead compressors or VRU systems. " * 14),
                section_heading="Mitigation Option A",
                is_boilerplate=False,
            ),
        ],
        tables=[
            ClassifiedTableItem(
                table_id="table_0001",
                content_id="table_0001",
                document_id="doc_full",
                document_name="sample_ogmp.pdf",
                page=2,
                headers=["Option", "Outcome"],
                rows=[["VRU", "Mitigated"]],
                markdown="| Option | Outcome |\n| --- | --- |\n| VRU | Mitigated |",
            )
        ],
        images=[
            ClassifiedImageItem(
                image_id="image_0001",
                content_id="image_0001",
                document_id="doc_full",
                document_name="sample_ogmp.pdf",
                page=1,
                image_path="images/doc_full/logo.png",
                image_url="/api/documents/doc_full/images/logo.png",
                image_format="png",
                width=120,
                height=60,
                is_decorative=True,
            ),
            ClassifiedImageItem(
                image_id="image_0002",
                content_id="image_0002",
                document_id="doc_full",
                document_name="sample_ogmp.pdf",
                page=2,
                image_path="images/doc_full/fig1.png",
                image_url="/api/documents/doc_full/images/fig1.png",
                image_format="png",
                width=200,
                height=150,
                is_decorative=False,
            ),
        ],
    )
    save_classified_document(settings.extracted_storage_path, classified)

    params = ChunkingParameters(fixed_chunk_size=300, fixed_overlap=50)
    res = chunk_document("doc_full", settings, params=params)

    assert len(res.method_stats) == 8
    assert res.table_chunks_count == 1
    assert res.image_chunks_count == 1
    for method in ALL_CHUNKING_METHODS:
        chunks = res.text_chunks[method]
        assert len(chunks) >= 1
        assert all("CCAC OGMP Banner" not in c.content for c in chunks)
        assert all(c.content_type == "text" and c.chunking_method == method for c in chunks)
        stats = compute_method_stats(method, chunks)
        assert stats.chunk_count == len(chunks)
        assert stats.min_chunk_length <= stats.avg_chunk_length <= stats.max_chunk_length

    out_dir = settings.chunk_outputs_path / "doc_full"
    assert (out_dir / "summary.json").is_file()
    assert (out_dir / "tables.json").is_file()
    assert (out_dir / "images.json").is_file()
    for method in ALL_CHUNKING_METHODS:
        method_file = out_dir / "methods" / f"{method}.json"
        assert method_file.is_file()
        assert isinstance(json.loads(method_file.read_text(encoding="utf-8")), list)

    with pytest.raises(FileNotFoundError):
        chunk_document("nonexistent_doc_xyz", settings)
