# Document Processing Platform — v2.2.0

Product & Project Definition Document (PDD)

**Document type:** Combined Product Design + Project Definition Document
**Project:** DPP — Document Processing Platform
**Domain:** Indian IT / Logistics Distribution
**Version:** 2.2.0
**Date:** March 2026
**Status:** Active Development

---

## Version History

The platform evolved across 7 distinct phases. Each phase is a working codebase preserved on disk at `E:\PROJECTS\Experiments\Logistic\`.

---

### Phase 1.0 — Document Platform v1.0
**Folder:** `phase 1.0/` and `b2b-document-connector/`
**Stack:** FastAPI + PostgreSQL + React + Vite + TypeScript. Single Docker image (Nginx + Uvicorn).

The first working version. Organised around a **Case** (linked to an Opportunity ID). All 6 document types could be uploaded under a case.

**What was built:**
- Case management (create, search by Opportunity ID, status: OPEN / IN_PROGRESS / CLOSED)
- Document upload for all 6 types: CUSTOMER_PO, VENDOR_INVOICE, VENDOR_DC, COMPANY_INVOICE, COMPANY_DC, POD
- NAS-based file storage at `/nas/cases/{CASE_ID}/`
- SHA-256 duplicate detection — re-uploading the same file was blocked
- PDF inline preview and download in-browser
- PDF rotation (90° / 180° / 270°) with cumulative angle tracking
- Document type checklist — shows which of the 6 types are still missing per case
- Audit log for all actions (upload, delete, rotate, view)
- Admin health check + stats dashboard

**Not yet built:**
- No Sales Order (SO) concept — all documents were flat under a Case
- No AI extraction — documents stored as files only, no metadata extracted
- No cross-document validation
- No user authentication

---

### Phase 1.1 — Document Platform v1.1
**Folder:** `Phase 1.1/`
**Stack:** Same as 1.0. Added dev container support (`.devcontainer/`).

Introduced the **Sales Order (SO)** as a first-class entity. The document hierarchy changed from flat (Case → Documents) to hierarchical (Case → SO → Documents).

**What was built:**
- `SalesOrder` model — globally unique SO numbers, month locked at creation (format: `YYYY-MM`)
- Two tiers of documents: CUSTOMER_PO attached to Case; all other types (VENDOR_DC, VENDOR_INVOICE, COMPANY_DC, COMPANY_INVOICE, POD) attached to a specific SO
- Per-SO document checklist — each SO tracks its own 5 missing types
- SO search — global search by SO number across all cases
- Month-based filtering — filter documents within a case by SO month
- Storage hierarchy updated: `/nas/cases/{CASE_ID}/{SO_MONTH}/SO-{SO_NUMBER}/{DOC_TYPE}/`
- Audit log upgraded to JSONB (structured details instead of plain strings)
- Month picker UI component for SO creation and filtering

**Not yet built:**
- No AI extraction
- No automatic SO generation from Customer PO
- No cross-document validation (no check that DC references the correct SO)
- No user authentication

---

### Phase 2.0 — Document Platform v2.0 (First AI Extraction)
**Folder:** `Phase 2.0/`
**Stack:** FastAPI + PostgreSQL + React. Added remote OCR via GLM-OCR (RunPod). Extraction still synchronous (no Celery).

The first version with **AI-powered data extraction**. Documents were no longer just stored files — they were processed by a vision model to extract structured metadata.

**What was built:**
- `DocumentMetadata` model — stores extracted JSONB data, primary reference number, document date, confidence score, extraction status (PENDING → EXTRACTED → VERIFIED), raw OCR text
- Single-layer OCR pipeline: PDF → images → GLM-OCR (vision model) → structured JSON
- 4-strategy JSON parser (direct parse → code blocks → brace extraction → clean-and-retry) for robust LLM output handling
- Human verification workflow — operator reviews extracted fields, edits if needed, then marks Verified
- Reject workflow — operator can send back to PENDING for re-extraction
- Force re-extraction endpoint — clear old metadata and re-run OCR
- JSONB metadata search — search across any extracted field value
- PURCHASE_BILL added as a 7th document type
- Prod Docker Compose (`docker-compose.prod.yml`) for first time

**Not yet built:**
- No Celery / async task queue — extraction blocked the request thread
- No chain completeness tracking (no % score)
- No Customer master data — customer stored as free text on Case
- No user authentication
- Two-layer pipeline (qwen2.5:7b not yet added)

---

### Phase 2.1 — DocPlatform V3 (Architecture Refactor)
**Folder:** `Phase 2.1/docplatform-v3/`
**Stack:** FastAPI (async) + PostgreSQL + Redis + Celery + React. Complete architecture rewrite.

The most significant architectural jump. Replaced the Case + Sales Order hierarchy with a **PurchaseOrder-centric model** matching how the business actually works. Added Customer master data, async extraction, and the foundation for cross-document validation.

**What was built:**
- `Customer` model — master data (name, GST number, contact, business ID format `XXX-XXXXXXXX`)
- `PurchaseOrder` model — replaces Case + SO. Fields: po_number, po_date, total_amount, status (INITIATED → IN_PROGRESS → NEAR_COMPLETE → COMPLETE → CANCELLED), chain_completeness (0.0–1.0)
- `ReferenceIndex` — denormalized lookup table mapping any reference number (invoice #, DC #, PO #) back to its document and PO. Enables fast cross-document search.
- `User` model — JWT-based authentication with roles (ADMIN / USER / VIEWER)
- Celery async extraction — documents extracted in background, API returns immediately
- 6 document statuses: UPLOADED → EXTRACTING → PENDING_REVIEW → VERIFIED (or EXTRACTION_FAILED / REJECTED)
- Multi-page OCR — all pages processed, results merged (first non-null field wins)
- Chain completeness % calculated automatically on every verification
- Global search across customers, POs, and documents via ReferenceIndex
- Advanced search — filter by invoice number, DC number, PO number, SO number, customer name, date range, document type
- UUID primary keys throughout (replacing integer PKs)
- Dashboard, Customer list, PO list, PO detail, Search — all implemented

**Not yet built:**
- Two-layer OCR pipeline (still single GLM-OCR layer)
- Cross-document SO validation (ReferenceIndex foundation laid but validation logic not written)
- PENDING_MODEL status

---

### Phase 2.1.0 — DocPlatform V3 (Two-Layer OCR)
**Folder:** `Phase 2.1.0/docplatform-v3/`
**Stack:** Same as 2.1. Added `qwen2.5:7b` as Layer 2.

Built on Phase 2.1. The key addition: a **configurable two-layer OCR pipeline** where GLM-OCR handles the vision-to-text step and qwen2.5:7b handles the text-to-JSON extraction step. Added VRAM management to run both models sequentially on a 6GB GPU.

**What was built:**
- Two-layer extraction pipeline: Layer 1 (glm-ocr → Markdown) + Layer 2 (qwen2.5:7b → structured JSON)
- VRAM release between layers — explicit unload of Layer 1 model before loading Layer 2 (fits both on RTX 3050 6GB)
- Circuit breaker — after 5 consecutive OCR failures, halt for 60 seconds before retrying
- Retry with exponential backoff — 5s / 10s between attempts
- Confidence scoring — fill-rate based (% of expected fields extracted)
- Debug markdown saving — OCR output saved to disk for troubleshooting
- Benchmark suite — `e2e_test.py`, `compare_ocr_layer.py`, `e2e_full_report.py` for measuring extraction speed and accuracy per model
- `setup_glm.ps1` / `start.ps1` for local dev startup on Windows
- `Modelfile.glm` — custom Ollama model configuration

**Not yet built:**
- SO number cross-document validation (still not implemented)
- PENDING_MODEL document status
- Admin requeue endpoint
- Docker Compose production setup

---

### v2.2.0 — DPP (Document Processing Platform)
**Folder:** `DPP 2.2.0/`
**Stack:** Same as Phase 2.1.0. Stable, fully tested, running locally.

Built on Phase 2.1.0. This version cleaned up the codebase, stabilised the extraction pipeline, and added the first cross-document validation logic.

**What was added over Phase 2.1.0:**
- `PENDING_MODEL` document status — separates endpoint/model availability issues from document-level extraction failures. Documents are held in this state when the OCR service is unreachable rather than marked as EXTRACTION_FAILED
- Pre-flight model check in Celery task — before attempting extraction, verify OCR endpoint responds; if not, set PENDING_MODEL instead of wasting attempts
- `POST /admin/requeue-pending-models` endpoint — operator can manually re-queue all PENDING_MODEL documents once the OCR service is restored
- SO number cross-document validation (backend) — `so_validator.py` compares extracted SO number against the PO's stored SO; injected into Celery extraction task for COMPANY_DC and COMPANY_INVOICE; mismatch routes document to PENDING_REVIEW with error detail; `PATCH /purchase-orders/{id}` stores the SO number; `requires_so_entry` flag returned from verify endpoint. Note: frontend SO entry prompt not yet built — validation logic exists but is not yet triggered from the UI
- COMPANY_PO renamed from PURCHASE_BILL to match the actual business terminology
- Alembic migration for PENDING_MODEL enum value added to PostgreSQL

**Stable baseline.** All 6 document types working. Chain completeness tracking live. Human review workflow complete.

---

### v2.3.0 — DPP (Production Hardening)
**Branch:** `DPP-2.3.0`

Built on v2.2.0. Focus: production-ready Docker deployment for on-prem Linux server.

**What was added:**

- Multi-stage `backend/Dockerfile` (API target + Celery worker target in one file)
- Multi-stage `frontend/Dockerfile` (build → nginx runtime)
- `docker-compose.prod.yml` — 6-service production stack: postgres, redis, backend, worker ×2, frontend, nginx
- `nginx/nginx.conf` — reverse proxy: `/api/` → backend:8000, `/` → frontend:80
- Rewrote initial Alembic migration to use `postgresql.ENUM(create_type=False)` — fixes duplicate enum error on fresh DB with asyncpg driver
- Fixed Celery worker module path (`celery_app` not `app.celery_app`)
- Replaced `window.confirm()` delete modal with custom React confirmation dialog
- Fixed nginx upstream staleness after backend container restart
- COMPANY_PO extraction prompt corrected (was designed for Purchase Bill; actual document is Vendor PO with Order No `1PTR...`)
- Operator Remarks field added to Review and Edit modals
- Ad-hoc Custom Fields added to Review and Edit modals (free-text label + value, any document type)

**Verified working (Docker Compose, local):**
- All 6 Alembic migrations applied on fresh PostgreSQL
- All containers healthy
- All pages load: Dashboard, Customers, POs, PO Detail, Documents, Search, Admin
- All API endpoints returning 200
- Celery extraction pipeline live with RunPod OCR endpoint
- Admin health check: DB ✅ Redis ✅ Storage ✅ Ollama ✅

Each version is a checkpoint in git. v2.2.0 is the stable baseline; v2.3.0 is the active development branch (branch: `DPP-2.3.0`).

---

## 1. Project Overview

The Document Processing Platform (DPP) is an internal web application built for Indian IT and logistics distribution companies to manage the complete document chain associated with each Purchase Order. It replaces fragmented manual workflows (ERP entries + physical files + WhatsApp) with a single, AI-powered platform that extracts, validates, and tracks all logistics documents from receipt to completion.

---

## 2. Stakeholders and Users

| Role | Who | What they need |
| ---- | --- | -------------- |
| Operations Staff | Data entry / admin team | Upload documents, verify extracted data, track status |
| Logistics Manager | Team lead / supervisor | Real-time visibility across all POs and document chains |
| Management | Director / owner | High-level summary — what is pending, what is complete |
| Developer | Internal / contracted | Maintain, extend, and deploy the platform |

---

## 3. Problem Statement — As-Is (Current State)

### How the team works today

The company currently uses **.Net based ERP** as the primary accounting and procurement system. Documents flow through the business but the system has significant gaps in visibility and traceability.

### Current document flow

```text
Customer sends PO
      |
      v
