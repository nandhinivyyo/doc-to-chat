# Intelligent Document-to-Chatbot Pipeline — Technical Documentation

**Use Case 5:** Intelligent Document-to-Chatbot Pipeline with Visualization  
**Document Scope:** Phases 1, 2, 3, 4, 5, 6, 7, and 8 (Implemented & Verified)  
**Repository Root:** `intelligent-document-chatbot` (`c:\HCL\USECASE`)

---

## 1. Project Overview

### Project Title
**INTELLIGENT DOCUMENT-TO-CHATBOT PIPELINE**

### Use Case
**Use Case 5: Intelligent Document-to-Chatbot Pipeline with Visualization**

### Problem Statement
Technical PDF documents (such as engineering standards and environmental compliance guidance) contain mixed content: multi-column or sectioned prose, structured tables, embedded technical photographs/diagrams, running headers/footers, and occasional scanned pages. Naive text-only PDF extraction often flattens tables into broken text, repeats boilerplate headers/logos on every page, and loses document structure and source traceability—degrading downstream chunking and Retrieval-Augmented Generation (RAG) answer quality.

### Objective
Build a modular, full-stack document intelligence pipeline that:
1. Ingests technical PDF documents with validation and structured logging.
2. Extracts multimodal content (**Text**, **Tables**, **Images**, plus **OCR fallback** when native text is missing/insufficient).
3. Cleans and classifies extracted content into an auditable intermediate representation without losing raw extraction data.
4. *(Future phases)* Applies and visualizes 8 chunking strategies, evaluates chunk quality, generates embeddings, indexes them into FAISS, and powers a source-grounded RAG chatbot.

### Expected Final System
The intended end-to-end system will allow a user to upload technical PDFs, compare 8 chunking strategies visually across text/table/image chunks, inspect chunk-quality metrics, and ask technical questions answered with page- and document-level citations.

### Current Implementation Status
**Phases 1, 2, 3, 4, 5, 6, 7, and 8 are currently implemented and verified.**

- **Phase 4 — Chunking Methods:** **COMPLETED**
- **Phase 5 — Chunk Visualization:** **COMPLETED**
- **Phase 6 — Embeddings & Vector Storage:** **COMPLETED**
- **Phase 7 — Semantic Search:** **COMPLETED**
- **Phase 8 — RAG Chatbot with Gemini API:** **COMPLETED**

### Overall Pipeline

```text
PDF
 ↓
PyMuPDF / pdfplumber             [IMPLEMENTED - Phase 1 & 2]
 ↓
Classification & Cleanup         [IMPLEMENTED & AUDITED - Phase 3]
 ↓
8 Chunking Methods + Tbl/Img     [IMPLEMENTED - Phase 4 & 5 Visualization]
 ↓
Sentence Transformer (384-dim)   [IMPLEMENTED - Phase 6]
 ↓
FAISS Vector Storage (IndexFlatIP) [IMPLEMENTED - Phase 6]
 ↓
Semantic Search (Top-K Chunks)   [IMPLEMENTED - Phase 7]
 ↓
Gemini API (Grounded RAG Answer) [IMPLEMENTED - Phase 8]
```

---

## 2. Dataset / Source

### Official Source
- **Climate and Clean Air Coalition (CCAC) — Oil and Gas Methane Partnership (OGMP) Technical Guidance Documents**

### Verified Test PDF
- **Filename:** `2017_OGMP-TGD9-Casinghead-venting_CCAC.pdf` (556,350 bytes)
- **Document Title:** *CCAC OGMP – Technical Guidance Document Number 9: Casinghead Gas Venting (Modified: November 2015)*

### Verified Document Characteristics
- **Total Pages:** 10 (`612.0 × 792.0 pt` per page)
- **Content Profile:** Technical prose, footnotes, bulleted operational procedures, 2 bordered tables, and 15 embedded images (10 repeated CCAC header logos + 5 exhibit photographs)
- **Text Layer:** Native PDF text available on all 10 pages
- **OCR Fallback:** Not required (`ocr_used: false`, `ocr_pages: []`)

### Why This Document Is Suitable for Testing
`2017_OGMP-TGD9-Casinghead-venting_CCAC.pdf` exercises every extraction and cleanup edge case in a single compact PDF:
- Structured multi-column technical tables alongside surrounding captions and footnotes.
- Repeated top-margin banners, bottom-margin page numbers (`Page X of 10`), and repeated header logos across all 10 pages.
- Meaningful technical field photographs (Exhibits A, B, and C) on pages 9–10.
- Multi-level bold section headings mixed within single PyMuPDF text blocks.

---

## 3. System Architecture

### Implemented Architecture Flow (Phases 1–3)

```text
Frontend (React + TypeScript + Tailwind CSS + Recharts via Vite)
   │   HTTP /api/* (Vite dev proxy -> http://127.0.0.1:8000)
   ▼
Backend API (FastAPI + Uvicorn)
   │
   ├──► PDF Processing & Validation (backend/app/api/documents.py)
   │       │
   │       ▼
   ├──► Raw Extraction (backend/app/extraction/pdf_extractor.py)
   │       ├── Text Extractor (PyMuPDF dict + heading detection)
   │       ├── Table Extractor (PyMuPDF find_tables + pdfplumber fallback)
   │       ├── Image Extractor (PyMuPDF extract_image + Pillow verify)
   │       └── OCR Processor (PyMuPDF render -> RapidOCR / Tesseract fallback)
   │       │
   │       ▼  persisted to extracted_data/{metadata,text,tables,images}/
   │
   └──► Classification & Cleanup (backend/app/classification/classifier.py)
           ├── Table Refiner (PyMuPDF vs pdfplumber quality scoring)
           ├── Table-Text Deduplicator (bbox overlap + cell-text match)
           ├── Boilerplate Detector (cross-page header/footer/page-num flags)
           └── Image Classifier (SHA-256 occurrence + margin logo flags)
           │
           ▼  persisted to extracted_data/classified/
   Structured Classified Data (TEXT / TABLE / IMAGE)
```

### Role of Frontend and Backend
- **Frontend (`frontend/`):** Provides PDF drag-and-drop/file upload, document selector, upload status/error feedback, summary metric cards, a `Classified & Cleaned (Phase 3)` vs `Raw Extraction (Phase 2)` view toggle, per-page content distribution bar chart (Recharts), and tabbed previews for Text, Tables (HTML table + Markdown toggle), Images, and Removed Duplicates.
- **Backend (`backend/`):** Handles file validation, PDF persistence, multimodal extraction, raw JSON/image storage, Phase 3 classification/cleanup, and REST API endpoints via FastAPI.

### Verified API Endpoints
The following endpoints are implemented in `backend/app/main.py`, `backend/app/api/documents.py`, and `backend/app/api/chunks.py`:

| Method | Endpoint | Purpose | Status Codes |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | Service health check (`status`, `phase`) | `200` |
| `GET` | `/api/documents` | List all processed documents (`DocumentListResponse`) | `200` |
| `POST` | `/api/documents/upload` | Upload single `.pdf`, run Phase 2 extraction + Phase 3 classification | `201`, `400`, `413`, `422` |
| `GET` | `/api/documents/{document_id}` | Retrieve document-level summary (`DocumentSummary`) | `200`, `404` |
| `GET` | `/api/documents/{document_id}/extraction` | Retrieve raw Phase 2 extraction payload (`DocumentExtractionResponse`) | `200`, `404` |
| `GET` | `/api/documents/{document_id}/images/{file_name}` | Serve extracted PNG/JPEG image with path-traversal protection | `200`, `400`, `404` |
| `POST` | `/api/documents/{document_id}/classify` | Run or re-run Phase 3 classification & cleanup (`ClassifiedDocumentResponse`) | `200`, `404` |
| `GET` | `/api/documents/{document_id}/classification` | Retrieve Phase 3 classified data (computes on demand if missing) | `200`, `404` |
| `POST` | `/api/documents/{document_id}/chunk` | Run Phase 4 chunking with default or custom `ChunkingParameters` | `200`, `400`, `404` |
| `GET` | `/api/documents/{document_id}/chunks` | Retrieve all 8 text chunk sets, table/image chunks, and statistics | `200`, `404` |
| `GET` | `/api/documents/{document_id}/chunks/summary` | Read-only summary & 8-method statistics (`ChunkSummaryResponse`) | `200`, `404` |
| `GET` | `/api/documents/{document_id}/chunks/tables` | Read-only structured table chunks (`TableChunksResponse`) | `200`, `404` |
| `GET` | `/api/documents/{document_id}/chunks/images` | Read-only non-decorative image chunks (`ImageChunksResponse`) | `200`, `404` |
| `GET` | `/api/documents/{document_id}/chunks/{method}` | Retrieve chunks and statistics for one specific text chunking method | `200`, `400`, `404` |
| `POST` | `/api/documents/{document_id}/embeddings/generate` | Generate batched embeddings & persist FAISS indexes + metadata | `200`, `400`, `404` |
| `GET` | `/api/documents/{document_id}/embeddings/summary` | Retrieve Phase 6 embedding model, dimensions, and vector counts | `200`, `404` |
| `POST` | `/api/documents/{document_id}/search` | Embed query and run FAISS cosine similarity search across vector stores | `200`, `400`, `404`, `422` |
| `POST` | `/api/documents/{document_id}/chat` | Run Phase 7 retrieval + Context Builder + Google Gemini grounded RAG | `200`, `400`, `404`, `422`, `502`, `503` |

---

## 4. Phase 1 — Project Foundation

