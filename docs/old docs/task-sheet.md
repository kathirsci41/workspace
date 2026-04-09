# DPP Project Task Sheet

---

## 2026-03-11

- Explored full codebase — models, services, API, extraction pipeline
- Identified cross-document validation gap (SO number never validated across documents)
- Designed SO Number Cross-Document Validation feature plan
- Designed Filter System Expansion plan (PO List + new Documents page)
- Designed Admin Console page plan

---

## 2026-03-16

- Implemented `PENDING_MODEL` document status
- Added pre-flight model/endpoint check to Celery extraction task
- New `POST /admin/requeue-pending-models` endpoint to re-queue held documents
- DB migration: added `PENDING_MODEL` to `documentstatus` enum

---

## 2026-03-17

### Production Docker Setup

- Created multi-stage `backend/Dockerfile` (api + worker targets)
- Created `frontend/Dockerfile` (build + nginx runtime)
- Created `docker-compose.prod.yml` (6 services: postgres, redis, backend, worker×2, frontend, nginx)
- Created `nginx/nginx.conf` (reverse proxy: `/api/` → backend, `/` → frontend)

### Bugs Fixed

| Bug | Fix |
| --- | --- |
| `npm ci` failed — lockfile mismatch | Changed to `npm install` in frontend Dockerfile |
| Alembic initial migration crashed on fresh DB (tried to ALTER non-existent tables) | Rewrote `upgrade()` to CREATE all tables from scratch |
| `sa.Enum(create_type=False)` not respected by asyncpg — duplicate enum error | Switched to `postgresql.ENUM(create_type=False)` |
| Celery worker couldn't find `app.celery_app` module | Fixed path to `celery_app` |
| nginx 502 after container restarts (stale upstream) | `docker restart app-nginx-1` after each backend restart |
| `window.confirm` for document delete silently blocked by browser over HTTP | Replaced with custom confirmation modal |

### Verified Working (Docker Compose)

- All 6 Alembic migrations applied on fresh DB
- All containers healthy (postgres, redis, backend, worker×2, frontend, nginx)
- All pages load: Dashboard, Customers, Purchase Orders, PO Detail, Documents, Search, Admin
- All API endpoints: GET/POST customers, POs, documents, admin health/stats/queue
- Celery workers: both running, extraction pipeline live
- Health check: DB ✅ Redis ✅ Storage ✅ Ollama ✅ Models ✅

---

## 2026-03-18

### PDD Documentation — Business Domain Sections

Added new sections to `docs/PDD.md` covering business domain knowledge:

- **Section 7.4 — Document Flow by Order Type**
  - Document requirement matrix (Trade/Software, Services, Stock/Inventory)
  - Three Mermaid flowcharts — one per order type
  - Gap note: chain completeness does not yet respect order type rules

- **Section 7.5 — Purchase Order Scenarios (CPO:SO:VPO)**
  - SO as backbone explanation
  - CPO:SO:VPO relationship matrix (1:1:1, 1:1:Many, 1:Many:Many, Many:Many:Many)
  - Architectural gap: current model assumes 1:1; future fix: `SOVendorPOLink` join table

- **Section 7.6 — Billing Scenarios**
  - Full / Partial / Recurring billing types
  - Billing vs document chain table
  - Architectural gap: no `billing_type` / `billing_frequency` fields

### PDD Documentation — Root `PDD.md` Version History

