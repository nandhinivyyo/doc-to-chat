from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from google.genai import errors as genai_errors
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.main import app
from app.schemas.rag import RagChatRequest
from app.schemas.search import SemanticSearchResponse, SemanticSearchResult
from app.services.context_builder import (
    build_document_context,
    extract_source_references,
)
from app.services.gemini_service import (
    GROUNDING_SYSTEM_INSTRUCTION,
    GeminiConfigurationError,
    GeminiServiceError,
    generate_grounded_answer,
)
from app.services.rag_service import (
    NO_RELEVANT_CONTEXT_MESSAGE,
    answer_document_question,
)


def _sample_search_results() -> list[SemanticSearchResult]:
    return [
        SemanticSearchResult(
            rank=1,
            score=0.5255,
            chunk_id="table_chunk_002",
            document_id="doc_test_123",
            content_type="table",
            chunking_method="table",
            page=6,
            section_heading=None,
            text=(
                "Table: table_0002\nHeaders:\nProject Component | Implementation Costs | Annual Costs\n"
                "Rows:\nCapital CostA | $12,500 | –\nInstallation CostsB | $18,750 | –\nTotal | $31,250 | -$97,450"
            ),
        ),
        SemanticSearchResult(
            rank=2,
            score=0.4874,
            chunk_id="fixed_size_chunk_032",
            document_id="doc_test_123",
            content_type="text",
            chunking_method="fixed_size",
            page=5,
            section_heading="Mitigation Option A",
            text="Major costs include compressor package/VRU equipment costs and installation costs.",
        ),
    ]


def test_1_request_validation():
    default_req = RagChatRequest(query="What are the implementation costs?")
    assert default_req.top_k == 5

    for invalid_q in ("", "   \n\t  "):
        with pytest.raises(ValidationError):
            RagChatRequest(query=invalid_q)

    for invalid_k in (0, -2, 21, 100):
        with pytest.raises(ValidationError):
            RagChatRequest(query="valid question", top_k=invalid_k)

    client = TestClient(app)
    assert client.post("/api/documents/any_doc/chat", json={"query": "", "top_k": 5}).status_code == 422
    assert client.post("/api/documents/any_doc/chat", json={"query": "   ", "top_k": 5}).status_code == 422
    assert client.post("/api/documents/any_doc/chat", json={"query": "costs?", "top_k": 0}).status_code == 422
    assert client.post("/api/documents/any_doc/chat", json={"query": "costs?", "top_k": 25}).status_code == 422


def test_2_semantic_search_integration():
    fake_results = _sample_search_results()
    fake_search_resp = SemanticSearchResponse(
        query="What are the implementation costs?",
        top_k=5,
        document_id="doc_test_123",
        chunking_method=None,
        model="sentence-transformers/all-MiniLM-L6-v2",
        searched_stores=["fixed_size", "tables"],
        total_candidates=2,
        results=fake_results,
    )
    settings = Settings(gemini_api_key="fake-unit-key", gemini_model="gemini-3.6-flash")

    with (
        patch("app.services.rag_service.search_document", return_value=fake_search_resp) as mock_search,
        patch("app.services.rag_service.generate_grounded_answer", return_value="Total cost is $31,250 (Page 6).") as mock_gemini,
    ):
        resp = answer_document_question(
            document_id="doc_test_123",
            request=RagChatRequest(query="What are the implementation costs?", top_k=5),
            settings=settings,
        )

    mock_search.assert_called_once()
    call_kwargs = mock_search.call_args.kwargs
    assert call_kwargs["document_id"] == "doc_test_123"
    assert call_kwargs["request"].query == "What are the implementation costs?"
    assert call_kwargs["request"].top_k == 5
    mock_gemini.assert_called_once()
    assert resp.retrieved_chunks == 2


def test_3_context_construction():
    results = _sample_search_results()
    context = build_document_context(results)

    assert context.startswith("DOCUMENT CONTEXT")
    assert "SOURCE 1" in context
    assert "Page: 6" in context
    assert "Content Type: Table" in context
    assert "Chunk ID: table_chunk_002" in context
    assert "Capital CostA | $12,500" in context

    assert "SOURCE 2" in context
    assert "Page: 5" in context
    assert "Content Type: Text" in context
    assert "Section: Mitigation Option A" in context

    assert build_document_context([]) == ""