### Project Structure & Configuration
- **Settings (`backend/app/core/config.py`):** Uses `pydantic_settings.BaseSettings` to load configuration from `backend/.env` (template in `backend/.env.example`), resolving `data_pdf_dir` (`../data/pdfs`) and `extracted_data_dir` (`../extracted_data`) relative to the backend directory without hardcoded absolute paths.
- **Logging (`backend/app/core/logging_config.py`):** Configures structured console logging (`[LEVEL] YYYY-MM-DD HH:MM:SS | logger | message`).
- **Frontend Setup (`frontend/`):** Configured with Vite (`vite.config.ts` proxying `/api` to `http://127.0.0.1:8000`), TypeScript (`tsconfig.app.json` with strict mode enabled), Tailwind CSS (`tailwind.config.js`, `postcss.config.js`), and Recharts (`recharts`).

### Upload, Validation, Identification & Error Handling (`backend/app/api/documents.py`)
- **Filename Sanitization:** Strips directory components and restricts characters via `_sanitize_filename`.
- **Extension & Header Validation:** Rejects non-`.pdf` files (`400`), 0-byte uploads (`400`), files exceeding `max_upload_size_mb` (`50 MB`, returning `413`), and files lacking the `%PDF-` magic header (`400`).
- **Document Identification:** Assigns a unique `document_id` formatted as `<sanitized_stem[:40]>_<8-hex-uuid>` (e.g., `2017_OGMP-TGD9-Casinghead-venting_CCAC_a048498a`).
- **Error Handling:** Raises `PDFExtractionError` (`422`) on unreadable, empty, 0-page, corrupted, or password-protected PDFs and removes failed temporary PDF uploads. Per-page table/image/OCR failures are logged with document and page context and recorded in `errors` without crashing the document pipeline.
- **Health Check:** `GET /api/health` returns `{"status": "ok", "phase": "Phase 3 - Content Classification & Cleanup"}`.

---

## 5. Phase 2 — PDF Ingestion & Extraction

Implemented in `backend/app/extraction/`:

1. **PDF Reading (`pdf_extractor.py`):** Opens the uploaded PDF with PyMuPDF (`pymupdf.open`), verifies it is not password-protected and has `> 0` pages, and also opens a `pdfplumber` handle for table fallback.
2. **Text Extraction (`text_extractor.py`):** Extracts text blocks via `page.get_text("dict")`, preserving bounding boxes (`bbox`), character counts, and `section_heading`. Splits blocks when standalone bold/large-font heading lines occur inside multi-line blocks.
3. **Table Extraction (`table_extractor.py`):** Uses PyMuPDF `page.find_tables()` as primary detector; if PyMuPDF fails or yields 0 valid tables on a page, falls back to `pdfplumber` (`plumber_page.extract_tables()`). Filters single-cell/decorative boxes via `is_valid_table` (requires `>= 2` rows, `>= 2` columns, `>= 3` non-empty cells) and generates a Markdown table representation (`table_to_markdown`).
4. **Image Extraction (`image_extractor.py`):** Iterates `page.get_images(full=True)` (deduplicating `xref` per page), extracts image bytes, validates integrity with Pillow (`Image.open(...).verify()`), skips degenerate `< 16×16` px artifacts, converts exotic color modes (`CMYK`, `P`, `LA`) to web-safe PNG or JPEG, records bounding boxes (`page.get_image_rects(xref)`), and exposes `/api/documents/{document_id}/images/{file_name}`.
5. **OCR Fallback (`ocr_processor.py`):** Normal PDF text extraction is attempted first on every page. `assess_text_meaningfulness` checks if extracted text meets thresholds (`min_meaningful_text_chars=40`, `min_alpha_chars=15`). Only when native text is missing or insufficient does `ocr_pdf_page` render the page at `ocr_dpi=200` and run OCR (`auto` uses Tesseract if installed, otherwise `rapidocr`).
6. **Page Metadata & Status:** Records per-page dimensions, counts, `ocr_used`, `ocr_reason`, `char_count`, and `errors`, producing `DocumentSummary` (`status`: `completed`, `completed_with_warnings`, or `failed`).

### Verified TGD9 Raw Extraction Result
- **Pages:** `10`
- **Raw text blocks:** `78` *(after the section-heading line-split refinement; initial Phase 2 run before splitting had `69`)*
- **Tables:** `2`
- **Images:** `15`
- **OCR fallback:** Not needed (`ocr_used: false`, `ocr_pages: []`)

---

## 6. Raw Extraction Storage

Verified directory layout under `extracted_data/`:

```text
extracted_data/
├── metadata/
│   └── <document_id>.json          # DocumentSummary + list of PageMetadata
├── text/
│   └── <document_id>.json          # List of raw TextItem objects
├── tables/
│   └── <document_id>.json          # List of raw TableItem objects
├── images/
│   ├── <document_id>.json          # List of ImageItem metadata objects
│   └── <document_id>/
│       └── page_XXX_img_YYYY.{png|jpeg}  # Validated extracted image files
└── classified/                     # Added in Phase 3
    └── <document_id>.json          # ClassifiedDocumentResponse
```

Verified files on disk for the audited TGD9 document ID `2017_OGMP-TGD9-Casinghead-venting_CCAC_a048498a`:
- `extracted_data/metadata/2017_OGMP-TGD9-Casinghead-venting_CCAC_a048498a.json`
- `extracted_data/text/2017_OGMP-TGD9-Casinghead-venting_CCAC_a048498a.json`
- `extracted_data/tables/2017_OGMP-TGD9-Casinghead-venting_CCAC_a048498a.json`
- `extracted_data/images/2017_OGMP-TGD9-Casinghead-venting_CCAC_a048498a.json`
- `extracted_data/images/2017_OGMP-TGD9-Casinghead-venting_CCAC_a048498a/page_001_img_0001.png` ... `page_010_img_0015.jpeg` (15 image files)
- `extracted_data/classified/2017_OGMP-TGD9-Casinghead-venting_CCAC_a048498a.json`

---

## 7. Phase 2 Validation

Before Phase 3 was built, the Phase 1 & Phase 2 suite passed **6 passed, 0 failed**:

| Test File | Test Name | What Was Verified |
| :--- | :--- | :--- |
| `backend/tests/test_api.py` | `test_api_upload_and_retrieval_flow` | `GET /api/health`, `POST /api/documents/upload`, `GET /api/documents/{id}`, `GET /api/documents/{id}/extraction`, `GET /api/documents` |
| `backend/tests/test_api.py` | `test_api_error_handling` | Non-PDF extension rejection (`400`), invalid `%PDF-` header rejection (`400`), missing document (`404`) |
| `backend/tests/test_extraction.py` | `test_assess_text_meaningfulness` | Meaningful text vs empty/short text OCR trigger logic |
| `backend/tests/test_extraction.py` | `test_table_helpers` | `clean_table_rows`, `is_valid_table`, `table_to_markdown` |
| `backend/tests/test_extraction.py` | `test_extract_pdf_document_full_pipeline` | End-to-end 2-page PDF extraction: native text + table + PNG image on page 1, RapidOCR fallback on scanned image-only page 2, valid JSON outputs, Pillow image verification |
| `backend/tests/test_extraction.py` | `test_extract_invalid_and_missing_pdfs` | Graceful `PDFExtractionError` on missing, 0-byte, and corrupted PDFs |

---

## 8. Phase 3 — Content Classification & Cleanup

### Problems Identified After Raw Extraction
1. **Table-Text Duplication:** Table cell text on pages 2 and 6 also appeared inside raw `text` blocks.
2. **Repeated Banners & Page Numbers:** Document header banners (`CCAC OGMP – Technical Guidance Document Number 9...`) and footers (`Page X of 10`) repeated on all 10 pages.
3. **Decorative Logos:** The CCAC header logo image was extracted separately on every page (`10` identical PNGs).
4. **Table Cell Spacing Defects:** PyMuPDF `find_tables()` concatenated adjacent words in several cells (e.g., `"MitigatedorUnmitigated"`, `"CapitalCostA"`) and split numeric punctuation (`"$104800 - ,"`).
5. **Section-Heading Leakage:** Multi-line blocks kept multiple headings merged, while wrapped caption tails (`"Scenario)"`) and table headers (`"Mitigated or Unmitigated"`, `"Annual Costs"`) leaked into `section_heading`.

### Solution Architecture (`backend/app/classification/`)
Phase 3 builds an isolated cleanup and classification layer (`classify_document`) that reads raw extraction outputs and produces `ClassifiedDocumentResponse`, separating every item cleanly into `text`, `tables`, or `images` while recording removed table duplicates in `excluded_duplicates`.

---

## 9. Content Classification

Every classified object has a single `content_type` (`"text"`, `"table"`, or `"image"`) defined in `backend/app/schemas/classification.py`:

### `TEXT` (`ClassifiedTextItem`)
- **Fields:** `content_id`, `document_id`, `document_name`, `page`, `content_type="text"`, `text`, `bbox`, `section_heading`, `extraction_method` (`"pymupdf"` or `"ocr"`), `is_boilerplate` (`bool`), `metadata` (`raw_content_id`, `char_count`, `ocr_used`, `boilerplate_reason`).
- **Covers:** Meaningful technical prose, section headings, table/exhibit captions, and footnotes, with normalized line whitespace and preserved paragraph breaks.

### `TABLE` (`ClassifiedTableItem`)
- **Fields:** `table_id`, `content_id`, `document_id`, `document_name`, `page`, `content_type="table"`, `headers`, `rows`, `structured_data` (list of `{header: value}` dicts), `markdown`, `bbox`, `extraction_method` (`"pymupdf"` or `"pdfplumber"`), `metadata` (`row_count`, `data_row_count`, `col_count`, `quality_score`, `raw_quality_metrics`, `comparison`).

