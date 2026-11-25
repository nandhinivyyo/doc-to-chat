import json
from pathlib import Path

import faiss
import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.embeddings.embedder import embed_texts
from app.main import app
from app.schemas.embeddings import VectorMetadataItem
from app.schemas.search import SemanticSearchRequest
from app.services.semantic_search import (
    embed_query,
    is_document_overview_query,
    search_document,
    search_single_index,
)
from app.vectorstore.faiss_store import build_and_save_faiss_index

TGD9_DOCUMENT_ID = "2017_OGMP-TGD9-Casinghead-venting_CCAC_662883b9"


def _make_metadata_item(
    vector_index: int,
    chunk_id: str,
    document_id: str,
    content_type: str,
    chunking_method: str,
    page: int,
    text: str,
    section_heading: str | None = None,
) -> VectorMetadataItem:
    return VectorMetadataItem(
        vector_index=vector_index,
        embedding_id=f"emb_{chunk_id}",
        chunk_id=chunk_id,
        document_id=document_id,
        content_type=content_type,  # type: ignore[arg-type]
        chunking_method=chunking_method,
        page=page,
        section_heading=section_heading,
        text=text,
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        embedding_dimension=384,
        metadata={"page": page},
    )


def _create_controlled_vector_store(vector_root: Path, document_id: str) -> Path:
    """Build a small controlled Phase 6-compatible vector store for deterministic search tests."""
    doc_dir = vector_root / document_id

    text_chunks = [
        (
            "fixed_size_chunk_001",
            1,
            "Introduction",
            "Casinghead gas is natural gas produced alongside crude oil from wellheads.",
        ),
        (
            "fixed_size_chunk_002",
            4,
            "Mitigation Option A",
            "Vapor recovery units compress and capture casinghead gas for pipeline sales.",
        ),
        (
            "fixed_size_chunk_003",
            5,
            "Flaring",
            "Routing casinghead gas to a flare destroys methane emissions where pipelines are unavailable.",
        ),
    ]
    vecs, dim = embed_texts([c[3] for c in text_chunks])
    text_meta = [
        _make_metadata_item(
            vector_index=idx,
            chunk_id=chunk_id,
            document_id=document_id,
            content_type="text",
            chunking_method="fixed_size",
            page=page,
            text=text,
            section_heading=heading,
        )
        for idx, (chunk_id, page, heading, text) in enumerate(text_chunks)
    ]
    build_and_save_faiss_index(vecs, text_meta, doc_dir / "fixed_size")

    table_text = (
        "Table: table_0001\nHeaders:\nOption | Capital Cost | Operating Cost\n"
        "Rows:\nVRU Installation | $104,800 | $12,000 per year"
    )
    tbl_vecs, _ = embed_texts([table_text])
    assert tbl_vecs.shape[1] == dim
    tbl_meta = [
        _make_metadata_item(
            vector_index=0,
            chunk_id="table_chunk_001",
            document_id=document_id,
            content_type="table",
            chunking_method="table",
            page=6,
            text=table_text,
            section_heading="Implementation Costs",
        )
    ]
    build_and_save_faiss_index(tbl_vecs, tbl_meta, doc_dir / "tables")
    return doc_dir


def test_1_query_embedding_format_and_normalization():
    vector, dim = embed_query("What are the implementation costs?")
    assert dim == 384
    assert vector.shape == (1, 384)
    assert vector.dtype == np.float32
    assert np.all(np.isfinite(vector))
    norm = float(np.linalg.norm(vector[0]))
    assert np.isclose(norm, 1.0, atol=1e-4)


def test_2_and_3_empty_and_whitespace_queries_rejected():
    with pytest.raises(ValidationError):
        SemanticSearchRequest(query="")

    with pytest.raises(ValidationError):
        SemanticSearchRequest(query="   \t\n  ")

    with pytest.raises(ValueError):
        embed_query("   \n ")


def test_4_top_k_and_method_validation(tmp_path: Path):
    req_ok = SemanticSearchRequest(query="casinghead gas", top_k=5)
    assert req_ok.top_k == 5
    assert SemanticSearchRequest(query="casinghead gas", top_k=3).top_k == 3
    assert SemanticSearchRequest(query="casinghead gas", top_k=10).top_k == 10
    assert SemanticSearchRequest(query="casinghead gas", top_k=20).top_k == 20
    assert SemanticSearchRequest(query="casinghead gas", chunking_method="tables").chunking_method == "tables"

    for invalid_k in (0, -1, -10, 21, 100):
        with pytest.raises(ValidationError):
            SemanticSearchRequest(query="casinghead gas", top_k=invalid_k)

    with pytest.raises(ValidationError):
        SemanticSearchRequest(query="casinghead gas", top_k=5, chunking_method="non_existent_method")


def test_5_6_8_9_controlled_faiss_search_ranking_and_metadata(tmp_path: Path):
    doc_id = "controlled_search_doc"
    _create_controlled_vector_store(tmp_path, doc_id)

    settings = Settings(vector_store_dir=str(tmp_path))
    response = search_document(
        document_id=doc_id,
        request=SemanticSearchRequest(query="What are the implementation and capital costs?", top_k=4),
        settings=settings,
    )

    assert response.query == "What are the implementation and capital costs?"
    assert response.top_k == 4
    assert response.document_id == doc_id
    assert set(response.searched_stores) == {"fixed_size", "tables"}
    assert len(response.results) == 4

    # Verify descending similarity scores and sequential 1-based ranking
    scores = [r.score for r in response.results]
    assert scores == sorted(scores, reverse=True)
    assert [r.rank for r in response.results] == [1, 2, 3, 4]

    # Top result should map accurately to the controlled cost table chunk
    top = response.results[0]
    assert top.chunk_id == "table_chunk_001"
    assert top.content_type == "table"
    assert top.chunking_method == "table"
    assert top.page == 6
    assert top.section_heading == "Implementation Costs"
    assert "$104,800" in top.text

    # Verify required metadata fields exist on every result
    for res in response.results:
        assert res.chunk_id
        assert res.document_id == doc_id
        assert res.content_type in {"text", "table"}
        assert res.chunking_method in {"fixed_size", "table"}
        assert res.page >= 1
        assert res.text
        assert isinstance(res.score, float)
        assert res.rank >= 1