def test_4_gemini_request_contains_question_context_and_grounding():
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = SimpleNamespace(
        text="Capital cost is $12,500 (Page 6)."
    )

    with patch("app.services.gemini_service.genai.Client", return_value=mock_client) as mock_ctor:
        answer = generate_grounded_answer(
            question="What is the capital cost?",
            document_context="DOCUMENT CONTEXT\nSOURCE 1\nCapital Cost: $12,500",
            api_key="unit-test-fake-key",
            model_name="gemini-3.6-flash",
            timeout_seconds=15.0,
        )

    mock_ctor.assert_called_once()
    assert answer == "Capital cost is $12,500 (Page 6)."

    gen_call = mock_client.models.generate_content.call_args.kwargs
    assert gen_call["model"] == "gemini-3.6-flash"
    assert "What is the capital cost?" in gen_call["contents"]
    assert "Capital Cost: $12,500" in gen_call["contents"]
    assert gen_call["config"].system_instruction == GROUNDING_SYSTEM_INSTRUCTION


def test_5_and_6_gemini_response_and_source_preservation_api():
    fake_results = _sample_search_results()
    fake_search_resp = SemanticSearchResponse(
        query="What are the implementation costs?",
        top_k=5,
        document_id="doc_test_123",
        chunking_method=None,
        model="sentence-transformers/all-MiniLM-L6-v2",
        searched_stores=["fixed_size", "tables"],
        total_candidates=2,
        results=fake_results,
    )
    settings = Settings(gemini_api_key="unit-test-fake-key", gemini_model="gemini-3.6-flash")
    app.dependency_overrides[get_settings] = lambda: settings

    try:
        with (
            patch("app.services.rag_service.search_document", return_value=fake_search_resp),
            patch(
                "app.services.rag_service.generate_grounded_answer",
                return_value="Total implementation cost is $31,250 (Page 6).",
            ),
        ):
            client = TestClient(app)
            http_resp = client.post(
                "/api/documents/doc_test_123/chat",
                json={"query": "What are the implementation costs?", "top_k": 5},
            )

        assert http_resp.status_code == 200
        body = http_resp.json()
        assert body["query"] == "What are the implementation costs?"
        assert body["answer"] == "Total implementation cost is $31,250 (Page 6)."
        assert body["retrieved_chunks"] == 2
        assert body["model"] == "gemini-3.6-flash"
        assert len(body["sources"]) == 2
        assert body["sources"][0] == {
            "rank": 1,
            "score": 0.5255,
            "page": 6,
            "chunk_id": "table_chunk_002",
            "content_type": "table",
            "chunking_method": "table",
            "section_heading": None,
        }
        assert body["sources"][1]["page"] == 5
        assert body["sources"][1]["chunk_id"] == "fixed_size_chunk_032"
        assert body["sources"][1]["content_type"] == "text"
        assert body["sources"][1]["chunking_method"] == "fixed_size"

        # Also verify helper directly
        refs = extract_source_references(fake_results)
        assert len(refs) == 2
        assert refs[0].chunk_id == "table_chunk_002"
    finally:
        app.dependency_overrides.clear()


def test_7_no_results_skips_gemini():
    empty_search = SemanticSearchResponse(
        query="Anything?",
        top_k=5,
        document_id="doc_empty",
        chunking_method=None,
        model="sentence-transformers/all-MiniLM-L6-v2",
        searched_stores=["fixed_size"],
        total_candidates=0,
        results=[],
    )
    settings = Settings(gemini_api_key="unit-test-fake-key", gemini_model="gemini-3.6-flash")

    with (
        patch("app.services.rag_service.search_document", return_value=empty_search),
        patch("app.services.rag_service.generate_grounded_answer") as mock_gemini,
    ):
        resp = answer_document_question(
            document_id="doc_empty",
            request=RagChatRequest(query="Anything?", top_k=5),
            settings=settings,
        )

    mock_gemini.assert_not_called()
    assert resp.answer == NO_RELEVANT_CONTEXT_MESSAGE
    assert resp.sources == []
    assert resp.retrieved_chunks == 0


