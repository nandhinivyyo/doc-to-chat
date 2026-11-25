from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.classification.storage import save_classified_document
from app.core.config import Settings, get_settings
from app.main import app
from app.schemas.chunking import ALL_CHUNKING_METHODS
from app.schemas.classification import (
    ClassificationStats,
    ClassifiedDocumentResponse,
    ClassifiedImageItem,
    ClassifiedTableItem,
    ClassifiedTextItem,
)


def _seed_classified_document(settings: Settings, document_id: str = "viz_doc_001") -> None:
    img_dir = settings.extracted_storage_path / "images" / document_id
    img_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (404, 201), color=(15, 50, 120)).save(img_dir / "logo.png")
    Image.new("RGB", (320, 240), color=(40, 120, 180)).save(img_dir / "exhibit_a.jpeg")

    classified = ClassifiedDocumentResponse(
        document_id=document_id,
        document_name="2017_OGMP-TGD9-Casinghead-venting_CCAC.pdf",
        total_pages=2,
        created_at="2026-11-25T12:00:00Z",
        stats=ClassificationStats(
            raw_text_items=3,
            classified_text_items=3,
            clean_text_items=2,
            boilerplate_text_items=1,
            removed_table_duplicates=0,
            raw_tables=2,
            classified_tables=2,
            refined_tables_count=2,
            raw_images=2,
            classified_images=2,
            content_images=1,
            decorative_images=1,
        ),
        text=[
            ClassifiedTextItem(
                content_id="text_0001",
                document_id=document_id,
                document_name="2017_OGMP-TGD9-Casinghead-venting_CCAC.pdf",
                page=1,
                text="Page 1 of 2",
                is_boilerplate=True,
            ),
            ClassifiedTextItem(
                content_id="text_0002",
                document_id=document_id,
                document_name="2017_OGMP-TGD9-Casinghead-venting_CCAC.pdf",
                page=1,
                text=(
                    "Introduction\n"
                    "Casinghead gas collects in the annular space between casing and tubing. "
                    * 10
                ),
                section_heading="Introduction",
                is_boilerplate=False,
            ),
            ClassifiedTextItem(
                content_id="text_0003",
                document_id=document_id,
                document_name="2017_OGMP-TGD9-Casinghead-venting_CCAC.pdf",
                page=2,
                text=(
                    "Mitigation Option A\n"
                    "Vapor recovery units capture casinghead gas and route it to sales pipelines. "
                    * 10
                ),
                section_heading="Mitigation Option A",
                is_boilerplate=False,
            ),
        ],
        tables=[
            ClassifiedTableItem(
                table_id="table_0001",
                content_id="table_0001",
                document_id=document_id,
                document_name="2017_OGMP-TGD9-Casinghead-venting_CCAC.pdf",
                page=2,
                headers=["Configuration", "Mitigated or Unmitigated"],
                rows=[["Direct vent", "Unmitigated"], ["VRU Option A", "Mitigated"]],
                markdown="| Configuration | Mitigated or Unmitigated |\n| --- | --- |",
                extraction_method="pdfplumber",
            ),
            ClassifiedTableItem(
                table_id="table_0002",
                content_id="table_0002",
                document_id=document_id,
                document_name="2017_OGMP-TGD9-Casinghead-venting_CCAC.pdf",
                page=2,
                headers=["Project Component", "Implementation Costs", "Annual Costs"],
                rows=[["Capital CostA", "$12,500", "–"]],
                markdown="| Project Component | Implementation Costs | Annual Costs |\n| --- | --- | --- |",
                extraction_method="pdfplumber",
            ),
        ],
        images=[
            ClassifiedImageItem(
                image_id="image_0001",
                content_id="image_0001",
                document_id=document_id,
                document_name="2017_OGMP-TGD9-Casinghead-venting_CCAC.pdf",
                page=1,
                image_path=f"images/{document_id}/logo.png",
                image_url=f"/api/documents/{document_id}/images/logo.png",
                image_format="png",
                width=404,
                height=201,
                is_decorative=True,
            ),
            ClassifiedImageItem(
                image_id="image_0002",
                content_id="image_0002",
                document_id=document_id,
                document_name="2017_OGMP-TGD9-Casinghead-venting_CCAC.pdf",
                page=2,
                image_path=f"images/{document_id}/exhibit_a.jpeg",
                image_url=f"/api/documents/{document_id}/images/exhibit_a.jpeg",
                image_format="jpeg",
                width=320,
                height=240,
                is_decorative=False,
            ),
        ],
    )
    save_classified_document(settings.extracted_storage_path, classified)