def test_7_mismatched_index_and_metadata_count_detected(tmp_path: Path):
    index = faiss.IndexFlatIP(4)
    vectors = np.array(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
        ],
        dtype=np.float32,
    )
    index.add(vectors)

    only_one_meta = [
        _make_metadata_item(
            vector_index=0,
            chunk_id="c1",
            document_id="doc_mismatch",
            content_type="text",
            chunking_method="fixed_size",
            page=1,
            text="first",
        )
    ]

    with pytest.raises(ValueError, match="does not match metadata count"):
        search_single_index(
            index=index,
            metadata_items=only_one_meta,
            query_vector=np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32),
            top_k=2,
        )

    # Also test persisted mismatch detection via API endpoint
    bad_store = tmp_path / "doc_mismatch" / "fixed_size"
    bad_store.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(bad_store / "index.faiss"))
    (bad_store / "metadata.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in only_one_meta]),
        encoding="utf-8",
    )

    test_settings = Settings(vector_store_dir=str(tmp_path))
    app.dependency_overrides[get_settings] = lambda: test_settings
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/documents/doc_mismatch/search",
            json={"query": "test mismatch", "top_k": 3},
        )
        assert resp.status_code == 400
        assert "does not match metadata count" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_api_search_validation_and_scope_filter(tmp_path: Path):
    doc_id = "api_search_doc"
    _create_controlled_vector_store(tmp_path, doc_id)
    test_settings = Settings(vector_store_dir=str(tmp_path))
    app.dependency_overrides[get_settings] = lambda: test_settings
    try:
        client = TestClient(app)

        # Health reports active pipeline status
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert "Phase" in health.json()["phase"]

        # Valid filtered search targeting tables only
        ok_resp = client.post(
            f"/api/documents/{doc_id}/search",
            json={"query": "capital cost", "top_k": 5, "chunking_method": "tables"},
        )
        assert ok_resp.status_code == 200
        payload = ok_resp.json()
        assert payload["searched_stores"] == ["tables"]
        assert len(payload["results"]) == 1
        assert payload["results"][0]["content_type"] == "table"

        # Validation errors: empty, whitespace, invalid top_k
        assert client.post(f"/api/documents/{doc_id}/search", json={"query": "", "top_k": 5}).status_code == 422
        assert client.post(f"/api/documents/{doc_id}/search", json={"query": "   ", "top_k": 5}).status_code == 422
        assert client.post(f"/api/documents/{doc_id}/search", json={"query": "gas", "top_k": 0}).status_code == 422
        assert client.post(f"/api/documents/{doc_id}/search", json={"query": "gas", "top_k": 25}).status_code == 422

        # Missing document vector store -> 404
        assert client.post("/api/documents/does_not_exist/search", json={"query": "gas", "top_k": 5}).status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_10_real_tgd9_semantic_search_queries():
    settings = get_settings()
    tgd9_vector_dir = settings.vector_store_path / TGD9_DOCUMENT_ID
    if not (tgd9_vector_dir / "summary.json").is_file():
        pytest.skip("TGD9 Phase 6 vector store is not present in workspace.")

    client = TestClient(app)
    queries = [
        "What are the implementation costs?",
        "What are the mitigation options?",
        "What is casinghead gas?",
    ]

    for query_text in queries:
        resp = client.post(
            f"/api/documents/{TGD9_DOCUMENT_ID}/search",
            json={"query": query_text, "top_k": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == query_text
        assert data["top_k"] == 5
        assert len(data["searched_stores"]) == 9
        assert len(data["results"]) == 5

        scores = [r["score"] for r in data["results"]]
        assert scores == sorted(scores, reverse=True)
        for idx, item in enumerate(data["results"], start=1):
            assert item["rank"] == idx
            assert isinstance(item["score"], float)
            assert item["score"] > 0.0
            assert item["document_id"] == TGD9_DOCUMENT_ID
            assert item["content_type"] in {"text", "table"}
            assert item["chunking_method"]
            assert item["page"] >= 1
            assert item["text"].strip()


def test_11_document_overview_queries_retrieve_introduction():
    assert is_document_overview_query("What is the PDF overall about?") is True
    assert is_document_overview_query("What is the main topic of this document?") is True
    assert is_document_overview_query("Give me an overview of this document.") is True
    assert is_document_overview_query("What is casinghead gas?") is False
    assert is_document_overview_query("Who is the CEO of Microsoft?") is False

    settings = get_settings()
    tgd9_vector_dir = settings.vector_store_path / TGD9_DOCUMENT_ID
    if not (tgd9_vector_dir / "summary.json").is_file():
        pytest.skip("TGD9 Phase 6 vector store is not present in workspace.")

    client = TestClient(app)
    for overview_q in (
        "What is the PDF overall about?",
        "What is the main topic of this document?",
        "Give me an overview of this document.",
    ):
        resp = client.post(
            f"/api/documents/{TGD9_DOCUMENT_ID}/search",
            json={"query": overview_q, "top_k": 5},
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) == 5
        assert any(r["page"] == 1 and "methane" in r["text"].lower() for r in results)
