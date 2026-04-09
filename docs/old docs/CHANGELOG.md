# Changelog — Document Processing Platform (DPP)

All notable changes are recorded here by version. Dates reflect the session when changes were made.

---

## [DPP-2.5.1] — 2026-03-25 *(development)*

### Fixed

- **`start.ps1` rewritten** — replaced `Start-Job` with `Start-Process powershell -NoExit` to open Backend, Celery, Frontend, Docker each in dedicated terminal windows; eliminates system Python process leakage
- **`start.ps1` parse error** — em dash characters (U+2014, 3-byte UTF-8) in string literals caused PowerShell 5.1 `MissingArgument` error at parse time; replaced all with ASCII hyphens
- **`--- Logging error ---` spam** — `_UTF8StreamHandler.handleError()` override added to suppress `ValueError`/`OSError` from closed stream; lazy `from celery_app import celery_app` inside `/admin/queue` route moved to module level
- **`pdfplumber` missing from `requirements.txt`** — was imported in `digital_extractor.py` but absent; added `pdfplumber>=0.11.0`
- **`_estimate_num_predict` formula** — `ceiling = num_ctx - 2048` produced `num_predict=6144` at default context (too slow for Cloudflare proxy) or truncated document input at low context; simplified to return configured `floor` value directly

### Changed

- **Layer 2 model: `qwen2.5:7b` -> `qwen2.5:3b`** — consistent HTTP 524 timeouts on RunPod (Cloudflare 100s limit); 3b model responds in 17s vs 88-130s; same model family, same prompts
- **`.env`**: `OCR_EXTRACTOR_MODEL=qwen2.5:3b`, `OCR_EXTRACTOR_NUM_CTX=8192`, `OCR_EXTRACTOR_NUM_PREDICT=4096`
- **Extraction confidence**: 0% -> 60% on CUSTOMER_PO after model + config fix

### Research

- Evaluated `phi4-mini:3.8b`, `llama3.2:3b`, `gemma3:4b` as Layer 2 alternatives
- Evaluated `dots.mocr` (3B, unified OCR + extraction, single pass) and `olmOCR-2-7B` (Allen AI SOTA OCR) as architecture candidates

---

## [DPP-2.5.0] — 2026-03-24 *(development)*

### Added

- **PO Profile Page** — `/purchase-orders/:id/profile` — consolidated read-only view of all extracted data for a PO
  - 6 document section cards: all extracted fields, per-field confidence colours, status badges, extraction route
  - Discrepancy panel: SO number mismatches (error), missing/mismatched PO references (warning); all-clear banner when clean
  - Order timeline: chronological events (uploaded -> extracted -> verified) per document, colour-coded dots
  - Cross-reference map: what each document references
  - Chain status bar reconstructed from profile data — no extra API call needed
  - Preview and Download links per document slot
- **"View Profile" button** in PO Detail page header — navigates to the profile page
- New backend endpoint: `GET /api/v1/purchase-orders/{id}/profile`
- New Pydantic schema: `POProfileResponse` (slots, discrepancies, timeline, cross_references)

---

## [DPP-2.4.0] — 2026-03-20

### Features

- **PDF Viewer** — Replaced `<iframe>` with `react-pdf` based `PDFViewer` component
  - Ctrl + scroll wheel zoom, two-finger touchpad pinch zoom
  - +/- toolbar buttons, rotation (90 deg CW per click, resets on document change)
  - Window-level wheel guard prevents browser page zoom when hovering PDF panel
  - Applies to both PDFPreviewPanel and ReviewModal
- **Global Toast Notifications** — App-wide toast system via `ToastContext`
  - Covers: extraction complete, failed, mixed, PENDING_MODEL, verify, save, re-extract, manual entry
  - Axios response interceptor: network down, 502/503/504, 5xx errors
  - 503 handler uses server `detail` message when present
- **NAS Error Handling (Option A)** — Check on upload
  - `NASUnavailableError` exception + `check_accessible()` in `StorageService`
  - Upload returns HTTP 503 with clear message if NAS is unreachable
- **Collapsible Sidebar** — Icon-only by default, expands on demand

### Performance

