from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env."""

    app_name: str = "Intelligent Document-to-Chatbot Pipeline"
    app_env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    data_pdf_dir: str = "../data/pdfs"
    extracted_data_dir: str = "../extracted_data"
    chunk_outputs_dir: str = "../chunk_outputs"
    vector_store_dir: str = "../vector_store"

    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_batch_size: int = 32

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_fallback_models: str = "gemini-3.7-flash,gemini-3.5-flash,gemini-3.8-flash,gemini-3.6-flash"
    gemini_timeout_seconds: float = 30.0

    min_meaningful_text_chars: int = 40
    min_alpha_chars: int = 15
    ocr_dpi: int = 200
    ocr_engine: str = "auto"
    max_upload_size_mb: int = 50

    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def gemini_fallback_model_list(self) -> List[str]:
        return [
            m.strip()
            for m in self.gemini_fallback_models.split(",")
            if m.strip() and m.strip() != self.gemini_model.strip()
        ]

    @property
    def pdf_storage_path(self) -> Path:
        path = Path(self.data_pdf_dir)
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()

    @property
    def extracted_storage_path(self) -> Path:
        path = Path(self.extracted_data_dir)
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()

    @property
    def chunk_outputs_path(self) -> Path:
        path = Path(self.chunk_outputs_dir)
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()

    @property
    def vector_store_path(self) -> Path:
        path = Path(self.vector_store_dir)
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()