Staff receives via email / WhatsApp / physical copy
      |
      v
Data manually entered into ERP (PO number, amounts)
      |
      v
Physical or scanned document saved to a local folder
(naming convention varies by staff member)
      |
      v
Vendor documents (DC, Invoice) arrive separately
      |
      v
Staff matches them manually to the original PO
      |
      v
Company issues its own DC and Invoice
      |
      v
All documents exist in separate places —
ERP has the financial data, folders have the files,
no single place ties them together
```

### Pain points identified

| Pain Point | Impact |
| ---------- | ------ |
| **No real-time visibility** | Management cannot see which POs are fully documented without asking staff |
| **Document chain is fragmented** | ERP has financial data but actual document files are in folders with no structured link to the PO |
| **No chain completeness tracking** | No system checks whether all 6 document types exist for a PO — gaps discovered only during audits or disputes |
| **Manual data extraction** | Staff re-types reference numbers, dates, and amounts from scanned documents into ERP — error-prone and slow |
| **Search is difficult** | Finding a specific invoice or DC requires navigating folder structures or scrolling ERP entries |
| **No cross-document validation** | Nobody checks whether the SO number on the Company DC matches the one generated for that Customer PO — mismatches go unnoticed |

---

## 4. Proposed Solution — To-Be (Future State)

### How the team works with DPP

```text
Customer sends PO (PDF or scan)
      |
      v