- `admin/health`: parallel checks via `asyncio.gather()` + Redis cache (30s TTL)
- `admin/stats`: 8 sequential queries replaced with single `COUNT(CASE ...)` query
- `admin/queue`: Celery inspect parallelised via `ThreadPoolExecutor(max_workers=3)`
- AdminPage: `AbortController` on unmount, raised poll intervals, smart poll when queue empty
- Alembic migration `c5d3e9f2a1b8`: `idx_document_status` index on `documents.status`

### Fixes

- **COMPANY_PO extraction schema** corrected — was targeting purchase bill fields; now extracts `po_number`, `po_date`, `mode_of_bill`, `vendor_name` (Order No / Order Date format)
- **Backend logging** — UTF-8 stream handler for Windows cp1252 terminals; Celery timer spam suppressed; task failure/retry signals added
- **Connection pooling** — `pool_recycle=300`, `pool_pre_ping=True` to fix idle connection drops
- **start.ps1** — Log file tail at 200ms replaces `Receive-Job` polling

### Tests

- 274 tests total (232 backend + 42 frontend), all passing
- New: `tests/backend/test_admin_helpers.py` — 11 tests for admin health cache, stats shape, storage check

---

## [DPP-2.3.0] — 2026-03-17

### Features

- **Docker Production Stack** — `docker-compose.prod.yml` with 6 services: postgres, redis, backend, worker x2, frontend, nginx
- **PENDING_MODEL Status** — New document status separating model/endpoint unavailability from extraction failures
- **Admin Requeue Endpoint** — `POST /admin/requeue-pending-models` re-enqueues held documents
- **Pre-flight Model Check** — Extraction task checks model availability before starting; sets `PENDING_MODEL` if offline
- **Operator Remarks** — Free-text `operator_notes` field always visible in Review/Edit modals
- **Custom Fields** — "Add Field" button in Review/Edit modals; stored as `custom_*` in `extracted_data`; persists across sessions

### Fixes

- Alembic initial migration rewritten to `CREATE TABLE` from scratch (fixes fresh DB installs)
- `postgresql.ENUM(create_type=False)` to prevent duplicate enum error on retry
- Celery worker module path corrected (`celery_app` not `app.celery_app`)
- nginx 502 upstream stale connection resolved
- `window.confirm` replaced with custom modal for document delete (blocked over HTTP)
- Logging config: fixed `->` arrow for cp1252 terminals; app catch-all routes to correct log file

### Tests

- Backend: 221 tests passing
- Frontend: 42 tests passing

---

## [DPP-2.2.0] — 2026-03-14

Baseline version — full working application as of project folder creation.

### Features

- **6-Document Chain** — CUSTOMER_PO, COMPANY_PO, VENDOR_DC, VENDOR_INVOICE, COMPANY_DC, COMPANY_INVOICE per PO
- **Two-Layer AI Extraction** — GLM-OCR (image -> Markdown) + Qwen2.5:7b (Markdown -> structured JSON)
- **Hybrid Router** — Digital PDF fast path (no GPU) vs. scanned path (full OCR pipeline)
- **SO Number Validation** — COMPANY_DC and COMPANY_INVOICE validated against stored SO number
- **Chain Completeness** — 0-100% score per PO, drives status progression
- **Human Review Workflow** — Operators verify or correct extracted fields; audit trail via `ExtractionCorrection`
- **Version-Safe Re-extraction** — Increments `extraction_version` instead of deleting; preserves corrections
- **Filter System** — PO List: date range, SO search, chain completeness, missing doc type, sort options
- **Documents Page** — Cross-PO document search by type, status, customer, date range
- **Admin Console** — Live health check (DB/Redis/Ollama/Storage), pipeline stats, Celery queue status
- **Global Search** — Full-text + reference number lookup via `ReferenceIndex` table
- **PDF Preview** — In-browser viewer, download
- **Manual Entry** — Operators can enter data manually when extraction fails

### Infrastructure

- FastAPI + PostgreSQL (async/sync split) + Redis + Celery
- NAS storage via `StorageService` (`NAS_BASE_PATH`)
- `start.ps1` — one-command Windows dev startup

---

## [DPP-2.1.0] — 2026-03-11 *(historical)*

- Full codebase explored and capability analysis completed
- Cross-document validation gap identified
- Filter system and Documents page designed
- Admin Console page designed

---

## [DPP-1.x -> 2.0.x] — 2026-01-01 to 2026-03-10 *(historical)*

Early phases — see `PDD.md` Version History (Section 2) for full detail.
