import json
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from app.chunking.storage import save_document_chunks
from app.core.config import Settings, get_settings
from app.embeddings.embedder import (
    embed_texts,
    format_table_for_embedding,
    get_embedding_model,
)
from app.embeddings.pipeline import generate_document_embeddings
from app.main import app
from app.schemas.chunking import (
    ALL_CHUNKING_METHODS,
    ChunkItem,
    ChunkingParameters,
    DocumentChunkingResponse,
    MethodChunkStats,
)
from app.vectorstore.faiss_store import (
    build_and_save_faiss_index,
    load_faiss_index_and_metadata,
)


def _seed_phase4_chunks(settings: Settings, document_id: str = "emb_doc_001") -> None:
    text_chunks = {}
    method_stats = []
    for method in ALL_CHUNKING_METHODS:
        chunks = [
            ChunkItem(
                chunk_id=f"{method}_chunk_001",
                document_id=document_id,
                page=1,
                content_type="text",
                chunking_method=method,
                content="Casinghead gas venting occurs in oil wells with beam pumps.",
                metadata={"section_heading": "Introduction"},
            ),
            ChunkItem(
                chunk_id=f"{method}_chunk_002",
                document_id=document_id,
                page=2,
                content_type="text",
                chunking_method=method,
                content="Vapor recovery units compress and capture casinghead methane gas.",
                metadata={"section_heading": "Mitigation Option A"},
            ),
        ]
        text_chunks[method] = chunks
        method_stats.append(
            MethodChunkStats(
                method=method,
                label=method,
                chunk_count=len(chunks),
                avg_chunk_length=60.0,
                min_chunk_length=55,
                max_chunk_length=65,
                total_characters=120,
                total_words=18,
            )
        )

    table_chunk = ChunkItem(
        chunk_id="table_chunk_001",
        document_id=document_id,
        page=2,
        content_type="table",
        chunking_method="table_structured",
        content="Table table_0001 (Page 2)",
        metadata={
            "table_id": "table_0001",
            "headers": ["Configuration", "Mitigated or Unmitigated"],
            "rows": [["Direct vent", "Unmitigated"], ["VRU Option A", "Mitigated"]],
        },
    )

    image_chunk = ChunkItem(
        chunk_id="image_chunk_001",
        document_id=document_id,
        page=9,
        content_type="image",
        chunking_method="image_metadata",
        content="Image image_0010 (Page 9)",
        metadata={
            "image_id": "image_0010",
            "image_path": f"images/{document_id}/page_009_img_0010.jpeg",
        },
    )

    chunk_resp = DocumentChunkingResponse(
        document_id=document_id,
        document_name="sample_tgd9.pdf",
        total_pages=2,
        created_at="2026-11-25T12:00:00Z",
        parameters=ChunkingParameters(),
        method_stats=method_stats,
        table_chunks_count=1,
        image_chunks_count=1,
        warnings=[],
        text_chunks=text_chunks,
        table_chunks=[table_chunk],
        image_chunks=[image_chunk],
    )
    save_document_chunks(settings.chunk_outputs_path, chunk_resp)


def test_embedding_model_and_empty_handling():
    model = get_embedding_model("sentence-transformers/all-MiniLM-L6-v2")
    assert model is not None

    vectors, dim = embed_texts(
        [
            "Natural gas vapor recovery reduces methane venting.",
            "Casinghead gas is routed to a flare.",
        ]
    )
    assert dim > 0
    assert vectors.shape == (2, dim)
    assert np.issubdtype(vectors.dtype, np.floating)
    assert np.all(np.isfinite(vectors))
    norms = np.linalg.norm(vectors, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-4)

    empty_vecs, empty_dim = embed_texts(["", "   \n "])
    assert empty_vecs.shape == (0, dim)
    assert empty_dim == dim