Staff uploads to DPP — takes 10 seconds
      |
      v
AI extracts all fields automatically (two-layer OCR)
glm-ocr reads the document → qwen2.5:7b structures the data
      |
      v
Staff reviews extracted data on screen — corrects if needed
One click to verify
      |
      v
System prompts: "Enter SO number for this PO"
SO stored — all future documents validated against it
      |
      v
Vendor documents uploaded as they arrive
Auto-extracted, auto-validated against PO reference
      |
      v
Company DC and Invoice uploaded
SO number auto-checked — mismatch flagged immediately
      |
      v
Chain completeness updates in real time (0% → 100%)
Management sees live dashboard — no need to ask staff
      |
      v
Any document findable in seconds via search or filter
```

### What changes

| Before (As-Is) | After (To-Be) |
| -------------- | ------------- |
| Documents in scattered folders | All files linked to a PO in one place |
| Data re-typed into ERP manually | AI extracts fields automatically |
| Chain status unknown until asked | Live chain completeness bar per PO (0–100%) |
| No cross-document validation | SO number auto-validated across COMPANY_DC and COMPANY_INVOICE |
| Management asks staff for status | Dashboard shows all pending, extracting, verified counts live |
| Finding old documents is slow | Full-text search + filter by type, date, customer |
| Extraction failures silent | Admin console shows exact error and where to fix it |

### What does NOT change

- .Net based ERP continues as the accounting system — DPP complements it, not replaces it
- Staff still reviews extracted data — human verification step is kept intentionally
- Physical document storage at the company — DPP stores digital copies alongside

---

## 5. Document Types and Business Flow

DPP manages 6 document types per Purchase Order, representing the complete logistics chain:

| # | Document Type | Direction | Primary Key | When it appears |
| - | ------------- | --------- | ----------- | --------------- |
| 1 | CUSTOMER_PO | Customer → Company | `po_number` | Start of chain — customer sends purchase order |
| 2 | COMPANY_PO | Company → Vendor | `po_number` | Company orders from vendor to fulfil |
| 3 | VENDOR_DC | Vendor → Company | `dc_number` | Vendor dispatches goods |
| 4 | VENDOR_INVOICE | Vendor → Company | `invoice_number` | Vendor bills the company |
| 5 | COMPANY_DC | Company → Customer | `dc_number` | Company dispatches to customer — contains SO number |
| 6 | COMPANY_INVOICE | Company → Customer | `invoice_number` | Company bills the customer — contains SO number |

### Chain completeness score

Each PO has a `chain_completeness` score from 0.0 to 1.0:

- Each verified document contributes ~0.167 (1/6)
- Failed or rejected documents do not count
- Score shown as a progress bar on every PO card

### SO Number flow

```text
Customer PO received
      ↓