### `IMAGE` (`ClassifiedImageItem`)
- **Fields:** `image_id`, `content_id`, `document_id`, `document_name`, `page`, `content_type="image"`, `image_path`, `image_url`, `image_format`, `width`, `height`, `bbox`, `ocr_text`, `is_decorative` (`bool`), `metadata` (`file_name`, `sha256`, `occurrence_count`, `decorative_reason`).

---

## 10. Phase 3 Verified Results

Audited output in `extracted_data/classified/2017_OGMP-TGD9-Casinghead-venting_CCAC_a048498a.json`:

| Metric | Verified Count |
| :--- | :---: |
| Raw text blocks (`raw_text_items`) | `78` |
| Clean technical text (`clean_text_items`) | `33` |
| Boilerplate text (`boilerplate_text_items`) | `20` |
| Table duplicates removed (`removed_table_duplicates`) | `25` |
| Refined tables (`classified_tables` / `refined_tables_count`) | `2` / `2` |
| Raw images (`raw_images`) | `15` |
| Content images (`content_images`) | `5` |
| Decorative images (`decorative_images`) | `10` |

### Exact Accounting
- **Text accounting:** `33` (clean technical text) + `20` (boilerplate) + `25` (table duplicates removed) = `78` (raw text blocks); `33 + 20 = 53` items retained in `classified_text_items`.
- **Image accounting:** `5` (content figures) + `10` (decorative logos) = `15` (raw images).
- **Table accounting:** `2` raw tables → `2` refined classified tables.

---

## 11. Boilerplate Handling

Implemented conservatively in `backend/app/classification/boilerplate_detector.py`:
- Normalizes digits (`\d+` → `#`) and whitespace so `Page 1 of 10`..`Page 10 of 10` share a signature.
- Requires both repetition across multiple pages (`>= max(3, int(total_pages * 0.4))` for `>= 3` pages) and placement inside margin bands (`y1 <= 0.14 * page_height` for top headers, `y0 >= 0.88 * page_height` for bottom footers) or a short page-number regex match.
- Skips blocks longer than `250` characters so technical prose is never flagged.
- Marks items with `is_boilerplate: true` and `boilerplate_reason` rather than deleting them permanently.

**Verified TGD9 Boilerplate Items (20 total, 0 false positives):**
- **10** top-margin document banners (`CCAC OGMP – Technical Guidance Document Number 9\nCasinghead Gas Venting\nModified: November 2015`, pages 1–10).
- **10** bottom-margin page numbers (`Page 1 of 10` through `Page 10 of 10`).

---

## 12. Table Duplicate Removal

Implemented in `backend/app/classification/deduplicator.py` (`remove_table_duplicates_from_text`):
- A raw text block on a page containing tables is excluded only when:
  1. Its bounding-box overlap with a detected table's `bbox` is `>= 0.60` (computed via `_box_overlap_ratio`), **and**
  2. Its alphanumeric-normalized content matches text inside the table's headers/rows (`_text_matches_table_content`).
- OCR-derived blocks, captions above tables, and footnotes below tables are preserved.
- Every removed block is recorded in `excluded_duplicates` with `raw_content_id`, `page`, `matched_table_id`, `overlap_ratio`, `reason`, and `text_preview`.

**Verified TGD9 Audit Result:** All **25** excluded blocks (`17` on page 2 matching `table_0001`, `8` on page 6 matching `table_0002`) had `overlap_ratio == 1.0` and matched table cell contents with zero false positives.

---

## 13. Section Heading Fix

### Audit Issue Discovered
In the initial Phase 3 run, PyMuPDF grouped multiple sections (e.g., `Introduction` and `Description of Source`) into single blocks, while wrapped caption tails (`"Scenario)"`) and table header cells (`"Mitigated or Unmitigated"`, `"Annual Costs"`) propagated as `section_heading` values across pages 2–8.

### Implemented Correction
1. In `backend/app/extraction/text_extractor.py`, `is_section_heading` now rejects table/figure captions (`Table X...`, `Figure X...`), bullet lines, unbalanced parenthesis fragments (`Scenario)`), parenthetical tags (`(OPTION A)`), trailing commas/semicolons, and unapproved single-word fragments. `extract_page_text_blocks` splits multi-line blocks at standalone bold/large-font heading lines.
2. In `backend/app/classification/classifier.py`, `active_clean_heading` is updated only when `item.section_heading` actually appears inside a kept, non-boilerplate, non-table-duplicate block.

### Verified Distinct Headings Retained in TGD9 Output
- `TECHNICAL GUIDANCE DOCUMENT NUMBER 9:`
- `CASINGHEAD GAS VENTING`
- `Introduction`
- `Description of Source`
- `Quantification Methodology`
- `Mitigation Option A – Install compressors/VRUs to capture casinghead gas.`
- `Mitigation Option B – Connect casing to tanks equipped with vapor recovery units.`
- `Mitigation Option C – Route casinghead gas to flare.`
- `Exhibit A – Manually Venting Casinghead Gas21`
- `Exhibit B – Casinghead Gas Recovered by a Wellhead Compressor22`
- `Exhibit C – Casinghead Gas Routed to a Flare23`

---

## 14. Image Classification

Implemented in `backend/app/classification/image_classifier.py`:
- Computes SHA-256 digests of saved image files and counts distinct pages on which each asset appears.
- Flags `is_decorative: true` conservatively when an identical asset repeats across `>= max(3, int(total_pages * 0.4))` pages inside header/footer bands (`y1 <= 0.16 * H` or `y0 >= 0.85 * H`), repeats across `>= max(4, int(total_pages * 0.6))` pages anywhere, or is `< 32×32` px.

**Verified TGD9 Result:**
- **15 extracted images** → **5 content images** (`is_decorative: false`) + **10 decorative images** (`is_decorative: true`).
- The **10 decorative images** (`page_001_img_0001.png`..`page_010_img_0014.png`, `404×201` PNG, identical SHA-256 `39561db11e39...`) are the repeated CCAC header logos.
- The **5 content images** (`page_009_img_0010.jpeg`–`0013.jpeg` and `page_010_img_0015.jpeg`) were visually verified as field photographs for Exhibits A (manual casinghead venting), B (wellhead compressor/VRU), and C (casinghead gas routed to flare).

---

## 15. Table Refinement

Implemented in `backend/app/classification/table_refiner.py`:
- Extracts candidate tables from the source PDF using `pdfplumber` (`find_tables()`), matches them to raw PyMuPDF tables by bounding-box IoU (`>= 0.4`) or `(row, col)` shape, and compares both using generic `score_table_quality` (rewarding clean word separation and penalizing concatenated camelCase tokens and split numeric punctuation).

### Verified Refined Tables (`2017_OGMP-TGD9-Casinghead-venting_CCAC_a048498a.json`)

#### Table 9.1 (`table_0001`, Page 2, `pdfplumber` selected over `pymupdf`: score `54.8` vs `-2.8`)
- **Headers:** `["Configuration", "Mitigated or Unmitigated"]`
- **Rows:**

| Configuration | Mitigated or Unmitigated |
| :--- | :--- |
| Casinghead gas is vented directly to the atmosphere, either continuously or periodically to relieve pressure build-up. Exhibit A | Unmitigated |
| Casinghead gas is recovered by a wellhead compressor/vapor recovery unit (VRU) and routed to sales or for on-site use. Exhibit B | Mitigated (if confirmed to be functioning with lowA or no emissions) (OPTION A) |
| Casinghead gas is routed to tanks with new or existing VRU systems and routed to sales or for on-site use. | Mitigated (if confirmed to be functioning with lowA or no emissions) (OPTION B) |
| Casinghead gas is routed to a flare.2 Exhibit C | Mitigated (if confirmed to be functioning with lowA or no emissions) (OPTION C) |

#### Table 9.2 (`table_0002`, Page 6, `pdfplumber` selected over `pymupdf`: score `28.4` vs `-13.6`)
- **Headers:** `["Project Component", "Implementation Costs", "Annual Costs"]`
- **Rows:**

| Project Component | Implementation Costs | Annual Costs |
| :--- | :--- | :--- |
| Capital CostA | `$12,500` | `–` |
| Installation CostsB | `$18,750` | `–` |
| O&M Costs (Electricity)C | `–` | `$7,350` |
| Gas SavingsD | `–` | `-$104,800` |
| Total | `$31,250` | `-$97,450` |

All numeric values, negative signs, footnote superscripts, and units were preserved without loss.

---

## 16. Testing — Final Phase 3

Command executed in `backend/`: `.\.venv\Scripts\pytest.exe -v`  
**Verified Result:** **11 passed, 0 failed** in **9.53s**