def test_chunk_visualization_endpoints_end_to_end(tmp_path: Path):
    test_settings = Settings(
        data_pdf_dir=str(tmp_path / "pdfs"),
        extracted_data_dir=str(tmp_path / "extracted"),
        chunk_outputs_dir=str(tmp_path / "chunks"),
    )
    _seed_classified_document(test_settings, "viz_doc_001")
    app.dependency_overrides[get_settings] = lambda: test_settings
    client = TestClient(app)

    try:
        # 1. Summary endpoint
        sum_res = client.get("/api/documents/viz_doc_001/chunks/summary")
        assert sum_res.status_code == 200
        summary = sum_res.json()
        assert summary["document_id"] == "viz_doc_001"
        assert len(summary["method_stats"]) == 8
        assert summary["table_chunks_count"] == 2
        assert summary["image_chunks_count"] == 1

        # 2 & 3 & 7. All 8 text methods load independently with metadata preserved
        for method in ALL_CHUNKING_METHODS:
            m_res = client.get(f"/api/documents/viz_doc_001/chunks/{method}")
            assert m_res.status_code == 200
            payload = m_res.json()
            assert payload["method"] == method
            assert payload["stats"]["chunk_count"] == len(payload["chunks"])
            assert len(payload["chunks"]) >= 1
            for chunk in payload["chunks"]:
                assert chunk["chunking_method"] == method
                assert chunk["content_type"] == "text"
                assert chunk["document_id"] == "viz_doc_001"
                assert chunk["page"] in (1, 2)
                assert chunk["metadata"]["document_name"] == "2017_OGMP-TGD9-Casinghead-venting_CCAC.pdf"
                assert chunk["metadata"]["section_heading"] in ("Introduction", "Mitigation Option A")

        # 4. Tables endpoint returns structured table chunks
        tbl_res = client.get("/api/documents/viz_doc_001/chunks/tables")
        assert tbl_res.status_code == 200
        tbl_payload = tbl_res.json()
        assert tbl_payload["table_chunks_count"] == 2
        assert tbl_payload["tables"][0]["metadata"]["headers"] == [
            "Configuration",
            "Mitigated or Unmitigated",
        ]

        # 5 & 6. Images endpoint returns only non-decorative images (excludes logo.png)
        img_res = client.get("/api/documents/viz_doc_001/chunks/images")
        assert img_res.status_code == 200
        img_payload = img_res.json()
        assert img_payload["image_chunks_count"] == 1
        assert img_payload["images"][0]["metadata"]["image_id"] == "image_0002"
        assert all("logo.png" not in i["metadata"]["image_path"] for i in img_payload["images"])
    finally:
        app.dependency_overrides.clear()


def test_chunk_visualization_error_handling(tmp_path: Path):
    test_settings = Settings(
        data_pdf_dir=str(tmp_path / "pdfs"),
        extracted_data_dir=str(tmp_path / "extracted"),
        chunk_outputs_dir=str(tmp_path / "chunks"),
    )
    _seed_classified_document(test_settings, "viz_doc_err")
    app.dependency_overrides[get_settings] = lambda: test_settings
    client = TestClient(app)

    try:
        # 8. Missing document returns 404 across read-only endpoints
        for suffix in ("summary", "tables", "images", "fixed_size"):
            res = client.get(f"/api/documents/missing_doc_999/chunks/{suffix}")
            assert res.status_code == 404

        # 9. Invalid method returns 400
        bad_method = client.get("/api/documents/viz_doc_err/chunks/invalid_method_name")
        assert bad_method.status_code == 400
        assert "Unsupported chunking method" in bad_method.json()["detail"]
    finally:
        app.dependency_overrides.clear()