ERP generates SO internally — never printed on vendor-facing documents
      ↓
Against the SO, ERP generates Vendor PO number (e.g. 1PTR2526000467)
Vendor PO sent to vendor — vendor sees only the VPO number, not the SO
      ↓
Vendor DC + Vendor Invoice → both reference the VPO number
ERP: VPO number → SO → Customer PO → Customer (all tracked inside ERP)
      ↓
Company DC → prints Customer Order No (CPO) + Sales Order No (SO)
Company Invoice → prints Customer Order No (CPO) + ref (not the VPO number)
```

The SO number appears **only** on Company DC and Company Invoice. It does not appear on the Vendor PO, Vendor DC, or Vendor Invoice — those use the VPO number instead.

---

### 5.4 Document Flow by Order Type

Orders fall into three types with different document chain requirements.

| Document | Trade / Software | Services (AMC, Cloud) | Stock / Inventory |
| -------- | ---------------- | --------------------- | ----------------- |
| Customer PO | Required | Required | Required |
| SO (internal) | Required | Required | Required |
| Vendor PO | Required | Required | Not applicable |
| Vendor DC | Required | If applicable | Not applicable |
| Vendor Invoice | Required | Required | Not applicable |
| Company DC | Required | If applicable | Required |
| Company Invoice | Required | Required | Required |
| POD | Required | Required | Required |

> **Services:** Vendor DC and Company DC are not always generated — the chain is complete without them.
> **Stock/Inventory:** Item fulfilled from stock — entire vendor procurement block is skipped.

#### Type 1 — Trade / Software (Full Chain)

```mermaid
flowchart LR
    A["Customer PO"] --> B["SO Generate"]
    B --> C["Vendor PO"]
    C --> D["Vendor DC"]
    D --> E["Vendor Invoice"]
    E --> F["Company DC"]
    F --> G["Company Invoice"]
    G --> H["POD"]

    style A fill:#4A90D9,color:#fff
    style B fill:#4A90D9,color:#fff
    style C fill:#E07B39,color:#fff
    style D fill:#E07B39,color:#fff
    style E fill:#E07B39,color:#fff
    style F fill:#5BA85A,color:#fff
    style G fill:#5BA85A,color:#fff
    style H fill:#2ECC71,color:#fff