| Test File | Test Name | Verification Scope |
| :--- | :--- | :--- |
| `backend/tests/test_api.py` | `test_api_upload_and_retrieval_flow` | Health check, PDF upload, summary/extraction/list endpoints, plus Phase 3 `GET .../classification` and `POST .../classify` |
| `backend/tests/test_api.py` | `test_api_error_handling` | Invalid extension, invalid `%PDF-` header, missing document `404` |
| `backend/tests/test_classification.py` | `test_table_quality_scoring_prefers_clean_spacing` | Generic `score_table_quality` preference for clean spacing & currency formatting |
| `backend/tests/test_classification.py` | `test_remove_table_duplicates_from_text_preserves_captions_and_footnotes` | Bbox + text duplicate removal keeping captions and footnotes intact |
| `backend/tests/test_classification.py` | `test_boilerplate_and_decorative_image_detection` | Cross-page margin boilerplate text and repeated logo detection |
| `backend/tests/test_classification.py` | `test_classify_document_end_to_end` | Full extraction → classification pipeline, JSON persistence, and no table-header leakage into `section_heading` |
| `backend/tests/test_classification.py` | `test_section_heading_filter_rejects_captions_and_fragments` | Phase 3 audit regression test for `is_section_heading` |
| `backend/tests/test_extraction.py` | `test_assess_text_meaningfulness` | Meaningful text vs OCR trigger rules |
| `backend/tests/test_extraction.py` | `test_table_helpers` | Table cleaning, validation, and Markdown formatting |
| `backend/tests/test_extraction.py` | `test_extract_pdf_document_full_pipeline` | Text, table, PNG image, and RapidOCR fallback extraction + JSON/Pillow verification |
| `backend/tests/test_extraction.py` | `test_extract_invalid_and_missing_pdfs` | Missing, 0-byte, and corrupted PDF handling |

---

## 17. Raw vs Clean Data Design

The system intentionally keeps both layers side by side:
- **Raw Extraction (`extracted_data/{metadata,text,tables,images}/`)** preserves untouched extractor output from Phase 2.
- **Clean Classified Data (`extracted_data/classified/`)** stores refined tables, deduplicated text, boilerplate/decorative flags, and `excluded_duplicates` audit records.

**Benefits:**
- Enables side-by-side debugging in the UI (`Raw Extraction (Phase 2)` vs `Classified & Cleaned (Phase 3)`).
- Allows re-running or improving classification logic (`POST /api/documents/{id}/classify`) without re-uploading or re-running OCR.
- Guarantees zero permanent data loss if downstream rules change.

---

## Phase 4 — Chunking

**Status:** **Phase 4 COMPLETED** *(Verified on automated unit/API tests and real CCAC TGD9 PDF)*  
**Not Implemented Yet:** Embeddings, FAISS vector database, semantic search retrieval, chunk visualization/evaluation UI, and RAG chatbot are **NOT IMPLEMENTED YET**.

### 1. Purpose of Phase 4
Consume the validated Phase 3 classified content (`extracted_data/classified/<document_id>.json`) without modifying Phase 1–3 behavior, apply **8 distinct, explainable text chunking methodologies**, create dedicated **table** and **image** chunks, compute chunk-length statistics, and persist clean JSON outputs ready for Phase 5 visualization.

```text
Phase 3 Clean Data
        ↓
   Phase 4 Chunking
        ↓
 ┌──────┼────────┐
 ↓      ↓        ↓
Text   Tables   Images
 ↓
8 Chunking Methods
 ↓
Chunk Output
 ↓
Statistics
        ↓
Future Phase 5 Visualization
```

### 2. Why Chunking Is Required for RAG
Large technical PDFs cannot be embedded or fed to an LLM as a single giant document because embedding models have fixed context limits and mixed-topic blocks dilute retrieval precision. Splitting clean technical text into focused chunks—while keeping structured tables and exhibit figures intact—enables accurate retrieval and allows the project to compare which chunking strategy works best.

### 3–5. The 8 Implemented Chunking Methods & Default Parameters
Implemented as standalone, readable Python functions in `backend/app/chunking/text_chunkers.py` and orchestrated per page (methods 1–7) or across consecutive section blocks (method 8) in `backend/app/chunking/pipeline.py`:

| # | Method Key | Function | Simple Explanation | Default Parameters (`ChunkingParameters`) |
| :-: | :--- | :--- | :--- | :--- |
| 1 | `fixed_size` | `fixed_size_chunk` | Splits text into equal character-length slices with optional character overlap. | `fixed_chunk_size=500`, `fixed_overlap=50` |
| 2 | `token_based` | `token_based_chunk` | Splits text by whitespace-delimited token count (`\S+`) with token overlap. | `token_max_tokens=100`, `token_overlap=15` |
| 3 | `sentence_based` | `sentence_based_chunk` | Splits text into sentences and groups up to `max_sentences` with sentence overlap. | `sentence_max_sentences=4`, `sentence_overlap=1`, `sentence_max_chars=1000` |
| 4 | `paragraph_based` | `paragraph_based_chunk` | Preserves paragraph breaks (`\n\n` / lines) and groups paragraphs up to `max_paragraphs`. | `paragraph_max_paragraphs=2`, `paragraph_max_chars=1000` |
| 5 | `recursive` | `recursive_chunk` | Splits recursively from larger to smaller separators (`\n\n`, `\n`, `. `, ` `, `""`) and merges pieces up to `chunk_size`. | `recursive_chunk_size=600`, `recursive_overlap=60` |
| 6 | `sliding_window` | `sliding_window_chunk` | Moves a fixed character window across text by `step_size` (50% overlap by default). | `sliding_window_size=400`, `sliding_step_size=200` |
| 7 | `semantic` | `semantic_chunk` | Sentences with similar meaning are grouped together based on TF-IDF cosine similarity using NumPy. | `semantic_similarity_threshold=0.12`, `semantic_max_chars=900`, `semantic_min_chars=120` |
| 8 | `structure_section` | `structure_section_chunk` / `_run_structure_section_chunker` | Groups consecutive Phase 3 blocks sharing the same `section_heading`, splitting only if a section exceeds `max_chars`. | `section_max_chars=1200`, `section_overlap_chars=0` |

### 6. How Text Is Chunked
- Input is filtered strictly from Phase 3 `classified.text` where `is_boilerplate == False` and `text.strip() != ""`.
- Boilerplate headers/footers (`20` items on TGD9), table duplicates (`25` excluded items), and decorative logos (`10` items) are excluded.
- Methods 1–7 run page-by-page so each chunk retains an exact `page` integer, `section_heading`, `source_content_ids`, `start_pos`, and `end_pos`.
- Method 8 (`structure_section`) groups consecutive clean blocks sharing the same `section_heading` across pages and records both start `page` and `pages` list in `metadata`.

### 7. How Tables Are Handled (`backend/app/chunking/table_chunker.py`)
- Uses the validated Phase 3 structured tables (`classified.tables`) instead of running text chunkers over table rows.
- Creates one intact `ChunkItem` (`content_type="table"`, `chunking_method="table_structured"`) per non-empty table, formatted cleanly (`Table <id> (Page X)`, `Headers: ...`, `Row 1: ...`) and storing `table_id`, `headers`, `rows`, `structured_data`, `markdown`, `bbox`, and `extraction_method` in `metadata`.

### 8. How Images Are Handled (`backend/app/chunking/image_chunker.py`)
- Uses only meaningful content images (`is_decorative == False`) and excludes decorative logos (`is_decorative == True`).
- Verifies each image file exists on disk (skipping missing files with a warning rather than crashing).
- Preserves `image_id`, `image_path`, `image_url`, `image_format`, `width`, `height`, `bbox`, existing page `section_heading` / exhibit caption context, and `ocr_text` if present—without inventing descriptions.

### 9. Common Chunk Structure (`backend/app/schemas/chunking.py`)
All text, table, and image chunks share `ChunkItem`:
```json
{
  "chunk_id": "recursive_chunk_001",
  "document_id": "2017_OGMP-TGD9-Casinghead-venting_CCAC_a048498a",
  "page": 1,
  "content_type": "text",
  "chunking_method": "recursive",
  "content": "...",
  "metadata": {
    "document_name": "2017_OGMP-TGD9-Casinghead-venting_CCAC.pdf",
    "section_heading": "...",
    "source_content_ids": ["..."],
    "start_pos": 0,
    "end_pos": 512,
    "char_count": 512
  }
}
```

### 10. Output / Storage Structure (`chunk_outputs/`)
Persisted cleanly by `backend/app/chunking/storage.py`:
```text
chunk_outputs/
└── <document_id>/
    ├── summary.json                 # Document info, parameters, 8-method stats, table/image counts, warnings
    ├── tables.json                  # Structured table chunks
    ├── images.json                  # Non-decorative image chunks
    └── methods/
        ├── fixed_size.json
        ├── token_based.json
        ├── sentence_based.json
        ├── paragraph_based.json
        ├── recursive.json
        ├── sliding_window.json
        ├── semantic.json
        └── structure_section.json
```

### 11. Chunk Statistics & 13. Real PDF Validation (`2017_OGMP-TGD9-Casinghead-venting_CCAC_a048498a`)
Verified end-to-end (`Phase 2 -> Phase 3 -> Phase 4`) on `2017_OGMP-TGD9-Casinghead-venting_CCAC.pdf`:

| Method | Chunks | Avg Length (chars) | Min Length | Max Length | Total Chars | Total Words |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `fixed_size` | `56` | `461.88` | `52` | `500` | `25,865` | `3,781` |
| `token_based` | `44` | `612.93` | `161` | `821` | `26,969` | `3,935` |
| `sentence_based` | `60` | `481.12` | `111` | `967` | `28,867` | `4,214` |
| `paragraph_based` | `26` | `905.58` | `61` | `3,670` | `23,545` | `3,425` |
| `recursive` | `51` | `509.94` | `69` | `599` | `26,007` | `3,791` |
| `sliding_window` | `113` | `390.70` | `202` | `400` | `44,149` | `6,538` |
| `semantic` | `72` | `326.28` | `7` | `880` | `23,492` | `3,425` |
| `structure_section` | `33` | `713.30` | `22` | `1,192` | `23,539` | `3,425` |