def test_8_missing_api_key_returns_clear_configuration_error():
    with pytest.raises(GeminiConfigurationError, match="GEMINI_API_KEY is not configured"):
        generate_grounded_answer(
            question="What are the costs?",
            document_context="DOCUMENT CONTEXT\nSOURCE 1\nCost: $10",
            api_key="   ",
            model_name="gemini-3.6-flash",
        )

    fake_search = SemanticSearchResponse(
        query="What are the costs?",
        top_k=5,
        document_id="doc_no_key",
        chunking_method=None,
        model="sentence-transformers/all-MiniLM-L6-v2",
        searched_stores=["tables"],
        total_candidates=1,
        results=_sample_search_results()[:1],
    )
    no_key_settings = Settings(gemini_api_key="", gemini_model="gemini-3.6-flash")
    app.dependency_overrides[get_settings] = lambda: no_key_settings

    try:
        with patch("app.services.rag_service.search_document", return_value=fake_search):
            client = TestClient(app)
            resp = client.post(
                "/api/documents/doc_no_key/chat",
                json={"query": "What are the costs?", "top_k": 5},
            )
        assert resp.status_code == 503
        assert "GEMINI_API_KEY" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_9_gemini_failures_and_secret_redaction():
    secret = "fake-secret-key-should-never-leak"

    # 1. Invalid key / APIError
    mock_client_auth = MagicMock()
    mock_client_auth.models.generate_content.side_effect = genai_errors.APIError(
        401, {"error": {"message": f"Invalid API key {secret}", "status": "UNAUTHENTICATED"}}
    )
    with patch("app.services.gemini_service.genai.Client", return_value=mock_client_auth):
        with pytest.raises(GeminiServiceError) as exc_info:
            generate_grounded_answer("q?", "ctx", secret, "gemini-3.6-flash")
        assert secret not in str(exc_info.value)

    # 2. Rate limit / 429
    mock_client_rate = MagicMock()
    mock_client_rate.models.generate_content.side_effect = genai_errors.APIError(
        429, {"error": {"message": "Rate limit exceeded", "status": "RESOURCE_EXHAUSTED"}}
    )
    with patch("app.services.gemini_service.genai.Client", return_value=mock_client_rate):
        with pytest.raises(GeminiServiceError, match="rate limit"):
            generate_grounded_answer("q?", "ctx", secret, "gemini-3.6-flash")

    # 3. Timeout
    mock_client_timeout = MagicMock()
    mock_client_timeout.models.generate_content.side_effect = TimeoutError("timed out")
    with patch("app.services.gemini_service.genai.Client", return_value=mock_client_timeout):
        with pytest.raises(GeminiServiceError, match="timed out"):
            generate_grounded_answer("q?", "ctx", secret, "gemini-3.6-flash")

    # 4. Network error
    mock_client_net = MagicMock()
    mock_client_net.models.generate_content.side_effect = OSError("DNS lookup failed")
    with patch("app.services.gemini_service.genai.Client", return_value=mock_client_net):
        with pytest.raises(GeminiServiceError, match="Network error"):
            generate_grounded_answer("q?", "ctx", secret, "gemini-3.6-flash")

    # 5. Malformed / empty Gemini response
    mock_client_empty = MagicMock()
    mock_client_empty.models.generate_content.return_value = SimpleNamespace(text="", candidates=[])
    with patch("app.services.gemini_service.genai.Client", return_value=mock_client_empty):
        with pytest.raises(GeminiServiceError, match="empty or malformed"):
            generate_grounded_answer("q?", "ctx", secret, "gemini-3.6-flash")


def test_10_out_of_document_question_grounding():
    fake_search = SemanticSearchResponse(
        query="Who is the president of France?",
        top_k=5,
        document_id="doc_test_123",
        chunking_method=None,
        model="sentence-transformers/all-MiniLM-L6-v2",
        searched_stores=["fixed_size"],
        total_candidates=1,
        results=_sample_search_results()[1:],
    )
    grounded_refusal = "The requested information is not available in the provided document context."
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = SimpleNamespace(text=grounded_refusal)
    settings = Settings(gemini_api_key="unit-test-fake-key", gemini_model="gemini-3.6-flash")

    with (
        patch("app.services.rag_service.search_document", return_value=fake_search),
        patch("app.services.gemini_service.genai.Client", return_value=mock_client),
    ):
        resp = answer_document_question(
            document_id="doc_test_123",
            request=RagChatRequest(query="Who is the president of France?", top_k=5),
            settings=settings,
        )

    assert "not available in the provided document context" in resp.answer.lower()
    gen_call = mock_client.models.generate_content.call_args.kwargs
    assert "ONLY the provided document context" in gen_call["config"].system_instruction
    assert resp.retrieved_chunks == 1