```

#### Type 2 — Services / AMC / Cloud (DC Optional)

```mermaid
flowchart LR
    A["Customer PO"] --> B["SO Generate"]
    B --> C["Vendor PO"]
    C --> D["Vendor DC\n(if applicable)"]
    D --> E["Vendor Invoice"]
    E --> F["Company DC\n(if applicable)"]
    F --> G["Company Invoice"]
    G --> H["POD"]

    style A fill:#4A90D9,color:#fff
    style B fill:#4A90D9,color:#fff
    style C fill:#E07B39,color:#fff
    style D fill:#E07B39,color:#fff,stroke-dasharray:5 5
    style E fill:#E07B39,color:#fff
    style F fill:#5BA85A,color:#fff,stroke-dasharray:5 5
    style G fill:#5BA85A,color:#fff
    style H fill:#2ECC71,color:#fff
```

#### Type 3 — Stock / Inventory (No Vendor Block)

```mermaid
flowchart LR
    A["Customer PO"] --> B["SO Generate"]
    B --> F["Company DC"]
    F --> G["Company Invoice"]
    G --> H["POD"]

    style A fill:#4A90D9,color:#fff
    style B fill:#4A90D9,color:#fff
    style F fill:#5BA85A,color:#fff
    style G fill:#5BA85A,color:#fff
    style H fill:#2ECC71,color:#fff