- Explored actual codebases in `E:\PROJECTS\Experiments\Logistic\` (7 folders)
- Wrote comprehensive version history from Phase 1.0 (Jan 2026) to DPP 2.3.0 (Mar 2026)
- Added Sections 5.4–5.6 to root `PDD.md` (order types, PO scenarios, billing)

---

## 2026-03-19

### PDD Documentation — Delivery Location (Section 7.7)

- Added Section 7.7 to `docs/PDD.md` — Pan India delivery location context
- Document fields: Customer PO `ship_to_address`, Company DC `delivery_address`, Vendor DC `delivery_address`
- Delivery scenarios table (same-state, inter-state, multi-site, drop-ship)
- Current state: address captured in `extracted_data` JSON — not a structured field yet
- Updated Section 8.2 Capability Matrix with delivery location rows
- Updated Section 8.3 Roadmap Gaps
- Added Section 5.7 to root `PDD.md`

### PDD Documentation — Full Rework of Sections 9–19 (`docs/PDD.md`)

Replaced stale v0.1 artifacts with accurate v2.3.0 content:

| Section | Before | After |
| --- | --- | --- |
| 9 Scope & Phasing | 3-row table | Original plan + actual 7-phase path + next phase backlog |
| 10 Functional Requirements | 9 FRs, wrong statuses | 5 sub-tables, 24 FRs, all statuses correct |
| 11 NFRs | 7 rows | 10 rows, 3 new NFRs added, statuses updated |
| 12 Data Model | v0.1 entities (Case, CaseDocumentLink) | Actual v2.3.0 tables + status lifecycle diagram |
| 13 Solution Options | Mostly correct | Zoho CRM removed |
| 14 Technical Architecture | 6-line stub | Full system diagram, component table, pipeline detail, deployment |
| 15 Implementation Plan | Original 1-week MVP plan (never executed) | Actual 7-phase development history |
| 16 Risks | NAS-era risks | Actual running-system risks (OCR, VRAM, no auth, ERP) |
| 17 Open Questions | All unanswered v0.1 questions | Separated: resolved vs still open |
| 18 Acceptance Criteria | NAS portal criteria | Split: Already Met / Not Yet Met |
| 19 Implementation Status | Sparse list | Full working feature list + pending list |

### PDD Corrections (both `docs/PDD.md` and `PDD.md`)

- **FR-05 Preview:** Marked ✅ — PDF preview and download already implemented
- **Zoho CRM:** Removed from all sections (Business Context, Stakeholders, AS-IS, options, roadmap)
- **Delivery location:** Extract-only — removed GST cross-validation, IGST/CGST inference, e-Way Bill flagging (not in scope)
- **CI/CD:** Removed — on-prem application; deployment section rewritten for Docker Compose on-prem
- **Staging references:** Removed — Azure VM / staging mentions removed throughout
- **Tally → .Net based ERP:** All instances replaced in both PDD files

### NAS Integration — Confirmed Already Supported

- `StorageService` (`backend/app/services/storage_service.py`) already built around `nas_base_path`
- No code changes needed — set `NAS_BASE_PATH` in `.env` to the NAS mount point
- Docker volume bind in `docker-compose.prod.yml` maps to NAS mount on the server

### COMPANY_PO Extraction Fix

**Problem:** Prompt was designed for a Purchase Bill (looking for `purchase_bill_no` `1PBTR...`). Actual document is the Vendor PO Skylark sends to vendor (Order No `1PTR...`) — completely different.

**`backend/app/services/extraction/prompts.py`**

- New schema: `po_number` (Order No), `po_date` (Order Date), `mode_of_bill`, `vendor_name`
- Primary field changed: `purchase_bill_no` → `po_number`
- Date field added: `po_date` (was empty)
- Searchable fields: `po_number` + `vendor_name` (was `purchase_bill_no` + `po_number` + `bill_no`)

**`frontend/src/components/ReviewModal.tsx`**

- `FIELD_ORDER[COMPANY_PO]` → `['po_number', 'po_date', 'mode_of_bill', 'vendor_name']`
- Removed labels: `purchase_bill_no`, `bill_no`; added `mode_of_bill`
- `DOC_LABEL_OVERRIDES[COMPANY_PO]`: `po_number → 'Order No'`, `po_date → 'Order Date'`

### Review / Edit Modal Enhancements

**`frontend/src/components/ReviewModal.tsx`**

**Operator Remarks field:**

- `Remarks` textarea always visible at bottom of both Review and Edit modals
- Saved as `operator_notes` in `extracted_data`
- Persists across sessions; shows ✎ when modified

**Ad-hoc Custom Fields:**

- **"+ Add Field"** button adds a row with free-text Label + Value inputs + × delete button
- Operator can add, edit, delete any number of custom fields per document
- Works on all 6 document types
- Saved as `custom_<label>` in `extracted_data` (e.g. `custom_Serial No: "SN-001"`)
- Persists — existing custom fields load pre-filled when modal reopens
- Included in both Verify and Save Changes flows
- `custom_*` keys excluded from the AI-extracted fields display

### Logging System Upgrade

**`backend/app/logging_config.py`**

- Added `_UTF8StreamHandler` — forces UTF-8 on stdout to prevent `UnicodeEncodeError` on Windows cp1252 terminals
- Fixed `→` in log message to `->` (cp1252 cannot encode the arrow character)
- Fixed app catch-all logger to route to `file_{component}` instead of hardcoded `file_app`

**`backend/celery_app.py`**

- Added `after_setup_logger` signal — suppresses `celery.worker` / `celery.utils.timer2` DEBUG timer spam after Celery's own logging init
- Added `task_failure` signal — logs full traceback on Celery task failure
- Added `task_retry` signal — logs retry reason

**`backend/app/database.py`**

- Added `pool_recycle=300` — fixes intermittent "connection is closed" errors from PostgreSQL closing idle connections
- Added `pool_pre_ping=True`

**`start.ps1`**

- Replaced `Receive-Job` stdout polling (2s interval) with log file tail loop at 200ms
- Backend/Celery now streams from `app.log` / `celery.log` in real time

### Business PDD (`docs/PDD.md`) — Cleanup

- Removed Section 12.3 (Original Design v0.1), Section 14 (Technical Architecture), Section 15 (Development History)
- Renumbered: Risks → 14, Open Questions → 15, Acceptance Criteria → 16, Implementation Status → 17
- Fixed FR-31 and FR-32 statuses to ✅
- Fixed Section 12.1: removed `Table` column, plain descriptions only
- Added Section 6.1 header + new Section 6.2 Document Traceability Chain (AS-IS): forward flow, reference table, ERP pain + DPP solution
- Added Manual Entry fallback user journey to Section 8
- Split "Manual review" bullet in Section 8.1 into three: AI review, Manual Entry fallback, Custom Fields
- Added FR-17 (Manual Entry ✅) and FR-18 (Custom Fields ✅) to Section 10.2
- Expanded Section 17 What's Working with plain business descriptions for Remarks, Custom Fields, Manual Entry

---

## 2026-03-20

### Business PDD (`docs/PDD.md`) — Refinements and Alignment Fixes

- Refined Section 6.2 flow into three named parts: **Forward (creation)**, **Match (vendor → customer)**, **Outward (billing)**
- Version History: added v2.2.0 row (2026-03-14 — Production baseline: PENDING_MODEL, SO validation, admin requeue)
- Section 16 Acceptance Criteria "Already Met": added Manual Entry and Custom Fields
- Section 8.2 Multi-Vendor row: removed `` `po_reference` `` code reference
- FR-20 status cell: replaced developer notes with one plain business sentence

### Full PDD Review

**Business PDD** — full document reviewed, all sections confirmed accurate and aligned

**Technical PDD (`PDD.md`)** — full document reviewed, 5 issues identified (not yet fixed):

1. Header + footer still say v2.2.0 — should be v2.3.0
2. Section 5 numbering jumps from 5 to 5.4 (5.1–5.3 missing)
3. File format contradiction — Technical PDD says PNG supported; Business PDD NFR-10 says PNG rejected
4. PENDING_MODEL not defined in Section 10 Glossary
5. Dev port in Section 8 says 5173 — actual port is 5174

---

### UX — PDF Zoom (Preview, Review, Edit panels)

**Problem:** PDF displayed in browser `<iframe>` — zoom only via toolbar buttons; no scroll or pinch zoom.

**Fix:**

- Installed `react-pdf` (v10.4.1, pdfjs-dist backed)
- Created new shared component `frontend/src/components/PDFViewer.tsx`
  - `Ctrl + scroll wheel` → zoom in/out
  - Two-finger pinch on touchpad → zoom in/out (touchpad pinch fires `ctrlKey: true` wheel events — no extra handling needed)
  - +/− buttons + reset in a thin toolbar
  - Rotate button (90° CW per click, resets on document change)
  - Scale range 50%–300%, proportional step per scroll delta
  - Window-level wheel guard prevents browser page zoom when hovering PDF panel
  - Multi-page scroll (all pages rendered, scroll between them naturally)
- Replaced `<iframe>` in `PDFPreviewPanel.tsx` and `ReviewModal.tsx` with `<PDFViewer>`

---

### Decision — Version & Change Tracking

- **Approach:** Git + `docs/CHANGELOG.md`
- Git commits provide full timestamped diff history; `CHANGELOG.md` provides human-readable session summaries
- Going forward: every session that modifies a PDD or makes a significant change adds a dated entry to `docs/CHANGELOG.md`
- PDD files themselves stay content-only — no revision log inside them

---

### Performance — Latency Fixes

**Admin page:**

- `health_check`: parallelised 4 checks via `asyncio.gather()` + Redis cache (30s TTL)
- `get_stats`: 8 sequential queries → single `COUNT(CASE ...)` query
- `get_queue`: Celery inspect via `ThreadPoolExecutor(max_workers=3)`

**Frontend polling (AdminPage):**

- All fetches accept `AbortSignal`, cancelled on unmount
- Intervals raised: active 10s→30s, queue 15s→30s, health/stats→60s
- Smart poll: active documents only fetched when queue shows work

**DB index:**

- Added `idx_document_status` on `documents.status` (Alembic migration `c5d3e9f2a1b8`)

---

### Global Toast System

**Problem:** Only PODetailPage had extraction toasts; network/server errors were silent.

**Fix:**

- Created `frontend/src/context/ToastContext.tsx` — global `useToast()` hook + `ToastStack` UI
- Updated `frontend/src/main.tsx` — wrapped `<App>` with `<ToastProvider>`
- Updated `frontend/src/api/client.ts` — response interceptor raises toasts for network down, 502/503/504, 5xx
- Updated `frontend/src/pages/PODetailPage.tsx` — migrated local toast state to `useToast()`; covers EXTRACTION_FAILED, PENDING_MODEL, mixed, complete, verify, save, re-extract, manual entry

**Toast scenarios covered:**

| Trigger | Type | Message |
| --- | --- | --- |
| Extraction complete | success | "Extraction complete — documents are ready to review." |
| Extraction failed | error | "Extraction failed — open the document to enter manually." |
| Mixed complete/failed | warn | "Extraction finished — one or more documents need attention." |
| PENDING_MODEL | warn | "AI model unavailable — document will retry when service is back." |
| Verify | success | "Document verified and saved." |
| Save changes | success | "Changes saved successfully." |
| Re-extract triggered | info | "Re-extraction queued." |
| Manual entry saved | info | "Manual entry saved." |
| 502/503/504 | error | Server detail if present, else "Extraction service unreachable…" |
| 5xx other | error | "Server error — please try again." |
| Network down | error | "Connection lost — check your network." |

---

### NAS — Option A: Check on Upload

**Problem:** If NAS is unreachable during upload, the server crashes with an unhandled `OSError` and the user sees a generic "Server error" toast.

**Fix:**

- `backend/app/services/storage_service.py` — added `NASUnavailableError` exception + `check_accessible()` method (checks `os.path.isdir` + `os.access(W_OK)`) + `OSError` guard in `save_file()`
- `backend/app/services/document_service.py` — catches `NASUnavailableError`, raises `HTTPException(503, detail="Storage unavailable — please check the storage status.")`
- `frontend/src/api/client.ts` — 503 handler uses `error.response.data.detail` when present

---

---

## 2026-03-23

### Branch Strategy Finalised

| Branch | Role |
| --- | --- |
| `master` | Stable production baseline |
| `staging` | Demo-ready — frozen at DPP-2.4.0 tag |
| `development` | Active development — next version |

- `staging` branch created from `DPP-2.4.0` tag and pushed to GitHub
- `development` branch created for next version work
- README updated to v2.4.0 (ports, model names, features, branch table)

### Planned — PO Profile Page (development branch)

**Feature:** Consolidated read-only profile view for a Purchase Order.

**Problem:** No single page shows all extracted data across all 6 document types. Operators must open each Review modal individually to see any extracted field.

**Solution:** New page at `/purchase-orders/:id/profile` showing:

- Header: PO number, customer, SO number, chain %, status, dates
- Per-document sections (6 slots): all extracted fields in a key-value grid, status badge, confidence %, Preview + Download links
- Discrepancy panel: SO mismatches, missing po_reference flags, cross-reference map
- Order timeline: uploaded → extracted → verified events per document

**Files:** 14 files (4 create, 10 modify) — no DB migrations, no new models

**Entry point:** "View Profile" button added to PODetailPage header

---

## 2026-03-24

### PO Profile Page — Implemented (development branch)

#### Backend

- Created `backend/app/schemas/po_profile.py` — `POProfileDocumentSlot`, `POProfileDiscrepancy`, `POProfileTimelineEvent`, `POProfileResponse`
- Added `get_po_profile()` to `backend/app/services/po_service.py` — reuses `get_po()` eager-load, zero extra DB queries
  - Builds 6 slots in chain order, "empty" status when no document
  - Discrepancy checks: SO_MISMATCH (error), MISSING_PO_REF and PO_REF_MISMATCH (warning)
  - Timeline: uploaded / extracted / verified / rejected events across all documents, sorted ascending
  - Cross-reference map: `po_ref_no` values grouped by doc type
- Added `GET /api/v1/purchase-orders/{id}/profile` route to `purchase_orders.py` — declared before `/{po_id}/documents` to prevent URL collision

#### Frontend

- Added 4 TypeScript interfaces to `frontend/src/types/index.ts`: `POProfileDocumentSlot`, `POProfileDiscrepancy`, `POProfileTimelineEvent`, `POProfile`
- Added `getPOProfile()` to `frontend/src/api/purchaseOrders.ts`
- Added `usePOProfile()` hook to `frontend/src/hooks/usePurchaseOrders.ts` — lazy fetch with `staleTime: 30_000`
- Created `frontend/src/components/ProfileDocumentSection.tsx` — card with left accent border, field grid, per-field confidence colours, Preview + Download links, empty slot placeholder
- Created `frontend/src/components/ProfileTimeline.tsx` — vertical dot-line timeline, colour-coded dots per event type
- Created `frontend/src/components/ProfileDiscrepancyPanel.tsx` — all-clear green banner or error/warning rows, cross-reference table
- Created `frontend/src/pages/POProfilePage.tsx` — single-column layout, header card (PO details + ChainStatusBar), discrepancy panel, 6 document sections, timeline
- Added route `/purchase-orders/:id/profile` to `frontend/src/App.tsx` (before `/:id` route)
- Added "View Profile" button to `PODetailPage` header (alongside Delete PO)

#### Documentation

- Updated `docs/CHANGELOG.md` — added DPP-2.5.0 entry

---

## 2026-03-25

### Startup & Process Fixes

- **Duplicate Python process root cause** — Windows venv `python.exe` is a launcher stub (274 KB, imports only `KERNEL32.dll`); it spawns the actual interpreter via `pyvenv.cfg → home` and waits. Normal Windows venv behavior, not a bug.
- **`start.ps1` rewritten** — replaced `Start-Job` with `Start-Process powershell -NoExit -Command` to open Backend, Celery, Frontend, Docker each in a dedicated terminal window
- **`start.ps1` parse error fixed** — em dash characters (U+2014) in string literals caused PowerShell 5.1 `MissingArgument` parse error; replaced all 4 em dashes with ASCII hyphens

### Logging Fixes

- **`_UTF8StreamHandler.handleError()` override** — `StreamHandler.emit()` catches `ValueError` internally and calls `handleError()` which printed `--- Logging error ---` tracebacks; fixed by overriding `handleError()` to suppress `ValueError`/`OSError`
- **`--- Logging error ---` spam on `/admin/queue` fixed** — lazy `from celery_app import celery_app` inside route handler triggered `setup_logging("celery")` mid-request on first call; moved import to module level

### Dependency Fix

- **`pdfplumber` added to `requirements.txt`** — was imported in `digital_extractor.py` but missing; installed `pdfplumber==0.11.9`

### Layer 2 Extraction — Model & Config

**Problem:** `qwen2.5:7b` consistently timed out (HTTP 524, Cloudflare 100s limit) on RunPod for 7-page documents

**Root cause in `_estimate_num_predict`:** formula `ceiling = num_ctx - 2048` produced `num_predict=6144` at `num_ctx=8192` → too slow; at `num_ctx=4096` → only 2048 tokens left for input → document truncated → 2 fields, 0% confidence

**Fix sequence:**

| Step | Change | Result |
| --- | --- | --- |
| 1 | `num_ctx=4096` | Still 524 → then truncated JSON at 88s |
| 2 | Fixed formula (always return `floor`), restored `num_ctx=8192` | JSON truncated mid-array (2048 tokens insufficient output) |
| 3 | Pulled `qwen2.5:3b` (1.9 GB) on RunPod; `num_predict=3000` | **HTTP 200, 17s, 60% confidence** ✓ |
| 4 | `num_predict=4096` | More headroom for large arrays |

**Files changed:** `backend/app/services/extraction/tasks.py`, `.env`

### Model Research

- Compared `phi4-mini:3.8b`, `llama3.2:3b`, `gemma3:4b`, `mistral:7b` for Layer 2
- Researched user-provided: `dots.mocr` (3B, single-pass OCR + extraction, vLLM), `olmOCR-2-7B` (SOTA OCR only, Allen AI)
- **Recommendation:** Test `phi4-mini:3.8b` next; consider `dots.mocr` long-term (replaces both layers)

---

## Pending / Next

- Test `phi4-mini:3.8b` on RunPod — compare field coverage vs `qwen2.5:3b`
- Fix Technical PDD (`PDD.md`) — 5 identified issues (version, section numbering, file formats, glossary, port)
- SO Number cross-document validation — frontend prompt after CUSTOMER_PO verify
- Multi-user authentication and RBAC
- .Net ERP integration
- Long-term: evaluate `dots.mocr` (3B) as single-pass replacement for both OCR layers
