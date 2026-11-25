from pathlib import Path

import pymupdf
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app


def _make_simple_pdf_bytes() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(
        (50, 72),
        "Oil and Gas Methane Partnership Technical Guidance Document test page with sufficient text.",
        fontsize=12,
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_api_upload_and_retrieval_flow(tmp_path: Path):
    test_settings = Settings(
        data_pdf_dir=str(tmp_path / "pdfs"),
        extracted_data_dir=str(tmp_path / "extracted"),
        chunk_outputs_dir=str(tmp_path / "chunks"),
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    client = TestClient(app)

    try:
        health_res = client.get("/api/health")
        assert health_res.status_code == 200
        assert health_res.json()["status"] == "ok"

        pdf_bytes = _make_simple_pdf_bytes()
        upload_res = client.post(
            "/api/documents/upload",
            files={"file": ("ogmp_test.pdf", pdf_bytes, "application/pdf")},
        )
        assert upload_res.status_code == 201
        summary = upload_res.json()
        doc_id = summary["document_id"]
        assert summary["document"] == "ogmp_test.pdf"
        assert summary["total_pages"] == 1
        assert summary["text_items"] >= 1

        get_res = client.get(f"/api/documents/{doc_id}")
        assert get_res.status_code == 200
        assert get_res.json()["document_id"] == doc_id

        ext_res = client.get(f"/api/documents/{doc_id}/extraction")
        assert ext_res.status_code == 200
        ext_payload = ext_res.json()
        assert len(ext_payload["text"]) >= 1
        assert ext_payload["pages"][0]["page"] == 1

        list_res = client.get("/api/documents")
        assert list_res.status_code == 200
        assert any(d["document_id"] == doc_id for d in list_res.json()["documents"])

        cls_res = client.get(f"/api/documents/{doc_id}/classification")
        assert cls_res.status_code == 200
        cls_payload = cls_res.json()
        assert cls_payload["document_id"] == doc_id
        assert cls_payload["stats"]["classified_text_items"] >= 1

        recls_res = client.post(f"/api/documents/{doc_id}/classify")
        assert recls_res.status_code == 200
        assert recls_res.json()["document_id"] == doc_id

        chunk_res = client.post(f"/api/documents/{doc_id}/chunk")
        assert chunk_res.status_code == 200
        chunk_payload = chunk_res.json()
        assert chunk_payload["document_id"] == doc_id
        assert len(chunk_payload["method_stats"]) == 8

        get_chunks_res = client.get(f"/api/documents/{doc_id}/chunks")
        assert get_chunks_res.status_code == 200
        assert len(get_chunks_res.json()["text_chunks"]) == 8

        method_res = client.get(f"/api/documents/{doc_id}/chunks/recursive")
        assert method_res.status_code == 200
        assert method_res.json()["method"] == "recursive"
        assert len(method_res.json()["chunks"]) >= 1

        bad_method = client.get(f"/api/documents/{doc_id}/chunks/unknown_method")
        assert bad_method.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_api_error_handling(tmp_path: Path):
    test_settings = Settings(
        data_pdf_dir=str(tmp_path / "pdfs"),
        extracted_data_dir=str(tmp_path / "extracted"),
        chunk_outputs_dir=str(tmp_path / "chunks"),
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    client = TestClient(app)

    try:
        bad_ext = client.post(
            "/api/documents/upload",
            files={"file": ("notes.txt", b"hello world", "text/plain")},
        )
        assert bad_ext.status_code == 400
        assert "Only .pdf" in bad_ext.json()["detail"]

        bad_header = client.post(
            "/api/documents/upload",
            files={"file": ("fake.pdf", b"not a real pdf", "application/pdf")},
        )
        assert bad_header.status_code == 400
        assert "valid PDF header" in bad_header.json()["detail"]

        missing = client.get("/api/documents/nonexistent_doc_123")
        assert missing.status_code == 404
    finally:
        app.dependency_overrides.clear()