- **Table chunks:** `2` (`table_chunk_001` on Page 2 for `table_0001`, `table_chunk_002` on Page 6 for `table_0002`).
- **Image chunks:** `5` (`image_0010`–`image_0013` on Page 9, `image_0015` on Page 10). All `10` decorative CCAC logos were excluded.
- **Zero leakage verified:** Boilerplate headers/page numbers (`Page 1 of 10`, `Modified: November 2015`) and table-only cell data (`-$104,800`) did not appear in any text chunk; `warnings = []`.

### 12. Phase 4 Testing (`backend/tests/test_chunking.py` + `backend/tests/test_api.py`)
Command executed: `.\.venv\Scripts\pytest.exe -v` → **24 passed, 0 failed in 13.30s** (all 11 Phase 1–3 tests + 13 new Phase 4 test cases):
- `test_all_methods_handle_empty_and_short_text` (8 parametrized cases across all 8 methods)
- `test_fixed_size_and_sliding_window_overlap`
- `test_token_sentence_paragraph_recursive_semantic_and_section_chunkers`
- `test_invalid_chunk_parameters_raise_value_error`
- `test_table_and_image_chunk_creation_and_missing_assets`
- `test_chunk_document_pipeline_persists_all_8_methods_and_stats`
- `test_api_upload_and_retrieval_flow` (extended to cover `POST /chunk`, `GET /chunks`, `GET /chunks/{method}`, and `400` for invalid method)

### 14–16. Dependencies, Design Decisions & Limitations
- **Dependencies Added:** **None.** Semantic chunking uses `numpy` (already installed via PyMuPDF) for lightweight TF-IDF cosine similarity, and token-based chunking uses Python `re` (`\S+`) to avoid external model/tokenizer downloads during Phase 4.
- **Design Decisions:** Simple standalone functions per method, common `ChunkItem` schema, page-bounded execution for methods 1–7 to guarantee exact page attribution, and cross-page section grouping for `structure_section`.
- **Limitations:** Semantic chunking currently relies on lexical TF-IDF sentence vectors rather than dense neural embeddings (which will arrive in Phase 7); `paragraph_based` keeps single unusually long extracted paragraphs intact (up to `3,670` chars on TGD9 page 4) rather than splitting inside a paragraph; short standalone footnotes (e.g., `'6 Ibid.'`, `7` chars) remain intact as small chunks when adjacent text reaches `max_chars`.

---

## Phase 5 — Chunk Visualization

### 5.1 Purpose
Provide a simple, mentor-friendly web interface that directly fulfills the core requirement (*"Visualizes the Chunks to See the Chunking are Correct or not"*), allowing users to inspect whether generated text, table, and image chunks are clean, accurate, and properly separated before moving to chunk evaluation, embeddings, and RAG.

### 5.2 Requirements Implemented
- **Separate content-type views:** `All`, `Text`, `Tables`, and `Images` tabs/filters in `ChunkVisualizationPanel.tsx`.
- **Separate 8-method text visualization:** Dropdown selecting `All Methods (Overview)` or any single method (`Fixed-Size`, `Token-Based`, `Sentence-Based`, `Paragraph-Based`, `Recursive`, `Sliding Window`, `Semantic`, `Structure / Section-Based`), showing only the selected method's chunks in the list.
- **Method-specific visual cues (`TextChunkCard.tsx`):**
  - Sliding Window displays `Overlap: 200 characters` and a `Previous Chunk ↓ Overlapping content ↓ Current Chunk` overlap preview.
  - Structure / Section-Based displays a `Section: <heading>` + `Page` / `Pages` banner.
  - Semantic displays a `Semantic similarity grouping` badge.
- **Separate Table Visualization (`TableChunksView.tsx`):** Renders actual HTML tables from Phase 4 `headers` and `rows` with `Table ID`, `Page`, `Extractor`, and a toggle for raw chunk text.
- **Separate Image Visualization (`ImageChunksView.tsx`):** Renders the extracted content images via `/api/documents/{id}/images/{file_name}` with `Image ID`, `Page`, `Section`, `Caption/context`, dimensions, and `image_path`—excluding all decorative logos.
- **Chunk Statistics:** Displays backend-computed `Total Chunks`, `Average Length`, `Minimum Length`, and `Maximum Length` above the chunk list.
- **Pagination & Inspection:** Paginates text chunks (`10` per page, `Showing 1–10 of N`, `Previous` / page numbers / `Next`) and includes a simple `Inspect` modal displaying full chunk text and JSON metadata.

### 5.3 Architecture

```text
Phase 4 Chunk Outputs (chunk_outputs/<document_id>/)
        ↓
Backend Read APIs (backend/app/api/chunks.py + storage.py)
        ↓
Frontend Visualization (ChunkVisualizationPanel + Text/Table/Image views)
        ↓
User verifies chunks
```

### 5.4 Text Visualization
The `Chunking Method` dropdown exposes all 8 Phase 4 strategies independently (`fixed_size`, `token_based`, `sentence_based`, `paragraph_based`, `recursive`, `sliding_window`, `semantic`, `structure_section`). Selecting a method queries `GET /api/documents/{document_id}/chunks/{method}` and renders only that method's chunks along with its `MethodChunkStats`. Selecting `All Methods (Overview)` shows a side-by-side summary table comparing all 8 methods' counts and length metrics.

### 5.5 Table Visualization
`TableChunksView.tsx` consumes `GET /api/documents/{document_id}/chunks/tables` and renders each `table_structured` chunk as a clean HTML `<table>` from `metadata.headers` and `metadata.rows`, preserving `table_id`, `page`, and `extraction_method` (`pdfplumber` / `pymupdf`) without hardcoding values.

### 5.6 Image Visualization
`ImageChunksView.tsx` consumes `GET /api/documents/{document_id}/chunks/images` and displays each meaningful content image alongside its `image_id`, `page`, `section_heading`, `caption_context` (when present), dimensions, and `image_path`. Because Phase 4 filters `is_decorative == False`, the 10 repeated CCAC header logos never appear in the Image Visualization view, and no fake descriptions are generated.

### 5.7 API Endpoints
Implemented in `backend/app/api/chunks.py` (reading from `chunk_outputs/<document_id>/` via `backend/app/chunking/storage.py`):
- `GET /api/documents/{document_id}/chunks/summary` — returns `ChunkSummaryResponse` (`method_stats`, `table_chunks_count`, `image_chunks_count`, `parameters`, `warnings`).
- `GET /api/documents/{document_id}/chunks/{method}` — returns `MethodChunksResponse` (`stats` + `chunks` for one of the 8 methods; `400` on invalid method).
- `GET /api/documents/{document_id}/chunks/tables` — returns `TableChunksResponse` (structured table chunks).
- `GET /api/documents/{document_id}/chunks/images` — returns `ImageChunksResponse` (meaningful content image chunks).
- Reuses existing `GET /api/documents/{document_id}/images/{file_name}` to serve image binaries and `POST /api/documents/{document_id}/chunk` for optional regeneration.

### 5.8 Testing (`backend/tests/test_chunk_visualization_api.py`)
Command executed: `.\.venv\Scripts\pytest.exe -v`  
**Verified Result:** **26 passed, 0 failed** in **12.84s** (all 24 Phase 1–4 tests + 2 Phase 5 API visualization test suites covering `summary`, all 8 `method` endpoints, `tables`, `images`, decorative-logo exclusion, metadata preservation, `404` missing document, and `400` invalid method).  
Frontend build (`npm run build`): `tsc -b && vite build` passed with `0` errors.

### 5.9 Real TGD9 Validation (`2017_OGMP-TGD9-Casinghead-venting_CCAC.pdf`)
Verified via live Vite proxy (`/api/documents/2017_OGMP-TGD9-Casinghead-venting_CCAC_662883b9/chunks/...`):
- **Text chunks across 8 methods:** `fixed_size` (`56`), `token_based` (`44`), `sentence_based` (`60`), `paragraph_based` (`26`), `recursive` (`51`), `sliding_window` (`113`), `semantic` (`72`), `structure_section` (`33`).
- **Tables:** `2` (`table_0001` on Page 2, `table_0002` on Page 6).
- **Images:** `5` meaningful exhibit photographs (`image_0010`–`image_0013` on Page 9, `image_0015` on Page 10), all returning `HTTP 200` `image/jpeg`; all `10` decorative CCAC logos excluded.

### 5.10 Limitations
- Read-only visualization inspects Phase 4 static outputs; custom parameter sliders in the UI and comparative charts/quality scoring belong to Phase 6 (Chunk Quality Evaluation).
- Automated Chrome DevTools browser-driver connection was unavailable in this environment (Chrome remote debugging `DevToolsActivePort` not active), so UI components were verified via `tsc -b && vite build`, `pytest` API tests, and live Vite-proxied HTTP verification.

### 5.11 Current Project Status
```text
Phase 1 — Completed
Phase 2 — Completed
Phase 3 — Completed
Phase 4 — Completed
Phase 5 — Completed
Phase 6 — Not implemented yet
Embeddings — Not implemented yet
Semantic Search — Not implemented yet
RAG Chatbot — Not implemented yet
```

---

## Phase 6 — Embeddings & Vector Storage

### 6.1 Purpose
Convert the validated Phase 4 text and table chunks into dense numerical vector representations and persist them in local FAISS indexes alongside linked chunk metadata so downstream phases can perform semantic similarity search without re-extracting or re-chunking the PDF.

### 6.2 Simple Concept

```text
Phase 4 Chunks (chunk_outputs/<document_id>/)
      ↓
Sentence Transformer (Batch Processing)
      ↓
384-dimensional L2-normalized vectors
      ↓
FAISS IndexFlatIP + metadata.json
      ↓
Ready for semantic search (future phase)
```

