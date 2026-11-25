import logging
from typing import List, Optional, Sequence

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

logger = logging.getLogger(__name__)

GROUNDING_SYSTEM_INSTRUCTION = (
    "You are a document question-answering assistant.\n"
    "Answer the user's question using ONLY the provided document context.\n"
    "Do not use outside knowledge.\n"
    "Do not invent or guess facts.\n"
    "If the answer cannot be found in the provided document context, clearly state: "
    '"The requested information is not available in the provided document context."\n'
    "When possible, identify the page or source that supports the answer.\n"
    "Keep the answer concise, clear, and easy to understand."
)


class GeminiConfigurationError(Exception):
    """Raised when GEMINI_API_KEY or model configuration is missing or invalid."""


class GeminiServiceError(Exception):
    """Raised when calling the Gemini API fails or returns a malformed/empty response."""


def _sanitize_error_message(message: str, api_key: str) -> str:
    """Ensure raw API keys or credentials are never leaked in error strings or logs."""
    cleaned = message
    if api_key and api_key in cleaned:
        cleaned = cleaned.replace(api_key, "[REDACTED]")
    return cleaned


def build_gemini_prompt(question: str, document_context: str) -> str:
    """Combine retrieved document context with the user's question."""
    return (
        f"{document_context}\n\n"
        f"USER QUESTION:\n{question.strip()}\n\n"
        "Answer using ONLY the provided DOCUMENT CONTEXT above."
    )


def _extract_response_text(response: object) -> Optional[str]:
    """Safely extract generated text from a Gemini response object."""
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    candidates = getattr(response, "candidates", None) or []
    parts_text = []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            part_text = getattr(part, "text", None)
            if isinstance(part_text, str) and part_text.strip():
                parts_text.append(part_text.strip())
    if parts_text:
        return "\n".join(parts_text)
    return None


class _RetryableModelError(GeminiServiceError):
    """Internal marker for model-level quota/503/404 errors that can try a fallback model."""


def _call_single_gemini_model(
    client: genai.Client,
    model_name: str,
    user_prompt: str,
    api_key: str,
    timeout_seconds: float,
) -> str:
    """Call one Gemini model and return extracted answer text."""
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=GROUNDING_SYSTEM_INSTRUCTION,
                temperature=0.1,
            ),
        )
    except genai_errors.APIError as exc:
        status_code = getattr(exc, "code", None)
        safe_msg = _sanitize_error_message(str(exc), api_key)
        logger.warning("Gemini APIError (model=%s, code=%s): %s", model_name, status_code, safe_msg)

        lowered = safe_msg.lower()
        if status_code in (401, 403) or "api key" in lowered or "api_key" in lowered:
            raise GeminiServiceError(
                "Gemini API rejected the configured credentials. Verify your local GEMINI_API_KEY."
            ) from exc
        if status_code == 429 or "rate limit" in lowered or "quota" in lowered or "resource_exhausted" in lowered:
            raise _RetryableModelError(
                "Gemini API rate limit or quota exceeded. Please retry shortly."
            ) from exc
        if status_code == 503 or "unavailable" in lowered or "high demand" in lowered:
            raise _RetryableModelError(
                f"Gemini model '{model_name}' is temporarily unavailable due to high demand. Please retry."
            ) from exc
        if status_code == 404 or "not_found" in lowered:
            raise _RetryableModelError(
                f"Gemini model '{model_name}' is unavailable on this account."
            ) from exc
        raise GeminiServiceError(
            f"Gemini API request failed (status {status_code or 'unknown'})."
        ) from exc
    except TimeoutError as exc:
        logger.warning("Gemini request timed out after %.1fs.", timeout_seconds)
        raise GeminiServiceError("Gemini API request timed out. Please try again.") from exc
    except OSError as exc:
        safe_msg = _sanitize_error_message(str(exc), api_key)
        logger.warning("Gemini network/connection error: %s", safe_msg)
        raise GeminiServiceError(
            "Network error while contacting Gemini API. Check internet connectivity."
        ) from exc
    except Exception as exc:
        safe_msg = _sanitize_error_message(str(exc), api_key)
        logger.warning("Unexpected error calling Gemini API: %s", safe_msg)
        lowered = safe_msg.lower()
        if "timeout" in lowered or "timed out" in lowered:
            raise GeminiServiceError("Gemini API request timed out. Please try again.") from exc
        if "connect" in lowered or "network" in lowered or "dns" in lowered:
            raise GeminiServiceError(
                "Network error while contacting Gemini API. Check internet connectivity."
            ) from exc
        raise GeminiServiceError("Failed to generate an answer from Gemini API.") from exc

    answer_text = _extract_response_text(response)
    if not answer_text:
        raise GeminiServiceError("Gemini API returned an empty or malformed response.")

    return answer_text


def generate_grounded_answer(
    question: str,
    document_context: str,
    api_key: str,
    model_name: str,
    timeout_seconds: float = 30.0,
    fallback_models: Optional[Sequence[str]] = None,
) -> str:
    """Send grounded RAG instructions, retrieved context, and question to Google Gemini."""
    cleaned_key = api_key.strip() if isinstance(api_key, str) else ""
    if not cleaned_key:
        raise GeminiConfigurationError(
            "GEMINI_API_KEY is not configured. Add GEMINI_API_KEY to your local .env file."
        )

    cleaned_model = model_name.strip() if isinstance(model_name, str) else ""
    if not cleaned_model:
        raise GeminiConfigurationError("GEMINI_MODEL is not configured.")

    if not document_context or not document_context.strip():
        raise ValueError("document_context must not be empty when calling Gemini.")

    user_prompt = build_gemini_prompt(question=question, document_context=document_context)
    timeout_ms = max(1000, int(timeout_seconds * 1000))

    candidate_models: List[str] = [cleaned_model]
    if fallback_models:
        for fb in fallback_models:
            cleaned_fb = fb.strip() if isinstance(fb, str) else ""
            if cleaned_fb and cleaned_fb not in candidate_models:
                candidate_models.append(cleaned_fb)

    client = genai.Client(
        api_key=cleaned_key,
        http_options=types.HttpOptions(timeout=timeout_ms),
    )

    last_retryable_exc: Optional[GeminiServiceError] = None
    for idx, candidate in enumerate(candidate_models):
        try:
            answer_text = _call_single_gemini_model(
                client=client,
                model_name=candidate,
                user_prompt=user_prompt,
                api_key=cleaned_key,
                timeout_seconds=timeout_seconds,
            )
            if idx > 0:
                logger.info("Gemini fallback succeeded with model '%s'.", candidate)
            return answer_text
        except _RetryableModelError as exc:
            last_retryable_exc = exc
            continue

    assert last_retryable_exc is not None
    raise last_retryable_exc