```

> **Current gap:** Chain completeness % treats all 6 document types equally for all order types. A future `order_type` flag on the PO will allow correct per-type calculation.

---

### 5.5 Purchase Order Scenarios — CPO : SO : VPO

The Sales Order (SO) is generated internally when a Customer PO is received. All Vendor POs are raised against the SO. The SO:VPO relationship is **many-to-many** in reality.

| CPO | SO | VPO | Description |
| --- | -- | --- | ----------- |
| 1 | 1 | 1 | Standard — single vendor, single delivery |
| 1 | 1 | Many | Multi-vendor — items sourced from multiple vendors |
| 1 | Many | Many | Split delivery — customer PO fulfilled in batches |
| Many | Many | 1 | Bulk procurement — one vendor PO covers multiple customer SOs |
| Many | Many | Many | Multiple independent customer orders |

> **Current gap:** The `purchase_orders` table stores one `so_number` per PO — assumes 1:1 between PO and SO. Multi-vendor and split delivery scenarios cannot be tracked. Future fix: `SalesOrder` entity + `SOVendorPOLink` join table.

---

### 5.6 Billing Scenarios

| Type | Description | Typical Order |
| ---- | ----------- | ------------- |
| Full billing | Single invoice for the entire PO amount | Trade / Software / Stock |
| Partial billing | Invoice per batch / per delivery | Split delivery |
| Recurring — vendor recurs | Both vendor and company bill per cycle | Cloud subscriptions |
| Recurring — vendor one-time | Vendor billed once; company bills periodically | AMC contracts |

**Billing frequencies for recurring:** Monthly / Quarterly / Half-yearly / Yearly

> **Current gap:** No `billing_type`, `billing_frequency`, or `contract_duration` fields in the data model. Recurring billing cycles cannot be tracked or auto-generated.

---

### 5.7 Delivery Location

Delivery address is one of the fields extracted from documents. The Customer PO contains the Ship To address (where goods should be delivered), and the Company DC contains the delivery address confirming where goods were dispatched. Address text is stored in `extracted_data` JSON — there is no dedicated structured column for it yet.

| Scenario | Description |
| --- | --- |
| Same site | Billing address and delivery address are the same |
| Different site | Customer PO specifies a Ship To address different from billing address |
| Multi-site | Customer wants items delivered to multiple locations — separate DC per site |
| Drop-ship | Vendor ships directly to customer's site, bypassing company warehouse |

---

## 6. Feature Scope

### Implemented (v2.2.0 — v2.3.0)

- Customer and PO management (CRUD)
- Document upload — PDF, PNG, TIFF
- Two-layer AI extraction (glm-ocr + qwen2.5:7b)
- Human review and verification workflow
- Chain completeness tracking per PO
- PENDING_MODEL status + pre-flight OCR check + admin requeue
- Dashboard — pipeline overview + top 10 pending queue
- Full-text search and reference number lookup
- PDF in-browser preview and download
- Re-extraction and manual data entry fallback
- Filter system on PO list — date range, SO number, sort, chain completeness, missing doc type
- Documents page — cross-PO list filterable by type, status, customer
- Admin console — system health, pipeline counters, failure diagnostics, Celery queue status
- Operator Remarks and Ad-hoc Custom Fields in Review / Edit modals

### Partially Working

- SO number cross-document validation — backend complete (validator, Celery injection, PATCH endpoint); frontend SO entry prompt not yet built

### Pending — not yet implemented

- Frontend SO entry prompt after CUSTOMER_PO verify
- JPEG file support (currently only PDF, PNG, TIFF accepted)
- Signed POD / Acknowledgement (7th document type)
- Audit trail (who verified what, when)
- Multi-user authentication and RBAC

### Out of scope — planned for future versions

- .Net based ERP two-way sync
- Bulk document upload
- Email / WhatsApp automatic ingestion
- Mobile app
- Single vision model pipeline (qwen2-vl:7b — planned for v3.0)
- Multi-company / multi-branch support

---

## 7. Technical Architecture

### Stack

| Layer | Technology |
| ----- | ---------- |
| Backend API | FastAPI (Python 3.12), async |
| Task Queue | Celery + Redis broker |
| Database | PostgreSQL 16, SQLAlchemy async ORM |
| Frontend | React 18 + TypeScript + Vite + TanStack Query |
| OCR Layer 1 | `glm-ocr:latest` via Ollama — image to Markdown |
| OCR Layer 2 | `qwen2.5:7b` via Ollama — Markdown to structured JSON |
| OCR Hosting | RunPod remote endpoint (current) / local Ollama (dev) |
| File Storage | Local filesystem (NAS-mountable path) |

### Development hardware

| Resource | Spec |
| -------- | ---- |
| CPU | Intel Core i5-13450HX |
| RAM | 16 GB |
| GPU | NVIDIA RTX 3050 6GB VRAM (laptop) |
| OCR | RunPod remote — offloads GPU from dev machine |

### Extraction pipeline

```text
PDF / image upload
      |
      v