### 6.3 Model
- **Model:** `sentence-transformers/all-MiniLM-L6-v2`
- **Why Selected:** Lightweight, runs locally without paid cloud APIs, widely used for semantic similarity, fast for CPU execution, and easy to explain during mentor review.
- **Embedding Dimension:** `384` (read dynamically from model output via `get_embedding_dimension()`).
- **Dependencies Added:** `sentence-transformers` (`6.3.0`), `faiss-cpu` (`1.16.0`), along with transitive dependencies (`torch` `2.15.0`, `transformers` `5.24.1`, `scikit-learn` `1.9.1`, `scipy` `1.18.1`).

### 6.4 Input
Reads directly from existing Phase 4 outputs in `chunk_outputs/<document_id>/` (`summary.json`, `methods/*.json`, `tables.json`, `images.json`) via `load_document_chunks(...)`. Does not re-extract the PDF or alter Phase 4 files.

### 6.5 Text Embeddings
Each of the **8 text chunking methods** (`fixed_size`, `token_based`, `sentence_based`, `paragraph_based`, `recursive`, `sliding_window`, `semantic`, `structure_section`) is embedded separately in configurable batches (`EMBEDDING_BATCH_SIZE=32`) and stored in its own FAISS index so retrieval performance across chunking strategies can be compared later without overwriting or merging methods.

### 6.6 Table Embeddings
Each structured table chunk is converted into a clean textual representation by `format_table_for_embedding` (`Table: <id>`, `Headers:`, `Rows:` separated by `|`) before generating its `384`-dimensional vector, while retaining original table headers, rows, and metadata inside `tables/metadata.json`.

### 6.7 Image Embeddings
**Image embeddings are NOT implemented in Phase 6** (`image_vectors = 0`, `"image_embeddings_status": "Not implemented in Phase 6"`). Existing Phase 4 image chunk metadata is preserved cleanly under `vector_store/<document_id>/images/metadata.json` rather than inventing fake descriptions or vectors.

### 6.8 Vector Storage & Normalization (`backend/app/vectorstore/faiss_store.py`)
- Vectors are **L2-normalized** (`normalize_embeddings=True`) during encoding and indexed in `faiss.IndexFlatIP(dim)` (inner product on unit-norm vectors equals exact cosine similarity).
- Each `metadata.json` records `vector_index` (`0..N-1`), `embedding_id`, `chunk_id`, `document_id`, `content_type`, `chunking_method`, `page`, `section_heading`, `text`, `embedding_model`, `embedding_dimension`, and preserved chunk `metadata`—ensuring exact 1-to-1 lookup between FAISS positions and source chunks.

### 6.9 APIs (`backend/app/api/embeddings.py`)
- `POST /api/documents/{document_id}/embeddings/generate` — loads Phase 4 chunks, generates batched normalized embeddings, builds and saves FAISS indexes + metadata, and returns `EmbeddingSummaryResponse` (`404` if chunks not found).
- `GET /api/documents/{document_id}/embeddings/summary` — loads persisted `vector_store/<document_id>/summary.json` (`404` if not yet generated).

### 6.10 Storage Structure (`vector_store/`)

```text
vector_store/
└── <document_id>/
    ├── summary.json
    ├── fixed_size/          (index.faiss + metadata.json)
    ├── token_based/         (index.faiss + metadata.json)
    ├── sentence_based/      (index.faiss + metadata.json)
    ├── paragraph_based/     (index.faiss + metadata.json)
    ├── recursive/           (index.faiss + metadata.json)
    ├── sliding_window/      (index.faiss + metadata.json)
    ├── semantic/            (index.faiss + metadata.json)
    ├── structure_section/   (index.faiss + metadata.json)
    ├── tables/              (index.faiss + metadata.json)
    └── images/              (metadata.json — image_vectors=0)
```

### 6.11 Testing (`backend/tests/test_embeddings.py`)
Command executed: `.\.venv\Scripts\pytest.exe -v`  
**Verified Result:** **29 passed, 0 failed** in **23.50s** (26 Phase 1–5 tests + 3 Phase 6 test suites covering model loading, numerical finite unit-norm vectors, consistent `384` dimension, empty text handling, table formatting + FAISS save/load round-trip, all 8 methods, unique `embedding_id`s, metadata count parity, and `POST .../embeddings/generate` + `GET .../embeddings/summary` + `404` error handling).

### 6.12 TGD9 Validation (`2017_OGMP-TGD9-Casinghead-venting_CCAC_662883b9`)
- **Model:** `sentence-transformers/all-MiniLM-L6-v2`
- **Dimension:** `384`
- **Vectors per text method:** `fixed_size` (`56`), `token_based` (`44`), `sentence_based` (`60`), `paragraph_based` (`26`), `recursive` (`51`), `sliding_window` (`113`), `semantic` (`72`), `structure_section` (`33`) → **`455` text vectors**
- **Table vectors:** `2` (`table_chunk_001`, `table_chunk_002`)
- **Image vectors:** `0` (`Not implemented in Phase 6`; `5` image metadata records saved)
- **Total vectors stored across FAISS indexes:** **`457`** (all `457` `embedding_id`s unique; every reloaded FAISS index `ntotal` verified equal to its `metadata.json` count).

### 6.13 Limitations
- Image embeddings are deferred (text-only `all-MiniLM-L6-v2` cannot embed raw pixels, and fake captions are intentionally avoided).
- Semantic search/querying and RAG LLM integration are not yet implemented in this phase.
- Embedding all 8 methods creates 8 separate per-method FAISS indexes (`455` text vectors total for one 10-page document), trading modest disk space for clean cross-method retrieval comparison.

### 6.14 Current Status
```text
Phase 1 — Completed
Phase 2 — Completed
Phase 3 — Completed
Phase 4 — Completed
Phase 5 — Completed
Phase 6 — Completed
Phase 7 — Completed
RAG Chatbot (Phase 8) — Not implemented yet
```

---

## Phase 7 — Semantic Search

### 7.1 Objective
Implement query-driven semantic similarity search over the existing Phase 6 FAISS vector stores without modifying Phase 4 chunk outputs or Phase 6 indexes, and display ranked retrieved chunks in the frontend UI.

**Important Scope Boundary:**
- **No LLM is used in Phase 7.**
- **No OpenAI API key is required for Phase 7.**
- **No chatbot answer generation, RAG prompt synthesis, or conversational memory is performed.**

### 7.2 Architecture

```text
User Query
      ↓
Sentence Transformer (all-MiniLM-L6-v2)
      ↓
384-dimensional L2-normalized float32 query vector
      ↓
FAISS IndexFlatIP similarity search (all 9 stores or single filtered store)
      ↓
Metadata mapping (vector position → metadata.json)
      ↓
Sorted & ranked Top-K chunks (default top_k = 5, range 1..20)
```

### 7.3 Query Embedding (`backend/app/services/semantic_search.py`)
- Reuses Phase 6 `embed_texts` from `backend/app/embeddings/embedder.py` via `embed_query(query, model_name)` so the query model (`sentence-transformers/all-MiniLM-L6-v2`), dtype (`float32`), dimension (`384`), and unit-norm scaling match the stored FAISS vectors identically.
- Empty and whitespace-only queries are rejected cleanly before model inference.

### 7.4 FAISS Search & Cosine Similarity
- Because Phase 6 indexes store L2-normalized vectors in `faiss.IndexFlatIP`, inner-product search returns exact **cosine similarity** scores.
- Searches across all 9 existing Phase 6 stores (`fixed_size`, `token_based`, `sentence_based`, `paragraph_based`, `recursive`, `sliding_window`, `semantic`, `structure_section`, and `tables`), or targets one store when optional `chunking_method` filtering is supplied (`"tables"` / `"table"` maps to the `tables` index).
- Results across searched indexes are sorted in descending score order, deduplicated only on identical `(chunking_method, chunk_id)` pairs so cross-method comparison identity is preserved, and sliced to `top_k`.

### 7.5 Top-K Retrieval & Metadata Mapping
- Default `top_k = 5`, configurable between `1` and `20` (validated by `SemanticSearchRequest` in `backend/app/schemas/search.py`; values `<= 0` or `> 20` raise `422` validation errors).
- `search_single_index` explicitly verifies `index.ntotal == len(metadata_items)` (both via `load_faiss_index_and_metadata` and inside `search_single_index`) before mapping FAISS positions back to `metadata.json` (`chunk_id`, `document_id`, `content_type`, `chunking_method`, `page`, `section_heading`, `text`). Count mismatches raise a clear error instead of returning stale or misaligned records.

### 7.6 API Endpoint (`backend/app/api/search.py`)
- **Endpoint:** `POST /api/documents/{document_id}/search`

**Request Example:**
```json
{
  "query": "What are the implementation costs?",
  "top_k": 5
}
```

*(Optional filter parameter `"chunking_method": "tables"` restricts search to a single Phase 6 store.)*

**Response Example (`200 OK`):**
```json
{
  "query": "What are the implementation costs?",
  "top_k": 5,
  "document_id": "2017_OGMP-TGD9-Casinghead-venting_CCAC_662883b9",
  "chunking_method": null,
  "model": "sentence-transformers/all-MiniLM-L6-v2",
  "searched_stores": [
    "fixed_size", "token_based", "sentence_based", "paragraph_based",
    "recursive", "sliding_window", "semantic", "structure_section", "tables"
  ],
  "total_candidates": 42,
  "results": [
    {
      "rank": 1,
      "score": 0.5255,
      "chunk_id": "table_chunk_002",
      "document_id": "2017_OGMP-TGD9-Casinghead-venting_CCAC_662883b9",
      "content_type": "table",
      "chunking_method": "table",
      "page": 6,
      "section_heading": null,
      "text": "Table: table_0002\nHeaders:\nProject Component | Implementation Costs | Annual Costs\n..."
    }
  ]
}
```

