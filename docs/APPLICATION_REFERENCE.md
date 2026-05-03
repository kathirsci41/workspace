# Document Processing Platform V3.0 — Application Reference

> Single authoritative reference. Every section contains exact column names, field names,
> endpoint paths, parameter names, service function signatures, and TypeScript interfaces
> directly from the source code. Nothing is summarised or abbreviated.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Infrastructure](#3-infrastructure)
4. [Configuration — config.py and .env](#4-configuration)
5. [Database Schema](#5-database-schema)
6. [API Reference — All 7 Routers](#6-api-reference)
7. [Backend Services](#7-backend-services)
8. [Extraction Pipeline — Deep Dive](#8-extraction-pipeline)
9. [Chain Validation System](#9-chain-validation-system)
10. [Frontend Architecture](#10-frontend-architecture)
11. [Frontend Pages](#11-frontend-pages)
12. [Frontend Components](#12-frontend-components)
13. [TypeScript Types](#13-typescript-types)
14. [Data Flow Diagrams](#14-data-flow-diagrams)
15. [Known Issues — from Code Review](#15-known-issues)

---

## 1. Project Overview

**Application name:** Document Processing Platform V3.0
**FastAPI title:** `"Document Platform V3.0"`
**Version string:** `"3.0.0"`
**Version label in UI:** `v2.2.0`

**Business domain:** Indian IT/logistics distribution. The company (Skylark Information Technologies) acts as a middle distributor:
- Receives purchase orders from enterprise customers (CUSTOMER_PO)
- Issues its own POs to vendors (COMPANY_PO)
- Receives delivery challans and invoices from vendors (VENDOR_DC, VENDOR_INVOICE)
- Issues delivery challans and invoices to customers (COMPANY_DC, COMPANY_INVOICE)

**Core problem solved:** Every sale produces 6+ documents that must be cross-validated.
Wrong SO numbers, billing mismatches, missing documents, and reference discrepancies
are discovered manually today. This platform automates extraction, cross-validation,
and completeness tracking.

**Phase 1 (current):** Manual data entry + rules-based validation + AI OCR extraction.
**Phase 2 (planned):** Full AI line-item matching, address normalisation, LayoutLMv3 fine-tuning.

---

## 2. Architecture

### 2.1 Architectural Pattern

**Modular Monolith + Background Worker.**

All synchronous business logic runs in a single Python process (FastAPI/uvicorn).
Celery workers are separate OS processes sharing the same codebase and database, but isolated from the API process by Redis message passing.

This is intentionally **not microservices**. Reasons:
- 2-person team, single business domain, predictable scale (hundreds of POs, not millions)
- Shared SQLAlchemy models + a single PostgreSQL instance are simpler than a distributed data layer
- Extraction latency is acceptable as async background work, not a streaming requirement

**Boundaries that are enforced:**
- Celery ↔ FastAPI: communicated only via Redis tasks + PostgreSQL state; no shared in-process state
- Provider layer: all LLM transport behind `Layer1Provider` / `Layer2Provider` interfaces in `providers/base.py`
- Storage: all file I/O behind `storage_service.py`; no direct path construction outside that module

**Boundaries that are NOT enforced:**
- Python services import each other freely (e.g., `po_service` imports `chain_validator`)
- No module-level dependency graph — no circular-import protection beyond Python's own checks

### 2.2 System Topology

```
┌────────────────────────────────────────────────────────────────┐
│             FRONTEND (React 18 + Vite + TypeScript)            │
│  10 pages, Axios API client, TanStack Query (server state)      │
│  frontend/src/pages/   frontend/src/components/                 │
└────────────────────────────┬───────────────────────────────────┘
                              │ HTTP REST + SSE  (Vite proxy → :8002)
┌────────────────────────────▼───────────────────────────────────┐
│           FASTAPI BACKEND (Python 3.12, Uvicorn :8002)         │
│  Middleware: CORS only (no auth)   Entry: backend/app/main.py  │
│  7 Routers: customers | purchase_orders | documents |          │
│             extraction | search | admin | chat                 │
│  13 Services: backend/app/services/                            │
│  Schemas:    backend/app/schemas/                              │
│  DB Session: asyncpg (FastAPI) + psycopg2 (Celery, separate)  │
└──────┬────────────────┬──────────────────┬─────────────────────┘
       │                │                  │
 ┌─────▼──────┐  ┌──────▼───────┐  ┌──────▼──────┐
 │ PostgreSQL │  │    Redis     │  │ NAS Storage │
 │  :5434 dev │  │  :6380 dev   │  │ PDF files   │
 │  :5432 prod│  │ Celery broker│  │ Layout:     │
 │            │  │ result back. │  │ {cust_id}/  │
 │ SQLAlchemy │  │ item-match   │  │ {po_number}/│
 │ 2 pools    │  │ cache (1h)   │  │ {uuid}_.pdf │
 └────────────┘  └──────┬───────┘  └─────────────┘
                        │
                 ┌──────▼───────┐
                 │ CELERY WORKER│
                 │ solo pool    │
                 │ task:        │
                 │ extract_doc  │
                 └──────┬───────┘
                        │
           ┌────────────▼────────────┐
           │   EXTRACTION PIPELINE   │
           │   pipeline.py           │
           │   HybridRouter          │
           │   Layer 1 (OCR)         │
           │   Layer 2 (extraction)  │
           └────────────┬────────────┘
                        │
          ┌─────────────▼──────────────┐
          │   AI MODEL ENDPOINT        │
          │ • Ollama local :11434      │
          │ • RunPod remote HTTPS      │
          │ • OpenAI-compat endpoint   │
          │ • Datalab cloud API        │
          └────────────────────────────┘
```

### 2.3 Layered View

| Layer | Path | Responsibility |
|---|---|---|
| Presentation | `frontend/src/pages/`, `frontend/src/components/` | React SPA — renders state, user interactions |
| API | `backend/app/api/v1/*.py`, `backend/app/schemas/` | Request validation, routing, response shaping |
| Service | `backend/app/services/*.py` | Business logic — no HTTP, no ORM column access outside here |
| Data | `backend/app/models/`, `backend/alembic/` | SQLAlchemy ORM definitions, schema migrations |

**Cross-cutting concerns** (not in any one layer):
- `backend/app/logging_config.py` — structured logging setup
- `backend/app/config.py` — all settings via pydantic-settings from `.env`
- `backend/app/services/storage_service.py` — NAS file I/O
- `backend/app/database.py` — two DB engines (async + sync)

### 2.4 Process Topology and Failure Modes

Five independent processes. Failure of each has different blast radius:

| Process | Command | Responsibility | Blast radius when down |
|---|---|---|---|
| uvicorn (FastAPI) | `uvicorn app.main:app --port 8002` | All HTTP + SSE | Full API unavailable |
| Celery worker | `celery -A celery_app worker` | Extraction background jobs | New extractions queue; in-flight re-queued via `task_acks_late=True` |
| PostgreSQL | docker compose | All durable state | API + worker both down until restored |
| Redis | docker compose | Celery broker + result backend + item-match cache | Extractions halt; API reads/writes still work |
| Ollama / RunPod | external | LLM inference (OCR + extraction + chat) | Extractions fail with `PENDING_MODEL`; API otherwise healthy |

**Recovery path for Ollama outages:** documents are marked `PENDING_MODEL` (not `EXTRACTION_FAILED`). `POST /admin/requeue-pending` bulk-requeues them when models come back online. See §7 Admin router and §8 Known Issues.

### 2.5 Request Lifecycles

**1. Sync CRUD (e.g., `POST /purchase-orders`)**
```
React (axios)
  → FastAPI router (purchase_orders.py)
  → po_service.create_po()
  → async SQLAlchemy INSERT
  → PostgreSQL
  → JSON response
```
No Celery, no LLM, no file I/O. Typical latency: <50ms.

**2. Async Extraction (e.g., upload + extract a document)**
```
React → POST /api/v1/purchase-orders/:id/documents
          ↓ storage_service saves PDF to NAS
          ↓ documents row created (status=PENDING)
        POST /api/v1/extract/:doc_id
          ↓ Celery task queued (extract_document)
          ↓ [Celery worker picks up task]
          ↓ HybridRouter: digital PDF or scanned?
             ├── digital: DigitalExtractor (PyMuPDF, no GPU)
             └── scanned: pdf_converter → scan_preprocessor
                          → ocr_client (glm-ocr, Layer 1)
                          → [release VRAM]
                          → two_layer_client (gemma4, Layer 2)
          ↓ field_validator, invoice_validator, so_validator
          ↓ document_metadata row + reference_index populated
          ↓ po_service.update_chain_completeness()
React polls GET /api/v1/metadata/:doc_id until status ≠ PROCESSING
```
Latency: 10–90 seconds depending on scan quality and model.

**3. Streaming Chat (`GET /api/v1/chat/stream`)**
```
React (EventSource SSE)
  → FastAPI SSE endpoint (chat.py)
  → chat_service.stream_chat_response()
  → _detect_intent(): order_query / search_query / platform_query / general
  → context builder (chat_context.py): queries DB for PO/document data
  → Ollama /api/chat (qwen2.5:3b, streaming=True)
  → SSE data: frames → React appends tokens in real time
```

### 2.6 Key Design Decisions

| ID | Decision | Rationale |
|---|---|---|
| D1 | **Provider abstraction** (`providers/base.py`) | `Layer1Provider` / `Layer2Provider` interfaces isolate all transport. New provider = one file. Switching = `.env` change only. |
| D2 | **Dual DB engine** (`database.py`) | asyncpg cannot run in synchronous Celery context. Two separate engine pools prevent event-loop conflicts. |
| D3 | **VRAM release between layers** | RTX 3050 6GB cannot hold glm-ocr (vision) and gemma4 (text) simultaneously. `release_vram()` + `wait_until_ready()` called explicitly between Layer 1 and Layer 2. |
| D4 | **Scenario-aware chain** (`chain_validator.py`) | Required documents differ by order type — a fixed 6-doc chain would permanently mark most real orders incomplete. UNKNOWN scenario defaults to requiring all 6 to prevent false COMPLETE. |
| D5 | **Two extraction failure states** | `PENDING_MODEL` = infrastructure problem (model offline). `EXTRACTION_FAILED` = document problem (corrupt scan). Admin bulk-requeue targets only `PENDING_MODEL`. |
| D6 | **Non-blocking validation errors** | Invoice math errors and SO mismatches are stored in `extracted_data._validation_errors`, not hard-failing extraction. Operators need partial data even when wrong. |
| D7 | **Extraction versioning** | Re-extraction increments `extraction_version` on the `documents` row rather than deleting. Preserves audit trail of re-processing events. |
| D8 | **Digital PDF fast path** | If `pypdfium2` extracts >50 characters of text, route to `DigitalExtractor` (no GPU). ERP-generated PDFs skip OCR entirely and process 5–10× faster. |

### 2.7 Scalability and Known Limits

**Current defaults (development/demo):**
- Celery `--pool=solo` — one extraction at a time; a 90-second scan blocks all other extractions
- Single uvicorn worker process
- Ollama on one local GPU (RTX 3050 6GB VRAM)

**Production changes required:**
- `celery -A celery_app worker --pool=gevent --concurrency=8` (I/O-bound tasks benefit from gevent)
- Multiple uvicorn workers: `uvicorn ... --workers=4` or gunicorn with uvicorn workers
- Remote Ollama cluster or RunPod: set `OCR_BASE_URL` in `.env`

### 2.8 Security Posture (Current State)

No authentication or RBAC. Every API endpoint is publicly accessible.

| Issue | Scope |
|---|---|
| No auth middleware | All 7 routers open — any HTTP client can read/write data |
| Admin endpoints unguarded | `POST /admin/requeue-pending` can bulk-mutate state |
| Document preview/delete by ID | Any caller who knows a UUID can download or delete |
| `verify=False` on provider HTTP | TLS certificate validation disabled on some Ollama provider calls |
| CORS: `allow_origins=settings.cors_origins` | Configured via `.env`; defaults to localhost only in dev |

**Treat as LAN-only** until auth/RBAC is added. Auth design is tracked at `docs/superpowers/plans/` — not yet implemented.

### 2.9 What Is Deliberately NOT in the Architecture

- No authentication or RBAC (planned, not built)
- No event bus / message broker for reads (only Celery for extraction tasks)
- No CQRS / event sourcing
- No multi-tenancy
- No GraphQL
- No WebSocket — only SSE for chat streaming; all other real-time patterns use frontend polling
- No service mesh or sidecar proxies
- No distributed tracing (structured logs only)

---

## 3. Infrastructure

### 3.1 Docker Compose (docker-compose.dev.yml)

```yaml
services:
  postgres:
    image: postgres:16
    ports: ["5434:5432"]          # host:container
    environment:
      POSTGRES_USER: docplatform
      POSTGRES_PASSWORD: docplatform
      POSTGRES_DB: docplatform

  redis:
    image: redis:7-alpine
    ports: ["6380:6379"]          # host:container
```

### 3.2 Backend

**Start command:** `uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload`
**Python version:** 3.12
**Entry point:** `backend/app/main.py`
**Application object:** `app = FastAPI(title="Document Platform V3.0", version="3.0.0")`
**CORS:** configured via `settings.cors_origins` list; methods=`["*"]`; headers=`["*"]`
**Global exception handler:** all unhandled exceptions return `{"detail": "Internal server error"}` with status 500
**Health probe:** `GET /` → `{"status": "ok", "app": "Document Platform V3.0"}`

### 3.3 Frontend

**Start command:** `npm run dev` (from `frontend/`)
**Dev port:** 5174
**Build tool:** Vite 5.x
**Node:** 18+
**API proxy:** Vite proxies `/api` to `http://localhost:8002`

**Key packages (from package.json):**
- `react` 18.x, `react-dom` 18.x
- `typescript` 5.x
- `vite` 5.x
- `tailwindcss` 3.x
- `@tanstack/react-query` 5.x
- `react-router-dom` 6.x (with `v7_startTransition`, `v7_relativeSplatPath` future flags)
- `axios` 1.x
- `lucide-react` (icons)
- `react-pdf` (PDF preview)
- `zustand` (client-side state)
- `recharts` (donut chart on dashboard)

### 3.4 Celery Worker

**Start command:** `celery -A celery_app worker --loglevel=info`
**Module:** `backend/celery_app.py`
**Broker:** `settings.redis_url` (default `redis://localhost:6380/0`)
**Result backend:** same Redis URL
**Task serialiser:** JSON
**Soft time limit:** 600 seconds
**Hard time limit:** 660 seconds
**Prefetch multiplier:** 1 (one task at a time per worker)
**Late ack:** enabled (`task_acks_late=True`)
**Autodiscover:** `app.services.extraction` — finds `extract_document` task in `tasks.py`

**Production note:** Default pool is `solo` (single-threaded). For production, use
`--pool=gevent` or `--pool=prefork --concurrency=4`.

### 3.5 Ollama

**Default local URL:** `http://localhost:11434`
**Remote (RunPod):** configured via `OCR_BASE_URL` in `.env` — URL changes when pod restarts

**Models:**
| Role | Model name | API endpoint used |
|---|---|---|
| Layer 1 OCR | `glm-ocr:latest` | `/api/generate` |
| Layer 2 extraction | `gemma4:31b-cloud` | `/api/chat` via openai_compat or `/api/generate` |
| Chat assistant | `qwen2.5:3b` | `/api/chat` |

### 3.6 Database Connection

**Async engine** (FastAPI): `pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`, `pool_recycle=300`
**Sync engine** (Celery): `pool_size=10`, `max_overflow=5`, `pool_pre_ping=True`, `pool_recycle=300`

---

## 4. Configuration

All settings are in `backend/app/config.py` as a `pydantic_settings.BaseSettings` class.
Values are read from the `.env` file at the project root (two levels above `app/`).

### 4.1 Full Settings Table

| Setting name | Type | Default | Description |
|---|---|---|---|
| `database_url` | str | `postgresql+asyncpg://docplatform:docplatform@localhost:5432/docplatform` | Async SQLAlchemy URL for FastAPI |
| `sync_database_url` | str | `postgresql://docplatform:docplatform@localhost:5432/docplatform` | Sync URL for Celery tasks |
| `redis_url` | str | `redis://localhost:6380/0` | Redis broker + result backend |
| `nas_base_path` | str | `/nas/documents` | Root folder for PDF storage |
| `company_state` | str | `""` | Company's home state for IGST/CGST auto-detection (e.g. `"Tamil Nadu"`) |
| `ocr_base_url` | str | `http://localhost:11434` | Ollama base URL for Layer 1 OCR |
| `ocr_model_name` | str | `glm-ocr` | Legacy single-layer model name |
| `ocr_timeout` | int | `120` | OCR request timeout in seconds |
| `ocr_max_retries` | int | `3` | Max retries for OCR requests |
| `ocr_pdf_dpi` | int | `300` | DPI for PDF→image conversion |
| `ocr_max_pages` | int | `10` | Max pages to process per document |
| `ocr_two_layer_enabled` | bool | `False` | Enable two-layer OCR pipeline |
| `ocr_custom_model` | str | `glm-ocr:latest` | Layer 1 model name (two-layer mode) |
| `ocr_extractor_model` | str | `qwen2.5:7b` | Layer 2 extraction model name |
| `ocr_extractor_num_ctx` | int | `4096` | Context window for Layer 2 extractor |
| `ocr_extractor_num_predict` | int | `4096` | Max tokens to predict in Layer 2 |
| `ocr_save_debug_markdown` | bool | `False` | Save OCR markdown to `ocr_debug_markdown_dir` |
| `ocr_debug_markdown_dir` | str | `debug_markdown` | Directory for debug markdown files |
| `ocr_extractor_base_url` | str | `""` | Layer 2 override URL (empty = use `ocr_base_url`) |
| `ocr_extractor_api_key` | str | `""` | API key for Layer 2 (empty = no auth header) |
| `ocr_extractor_ca_bundle` | str \| None | `None` | CA bundle path for Layer 2 TLS; None = system default |
| `layer1_provider` | str | `""` | Provider type: `"ollama"` \| `"datalab"` \| `"openai_compat"` \| `"digital"` |
| `layer2_provider` | str | `""` | Provider type: `"ollama"` \| `"openai_compat"` |
| `datalab_api_key` | str | `""` | Datalab API key |
| `datalab_base_url` | str | `https://api.datalab.to` | Datalab API endpoint |
| `datalab_timeout` | int | `300` | Datalab request timeout in seconds |
| `datalab_poll_interval` | int | `3` | Datalab polling interval in seconds |
| `openai_compat_base_url` | str | `""` | OpenAI-compatible endpoint base URL |
| `openai_compat_api_key` | str | `""` | API key for OpenAI-compatible endpoint |
| `openai_compat_layer1_model` | str | `""` | Vision model for Layer 1 via OpenAI-compat |
| `openai_compat_layer2_model` | str | `""` | Text model for Layer 2 via OpenAI-compat |
| `openai_compat_max_tokens` | int | `4096` | Max tokens for OpenAI-compat requests |
| `openai_compat_timeout` | int | `120` | Timeout for OpenAI-compat requests |
| `ocr_num_ctx` | int | `16384` | Context window (shared by legacy + Ollama provider) |
| `chat_model` | str | `qwen2.5:3b` | Chat assistant model (must support `/api/chat`) |
| `chat_base_url` | str | `""` | Chat model URL override (empty = use `ocr_base_url`) |
| `cors_origins` | List[str] | `[]` | Allowed CORS origins |
| `debug` | bool | `False` | Enable SQLAlchemy echo + debug logging |

### 4.2 Provider Selection Logic

When `layer1_provider` is set, the new provider abstraction layer is used.
When empty, the legacy `ocr_*` settings are used (zero disruption for existing deployments).

**Provider modules:**
- `backend/app/services/extraction/providers/ollama_provider.py`
- `backend/app/services/extraction/providers/openai_compat_provider.py`
- `backend/app/services/extraction/providers/datalab_provider.py`
- `backend/app/services/extraction/providers/digital_provider.py`
- `backend/app/services/extraction/providers/base.py` — abstract base

---

## 5. Database Schema

**6 tables** + **1 support table** + **TimestampMixin** on every table.

**TimestampMixin** (from `backend/app/models/base.py`) adds to every table:
- `created_at: DateTime(timezone=True)` — auto-set on insert
- `updated_at: DateTime(timezone=True)` — auto-updated on every change

### 5.1 customers

**SQLAlchemy model:** `Customer` in `backend/app/models/customer.py`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, default=uuid4 | Internal UUID |
| `customer_id` | String(50) | UNIQUE, NOT NULL | Business ID (e.g. `SKY-AB1234`), used as NAS folder name |
| `name` | String(255) | NOT NULL | Display name (e.g. `Acme Corp`) |
| `contact_email` | String(255) | nullable | Validated as `EmailStr` on create/update |
| `contact_phone` | String(50) | nullable | |
| `address` | Text | nullable | Full postal address |
| `gst_number` | String(50) | nullable | GST identification number |
| `notes` | Text | nullable | Free-text notes |
| `is_active` | Boolean | NOT NULL, default=True | Soft delete flag |
| `created_at` | DateTime(tz) | auto | |
| `updated_at` | DateTime(tz) | auto | |

**Indexes:**
- `ix_customers_customer_id` on `customer_id` UNIQUE
- `ix_customers_name` on `name`
- `ix_customers_gst` on `gst_number`

**Relationships:**
- `purchase_orders` → List[PurchaseOrder] (back_populates="customer", lazy="selectin")

---

### 5.2 purchase_orders

**SQLAlchemy model:** `PurchaseOrder` in `backend/app/models/purchase_order.py`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, default=uuid4 | |
| `customer_id` | UUID | FK→customers.id, NOT NULL | |
| `po_number` | String(100) | UNIQUE, NOT NULL | Customer's PO reference number |
| `po_date` | Date | nullable | Date of the customer PO |
| `total_amount` | Numeric(15,2) | nullable | PO value from CUSTOMER_PO extraction |
| `status` | Enum(POStatus) | NOT NULL, default=INITIATED | Computed from chain_completeness |
| `chain_completeness` | Float | NOT NULL, default=0.0 | 0–100 percentage of required docs present |
| `notes` | Text | nullable | Operator notes |
| `so_number` | String(100) | nullable | Sales Order number (operator-entered) |
| `fulfillment_type` | Enum(FulfillmentType) | NOT NULL, default=procurement | |
| `items_verified` | Boolean | NOT NULL, default=False | Manual item comparison flag |
| `order_scenario` | Enum(OrderScenario) | NOT NULL, default=unknown | Auto-derived from uploaded documents |
| `gst_type` | Enum(GstType) | NOT NULL, default=unknown | IGST or CGST_SGST |
| `invoice_split` | Boolean | NOT NULL, default=False | Multiple invoices for this PO |
| `manually_completed` | Boolean | NOT NULL, default=False | Set True when operator closes PO |
| `completed_at` | DateTime(tz) | nullable | Timestamp of manual close |
| `completion_note` | Text | nullable | Operator's close reason |
| `billing_type` | Enum(BillingType) | NOT NULL, default=full | FULL / STAGED / RECURRING |
| `billing_milestones` | JSONB | nullable | `[{stage: int, percent: float}]` for STAGED billing |
| `requires_install_report` | Boolean | NOT NULL, default=False | Adds INSTALLATION_REPORT to required chain |
| `chain_status` | Enum(ChainStatus) | NOT NULL, default=incomplete | Computed by chain_validator |
| `created_at` | DateTime(tz) | auto | |
| `updated_at` | DateTime(tz) | auto | |

**Indexes:**
- `ix_po_number` on `po_number` UNIQUE
- `ix_po_customer_id` on `customer_id`
- `ix_po_status` on `status`
- `ix_po_date` on `po_date`
- `ix_po_so_number` on `so_number`

**Relationships:**
- `customer` → Customer (lazy="selectin")
- `documents` → List[Document] (lazy="selectin")

**Enums:**

`POStatus` values: `INITIATED`, `IN_PROGRESS`, `NEAR_COMPLETE`, `COMPLETE`, `CANCELLED`

`FulfillmentType` values: `procurement`, `stock`

`OrderScenario` values: `unknown`, `procurement`, `stock`, `drop_ship`, `service_amc`

`GstType` values: `unknown`, `igst`, `cgst_sgst`

`BillingType` values: `full`, `staged`, `recurring`

`ChainStatus` values: `incomplete`, `complete`, `verified`, `mismatch`

---

### 5.3 documents

**SQLAlchemy model:** `Document` in `backend/app/models/document.py`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, default=uuid4 | |
| `po_id` | UUID | FK→purchase_orders.id, NOT NULL | |
| `document_type` | Enum(DocumentType) | NOT NULL | |
| `filename` | String(255) | NOT NULL | UUID-prefixed stored name (NAS) |
| `original_filename` | String(255) | NOT NULL | User's original filename |
| `file_path` | String(500) | NOT NULL | Relative NAS path |
| `file_size` | Integer | NOT NULL | File size in bytes |
| `mime_type` | String(100) | NOT NULL, default=application/pdf | |
| `page_count` | Integer | nullable | Detected PDF page count |
| `checksum` | String(64) | NOT NULL | SHA-256 hex of file contents |
| `status` | Enum(DocumentStatus) | NOT NULL, default=UPLOADED | |
| `rotation` | Integer | NOT NULL, default=0 | Display rotation: 0, 90, 180, 270 |
| `so_number` | String(100) | nullable | Extracted SO number (from OCR) |
| `vpo_numbers` | JSONB | nullable, default=list | List of VPO numbers (from COMPANY_PO) |
| `billing_stage` | Integer | nullable | Stage number for STAGED billing |
| `extraction_ok` | Boolean | NOT NULL, default=True | False if extraction had errors |
| `created_at` | DateTime(tz) | auto | |
| `updated_at` | DateTime(tz) | auto | |

**Unique constraint:** `uq_doc_per_po` on `(po_id, checksum)` — prevents duplicate uploads

**Indexes:**
- `ix_doc_po_id` on `po_id`
- `ix_doc_type` on `document_type`
- `ix_doc_checksum` on `checksum`
- `ix_doc_status` on `status`
- `ix_doc_so_number` on `so_number`

**Enums:**

`DocumentType` values: `CUSTOMER_PO`, `COMPANY_PO`, `VENDOR_DC`, `VENDOR_INVOICE`, `COMPANY_DC`, `COMPANY_INVOICE`, `INSTALLATION_REPORT`, `VENDOR_CREDIT_NOTE`

`DocumentStatus` values: `UPLOADED`, `EXTRACTING`, `PENDING_REVIEW`, `VERIFIED`, `REJECTED`, `EXTRACTION_FAILED`, `PENDING_MODEL`

`PENDING_MODEL` = document is fine; required LLM model is unavailable on the endpoint.

---

### 5.4 document_metadata

**SQLAlchemy model:** `DocumentMetadata` in `backend/app/models/document_metadata.py`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, default=uuid4 | |
| `document_id` | UUID | FK→documents.id, UNIQUE, NOT NULL | 1:1 with documents |
| `document_type` | Enum(DocumentType) | NOT NULL | Denormalised from document |
| `extracted_data` | JSONB | nullable | Full extracted field dict from LLM |
| `raw_ocr_text` | Text | nullable | Raw markdown from Layer 1; pages joined with `\n---PAGE_BREAK---\n` |
| `primary_ref_no` | String(100) | nullable | Main reference (invoice_no / dc_no / po_no) |
| `po_ref_no` | String(100) | nullable | Cross-reference back to customer PO |
| `doc_date` | Date | nullable | Document issue date |
| `total_amount` | Numeric(15,2) | nullable | Extracted total/grand total |
| `confidence_score` | Float | nullable | Document-level confidence 0.0–1.0 |
| `status` | Enum(MetadataStatus) | NOT NULL, default=PENDING | |
| `extraction_attempts` | Integer | NOT NULL, default=0 | Total extraction runs |
| `last_error` | Text | nullable | Last extraction error message |
| `extracted_at` | DateTime | nullable | Timestamp of last successful extraction |
| `verified_at` | DateTime | nullable | Timestamp of human verification |
| `model_version` | String(50) | nullable | Model string used for extraction |
| `processing_time_ms` | Integer | nullable | Total OCR+extraction time in ms |
| `extraction_version` | Integer | NOT NULL, default=1 | Increments on every re-extract |
| `field_confidences` | JSONB | nullable | `{"field_name": 0.0–1.0}` per-field confidence |
| `extraction_route` | String(20) | nullable | `"digital"` or `"scanned"` |
| `created_at` | DateTime(tz) | auto | |
| `updated_at` | DateTime(tz) | auto | |

**Indexes:**
- `ix_meta_document_id` on `document_id` UNIQUE
- `ix_meta_primary_ref` on `primary_ref_no`
- `ix_meta_po_ref` on `po_ref_no`
- `ix_meta_doc_date` on `doc_date`
- `ix_meta_status` on `status`
- `ix_meta_extracted_data` on `extracted_data` using GIN (JSONB full-text search)

`MetadataStatus` values: `PENDING`, `EXTRACTED`, `VERIFIED`, `FAILED`

---

### 5.5 reference_index

**SQLAlchemy model:** `ReferenceIndex` in `backend/app/models/reference_index.py`

Denormalised search table. Rebuilt from scratch on every extraction and every verify.
Powers the global search and inline search autocomplete.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, default=uuid4 | |
| `document_id` | UUID | FK→documents.id, NOT NULL | |
| `po_id` | UUID | FK→purchase_orders.id, NOT NULL | Denormalised for speed |
| `ref_type` | String(50) | NOT NULL | e.g. `invoice_number`, `dc_number`, `po_number` |
| `ref_value` | String(255) | NOT NULL, indexed | The actual reference value string |
| `document_type` | Enum(DocumentType) | NOT NULL | |
| `created_at` | DateTime(tz) | auto | |
| `updated_at` | DateTime(tz) | auto | |

**Indexes:**
- `ix_ref_value` on `ref_value`
- `ix_ref_type_value` on `(ref_type, ref_value)`
- `ix_ref_document_id` on `document_id`
- `ix_ref_po_id` on `po_id`

---

### 5.6 extraction_corrections

**SQLAlchemy model:** `ExtractionCorrection` in `backend/app/models/extraction_correction.py`

Captures every human correction during document review. Used for LayoutLMv3 fine-tuning.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, default=uuid4 | |
| `document_id` | UUID | FK→documents.id, NOT NULL | |
| `field_name` | String(100) | NOT NULL | Name of the corrected field |
| `original_value` | Text | nullable | Value the model extracted |
| `corrected_value` | Text | nullable | Value the human entered |
| `operator_id` | String(100) | nullable | User who made the correction (currently hardcoded `"system"`) |
| `corrected_at` | DateTime | NOT NULL, default=utcnow | |
| `extraction_version` | Integer | NOT NULL, default=1 | Matches the document_metadata.extraction_version |
| `used_for_training` | Boolean | NOT NULL, default=False | Flagged after LayoutLMv3 fine-tune |
| `created_at` | DateTime(tz) | auto | |
| `updated_at` | DateTime(tz) | auto | |

### 5.7 Entity Relationships

```
customers
  └──< purchase_orders (customer_id FK)
         └──< documents (po_id FK)
                ├──  document_metadata (document_id FK, 1:1)
                ├──< reference_index (document_id FK)
                └──< extraction_corrections (document_id FK)
```

---

## 6. API Reference

**Base URL:** `/api/v1`

All routers registered in `backend/app/api/router.py`:

```
/api/v1/customers          → customers_router
/api/v1/purchase-orders    → purchase_orders_router
/api/v1/documents          → documents_router
/api/v1/                   → extraction_router  (no prefix — endpoints start with /documents)
/api/v1/search             → search_router
/api/v1/admin              → admin_router
/api/v1/chat               → chat_router
```

---

### 6.1 Customers Router — `/api/v1/customers`

**File:** `backend/app/api/v1/customers.py`

---

#### POST /api/v1/customers
**Request body** (`CustomerCreate`):
```json
{
  "customer_id": "SKY-AB1234",
  "name": "Acme Corp",
  "contact_email": "ops@acme.com",
  "contact_phone": "+91-9876543210",
  "address": "123 Main St, Chennai",
  "gst_number": "33AABCA1234F1Z5",
  "notes": ""
}
```
`contact_email` is validated as `EmailStr` (Pydantic). All fields except `customer_id` and `name` are optional.
**Response:** `CustomerResponse` (201)

---

#### GET /api/v1/customers
**Query params:**
- `page` int (default=1, min=1)
- `per_page` int (default=20, min=1, max=100)
- `search` str (optional) — name substring search

**Response:** `CustomerListResponse` = `{items: CustomerResponse[], total: int, page: int, per_page: int}`

Each `CustomerResponse` includes `po_count` (live count query).

---

#### GET /api/v1/customers/{id}
Returns `CustomerResponse` with `po_count`.

---

#### PATCH /api/v1/customers/{id}
**Request body** (`CustomerUpdate`): same fields as Create, all optional. `contact_email` validated as `EmailStr`.
**Response:** `CustomerResponse`

---

#### GET /api/v1/customers/{id}/purchase-orders
**Query params:** `page`, `per_page`, `status`
**Response:** `POListResponse`

---

### 6.2 Purchase Orders Router — `/api/v1/purchase-orders`

**File:** `backend/app/api/v1/purchase_orders.py`

---

#### POST /api/v1/purchase-orders
**Request body** (`POCreate`):
```json
{
  "customer_id": "uuid",
  "po_number": "PWFA260320016",
  "po_date": "2026-03-20",
  "total_amount": 125000.00,
  "notes": "",
  "so_number": null,
  "fulfillment_type": "procurement",
  "gst_type": "igst",
  "invoice_split": false,
  "billing_type": "full",
  "billing_milestones": null,
  "requires_install_report": false
}
```
**Response:** `POResponse` (201)

---

#### GET /api/v1/purchase-orders
**Query params:**
- `page` int (default=1)
- `per_page` int (default=20, max=100)
- `customer_id` UUID (optional)
- `status` str (optional) — e.g. `"IN_PROGRESS"`
- `search` str (optional) — PO number substring
- `date_from` date (optional) — filter `po_date ≥ date_from`
- `date_to` date (optional) — filter `po_date ≤ date_to`
- `sort_by` str (default=`"created_at"`) — `created_at` | `po_date` | `chain_completeness` | `total_amount`
- `sort_order` str (default=`"desc"`) — `asc` | `desc`
- `chain_filter` str (optional) — `"incomplete"` | `"critical"` | `"complete"`
- `missing_doc_type` str (optional) — filter POs missing a specific doc type

**Response:** `POListResponse`

---

#### GET /api/v1/purchase-orders/{id}
**Response:** `POResponse`

---

#### PATCH /api/v1/purchase-orders/{id}
**Request body** (`POUpdate`): same fields as Create, all optional.
**Response:** `POResponse`

---

#### DELETE /api/v1/purchase-orders/{id}
**Response:** 204 No Content

---

#### POST /api/v1/purchase-orders/{id}/close
**Request body:** `{"note": "optional close reason"}`
**Behaviour:** Sets `manually_completed=True`, `completed_at=now`, `completion_note=note`.
If `chain_status == MISMATCH`, returns a `JSONResponse` with extra `_warning` field:
```json
{
  ...POResponse fields...,
  "_warning": "Order closed with unresolved reference mismatches. Review chain validation before dispatch."
}
```
**Response:** `POResponse` (200) or JSONResponse with `_warning` key

---

#### PATCH /api/v1/purchase-orders/{po_id}/so-number
**Request body:** `{"so_number": "1OTM2526001448"}`
Sets `po.so_number` (strips whitespace, sets to null if empty string).
**Response:** Full `POResponse` including `customer_name` and `customer_sky_id`

---

#### GET /api/v1/purchase-orders/{po_id}/chain
Full live chain validation. Does NOT use stored values — recomputes from documents.
Falls back to stored `chain_completeness` when scenario produces 0 slots.
Updates `po.chain_status` in background (best-effort).
**Response:**
```json
{
  "chain_status": "incomplete",
  "completeness_pct": 60,
  "missing_slots": ["COMPANY_DC", "COMPANY_INVOICE"],
  "missing_vendor_invoices": [],
  "reference_checks": [
    {"document_type": "COMPANY_DC", "check": "so_consistency", "result": "pass"},
    {"document_type": "COMPANY_DC", "check": "cpo_reference", "result": "pass"}
  ],
  "billing": {"overall": "pending"}
}
```

---

#### GET /api/v1/purchase-orders/{id}/chain-status
Returns `ChainStatusResponse` (stored values from `po_service.get_chain_status()`).
`ChainStatusResponse` fields: `chain_status`, `completeness_pct: int`, `missing_slots`, `missing_vendor_invoices`

---

#### GET /api/v1/purchase-orders/{id}/profile
Full PO profile for the Profile page. Returns `POProfileResponse` — see Section 7.2.

---

#### GET /api/v1/purchase-orders/{id}/export
**Query params:** `mode` str (`"separate"` | `"single"`, default=`"separate"`)
Returns Excel file (.xlsx) as binary download.
Filename format: `PO_{po_number}_{date}.xlsx` or `PO_{po_number}_consolidated_{date}.xlsx`
Content-Type: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

---

#### POST /api/v1/purchase-orders/{po_id}/documents
**Form data:**
- `file` — PDF file (multipart)
- `document_type` — string (must match `DocumentType` enum values)

Only PDF files accepted. Extension check: `.pdf`. MIME check: `application/pdf`.
Non-PDF returns 415 with message: `"Only PDF files are accepted (scanned or digital). Please convert your document to PDF before uploading."`
**Response:** `DocumentUploadResponse` (201)

---

#### GET /api/v1/purchase-orders/{po_id}/documents
**Response:** `DocumentListResponse`

---

### 6.3 Documents Router — `/api/v1/documents`

**File:** `backend/app/api/v1/documents.py`

---

#### GET /api/v1/documents
**Query params:**
- `status` str (optional) — e.g. `"PENDING_REVIEW"`
- `document_type` str (optional) — e.g. `"VENDOR_INVOICE"`
- `customer_id` UUID (optional)
- `date_from` date (optional)
- `date_to` date (optional)
- `page` int (default=1)
- `per_page` int (default=50, max=200)

Documents with `status=PENDING_REVIEW` also include `days_pending` (how many days since upload).
**Response:** `DocumentListResponse` with `{items, total}`

---

#### GET /api/v1/documents/{id}
**Response:** `DocumentResponse` with nested `metadata: ExtractionResponse`

---

#### DELETE /api/v1/documents/{id}
**Response:** 204 No Content

---

#### GET /api/v1/documents/{id}/preview
Streams file bytes from NAS.
Returns 503 if NAS is unavailable.
Returns 404 if file not found.
`Content-Disposition: inline; filename="{original_filename}"`

---

#### GET /api/v1/documents/{id}/download
Same as preview but `Content-Disposition: attachment`.

---

#### POST /api/v1/documents/{id}/rotate
**Request body:** `{"angle": 90}` — angle must be 90, 180, or 270
Adds to existing rotation, wraps at 360.
**Response:** `DocumentResponse`

---

### 6.4 Extraction Router — `/api/v1/`

**File:** `backend/app/api/v1/extraction.py`
No prefix — endpoints start with `/documents`.

---

#### GET /api/v1/documents/{document_id}/metadata/template
Returns the expected extraction field schema for a document type.
**Response:** `{"document_type": str, "fields": {field: null, ...}, "field_descriptions": {field: desc, ...}}`

---

#### POST /api/v1/documents/{document_id}/metadata/manual
Creates an empty `DocumentMetadata` stub for manual data entry.
Sets `status=EXTRACTED`, `model_version="manual"`, `doc.status=PENDING_REVIEW`.
If metadata already exists but is empty/failed, resets it for manual entry.
**Response:** `ExtractionResponse`

---

#### POST /api/v1/documents/{document_id}/re-extract
Triggers re-extraction. Increments `extraction_version` (never deletes metadata).
Clears `extracted_data`, `confidence_score`, `field_confidences`, `last_error`, `extracted_at`.
Deletes `ReferenceIndex` entries for this document.
Resets `doc.status = UPLOADED`.
Queues `extract_document.delay(document_id)` Celery task.
**Response:** `{"message": "Extraction queued", "document_id": str, "extraction_version": int}`

---

#### GET /api/v1/documents/{document_id}/metadata
**Response:** `ExtractionResponse`

---

#### PUT /api/v1/documents/{document_id}/metadata/verify
Human verification with optional field edits.
**Request body** (`VerifyRequest`): `{"extracted_data": {...edited fields...}}`

**Verification rules:**
1. `CUSTOMER_PO` requires `po.so_number` to be set before verification completes. If not set: returns with `requires_so_entry=True`, `verification_pending=True`
2. `COMPANY_DC` / `COMPANY_INVOICE`: extracted SO must match `po.so_number`. Mismatch returns `so_mismatch_message`
3. If all checks pass: `meta.status=VERIFIED`, `doc.status=VERIFIED`, triggers chain recomputation

**Array field preservation:** `order_items` and `delivery_locations` are preserved from existing metadata if not in the submitted payload.

**Response:** `ExtractionResponse` (with extra fields: `requires_so_entry`, `verification_pending`, `so_mismatch_message`, `po_id`, `po_so_number`)

---

#### PUT /api/v1/documents/{document_id}/metadata/reject
Sets `meta.status=FAILED`, `doc.status=REJECTED`. Clears `ReferenceIndex`. Updates chain.
**Response:** `ExtractionResponse`

---

#### POST /api/v1/documents/{document_id}/corrections
**Request body:** `[{"field": "invoice_number", "corrected_value": "1ITR2526001748"}, ...]`
Saves only changed fields (skips if `original_value == corrected_value`).
Updates `meta.extracted_data` in place and writes `ExtractionCorrection` records.
**Response:** `{"saved_fields": [...], "document_id": str, "corrections_count": int}`

---

### 6.5 Search Router — `/api/v1/search`

**File:** `backend/app/api/v1/search.py`

---

#### GET /api/v1/search
**Query params:**
- `q` str (min_length=0) — minimum 2 chars to trigger search
- `page` int (default=1)
- `per_page` int (default=20, max=100)

Searches: `ReferenceIndex.ref_value`, `Customer.name`, `Customer.customer_id`, `PurchaseOrder.po_number`.
Returns 0 results if `len(q) < 2`.
**Response:** `SearchResponse = {results: SearchResult[], total: int, query: str}`

---

#### GET /api/v1/search/by-ref/{ref_value}
Exact match lookup in `ReferenceIndex`. No pagination.
**Response:** `{results: SearchResult[], total: int, query: str}`

---

#### GET /api/v1/search/advanced
**Query params:**
- `invoice_no` str (optional)
- `dc_no` str (optional)
- `po_no` str (optional) — also searches `purchase_orders.po_number` directly
- `so_no` str (optional)
- `customer_name` str (optional)
- `delivery_address` str (optional)
- `date_from` str (optional)
- `date_to` str (optional)
- `document_type` str (optional)
- `page` int (default=1)
- `per_page` int (default=20, max=100)

Blank `ref_number` results are filtered out. Deduplicated by `po-{id}` / `doc-{id}` keys.
**Response:** `SearchResponse`

---

### 6.6 Admin Router — `/api/v1/admin`

**File:** `backend/app/api/v1/admin.py`

---

#### GET /api/v1/admin/health
Checks all services in parallel. Result cached in Redis for 30 seconds (key: `admin:health:cache`).
**Response:**
```json
{
  "database": "ok",
  "redis": "ok",
  "ollama": "ok",
  "models": "ok",
  "storage": "ok"
}
```
Each value is either `"ok"` or an error string like `"error: connection refused"`.

---

#### GET /api/v1/admin/stats
Dashboard statistics. All document counts in one SQL round-trip using conditional aggregation.
Time-series deltas use raw `text()` SQL to avoid asyncpg datetime codec issues.
**Response:**
```json
{
  "total_customers": 9,
  "total_purchase_orders": 10,
  "total_documents": 24,
  "uploaded": 0,
  "extracting": 0,
  "pending_reviews": 15,
  "verified": 9,
  "extraction_failures": 0,
  "pending_model": 0,
  "rejected": 0,
  "stats_delta": {
    "total_purchase_orders": 2,
    "total_documents": 5,
    "verified": 3
  }
}
```
`stats_delta` = count in last 24h minus count in previous 24h window.

---

#### GET /api/v1/admin/queue
Celery worker status. Runs `inspect.active()`, `inspect.reserved()`, `inspect.stats()` concurrently via `ThreadPoolExecutor`. Timeout: 2 seconds.
**Response:** `{"workers_online": int, "active_tasks": int, "queued_tasks": int}`
Returns `{0, 0, 0}` on any error (Celery not running is not an error for the API).

---

#### POST /api/v1/admin/requeue-pending-models
Re-queues all documents with `status=PENDING_MODEL`.
Resets each doc to `UPLOADED`, resets metadata to `status=PENDING`, clears `last_error`.
Dispatches `extract_document.delay(doc_id)` for each.
**Response:** `{"requeued": int, "document_ids": [str, ...]}`

---

### 6.7 Chat Router — `/api/v1/chat`

**File:** `backend/app/api/v1/chat.py`

---

#### GET /api/v1/chat/stream
Server-Sent Events streaming endpoint.
**Query params:**
- `message` str (min=1, max=2000, required)
- `po_id` str (optional) — if provided, forces `intent="order_query"` with full order context

**Response headers:** `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`

**Event format:**
```
data: {"chunk": "partial text...", "done": false}\n\n
data: {"chunk": "", "done": true}\n\n
```
Error: `{"chunk": "Chat service unavailable: <error>", "done": false}` followed by done event.

---

## 7. Backend Services

### 7.1 po_service.py

**File:** `backend/app/services/po_service.py` (~1103 lines)

**Constants:**
```python
CHAIN_DOC_TYPES = [
    DocumentType.CUSTOMER_PO, DocumentType.COMPANY_PO,
    DocumentType.VENDOR_DC, DocumentType.VENDOR_INVOICE,
    DocumentType.COMPANY_DC, DocumentType.COMPANY_INVOICE,
]
```

**Required doc chain per scenario:**
```python
_SCENARIO_CHAIN = {
    OrderScenario.UNKNOWN: None,
    OrderScenario.PROCUREMENT: [CUSTOMER_PO, COMPANY_PO, VENDOR_INVOICE, COMPANY_DC, COMPANY_INVOICE],
    OrderScenario.STOCK: [CUSTOMER_PO, COMPANY_DC, COMPANY_INVOICE],
    OrderScenario.DROP_SHIP: [CUSTOMER_PO, COMPANY_PO, VENDOR_DC, VENDOR_INVOICE, COMPANY_INVOICE],
    OrderScenario.SERVICE_AMC: [CUSTOMER_PO, COMPANY_INVOICE],
}
```
Note: `VENDOR_DC` is excluded from PROCUREMENT (optional for many vendors). `COMPANY_DC` is excluded from DROP_SHIP (not needed on direct vendor-to-customer shipments).

**Key functions:**

`get_scenario_chain(scenario)` → `list[DocumentType] | None`
Returns required doc list. `None` = indeterminate (unknown scenario).

`derive_scenario(vpo_count, has_vendor_dc, has_service_hint)` → `OrderScenario`
Scenario derivation rules:
- `vpo_count > 0` → PROCUREMENT
- `vpo_count == 0` + `has_vendor_dc` → DROP_SHIP
- `vpo_count == 0` + `has_service_hint` → SERVICE_AMC
- `vpo_count == 0` (neither) → STOCK

`create_po(db, data: POCreate)` → `PurchaseOrder`
Creates PO, loads customer relationship.

`get_po(db, id)` → `PurchaseOrder` (raises 404 if not found)

`list_pos(db, page, per_page, customer_id, status, search, date_from, date_to, sort_by, sort_order, chain_filter, missing_doc_type)` → `(list[PurchaseOrder], int)`

`update_po(db, id, data: POUpdate)` → `PurchaseOrder`
Sets `gst_type` automatically from company_state setting and delivery address.

`close_order(db, id, note)` → `PurchaseOrder`
Sets `manually_completed=True`, `completed_at=utcnow()`, `completion_note=note`.
Preserves existing `chain_status` (does NOT reset to COMPLETE).

`delete_po(db, id)`
Deletes PO and cascades to documents, metadata, reference_index.

`get_chain_status(db, id)` → `ChainStatusResponse`
Returns stored chain values. `completeness_pct` returned as `int`.

`get_po_profile(db, id)` → `POProfileResponse`
Assembles the full PO profile: slots, timeline, discrepancies, cross-references,
vendor groups, field comparisons, item comparisons, item matches, delivery addresses.

`update_chain_completeness(db, po_id)`
Sync function. Called after document changes. Derives scenario, counts required docs,
updates `po.chain_completeness` and `po.status`. Skips if `po.manually_completed=True`.
Calls `derive_scenario()` when `order_scenario == UNKNOWN`.

---

### 7.2 document_service.py

**File:** `backend/app/services/document_service.py`

`upload_document(db, po_id, document_type, file: UploadFile)` → `Document`
1. Reads file bytes, computes SHA-256 checksum
2. Builds path: `{customer_id}/{po_number}/{uuid}_{original_filename}.pdf`
3. Saves to NAS via `StorageService`
4. Creates `Document` record with `status=UPLOADED`
5. Queues Celery task: `extract_document.delay(str(doc.id))`

`list_documents_for_po(db, po_id)` → `list[Document]`

`get_document(db, id)` → `Document` (raises 404 if not found)

`delete_document(db, id)`
Deletes document record + NAS file + cascaded metadata/corrections.

`get_preview_data(db, id)` → `(bytes, mime_type, original_filename)`
Reads file from NAS. Raises `NASUnavailableError` or `FileNotFoundError`.

---

### 7.3 search_service.py

**File:** `backend/app/services/search_service.py`

`global_search(db, query, page, per_page)` → `{results, total, query}`
Searches:
- `ReferenceIndex.ref_value` ILIKE `%q%`
- `Customer.name` ILIKE `%q%`
- `Customer.customer_id` ILIKE `%q%`
- `PurchaseOrder.po_number` ILIKE `%q%`
Deduplicates by composite key. Filters out blank `ref_number` results.

`search_by_ref(db, ref_value)` → list
Exact ILIKE match on `ReferenceIndex.ref_value`.

`advanced_search(db, invoice_no, dc_no, po_no, so_no, customer_name, delivery_address, date_from, date_to, document_type, page, per_page)` → `{results, total, query}`
For `po_no`: also runs a fallback direct query on `purchase_orders.po_number`.
Blank `ref_number` results filtered out.

---

### 7.4 chain_validator.py

**File:** `backend/app/services/chain_validator.py`

`compute_chain_status(scenario, po_number, so_number, po_total, billing_type, billing_milestones, vpo_numbers, documents, requires_install_report, invoiced_total)` → dict

Orchestrates three checks:
1. **Slot presence** — which required doc types are missing
2. **Reference validation** — SO consistency, CPO reference, VPO reference
3. **Billing completeness** — FULL (1% tolerance) or STAGED (5% per-stage tolerance)

Priority: MISMATCH > INCOMPLETE > (billing complete = COMPLETE) > INCOMPLETE

Returns:
```json
{
  "chain_status": "ChainStatus",
  "completeness_pct": int,
  "missing_slots": [DocumentType, ...],
  "missing_vendor_invoices": [str, ...],
  "reference_checks": [{document_type, check, result}, ...],
  "billing": {"overall": BillingStatus, "stages": [...]}
}
```

`SlotState` enum: `WAITING`, `RECEIVED`, `VERIFIED`, `MISMATCH`, `CANCELLED`

---

### 7.5 billing_tracker.py

**File:** `backend/app/services/billing_tracker.py`

`BillingStatus` enum: `PENDING`, `PARTIAL`, `COMPLETE`, `MISMATCH`, `PAID`

`check_full_billing(invoiced_total, po_total)` → `BillingStatus`
- 1% tolerance (`_FULL_TOLERANCE = 0.01`)
- PENDING if `invoiced_total == 0`
- COMPLETE if `invoiced_total >= po_total * 0.99`
- PARTIAL otherwise

`check_staged_billing(po_total, milestones, stage_invoices)` → `{stages: list, overall: BillingStatus}`
- 5% tolerance per stage (`_STAGE_TOLERANCE = 0.05`)
- `milestones`: `[{stage: int, percent: float}]`
- `stage_invoices`: `[{billing_stage: int, amount: float}]`
- Overall: COMPLETE if all stages PAID, MISMATCH if any mismatch, PARTIAL if any paid but incomplete, PENDING otherwise

---

### 7.6 reference_validator.py

**File:** `backend/app/services/reference_validator.py`

`ReferenceCheckResult` enum: `PASS`, `MISMATCH`, `SKIP`

`check_so_consistency(extracted_so, expected_so)` → `ReferenceCheckResult`
Strip-compare. Returns SKIP if either is None/empty.

`check_cpo_reference(extracted_cpo_ref, expected_po_number)` → `ReferenceCheckResult`
Checks `customer_order_no` in document matches PO number. Returns SKIP if either None/empty.

`check_vpo_reference(doc_vpo_numbers, registered_vpo_numbers)` → `ReferenceCheckResult`
Checks if any VPO number in the vendor invoice matches registered VPOs for this CPO.
Returns SKIP if either list empty.

---

### 7.7 chat_service.py

**File:** `backend/app/services/chat_service.py`

**Intent detection keywords:**
```python
_ORDER_KEYWORDS = {"order", "po", "status", "chain", "invoice", "document",
                   "missing", "wrong", "issue", "problem", "mismatch",
                   "billing", "verify", "verified"}
_SEARCH_KEYWORDS = {"find", "search", "look", "locate", "where", "which",
                    "ref", "reference", "number"}
_PLATFORM_KEYWORDS = {"today", "attention", "summary", "overview", "all orders",
                      "dashboard", "pending", "total", "how many"}
```

`_detect_intent(message, po_id)` → `"order_query" | "search_query" | "platform_query" | "general"`
- If `po_id` provided: always `"order_query"`
- Otherwise keyword token match (platform → search → order → general)
- Note: `_PLATFORM_KEYWORDS` contains multi-word entries (`"all orders"`) — token-based match will never match these

`stream_chat_response(message, po_id, db)` → `AsyncIterator[str]`
1. Detects intent
2. Builds context block (`build_order_context` / `build_search_context` / `build_platform_context`)
3. Prepends context to `SYSTEM_PROMPT`
4. Calls `{chat_base_url or ocr_base_url}/api/chat` with `settings.chat_model`
5. Yields SSE events: `data: {"chunk": str, "done": bool}\n\n`
6. Timeout: 120 seconds. Options: `num_ctx=8192`, `num_predict=1024`, `temperature=0.3`

**System prompt:**
```
You are an assistant for a logistics document processing platform.
You help operators and managers understand order status, find documents, and identify issues.
Be concise and specific. Reference exact document types, amounts, and reference numbers
from the data provided. If an issue exists, explain what it is and what action is needed.
Format responses in plain text — avoid markdown headers. Use bullet points only for lists of 3+ items.
```

---

### 7.8 chat_context.py

**File:** `backend/app/services/chat_context.py`

`build_order_context(po_id, db)` → str
Full text block: PO header, chain validation result, missing docs, reference mismatches,
billing status, document list with ref/amount/confidence per doc.

`build_search_context(query, db)` → str
Searches `ReferenceIndex.ref_value` and `DocumentMetadata.primary_ref_no` (5 results each).
Returns "No documents or references found..." if empty.

`build_platform_context(db)` → str
Order counts by status + document counts by status + top 10 orders needing attention
(MISMATCH or INCOMPLETE chain status).

---

### 7.9 export_service.py

**File:** `backend/app/services/export_service.py`

`export_po_to_excel(db, id, mode)` → bytes
Generates `.xlsx` file from `POProfileResponse`.
`mode="separate"` — one sheet per document type.
`mode="single"` — consolidated single sheet.

---

### 7.10 address_parser.py

**File:** `backend/app/services/address_parser.py`

`parse_address(address_str)` → `ParsedAddress`
Extracts `pin_code`, `city`, `state`, `full_address` from free-text Indian address.

`validate_addresses(po_dc_address, po_invoice_address)` → `bool`
Fuzzy match on pin code and city.

---

### 7.11 item_matcher.py

**File:** `backend/app/services/item_matcher.py`

`match_items_by_description(items_a, items_b)` → `list[ItemMatch]`
Fuzzy description matching between two order_items arrays.

`compare_po_to_delivery(po_items, dc_items)` → `list[ItemComparison]`
Line-item comparison: qty match, price match.

Known issue at line 194, 210: `int()` call on qty strings that may contain decimals (e.g. `"2.000"`) → will crash on Redington invoices which use decimal quantities.

---

### 7.12 storage_service.py

**File:** `backend/app/services/storage_service.py`

`StorageService(base_path)` — initialised with `settings.nas_base_path`

`save_file(customer_id, po_number, filename, data)` → `str` (relative path)
Creates directory if needed. Returns path relative to `base_path`.

`delete_file(file_path)` — deletes file, ignores `FileNotFoundError`

`get_file_path(file_path)` → `str` (absolute path)

`NASUnavailableError` — raised when base_path is not accessible

---

## 8. Extraction Pipeline — Deep Dive

**Files:** `backend/app/services/extraction/`

### 8.1 Full Flow (step by step)

```
1. User uploads PDF → POST /purchase-orders/{id}/documents
   └── document_service.upload_document()
       ├── Compute SHA-256 checksum
       ├── Save PDF to NAS: {NAS_BASE_PATH}/{customer_id}/{po_number}/{uuid}_{filename}
       ├── Create documents record (status=UPLOADED)
       └── Queue Celery task: extract_document.delay(document_id)

2. Celery worker picks up task → tasks.py:extract_document()

3. Fetch document from DB (sync session)

4. Build pipeline → pipeline.py:build_pipeline_from_config(settings)
   ├── If layer1_provider set → new provider abstraction
   └── If empty → legacy ocr_* settings path

5. Update doc.status = EXTRACTING, commit

6. HybridRouter.route(storage_path) → ExtractionRoute
   ├── ExtractionRoute.DIGITAL  — embedded text detected (pypdf)
   └── ExtractionRoute.SCANNED  — image-only or minimal text

7A. DIGITAL fast path:
    DigitalExtractor.extract(path) → markdown text (no GPU)
    Falls back to SCANNED if markdown < 50 chars

7B. SCANNED path:
    PDFConverter.convert_to_images(path, dpi=ocr_pdf_dpi, max_pages=ocr_max_pages)
    For each page image:
      scan_preprocessor.preprocess_scan(image) — enhance contrast, deskew
      pipeline.run_ocr(image, doc_type, page_label)
        └── Layer 1 model (glm-ocr or qwen2.5vl) → markdown text

8. Layer 2 extraction (if pipeline.layer2 is not None):
   pipeline.run_extraction(markdown, doc_type, customer_hint)
   └── two_layer_client.py calls Layer 2 model with build_extraction_prompt()
       ├── EXTRACTION_SCHEMAS[doc_type] — field definitions
       ├── ANTI_CONFUSION_RULES[doc_type] — vendor/layout hints
       ├── VENDOR_INVOICE_TEMPLATES — Redington special parsing
       └── CUSTOMER_DELIVERY_SCHEMAS — Shriram Finance column order
   Each scalar field returned as: {"value": x, "confidence": 0.0–1.0}
   Array fields returned directly (no wrapper)

9. _extract_field_confidences(fields) → (flat_fields, _field_confidences dict)
   Unwraps {"value": x, "confidence": 0.97} → field=x, confidences={field: 0.97}

10. Multi-page merge: first non-null wins per field

11. validate_extracted_fields(extracted_data, doc_type) — normalise amounts, fix dates

12. validate_invoice_math(extracted_data, doc_type)
    ├── Check line-item total vs header total
    └── Returns ValidationResult with errors/warnings/_route

13. validate_so_number(extracted_data, doc_type, po.so_number)
    COMPANY_DC / COMPANY_INVOICE: extracted SO must match po.so_number

14. Create or update DocumentMetadata:
    ├── extracted_data = merged fields
    ├── raw_ocr_text = pages joined with ---PAGE_BREAK---
    ├── primary_ref_no = value of primary field (invoice_no / dc_no / po_no)
    ├── po_ref_no = extracted_data.get("po_reference")
    ├── doc_date = parsed date
    ├── total_amount = cleaned float
    ├── confidence_score = filled_fields / total_schema_fields
    ├── extraction_route = "digital" | "scanned"
    ├── field_confidences = _field_confidences dict (popped from extracted_data)
    └── model_version = pipeline.model_version

15. Rebuild ReferenceIndex:
    Delete old entries for this document_id
    For each searchable field → insert ReferenceIndex row
    Searchable fields per type:
      CUSTOMER_PO: po_number
      COMPANY_PO: po_number
      VENDOR_DC: dc_number, po_reference
      VENDOR_INVOICE: invoice_number, po_reference
      COMPANY_DC: dc_number, po_reference, so_number
      COMPANY_INVOICE: invoice_number, po_reference, so_number

16. doc.status = PENDING_REVIEW (or stays EXTRACTION_FAILED on error)

17. _update_chain_sync(db, po_id)
    Updates po.chain_completeness and po.status
```

### 8.2 Model Health Check

Before OCR, the pipeline calls `pipeline.health_check()`.
If model unavailable: `_PipelineNotReady` raised → doc moved to `PENDING_MODEL`.
Operator uses Admin → "Requeue Pending Models" to retry when model is available.

### 8.3 Layer 1 Prompts

All document types use the same plain-text prompt: `"Extract the text in the image."`
(Previously used `<|grounding|>` for table-heavy types with glm-ocr, but this caused
header fields to be missed. Plain prompt works for both glm-ocr and qwen2.5vl.)

### 8.4 Layer 2 Prompt Structure

```
You are a business document data extraction assistant.
Your job is to extract specific fields from the document text provided.

Document Type: {doc_type}

{ANTI_CONFUSION_RULES[doc_type]}   ← doc-type specific corrections
{vendor_template}                   ← injected for VENDOR_INVOICE/VENDOR_DC (Redington etc.)
{customer_delivery_schema}          ← injected for CUSTOMER_PO (Shriram Finance etc.)

Fields to extract:
{schema fields with descriptions}

Rules:
- Return ONLY valid JSON — no explanation, no markdown fences
- Scalar fields: {"value": x, "confidence": 0.0–1.0}
- Array fields (order_items, delivery_locations): return array directly
- null for missing fields
- No commas in numbers
- Dates as printed

Document text:
---
{markdown_text}
---
JSON:
```

### 8.5 Confidence Score Calculation

**Document-level:** `filled_fields / total_schema_fields` (0.0–1.0)
Where `filled_fields = len([v for v in fields.values() if v is not None])`

**Field-level:** Per-field confidence from LLM (0.0–1.0):
- 1.0 = printed clearly and unambiguously
- 0.7 = partially obscured or requires interpretation
- 0.4 = guessed or inferred from context
- 0.1 = very uncertain

Stored in `document_metadata.field_confidences` as JSONB: `{"po_number": 0.97, ...}`

**UI display thresholds (ReviewModal.tsx):**
- Green badge: confidence ≥ 0.80
- Yellow badge: confidence ≥ 0.50
- Red badge: confidence < 0.50

---

## 9. Chain Validation System

### 9.1 Scenario Engine

**Auto-derivation logic** (`derive_scenario()` in `po_service.py`):
1. Count VPO numbers registered on any COMPANY_PO document for this PO
2. Check if any VENDOR_DC document exists
3. Check `has_service_hint` (currently always False — planned future logic)

Result:
- `vpo_count > 0` → PROCUREMENT (we issued a company PO to vendors)
- `vpo_count == 0` + VENDOR_DC exists → DROP_SHIP (vendor ships directly to customer)
- `vpo_count == 0` + service hint → SERVICE_AMC (maintenance/support contract)
- `vpo_count == 0` (default) → STOCK (fulfilled from existing stock)

Scenario is re-derived every time `update_chain_completeness()` runs if current scenario is UNKNOWN.

### 9.2 Required Document Chains per Scenario

| Scenario | Required Documents |
|---|---|
| PROCUREMENT | CUSTOMER_PO, COMPANY_PO, VENDOR_INVOICE, COMPANY_DC, COMPANY_INVOICE |
| STOCK | CUSTOMER_PO, COMPANY_DC, COMPANY_INVOICE |
| DROP_SHIP | CUSTOMER_PO, COMPANY_PO, VENDOR_DC, VENDOR_INVOICE, COMPANY_INVOICE |
| SERVICE_AMC | CUSTOMER_PO, COMPANY_INVOICE |
| UNKNOWN | Full chain: all 6 types (completeness stays 0 if unknown) |

If `requires_install_report=True` on the PO, `INSTALLATION_REPORT` is appended to the required chain.

### 9.3 Reference Validation

Three cross-document checks run on every `GET /chain` call:

**SO Consistency** (for COMPANY_DC and COMPANY_INVOICE):
- Extracted `so_number` from document must match `po.so_number`
- SKIP if either is None/empty (extraction may have missed it)
- MISMATCH if both present but differ

**CPO Reference** (for COMPANY_DC and COMPANY_INVOICE):
- Extracted `po_reference` (Customer Order No.) must match `po.po_number`
- SKIP if either is None/empty
- MISMATCH if both present but differ

**VPO Reference** (for VENDOR_INVOICE):
- Any VPO number in `doc.vpo_numbers` must appear in `po`'s registered VPO list
- Registered VPOs come from COMPANY_PO documents' `vpo_numbers` field
- SKIP if either list is empty

### 9.4 Chain Status Determination (priority order)

1. Any reference check → MISMATCH → `chain_status = MISMATCH`
2. Missing required slots OR missing vendor invoices → `chain_status = INCOMPLETE`
3. `billing_complete == True` → `chain_status = COMPLETE`
4. Otherwise → `chain_status = INCOMPLETE`

### 9.5 Completeness Percentage

```python
completeness_pct = round(verified_slots / total_slots * 100)
# verified_slots = total_slots - len(missing_slots)
# Returns int (0–100)
```

If total_slots == 0 (UNKNOWN scenario with no documents): returns 0.
Fallback: if result is 0 and `po.chain_completeness > 0`, use stored value.

---

## 10. Frontend Architecture

**Language:** TypeScript 5.x
**Framework:** React 18 with hooks only (no class components)
**Build tool:** Vite 5.x
**Styling:** Tailwind CSS 3.x (utility-first, no CSS-in-JS)
**Routing:** react-router-dom v6 with future flags:
```tsx
<BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
```
**Server state:** @tanstack/react-query v5 (caching, background refetch, stale-while-revalidate)
**Client state:** zustand (lightweight stores where needed)
**HTTP:** axios with base URL `/api/v1` (proxied to port 8002 by Vite)
**Icons:** lucide-react (Feather icon style)
**PDF preview:** react-pdf (renders PDF pages as canvas)
**Charts:** recharts (donut chart on Dashboard)

### 10.1 Route Map (App.tsx)

```
/                    → DashboardPage
/customers           → CustomersPage
/orders              → POListPage
/orders/:id          → PODetailPage
/orders/:id/profile  → POProfilePage
/documents           → DocumentsPage (all docs across all POs)
/documents/:id       → DocumentDetailPage
/search              → SearchPage
/admin               → AdminPage
/chat                → ChatPage
```

### 10.2 API Client (axios)

**File:** `frontend/src/api/`
- `customers.ts` — `getCustomers`, `createCustomer`, `updateCustomer`, `deleteCustomer`
- `purchaseOrders.ts` — `getPOs`, `getPO`, `createPO`, `updatePO`, `closePO`, `updateSONumber`, `getChain`, `getProfile`, `exportPO`
- `documents.ts` — `getDocuments`, `getDocument`, `deleteDocument`, `uploadDocument`, `rotateDocument`
- `extraction.ts` — `getMetadata`, `verifyMetadata`, `rejectMetadata`, `reExtract`, `saveCorrections`, `createManualEntry`
- `search.ts` — `globalSearch`, `advancedSearch`
- `chat.ts` — `streamMessage()` using native `EventSource` (not axios)

### 10.3 Custom Hooks

**File:** `frontend/src/hooks/`
- `usePurchaseOrders.ts` — `useQuery` wrappers for PO CRUD
- `useCustomers.ts` — customer queries and mutations
- `useDocuments.ts` — document list, detail, upload mutations
- `useSearch.ts` — debounced global search
- `useExtraction.ts` — extraction metadata and verification

---

## 11. Frontend Pages

### 11.1 DashboardPage

**File:** `frontend/src/pages/DashboardPage.tsx`

**Features:**
- 5 stat cards with delta badges (▲/▼ vs previous 24h window): Total Orders, Pending Review, Verified Today, Total Customers, Extraction Failures
- Donut chart (recharts): document status breakdown
- Quick action buttons: Upload New Document, View All Orders, Search Documents
- Chain status summary bar

**Data source:** `GET /api/v1/admin/stats`

---

### 11.2 CustomersPage

**File:** `frontend/src/pages/CustomersPage.tsx`

**Features:**
- Customer table: customer_id, name, contact email, GST number, PO count, actions
- Inline search (debounced)
- Create customer modal with form validation (email validated client + server)
- Edit customer inline
- Delete with confirmation
- Empty state illustration

**Data source:** `GET /api/v1/customers`

---

### 11.3 POListPage

**File:** `frontend/src/pages/POListPage.tsx`

**Features:**
- Filterable PO table: PO number, customer, date, amount, status badge, chain completeness bar, document count
- Filter panel: customer, status, date range, chain filter (incomplete/critical/complete), missing doc type
- Sort: by created_at, po_date, chain_completeness, total_amount
- Pagination
- Chain status mini-bar (coloured progress) per row
- Click row → `/orders/:id`

**Data source:** `GET /api/v1/purchase-orders`

---

### 11.4 PODetailPage

**File:** `frontend/src/pages/PODetailPage.tsx`

**Features:**
- PO header: number, customer, date, amount, SO number (editable inline), status
- `ChainTimeline` component — 6 document slots with status and ref_no
- Document upload button per slot (triggers file picker)
- Document list with status badges
- View document button → `/documents/:id`
- Order settings panel: fulfillment type, GST type, billing type, install report flag
- Close PO button → `POST /close` with note

**Chain slot ref display:** `buildSlots()` sets `ref: chainByType?.[type]?.[0]?.ref_no`

**Data sources:** `GET /purchase-orders/{id}`, `GET /purchase-orders/{id}/chain-status`, `GET /purchase-orders/{id}/documents`

---

### 11.5 POProfilePage

**File:** `frontend/src/pages/POProfilePage.tsx`

**Features:**
- Sticky section navigation (7 sections)
- Section 1: Overview — PO details, customer, amounts, chain status
- Section 2: Discrepancies — SO mismatches, CPO mismatches, VPO mismatches, billing issues
- Section 3: Field Comparisons — cross-document field value comparison table
- Section 4: Item Comparisons — line-item qty/price comparison table
- Section 5: Vendor Groups — per-vendor chain completeness
- Section 6: Documents — all uploaded documents with metadata
- Section 7: Timeline — event timeline (uploaded, verified, closed, etc.)

**Data source:** `GET /purchase-orders/{id}/profile`

---

### 11.6 DocumentsPage

**File:** `frontend/src/pages/DocumentsPage.tsx` (called `DocumentListPage` internally)

**Features:**
- All documents across all POs
- SLA aging badge: documents pending review > 48h shown with warning colour
- Filter: status, document type, customer, date range
- Pagination
- Click → `/documents/:id`

**Data source:** `GET /api/v1/documents`

---

### 11.7 DocumentDetailPage

**File:** `frontend/src/pages/DocumentDetailPage.tsx`

**Features:**
- Two-column layout: PDF preview (left) + metadata panel (right)
- `PDFViewer` component with page navigation, zoom
- Rotation controls (90° increments)
- Extraction metadata: all fields, per-field confidence badges
- Verify button → opens `ReviewModal`
- Reject button
- Re-extract button
- Manual entry button

**Data sources:** `GET /documents/{id}`, `GET /documents/{id}/preview`, `GET /documents/{document_id}/metadata`

---

### 11.8 SearchPage

**File:** `frontend/src/pages/SearchPage.tsx`

**Features:**
- Global search bar with submit button
- Advanced search panel with 8 fields: invoice_no, dc_no, po_no, so_no, customer_name, delivery_address, date_from, date_to
- Results table: type badge, ref number, display name, customer, actions
- Result types: `customer` (blue), `purchase_order` (green), `document` (purple)
- Deep-link: clicking PO result → `/orders/:id`, document result → `/documents/:id`
- `InlineSearch` dropdown suppressed on this page (guarded by `pathname !== '/search'`)

**Data sources:** `GET /search`, `GET /search/advanced`

---

### 11.9 AdminPage

**File:** `frontend/src/pages/AdminPage.tsx`

**Features:**
- System health panel: database, redis, ollama, models, storage — each with green/red indicator
- Document statistics: pending count, failure count
- Worker queue: workers online, active tasks, queued tasks
- Requeue Pending Models button → `POST /admin/requeue-pending-models`
- Auto-refresh every 30 seconds

**Data sources:** `GET /admin/health`, `GET /admin/stats`, `GET /admin/queue`

---

### 11.10 ChatPage

**File:** `frontend/src/pages/ChatPage.tsx`

**Features:**
- Chat message list with streaming (SSE via native `EventSource`)
- PO context selector dropdown: select a specific PO to anchor queries
- Quick chips: "Show pending documents", "Summarise all orders", "Which orders have issues?"
- Streaming text rendering (chunk-by-chunk append)
- PO number detection in responses: numbers matching `/[A-Z0-9\/-]+/` rendered as clickable links → `/orders/:id`
- Auto-scroll to latest message

**Data source:** `GET /api/v1/chat/stream?message=...&po_id=...` (SSE)

---

## 12. Frontend Components

### 12.1 ChainTimeline

**File:** `frontend/src/components/ChainTimeline/`

Renders 6 document type slots in pipeline order:
`CUSTOMER_PO → COMPANY_PO → VENDOR_DC → VENDOR_INVOICE → COMPANY_DC → COMPANY_INVOICE`

Each slot shows:
- Status icon: waiting (grey), received (blue), verified (green), mismatch (red)
- Document type label
- Reference number (from `ChainSlot.ref_no`)
- Upload / View action button

**Props:** `chain: Record<DocumentType, ChainSlot[]>`, `onUpload`, `onView`

---

### 12.2 ChainStatusBar

**File:** `frontend/src/components/ChainStatusBar/`

Horizontal coloured progress bar. Shows completeness percentage.
Colours: incomplete (yellow), mismatch (red), complete (blue), verified (green).

---

### 12.3 ReviewModal

**File:** `frontend/src/components/ReviewModal.tsx`

Full-screen modal for document extraction review.
- All extracted fields editable
- Per-field confidence badge (coloured dot: green ≥0.80, yellow ≥0.50, red <0.50)
- Side-by-side with PDF preview
- Submit sends `PUT /verify` with edited field values
- Cancel discards changes
- Handles SO entry prompt (`requires_so_entry=true`)
- Handles SO mismatch warning (`so_mismatch_message`)

---

### 12.4 UploadZone

**File:** `frontend/src/components/UploadZone.tsx`

Drag-and-drop + click-to-browse file upload.
Client-side validation: PDF only. Shows filename and size preview.
On submit: calls `POST /purchase-orders/{po_id}/documents`.

---

### 12.5 PDFViewer

**File:** `frontend/src/components/PDFViewer.tsx`

Wraps `react-pdf`. Page navigation, zoom controls, rotation display.
Source: fetches from `GET /documents/{id}/preview`.

---

### 12.6 OrderItemsTable

**File:** `frontend/src/components/OrderItemsTable.tsx`

Renders `order_items` array from `extracted_data`.
Columns: sr_no, part_no, description, qty, unit_price, total_price.
Handles missing columns gracefully. Shows totals row.

---

### 12.7 BillingCompletenessPanel

**File:** `frontend/src/components/BillingCompletenessPanel/`

Displays billing result from `GET /chain`.
FULL billing: one row showing invoiced vs PO total.
STAGED billing: per-milestone table with status badge.

---

### 12.8 ReferenceValidationPanel

**File:** `frontend/src/components/ReferenceValidationPanel/`

Table of reference checks from `GET /chain`.
Columns: document, check type, result (PASS/MISMATCH/SKIP).
MISMATCH rows highlighted red.

---

### 12.9 InlineSearch

**File:** `frontend/src/components/layout/InlineSearch.tsx`

Header search bar with autocomplete dropdown.
- Debounced query (300ms)
- Dropdown suppressed when `pathname === '/search'` (avoids conflicts with search page)
- Arrow key navigation
- Enter key navigates to full `/search?q=...` page
- Dropdown closes on outside click

---

### 12.10 AppShell

**File:** `frontend/src/components/layout/AppShell.tsx`

Sidebar navigation + top header.
Nav links:
- Dashboard (`/`)
- Orders (`/orders`)
- Documents (`/documents`)
- Customers (`/customers`)
- Search (`/search`)
- Chat (`/chat`)
- Admin (`/admin`)

Header: app title, version label `v2.2.0`, `InlineSearch`

---

### 12.11 CustomerCombobox

**File:** `frontend/src/components/CustomerCombobox.tsx`

Searchable dropdown for customer selection on PO create/edit.
Fetches customer list and filters client-side.

---

### 12.12 Other Components

- `Breadcrumb` — `frontend/src/components/layout/Breadcrumb.tsx` — dynamic breadcrumb trail
- `DocumentCard` — compact document card with status badge, type, filename
- `ProfileDocumentSection` — document slot table for POProfile
- `ProfileFieldComparison` — field comparison table for POProfile
- `ProfileItemComparison` — item comparison table for POProfile
- `ProfileDiscrepancyPanel` — severity-sorted discrepancy list
- `ProfileTimeline` — event timeline for POProfile
- `ToastContext` — `frontend/src/context/ToastContext.tsx` — global toast notifications

---

## 13. TypeScript Types

**File:** `frontend/src/types/index.ts` (332 lines)

```typescript
// Enums as string unions
export type DocumentType =
  | 'CUSTOMER_PO' | 'COMPANY_PO' | 'VENDOR_DC' | 'VENDOR_INVOICE'
  | 'COMPANY_DC' | 'COMPANY_INVOICE';

export type DocumentStatus =
  | 'UPLOADED' | 'EXTRACTING' | 'PENDING_REVIEW' | 'PENDING_MODEL'
  | 'VERIFIED' | 'EXTRACTION_FAILED' | 'REJECTED';

export type POStatus =
  | 'INITIATED' | 'IN_PROGRESS' | 'NEAR_COMPLETE' | 'COMPLETE' | 'CANCELLED';

export type MetadataStatus = 'PENDING' | 'EXTRACTED' | 'VERIFIED' | 'FAILED';

export type ExtractionRoute = 'digital' | 'scanned' | null;

export interface Customer {
  id: string;
  customer_id: string;       // e.g. "SKY-AB1234"
  name: string;
  contact_email: string | null;
  gst_number: string | null;
  address: string | null;
  phone: string | null;
  created_at: string;
  updated_at: string;
}

export interface PurchaseOrder {
  id: string;
  po_number: string;
  customer_id: string;
  customer_name?: string;
  customer_sky_id?: string;
  po_date: string | null;
  expected_delivery_date: string | null;
  total_amount: number | null;
  currency: string;
  status: POStatus;
  chain_completeness: number;
  so_number: string | null;
  notes: string | null;
  fulfillment_type: 'procurement' | 'stock';
  items_verified: boolean;
  order_scenario: 'unknown' | 'procurement' | 'stock' | 'drop_ship' | 'service_amc';
  gst_type: 'unknown' | 'igst' | 'cgst_sgst';
  invoice_split: boolean;
  manually_completed: boolean;
  completed_at: string | null;
  completion_note: string | null;
  billing_type?: 'full' | 'staged' | 'recurring';
  created_at: string;
  updated_at: string;
}

export interface DocumentMetadata {
  id: string;
  document_id: string;
  document_type: DocumentType;
  extracted_data: Record<string, unknown> | null;
  primary_ref_no: string | null;
  po_ref_no: string | null;
  doc_date: string | null;
  total_amount: number | null;
  confidence_score: number | null;
  status: MetadataStatus;
  extraction_attempts: number;
  last_error: string | null;
  extracted_at: string | null;
  verified_at: string | null;
  model_version: string | null;
  processing_time_ms: number | null;
  raw_ocr_text: string | null;
  field_confidences: Record<string, number> | null;  // {"po_number": 0.97, ...}
  extraction_version: number | null;
  extraction_route: ExtractionRoute;
}

export interface VerifyResponse extends DocumentMetadata {
  requires_so_entry: boolean;
  verification_pending: boolean;
  so_mismatch_message: string | null;
  po_id: string | null;
  po_so_number: string | null;
}

export interface Document {
  id: string;
  po_id: string;
  document_type: DocumentType;
  original_filename: string;
  file_path: string;
  file_size: number;
  mime_type: string;
  checksum: string;
  page_count: number | null;
  status: DocumentStatus;
  po_number: string;
  customer_name: string;
  po_so_number: string | null;
  metadata: DocumentMetadata | null;
  created_at: string;
  updated_at: string;
  days_pending?: number | null;
}

export interface ChainSlot {
  status: string;
  document_id: string | null;
  ref_no: string | null;
  uploaded_at: string | null;
  confidence: number | null;
  has_validation_errors?: boolean;
  required?: boolean;
  optional?: boolean;
  extraction_route?: ExtractionRoute;
  slot_message?: string | null;
}

export interface ChainStatus {
  po_id: string;
  po_number: string;
  completeness_pct: number;
  chain: Record<string, ChainSlot[]>;
}

export interface FieldCorrection {
  field: string;
  corrected_value: string | null;
}

export interface SearchResult {
  result_type: 'customer' | 'purchase_order' | 'document';
  id: string;
  ref_number: string;
  display_name: string;
  document_type: DocumentType | null;
  po_number: string | null;
  po_id?: string | null;
  customer_name: string | null;
  confidence: number | null;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  query: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: int;
  per_page: int;
}

// Document type ordering and display labels
export const CHAIN_ORDER: DocumentType[] = [
  'CUSTOMER_PO', 'COMPANY_PO', 'VENDOR_DC', 'VENDOR_INVOICE', 'COMPANY_DC', 'COMPANY_INVOICE',
];

export const DOC_TYPE_LABELS: Record<DocumentType, string> = {
  CUSTOMER_PO: 'Customer PO',
  COMPANY_PO: 'Company PO',
  VENDOR_DC: 'Vendor DC',
  VENDOR_INVOICE: 'Vendor Invoice',
  COMPANY_DC: 'Company DC',
  COMPANY_INVOICE: 'Company Invoice',
};

export const DOC_TYPE_SHORT: Record<DocumentType, string> = {
  CUSTOMER_PO: 'C.PO',
  COMPANY_PO: 'PO',
  VENDOR_DC: 'V.DC',
  VENDOR_INVOICE: 'V.Inv',
  COMPANY_DC: 'C.DC',
  COMPANY_INVOICE: 'C.Inv',
};

// PO Profile types
export interface POProfileDocument {
  document_id: string;
  status: string;
  filename: string | null;
  original_filename: string | null;
  primary_ref_no: string | null;
  po_ref_no: string | null;
  doc_date: string | null;
  total_amount: number | null;
  confidence_score: number | null;
  field_confidences: Record<string, number> | null;
  extraction_route: string | null;
  extracted_data: Record<string, unknown> | null;
  verified_at: string | null;
  uploaded_at: string | null;
}

export interface POProfileDocumentSlot {
  document_type: string;
  status: string;       // 'empty' | 'not_applicable' | DocumentStatus value
  documents: POProfileDocument[];
  required: boolean;
  optional: boolean;
}

export interface POProfileDiscrepancy {
  type: string;
  doc_type: string;
  message: string;
  severity: 'error' | 'warning';
}

export interface POProfileTimelineEvent {
  event_type: string;
  doc_type: string;
  timestamp: string;
  detail: string | null;
}

export interface FieldComparison {
  field_label: string;
  source_doc: string;
  source_value: string | null;
  compared_doc: string;
  compared_value: string | null;
  match: boolean | null;
  note: string | null;
}

export interface VendorGroup {
  vendor_po_ref: string;
  vendor_name: string | null;
  completeness_pct: number;
  slots: POProfileDocumentSlot[];
}

export interface ItemComparison {
  sr_no: string | null;
  description: string | null;
  part_no: string | null;
  source_doc: string;
  source_qty: number | null;
  compared_doc: string;
  compared_qty: number | null;
  qty_match: boolean | null;
  source_price?: number | null;
  compared_price?: number | null;
  price_match?: boolean | null;
}

export interface ItemMatch {
  sr_no: string | null;
  description: string | null;
  matched_part_no: string | null;
  confidence: number;
  match_type: 'exact' | 'ai' | 'unmatched';
}

export interface ParsedAddress {
  pin_code: string | null;
  city: string | null;
  state: string | null;
  full_address: string | null;
}

export interface POProfile {
  po_id: string;
  po_number: string;
  customer_name: string;
  customer_sky_id: string;
  so_number: string | null;
  po_date: string | null;
  total_amount: number | null;
  status: string;
  chain_completeness: number;
  chain_completeness_display: string | null;   // "72.5%" | "—" when scenario unknown
  fulfillment_type: 'procurement' | 'stock';
  order_scenario: 'unknown' | 'procurement' | 'stock' | 'drop_ship' | 'service_amc';
  gst_type: 'unknown' | 'igst' | 'cgst_sgst';
  invoice_split: boolean;
  manually_completed: boolean;
  completed_at: string | null;
  completion_note: string | null;
  created_at: string;
  slots: POProfileDocumentSlot[];
  timeline: POProfileTimelineEvent[];
  discrepancies: POProfileDiscrepancy[];
  cross_references: Record<string, string[]>;
  vendor_groups: VendorGroup[];
  items_verified: boolean;
  field_comparisons: FieldComparison[];
  item_comparisons: ItemComparison[];
  item_matches: ItemMatch[];
  delivery_address_parsed: ParsedAddress | null;
}
```

---

## 14. Data Flow Diagrams

### 14.1 Document Upload → Extraction → Review → Verify

```
Operator uploads PDF
    │
    ▼
POST /purchase-orders/{po_id}/documents
    ├── Validates: PDF only (extension + MIME)
    ├── Saves file to NAS: {NAS_BASE_PATH}/{customer_id}/{po_number}/{uuid}_{filename}
    ├── Creates Document record: status=UPLOADED
    ├── Creates DocumentMetadata stub: status=PENDING
    └── Queues Celery: extract_document.delay(doc_id)
          │
          ▼ (background, async)
    Celery Worker: extract_document(doc_id)
          ├── doc.status = EXTRACTING
          ├── HybridRouter → DIGITAL or SCANNED
          ├── [SCANNED] PDF → images → Layer 1 OCR → markdown
          │   [DIGITAL] pypdf text extraction → markdown
          ├── Layer 2 LLM → JSON with per-field confidence
          ├── _extract_field_confidences() → flat fields + field_confidences dict
          ├── validate_extracted_fields() → normalise amounts/dates
          ├── validate_invoice_math() → check line totals
          ├── validate_so_number() → check SO against po.so_number
          ├── Write DocumentMetadata: extracted_data, field_confidences, confidence_score
          ├── Write ReferenceIndex entries
          ├── doc.status = PENDING_REVIEW
          └── _update_chain_sync() → po.chain_completeness, po.status
                │
                ▼
    Operator opens Document Detail page
          ├── See PDF + extracted fields + confidence badges
          ├── Edit fields if needed
          └── Click Verify
                │
                ▼
    PUT /documents/{doc_id}/metadata/verify
          ├── [CUSTOMER_PO] Check po.so_number set → if not: requires_so_entry=True
          ├── [COMPANY_DC/INVOICE] Check SO match → if mismatch: so_mismatch_message
          ├── All pass: meta.status=VERIFIED, doc.status=VERIFIED
          ├── Rebuild ReferenceIndex with verified values
          └── _update_chain_async() → po.chain_completeness, chain_status
```

### 14.2 Chain Validation Computation

```
GET /purchase-orders/{po_id}/chain
    │
    ├── Load PO with documents + metadata
    ├── Collect vpo_numbers from COMPANY_PO documents
    ├── Sum invoiced_total from COMPANY_INVOICE metadata
    ├── Build docs_payload: [{document_type, so_number, vpo_numbers, extraction_ok,
    │                          cpo_ref, billing_stage, amount}, ...]
    └── compute_chain_status(scenario, po_number, so_number, po_total, ...)
            │
            ├── get_scenario_chain(scenario) → required_types list
            ├── Missing slots = required_types - present_types
            ├── Missing vendor invoices = VPOs with no matching VENDOR_INVOICE
            ├── For each COMPANY_DC / COMPANY_INVOICE:
            │     check_so_consistency(extracted_so, po.so_number)
            │     check_cpo_reference(extracted_cpo_ref, po.po_number)
            ├── For each VENDOR_INVOICE:
            │     check_vpo_reference(doc_vpo_numbers, registered_vpo_numbers)
            ├── Billing check:
            │     STAGED → check_staged_billing(po_total, milestones, invoices)
            │     FULL   → check_full_billing(invoiced_total, po_total)
            └── Determine chain_status:
                  MISMATCH (any reference mismatch) takes priority
                  INCOMPLETE if any missing slots
                  COMPLETE if billing complete
                  INCOMPLETE otherwise
```

### 14.3 Search Indexing

```
On extraction or verify:
    delete ReferenceIndex where document_id = doc.id
    for each searchable field in doc_type:
        if value is not null and not empty:
            insert ReferenceIndex(document_id, po_id, ref_type, ref_value, document_type)

Global search query:
    SELECT * FROM reference_index WHERE ref_value ILIKE '%q%'  -- reference matches
    SELECT * FROM customers WHERE name ILIKE '%q%'              -- customer name
    SELECT * FROM customers WHERE customer_id ILIKE '%q%'       -- customer ID
    SELECT * FROM purchase_orders WHERE po_number ILIKE '%q%'   -- PO number
    Deduplicate by type+id key
    Filter: ref_number must not be blank

Searchable fields per document type:
    CUSTOMER_PO:     po_number
    COMPANY_PO:      po_number
    VENDOR_DC:       dc_number, po_reference
    VENDOR_INVOICE:  invoice_number, po_reference
    COMPANY_DC:      dc_number, po_reference, so_number
    COMPANY_INVOICE: invoice_number, po_reference, so_number
```

### 14.4 Chat Intent → Context → LLM → SSE

```
GET /chat/stream?message=...&po_id=...
    │
    ├── _detect_intent(message, po_id):
    │     if po_id: "order_query"
    │     token match _PLATFORM_KEYWORDS: "platform_query"
    │     token match _SEARCH_KEYWORDS: "search_query"
    │     token match _ORDER_KEYWORDS: "order_query"
    │     default: "general"
    │
    ├── Build context block:
    │     order_query  → build_order_context(po_id)
    │                    → loads PO, docs, runs compute_chain_status()
    │                    → text: ORDER CONTEXT, billing, missing docs, doc list
    │     search_query → build_search_context(message)
    │                    → searches ReferenceIndex + DocumentMetadata
    │     platform_query → build_platform_context()
    │                    → order counts, doc counts, critical orders
    │
    ├── POST {chat_base_url}/api/chat:
    │     model: settings.chat_model (default "qwen2.5:3b")
    │     messages: [{role: system, content: SYSTEM_PROMPT + context},
    │                {role: user, content: message}]
    │     stream: true
    │     options: {num_ctx: 8192, num_predict: 1024, temperature: 0.3}
    │
    └── StreamingResponse yields SSE:
          Each Ollama chunk → data: {"chunk": "...", "done": false}\n\n
          Final           → data: {"chunk": "", "done": true}\n\n
          Error           → data: {"chunk": "Chat service unavailable: ...", "done": false}\n\n
                            data: {"chunk": "", "done": true}\n\n
```

---

## 15. Known Issues — from Code Review

These issues were identified during code review and have not yet been fixed.

---

### Issue 1 — Provider confidence unwrapping gap (medium)

**Files:** `backend/app/services/extraction/providers/ollama_provider.py`,
`backend/app/services/extraction/providers/openai_compat_provider.py`

**Problem:** `two_layer_client.py._extract_field_confidences()` unwraps `{"value": x, "confidence": 0.97}`
format correctly. However, the new provider abstraction layer (`OllamaProvider.run_extraction()` and
`OpenAICompatProvider.run_extraction()`) may return raw parsed JSON without calling
`_extract_field_confidences()`, meaning `field_confidences` stays null for documents
processed through the new provider path.

**Impact:** Per-field confidence badges show nothing in ReviewModal for those documents.

---

### Issue 2 — Redis connection not closed in get_po_profile (medium)

**File:** `backend/app/services/po_service.py` around line 1034–1045

**Problem:** `get_po_profile()` opens a Redis connection for profile caching but
`await r.aclose()` may not be reached in all exception paths, leaking connections
under high load.

**Impact:** Redis connection pool exhaustion under sustained traffic.

---

### Issue 3 — verify=False on provider HTTP calls (medium)

**Files:** `backend/app/services/extraction/providers/ollama_provider.py` and others

**Problem:** `verify=False` on `httpx.AsyncClient` calls (TLS verification disabled).
This was added to support RunPod's self-signed certificates but applies globally,
removing certificate validation even for remote endpoints.

**Impact:** Man-in-the-middle attacks possible on extraction traffic to remote Ollama.
**Fix:** Use `ocr_extractor_ca_bundle` setting to specify the CA bundle instead of disabling verification entirely.

---

### Issue 4 — Chain completeness fallback edge case (low)

**File:** `backend/app/api/v1/purchase_orders.py` line 180

**Problem:**
```python
if result["completeness_pct"] == 0 and po.chain_completeness:
    result["completeness_pct"] = int(po.chain_completeness)
```
For UNKNOWN scenario, `completeness_pct` is always 0. If an operator previously
set `chain_completeness` manually or it was computed under a different scenario,
the old stale value is returned instead of 0, hiding the fact that the scenario
is still unknown.

---

### Issue 5 — Multi-word entries in _PLATFORM_KEYWORDS never match (low)

**File:** `backend/app/services/chat_service.py` line 28

**Problem:**
```python
_PLATFORM_KEYWORDS = {"today", "attention", "summary", "overview",
                      "all orders", "dashboard", "pending", "total", "how many"}
```
Intent detection uses `tokens & _PLATFORM_KEYWORDS` where `tokens` is a set of
individual words from `re.findall(r"\b\w+\b", lower)`. Multi-word entries like
`"all orders"` and `"how many"` are never in the token set so they never match.
The user saying "show all orders" will not trigger `platform_query` intent.

**Fix:** Either split multi-word entries into individual keywords, or use a substring check for multi-word phrases.

---

### Issue 6 — int() crash on decimal quantity strings (low)

**File:** `backend/app/services/item_matcher.py` lines 194 and 210

**Problem:** Redington invoices use decimal quantities (`"2.000"`, `"1.000 EA"`).
`item_matcher.py` calls `int()` on qty strings directly without handling the decimal
or the `" EA"` suffix. This causes a `ValueError` crash when matching items from
Redington invoices.

**Fix:** Use `float(qty_str.split()[0].replace(",",""))` or guard with try/except.

---

*End of APPLICATION_REFERENCE.md — generated 2026-04-17 from source code*
