# Intelligent Document-to-Chatbot Pipeline with Visualization

An end-to-end research and engineering application for comparing chunking methodologies on technical PDF documents, visualizing extracted content and chunk distributions, and powering a source-grounded RAG chatbot.

> **Current Stage:** **Phase 1 & Phase 2** (Project Scaffolding, PDF Ingestion & Multimodal Content Extraction)

---

## Project Architecture (Phase 1 & 2)

```text
intelligent-document-chatbot/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI endpoints (/api/documents/*, /api/health)
│   │   ├── core/           # Configuration (pydantic-settings) and structured logging
│   │   ├── extraction/     # PyMuPDF text/table/image extractors, pdfplumber fallback, OCR
│   │   ├── schemas/        # Pydantic v2 data models
│   │   └── main.py         # FastAPI entry point
│   ├── tests/              # Unit and API integration tests (pytest)
│   ├── requirements.txt
│   └── .env.example
├── frontend/               # React + TypeScript + Tailwind CSS + Recharts UI
├── data/pdfs/              # Uploaded PDF storage
└── extracted_data/         # Structured JSON & image outputs (text, tables, images, metadata)
```

---

## Prerequisites

- **Python** 3.11+ (tested with Python 3.13)
- **Node.js** 18+ and **npm** 9+
- **Optional:** Tesseract OCR binary if you prefer `OCR_ENGINE=tesseract` (by default `OCR_ENGINE=auto` automatically uses `rapidocr` if Tesseract is not installed on PATH).

---

## Setup & Running Locally

### 1. Backend Setup (FastAPI)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Start the backend API server:

```powershell
cd backend
.\.venv\Scripts\uvicorn.exe app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs are available at `http://localhost:8000/docs`.

### 2. Frontend Setup (React + TypeScript + Vite)

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser. Vite proxies `/api/*` requests to `http://localhost:8000`.

---

## Running Tests

```powershell
cd backend
.\.venv\Scripts\pytest.exe -v
```

---

## Phase 2 API Endpoints

- `GET /api/health` — Backend health check
- `GET /api/documents` — List processed documents
- `POST /api/documents/upload` — Upload a single PDF and execute multimodal extraction
- `GET /api/documents/{document_id}` — Fetch document-level extraction summary
- `GET /api/documents/{document_id}/extraction` — Fetch extracted text, tables, images, and per-page metadata
- `GET /api/documents/{document_id}/images/{file_name}` — Retrieve an extracted image asset

---

## Extracted Output Structure

```text
extracted_data/
├── text/<document_id>.json
├── tables/<document_id>.json
├── images/
│   ├── <document_id>.json
│   └── <document_id>/page_001_img_0001.png
└── metadata/<document_id>.json
```