def test_table_formatting_and_faiss_save_load(tmp_path: Path):
    table_chunk = ChunkItem(
        chunk_id="table_chunk_001",
        document_id="doc_tbl",
        page=6,
        content_type="table",
        chunking_method="table_structured",
        content="raw",
        metadata={
            "table_id": "table_0002",
            "headers": ["Project Component", "Implementation Costs", "Annual Costs"],
            "rows": [["Capital CostA", "$12,500", "–"]],
        },
    )
    table_text = format_table_for_embedding(table_chunk)
    assert "Table: table_0002" in table_text
    assert "Project Component | Implementation Costs | Annual Costs" in table_text
    assert "Capital CostA | $12,500 | –" in table_text

    vectors, dim = embed_texts([table_text])
    assert vectors.shape == (1, dim)

    from app.schemas.embeddings import VectorMetadataItem

    meta = [
        VectorMetadataItem(
            vector_index=0,
            embedding_id="emb_table_chunk_001",
            chunk_id="table_chunk_001",
            document_id="doc_tbl",
            content_type="table",
            chunking_method="table",
            page=6,
            text=table_text,
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            embedding_dimension=dim,
        )
    ]

    idx_dir = tmp_path / "faiss_tbl"
    idx_path, meta_path = build_and_save_faiss_index(vectors, meta, idx_dir)
    assert idx_path.is_file()
    assert meta_path.is_file()

    loaded_index, loaded_meta = load_faiss_index_and_metadata(idx_dir)
    assert loaded_index.ntotal == 1
    assert len(loaded_meta) == 1
    assert loaded_meta[0].chunk_id == "table_chunk_001"


def test_generate_document_embeddings_pipeline_and_api(tmp_path: Path):
    settings = Settings(
        data_pdf_dir=str(tmp_path / "pdfs"),
        extracted_data_dir=str(tmp_path / "extracted"),
        chunk_outputs_dir=str(tmp_path / "chunks"),
        vector_store_dir=str(tmp_path / "vectors"),
        embedding_batch_size=4,
    )
    _seed_phase4_chunks(settings, "emb_doc_001")

    summary = generate_document_embeddings("emb_doc_001", settings)
    assert summary.methods_processed == 8
    assert summary.text_vectors == 16
    assert summary.table_vectors == 1
    assert summary.image_vectors == 0
    assert summary.total_vectors == 17
    assert summary.dimension > 0

    all_embedding_ids: list[str] = []
    for method in ALL_CHUNKING_METHODS:
        idx, meta = load_faiss_index_and_metadata(settings.vector_store_path / "emb_doc_001" / method)
        assert idx.ntotal == len(meta) == 2
        all_embedding_ids.extend(m.embedding_id for m in meta)

    tbl_idx, tbl_meta = load_faiss_index_and_metadata(settings.vector_store_path / "emb_doc_001" / "tables")
    assert tbl_idx.ntotal == len(tbl_meta) == 1
    all_embedding_ids.extend(m.embedding_id for m in tbl_meta)

    assert len(all_embedding_ids) == len(set(all_embedding_ids))

    img_meta_file = settings.vector_store_path / "emb_doc_001" / "images" / "metadata.json"
    assert img_meta_file.is_file()
    img_payload = json.loads(img_meta_file.read_text(encoding="utf-8"))
    assert img_payload["image_vectors"] == 0
    assert "Not implemented in Phase 6" in img_payload["image_embeddings_status"]

    # Verify API endpoints
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    try:
        gen_res = client.post("/api/documents/emb_doc_001/embeddings/generate")
        assert gen_res.status_code == 200
        assert gen_res.json()["total_vectors"] == 17

        sum_res = client.get("/api/documents/emb_doc_001/embeddings/summary")
        assert sum_res.status_code == 200
        assert sum_res.json()["methods_processed"] == 8

        missing_res = client.get("/api/documents/missing_doc_xyz/embeddings/summary")
        assert missing_res.status_code == 404
    finally:
        app.dependency_overrides.clear()