### 7.7 Frontend Semantic Search UI (`frontend/src/components/SemanticSearchPanel.tsx`)
Integrated cleanly into `IngestionPage.tsx` without redesigning the Phase 5 visualization workspace:
- Query input (`Ask about this document...`) and `Search` submit button.
- Top-K dropdown (`3`, `5`, `10`) and optional Vector Store Scope selector (`All Vector Stores (9)` or individual method/`Tables Only`).
- Inline validation for empty queries and error display if a document has no generated FAISS index.
- Ranked chunk result cards displaying Rank (`#1`), actual FAISS Cosine Similarity score (`0.xxxx`), Content Type (`Text` / `Table`), Chunking Method, Page number, Section Heading, Chunk ID, and full retrieved chunk text.

### 7.8 Testing (`backend/tests/test_semantic_search.py`)
Command executed: `.\.venv\Scripts\pytest.exe -v`  
**Verified Result:** **36 passed, 0 failed** in **22.48s** (`29` Phase 1–6 tests + `7` Phase 7 test functions covering all 10 required checks: query vector format/float32/384-dim/L2-norm, empty & whitespace rejection, `top_k` bounds & method filter validation, controlled FAISS search, metadata mapping, `index.ntotal != len(metadata)` mismatch detection, descending similarity ranking, required metadata fields, API error codes, and live TGD9 queries).

### 7.9 Real TGD9 Validation (`2017_OGMP-TGD9-Casinghead-venting_CCAC_662883b9`)
Executed across all `9` Phase 6 FAISS stores (`top_k = 5`, `total_candidates = 42` per query):
- **`"What are the implementation costs?"`** → Rank `#1` score `0.5255`, `type=table`, `method=table`, `page=6` (`table_chunk_002`: *Project Component | Implementation Costs | Annual Costs*).
- **`"What are the mitigation options?"`** → Rank `#1` score `0.5632`, `type=text`, `method=sliding_window`, `page=1`, `section='Introduction'`; also retrieved `table_chunk_001` (*Table 9.1 Configuration | Mitigated or Unmitigated*, `page=2`, score `0.4575`) at rank `#5`.
- **`"What is casinghead gas?"`** → Rank `#1` score `0.7572`, `type=text`, `method=sliding_window`, `page=1`, `section='Introduction'` (*"Casinghead gas is gas that collects in the annular space between the casing and tubing..."*).

---

## Phase 8 — RAG Chatbot with Gemini API

### 8.1 Overview & Clear Responsibility Separation
Phase 8 connects Phase 7 semantic search retrieval to Google Gemini for grounded natural-language question answering, while keeping every stage strictly modular:

- **Phase 7:** `Question → Semantic Search → Relevant Chunks`
- **Phase 8:** `Question → Semantic Search → Relevant Chunks → Context Builder → Gemini API → Grounded Answer + Sources`

Gemini is used **only** for answer generation. `sentence-transformers/all-MiniLM-L6-v2` remains solely responsible for embeddings, and FAISS remains solely responsible for vector retrieval.

```text
PyMuPDF / pdfplumber              → PDF Extraction
Classification / Cleanup          → Clean Content
8 Chunking Methods                → Chunks
Sentence Transformer (all-MiniLM) → 384-Dimensional Embeddings
FAISS (IndexFlatIP)               → Vector Storage
Semantic Search                   → Relevant Chunks
Gemini API (gemini-3.6-flash)     → Natural-Language Answer
```

### 8.2 API Key & Model Configuration
- Configured in `backend/app/core/config.py` (`Settings` reads both root `.env` and `backend/.env` via `env_file`) and templated cleanly with an empty value in `backend/.env.example`:
  - `GEMINI_API_KEY=` (stored **only** in local `.env`; `.gitignore` ignores `.env` and `backend/.env`; never committed, logged, returned in API responses, or placed in frontend code)
  - `GEMINI_MODEL=gemini-3.6-flash` (verified live on the Gemini API via `client.models.list()` + `generate_content` after testing current Flash model availability)
  - `GEMINI_TIMEOUT_SECONDS=30.0`
- Dependency added: `google-genai>=3.0.0` (`3.6.1` installed in `backend/.venv`).

### 8.3 Context Builder (`backend/app/services/context_builder.py`)
- `build_document_context(results)` formats Phase 7 `SemanticSearchResult` entries into cleanly separated `SOURCE 1..N` blocks containing `Page`, `Content Type` (`Table` / `Text`), `Method`, `Chunk ID`, optional `Section`, and chunk text.
- `extract_source_references(results)` maps retrieved chunks into `RagSourceReference` entries without inventing or altering page numbers or chunk metadata.

### 8.4 Gemini Service & Grounding (`backend/app/services/gemini_service.py`)
- Uses `google.genai.Client` on the backend only (`temperature=0.1` + `system_instruction=GROUNDING_SYSTEM_INSTRUCTION`).
- **Grounding Instruction:** Instructs Gemini to answer **only** from the supplied `DOCUMENT CONTEXT`, never invent facts or use outside knowledge, cite page/source where possible, and respond with `"The requested information is not available in the provided document context."` when unsupported.
- **No-Context & Error Handling:**
  - `rag_service.py` skips Gemini completely and returns `"No relevant information was found in the document."` when Phase 7 returns empty context.
  - Missing `GEMINI_API_KEY` raises `GeminiConfigurationError` (`HTTP 503`).
  - Invalid credentials (`401`/`403`), rate limits (`429`), high-demand unavailability (`503`), timeouts, network failures, and empty/malformed responses are mapped to `GeminiServiceError` (`HTTP 502`) with secret scrubbing (`_sanitize_error_message`).

### 8.5 API Endpoint (`backend/app/api/rag.py`)
- **Endpoint:** `POST /api/documents/{document_id}/chat`

**Request Example:**
```json
{
  "query": "What are the implementation costs?",
  "top_k": 5
}
```

**Response Structure (`200 OK`):**
```json
{
  "query": "What are the implementation costs?",
  "answer": "Based on the provided document context, the implementation costs include Capital Cost ($12,500), Installation Costs ($18,750), and Total Implementation Cost ($31,250)...",
  "sources": [
    {
      "rank": 1,
      "score": 0.525472,
      "page": 6,
      "chunk_id": "table_chunk_002",
      "content_type": "table",
      "chunking_method": "table",
      "section_heading": null
    }
  ],
  "retrieved_chunks": 5,
  "model": "gemini-3.6-flash"
}
```

### 8.6 Frontend Chatbot UI (`frontend/src/components/RagChatbotPanel.tsx`)
- Added alongside the existing **Phase 7 Semantic Search** panel in `IngestionPage.tsx` (Phase 7 remains visible and functional so both retrieval-only and RAG generation can be demonstrated side by side).
- Implements a full conversational chatbot interface with React state (`ChatMessage[]`), auto-scroll (`messagesEndRef`), document-scoped header, right-aligned user bubbles, left-aligned assistant bubbles with bot avatar, initial welcome prompt + 3 clickable suggested starter questions, animated `"Thinking..."` loading bubble, per-message `Sources` list (`Page X — Detail — method (chunk_id)`), bottom textarea (`Ask a follow-up question...`, `Enter` to send, `Shift+Enter` for newline), `Top-K` selector (`3`, `5`, `10`, default `5`), and `Clear Chat` reset button.

### 8.7 Testing (`backend/tests/test_rag.py`)
Command executed: `.\.venv\Scripts\pytest.exe -v`  
**Verified Result:** **45 passed, 0 failed** in **39.10s** (`36` Phase 1–7 tests + `9` Phase 8 test functions covering all 10 unit/mocked integration cases: request validation, Phase 7 integration, context construction, mocked Gemini payload/grounding check, Gemini answer mapping, source preservation, no-results skip check, missing API key `503`, Gemini failure/secret redaction `502`, and out-of-document grounding).

### 8.8 Real TGD9 End-to-End Validation (`2017_OGMP-TGD9-Casinghead-venting_CCAC_662883b9`)
Verified against live `gemini-3.6-flash` and the existing Phase 6 FAISS stores (`top_k = 5`, API key masked in `.env`):
1. **`"What are the implementation costs?"`** → Generated accurate breakdown (`Capital Cost: $12,500`, `Installation Costs: $18,750`, `Total Implementation Cost: $31,250`) citing `Page 6` & `Page 5` with `5` sources (`table_chunk_002` at `#1`).
2. **`"What are the mitigation options?"`** → Summarized `Mitigation Option A`, `Option B`, and `Option C` grounded in `Page 2 (Table 0001)` & `Page 3` with `5` sources.
3. **`"What is casinghead gas?"`** → Defined casinghead gas as gas collecting in the annular space between the casing and tubing in an oil well (`Page 1`, `5` sources).
4. **`"Who is the president of France?"`** (out-of-document test) → Returned exact grounded refusal: `"The requested information is not available in the provided document context."` without using external knowledge.

---

## 18. Current Project Status

| Component / Phase | Status |
| :--- | :--- |
| **Phase 1 — Project Foundation & Scaffolding** | **Completed** |
| **Phase 2 — PDF Ingestion & Multimodal Extraction** | **Completed** |
| **Phase 3 — Content Classification & Cleanup** | **Completed and Audited** |
| **Phase 4 — Chunking Methods (8 Strategies + Table/Image Chunks)** | **Completed** |
| **Phase 5 — Chunk Visualization** | **Completed** |
| **Phase 6 — Embeddings & Vector Storage (FAISS)** | **Completed** |
| **Phase 7 — Semantic Search (FAISS Similarity Retrieval)** | **Completed** |
| **Phase 8 — RAG Chatbot with Google Gemini API** | **Completed** |

