import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chunks import router as chunks_router
from app.api.documents import router as documents_router
from app.api.embeddings import router as embeddings_router
from app.api.rag import router as rag_router
from app.api.search import router as search_router
from app.core.config import get_settings
from app.core.logging_config import setup_logging

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.pdf_storage_path.mkdir(parents=True, exist_ok=True)
    settings.extracted_storage_path.mkdir(parents=True, exist_ok=True)
    logger.info("Starting %s (env=%s)", settings.app_name, settings.app_env)
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version="0.8.0",
    description="Phase 1-8: PDF ingestion, extraction, classification, 8-method chunking, visualization, FAISS embeddings, semantic search, and Gemini RAG chatbot API.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)
app.include_router(chunks_router)
app.include_router(embeddings_router)
app.include_router(search_router)
app.include_router(rag_router)


@app.get("/api/health", tags=["health"])
def health_check() -> dict:
    """Verify backend service availability."""
    return {"status": "ok", "phase": "Phase 8 - RAG Chatbot with Gemini API"}