Celery async task (non-blocking)
      |
      v
Layer 1 — glm-ocr:latest
  Convert pages to images (PyMuPDF, 200 DPI, max 768px)
  Each page sent to Ollama vision model
  Output: raw Markdown preserving tables and layout
      |
      v
Layer 2 — qwen2.5:7b
  Markdown + document-type-specific JSON schema prompt
  Output: structured JSON with all extracted fields
      |
      v
Validation
  Invoice math check (line items × qty vs total)
  SO number cross-check (COMPANY_DC, COMPANY_INVOICE)
  Errors stored in extracted_data._validation_errors
      |
      v
Status → PENDING_REVIEW
Operator reviews, corrects, and verifies
```

**On failure:** full exception string stored in `DocumentMetadata.last_error`, status set to `EXTRACTION_FAILED`, partial data preserved for review.

---

## 8. Deployment Plan

### Phase 1 — Development (current)

- Dev machine: FastAPI on port 8000, React on port 5173
- PostgreSQL + Redis via Docker Compose
- OCR on RunPod remote endpoint (local Ollama optional)

### Phase 2 — On-Prem Deployment (planned)

- Customer's server or company intranet Linux machine
- All 6 services via Docker Compose: postgres, redis, backend, worker ×2, frontend, nginx
- OCR via local Ollama (on-prem, no external dependency) or RunPod fallback
- GPU-capable server recommended: NVIDIA T4 or equivalent (16GB VRAM), both models loaded simultaneously

### Branch strategy

```text
dev   → local development (unstable, experimental)
main  → production releases (tagged snapshots)
```

---

## 9. Known Limitations and Risks

| Item | Detail | Mitigation |
| ---- | ------ | ---------- |
| OCR quality on bad scans | glm-ocr can struggle with blurry, rotated, or very low-res phone photos | Re-upload with better scan; rotation tool built in |
| RunPod dependency | If RunPod endpoint goes down, all extraction stops | Admin console flags Ollama health in real time; local Ollama fallback available |
| No user authentication | Any user on the network can access and modify data | Acceptable for internal single-team use; auth planned for v3.0 |
| VRAM constraint (dev) | RTX 3050 6GB requires sequential model unloading between layers | RunPod handles OCR in dev; not a constraint on cloud deployment |
| No audit trail | No record of who verified or corrected a document | Planned for v3.0 with user login system |
| Celery solo pool (Windows dev) | Single-threaded task execution | Linux deployment uses standard Celery pool |
| ERP not connected | Verified extracted data stays in DPP, not synced to ERP | Manual cross-reference required until integration is built in future version |

---

## 10. Glossary

| Term | Meaning |
| ---- | ------- |
| PO | Purchase Order |
| DC | Delivery Challan |
| SO | Sales Order number — generated internally, links outgoing company documents |
| Chain completeness | 0.0–1.0 score showing how many of the 6 document types are verified for a PO |
| PENDING_REVIEW | Document extracted, waiting for operator to verify |
| EXTRACTION_FAILED | AI extraction crashed — error stored, needs re-upload or manual entry |
| Layer 1 | glm-ocr — converts document image to Markdown text |
| Layer 2 | qwen2.5:7b — converts Markdown to structured JSON |
| RunPod | Remote GPU cloud hosting the Ollama models |
| ERP | .Net based Enterprise Resource Planning system used for accounting, procurement, and invoicing |

---

*This document reflects DPP v2.2.0 as of March 2026.*
*Next major version (v3.0) targets: single-model pipeline, user authentication, ERP integration.*