---

## 19. Scope Exclusions Verification

- **LLM Provider Used:** Google Gemini API (`google-genai`, model `gemini-3.6-flash`).
- **Not Implemented / Intentionally Excluded:** OpenAI API, external vector databases, multimodal image embeddings, web search, fine-tuning, and multi-turn conversational long-term memory.

---

## 20. Project File Structure

```text
c:\HCL\USECASE\
├── .gitignore
├── README.md
├── docs/
│   └── PROJECT_DOCUMENTATION.md
├── data/
│   └── pdfs/
│       └── 2017_OGMP-TGD9-Casinghead-venting_CCAC.pdf (+ uploaded copies)
├── extracted_data/
│   ├── classified/
│   ├── images/
│   ├── metadata/
│   ├── tables/
│   └── text/
├── chunk_outputs/
│   └── <document_id>/
│       ├── summary.json
│       ├── tables.json
│       ├── images.json
│       └── methods/
│           ├── fixed_size.json
│           ├── token_based.json
│           ├── sentence_based.json
│           ├── paragraph_based.json
│           ├── recursive.json
│           ├── sliding_window.json
│           ├── semantic.json
│           └── structure_section.json
├── vector_store/
│   └── <document_id>/
│       ├── summary.json
│       ├── fixed_size/            (index.faiss + metadata.json)
│       ├── token_based/           (index.faiss + metadata.json)
│       ├── sentence_based/        (index.faiss + metadata.json)
│       ├── paragraph_based/       (index.faiss + metadata.json)
│       ├── recursive/             (index.faiss + metadata.json)
│       ├── sliding_window/        (index.faiss + metadata.json)
│       ├── semantic/              (index.faiss + metadata.json)
│       ├── structure_section/     (index.faiss + metadata.json)
│       ├── tables/                (index.faiss + metadata.json)
│       └── images/                (metadata.json)
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── documents.py
│   │   │   ├── chunks.py
│   │   │   ├── embeddings.py
│   │   │   ├── search.py
│   │   │   └── rag.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   └── logging_config.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── document.py
│   │   │   ├── classification.py
│   │   │   ├── chunking.py
│   │   │   ├── embeddings.py
│   │   │   ├── search.py
│   │   │   └── rag.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── semantic_search.py
│   │   │   ├── context_builder.py
│   │   │   ├── gemini_service.py
│   │   │   └── rag_service.py
│   │   ├── extraction/
│   │   │   ├── __init__.py
│   │   │   ├── pdf_extractor.py
│   │   │   ├── text_extractor.py
│   │   │   ├── table_extractor.py
│   │   │   ├── image_extractor.py
│   │   │   ├── ocr_processor.py
│   │   │   └── storage.py
│   │   ├── classification/
│   │   │   ├── __init__.py
│   │   │   ├── classifier.py
│   │   │   ├── table_refiner.py
│   │   │   ├── deduplicator.py
│   │   │   ├── boilerplate_detector.py
│   │   │   ├── image_classifier.py
│   │   │   └── storage.py
│   │   ├── chunking/
│   │   │   ├── __init__.py
│   │   │   ├── text_chunkers.py
│   │   │   ├── table_chunker.py
│   │   │   ├── image_chunker.py
│   │   │   ├── stats.py
│   │   │   ├── storage.py
│   │   │   └── pipeline.py
│   │   ├── embeddings/
│   │   │   ├── __init__.py
│   │   │   ├── embedder.py
│   │   │   └── pipeline.py
│   │   └── vectorstore/
│   │       ├── __init__.py
│   │       └── faiss_store.py
│   └── tests/
│       ├── __init__.py
│       ├── test_api.py
│       ├── test_extraction.py
│       ├── test_classification.py
│       ├── test_chunking.py
│       ├── test_chunk_visualization_api.py
│       ├── test_embeddings.py
│       ├── test_semantic_search.py
│       └── test_rag.py
└── frontend/
    ├── index.html
    ├── package.json
    ├── package-lock.json
    ├── postcss.config.js
    ├── tailwind.config.js
    ├── tsconfig.json
    ├── tsconfig.app.json
    ├── tsconfig.node.json
    ├── vite.config.ts
    └── src/
        ├── App.tsx
        ├── index.css
        ├── main.tsx
        ├── vite-env.d.ts
        ├── types/
        │   └── document.ts
        ├── services/
        │   └── api.ts
        ├── pages/
        │   └── IngestionPage.tsx
        └── components/
            ├── FileUpload.tsx
            ├── DocumentSummaryCards.tsx
            ├── ExtractionPreview.tsx
            ├── ClassificationPreview.tsx
            ├── PhaseRoadmapBanner.tsx
            ├── SemanticSearchPanel.tsx
            ├── RagChatbotPanel.tsx
            └── chunks/
                ├── ChunkVisualizationPanel.tsx
                ├── TextChunkCard.tsx
                ├── TableChunksView.tsx
                └── ImageChunksView.tsx
```

---

## 21. Technology Stack (Verified from Project Files & Environment)

### Frontend (`frontend/package.json`)
- **React:** `18.3.1` (`react-dom` `18.3.1`)
- **TypeScript:** `~5.6.2`
- **Vite:** `5.4.11` (`@vitejs/plugin-react` `4.3.3`)
- **Tailwind CSS:** `3.4.15` (`postcss` `8.4.47`, `autoprefixer` `10.4.20`)
- **Recharts:** `2.13.3` (installed `2.15.4`)
- **Lucide React:** `0.460.0`

### Backend (`backend/requirements.txt` & `backend/.venv`, Python `3.13.3`)
- **FastAPI:** `0.165.0`
- **Uvicorn:** `0.54.0`
- **Pydantic / Pydantic-Settings:** `2.14.4` / `2.16.3`
- **python-multipart:** `0.0.34`
- **python-dotenv:** `1.2.4`
- **PyMuPDF:** `2.1` (primary PDF, text, table, and image extractor)
- **pdfplumber:** `0.11.11` (table fallback and Phase 3 table spacing comparison/refinement)
- **Pillow:** `13.0.0` (image integrity verification and PNG/JPEG conversion)
- **RapidOCR / ONNX Runtime:** `3.10.0` / `1.32.0` (default pure-Python OCR fallback)
- **pytesseract:** `0.3.13` (optional OCR backend when Tesseract binary is installed)
- **NumPy:** `2.5.5` (used for lightweight TF-IDF cosine similarity in Phase 4 semantic chunking)
- **Sentence Transformers:** `6.3.0` (`sentence-transformers/all-MiniLM-L6-v2` embeddings in Phase 6)
- **FAISS:** `faiss-cpu` `1.16.0` (local `IndexFlatIP` vector storage in Phase 6 & search in Phase 7)
- **PyTorch / Transformers:** `2.15.0` / `5.24.1` (runtime backend for Sentence Transformers)
- **Google Gen AI SDK:** `google-genai` `3.6.1` (`gemini-3.6-flash` grounded answer generation in Phase 8)
- **pytest / httpx / httpx2:** `9.2.0` / `0.28.1` / `2.16.2`

---

## 22. Troubleshooting & Lessons Learned

1. **`httpx2` Requirement for Starlette/FastAPI `TestClient`:** FastAPI `0.165.0` / Starlette `1.10.0` emitted a deprecation warning and required `httpx2` (`2.16.2`) for `TestClient`; added `httpx2>=2.0.0` to `backend/requirements.txt`.
2. **Windows `asyncio` Loopback in Restricted Sandbox:** Running `TestClient` or `uvicorn` inside a network-restricted Windows sandbox stalls on Python's internal `asyncio` loopback `socketpair()`. API tests and local dev servers should run normally outside network-restricted sandboxes.
3. **Table Cell Spacing Differences (PyMuPDF vs `pdfplumber`):** PyMuPDF merged spaces in TGD9 cells (`"MitigatedorUnmitigated"`, `"$104800 - ,"`), whereas `pdfplumber` preserved `"Mitigated or Unmitigated"` and `"-$104,800"`. Adding generic quality scoring (`score_table_quality`) in `table_refiner.py` automatically selects the cleaner extraction.
4. **Table Text Duplication:** Raw text extraction captured table cell text inside table regions. Comparing text `bbox` overlap (`>= 0.60`) plus normalized cell-text matching cleanly removes duplicates while keeping captions and footnotes.
5. **Repeated Headers, Footers & Logos:** Margin-band repetition checks flagged all 10 banners and 10 page numbers (`is_boilerplate`), while SHA-256 occurrence + margin checks flagged all 10 repeated CCAC header logos (`is_decorative`) without hiding the 5 Exhibit photos.
6. **Section-Heading Leakage:** Multi-line blocks initially hid subheadings (`Introduction`, `Description of Source`) while caption fragments (`Scenario)`) and table headers leaked into `section_heading`. Line-level bold-heading splitting in `text_extractor.py` and non-table heading propagation in `classifier.py` resolved this cleanly.
7. **Frontend Build & Package Adjustments:** Fixed `postcss` from `^10.4.47` to `^8.4.47` for `autoprefixer` peer compatibility, and added `frontend/src/vite-env.d.ts` for `import.meta.env` TypeScript support.
8. **OCR Package Update:** Replaced outdated `rapidocr-onnxruntime>=1.3.24` with `rapidocr>=2.0.0` + `onnxruntime>=1.19.0` and updated `ocr_processor.py` to read `RapidOCROutput.txts`.

