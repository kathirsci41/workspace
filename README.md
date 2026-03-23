# Document Processing Platform (DPP) — v2.4.0

PO-centric logistics document management with two-layer AI extraction.
Handles the full document chain — Customer PO, Company PO, Vendor DC, Vendor Invoice, Company DC, Company Invoice — grouped under each Purchase Order with chain completeness tracking.

---

## Architecture

| Component | Technology | Port |
| ----------- | ------------ | ---- |
| Backend | FastAPI (Python 3.12) | 8000 |
| Frontend | React 18 + Vite + TypeScript | 5174 |
| Database | PostgreSQL 16 | 5434 |
| Cache / Broker | Redis 7 | 6380 |
| Task Queue | Celery (solo pool) | — |
| OCR — Layer 1 | Ollama + `glm-ocr:latest` | 11434 |
| OCR — Layer 2 | Ollama + `qwen2.5:7b` | 11434 |

**OCR endpoint:** RunPod remote (`https://<id>.proxy.runpod.net/`) or local Ollama at `http://localhost:11434`

---

## Features

- **Customer and PO management** — CRUD with status tracking and chain completeness score
- **Two-layer AI extraction** — `glm-ocr` converts document to Markdown, `qwen2.5:7b` extracts structured JSON
- **Document chain** — 6 document types per PO with 0–100% completeness score
- **SO number validation** — COMPANY_DC and COMPANY_INVOICE auto-validated against stored SO number
- **Human review workflow** — Operators verify or correct extracted fields with full audit trail
- **Operator remarks + custom fields** — Free-text notes and ad-hoc fields per document, persisted in extracted data
- **PDF viewer** — In-browser viewer with scroll/pinch zoom, Ctrl+scroll, rotate (per document), download
- **Global toast notifications** — Real-time feedback for extraction, verification, network errors, service outages
- **NAS error handling** — Upload fails fast with a clear message if storage is unreachable
- **Collapsible sidebar** — Icon-only by default, expands on demand
- **Filter system (PO List)** — Date range, SO search, chain completeness, missing doc type, sort options
- **Documents page** — Cross-PO document search by type, status, customer, date range
- **Admin console** — Live system health, pipeline counters, Celery queue status, model requeue
- **Search** — Global full-text search + reference number lookup across all extracted data
- **Re-extraction** — Re-run OCR on any document without losing manual corrections
- **PENDING_MODEL status** — Documents held when AI model is offline, auto-requeued when service recovers

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker Desktop (for PostgreSQL and Redis)
- Ollama with both models pulled **or** a RunPod endpoint configured in `.env`

### 1. Start infrastructure

```bash
docker compose -f docker-compose.dev.yml up -d postgres redis
```

### 2. Pull Ollama models (local only — skip if using RunPod)

```bash
ollama pull glm-ocr
ollama pull qwen2.5:7b
```

### 3. Backend

```bash
cd backend

python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1
# Linux / Mac
source venv/bin/activate

pip install -r requirements.txt

# Run DB migrations
alembic upgrade head

# Start API
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 4. Celery worker (separate terminal)

```bash
cd backend
.\venv\Scripts\Activate.ps1   # or source venv/bin/activate
celery -A celery_app worker --loglevel=info --pool=solo
```

### 5. Frontend (separate terminal)

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5174>

### Windows one-command startup

```powershell
.\start.ps1
```

Starts Docker infra, backend, Celery worker, and frontend dev server. Streams logs from `logs/app.log` and `logs/celery.log` in real time.

---

## Environment Variables

Copy `.env.example` to `.env` and adjust. Key settings:

| Variable | Default | Description |
| ---------- | ------- | ----------- |
| `DATABASE_URL` | `...@localhost:5434/docplatform` | Async PostgreSQL connection |
| `SYNC_DATABASE_URL` | `...@localhost:5434/docplatform` | Sync connection for Alembic / Celery |
| `REDIS_URL` | `redis://localhost:6380/0` | Redis broker URL |
| `NAS_BASE_PATH` | `./storage/documents` | Document file storage root (NAS mount or local) |
| `OCR_BASE_URL` | `http://localhost:11434` | Ollama endpoint (local or RunPod) |
| `OCR_MODEL_NAME` | `glm-ocr:latest` | Layer 1 OCR model |
| `OCR_TWO_LAYER_ENABLED` | `true` | Enable two-layer pipeline |
| `OCR_EXTRACTOR_BASE_URL` | same as `OCR_BASE_URL` | Layer 2 model endpoint |
| `OCR_EXTRACTOR_MODEL` | `qwen2.5:7b` | Layer 2 extraction model |
| `OCR_EXTRACTOR_NUM_CTX` | `8192` | Context window for Layer 2 |
| `OCR_TIMEOUT` | `1200` | Seconds per OCR request |
| `OCR_PDF_DPI` | `200` | PDF-to-image render DPI |
| `OCR_MAX_PAGES` | `10` | Max pages per document |
| `OCR_SAVE_DEBUG_MARKDOWN` | `false` | Save raw OCR output to disk |
| `CORS_ORIGINS` | `["http://localhost:5174"]` | Allowed frontend origins |
| `DEBUG` | `false` | FastAPI debug mode |

---

## Project Structure

```
DPP 2.2.0/
├── backend/
│   ├── app/
│   │   ├── api/v1/            # FastAPI route handlers
│   │   │   ├── admin.py       # Health, stats, queue, requeue
│   │   │   ├── customers.py
│   │   │   ├── documents.py
│   │   │   ├── extraction.py
│   │   │   ├── purchase_orders.py
│   │   │   └── search.py
│   │   ├── models/            # SQLAlchemy ORM models
│   │   ├── schemas/           # Pydantic request/response schemas
│   │   ├── services/
│   │   │   ├── extraction/    # Two-layer OCR pipeline
│   │   │   │   ├── tasks.py   # Celery extraction task
│   │   │   │   ├── ocr_client.py
│   │   │   │   ├── prompts.py
│   │   │   │   ├── response_parser.py
│   │   │   │   └── so_validator.py
│   │   │   ├── storage_service.py  # NAS file I/O + availability check
│   │   │   └── po_service.py
│   │   ├── config.py          # Settings (pydantic-settings)
│   │   ├── database.py        # Async + sync engines, connection pooling
│   │   └── main.py            # FastAPI app entry
│   ├── alembic/versions/      # DB migrations (6 versions)
│   ├── celery_app.py          # Celery configuration + task signals
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/               # Axios API functions
│   │   ├── components/        # Shared React components
│   │   │   ├── PDFViewer.tsx  # PDF viewer (zoom, rotate, scroll)
│   │   │   ├── ReviewModal.tsx
│   │   │   ├── PDFPreviewPanel.tsx
│   │   │   └── layout/        # AppShell, collapsible sidebar
│   │   ├── context/
│   │   │   └── ToastContext.tsx  # Global toast notifications
│   │   ├── hooks/             # TanStack Query hooks
│   │   ├── pages/             # Route pages (7 pages)
│   │   └── App.tsx
│   └── package.json
├── nginx/
│   └── nginx.conf             # Reverse proxy config
├── storage/                   # Local document storage (dev fallback)
├── logs/                      # Runtime log files (app, celery, ai, db)
├── docker-compose.dev.yml     # Dev infra (postgres + redis only)
├── docker-compose.prod.yml    # Full production stack (6 services)
├── docs/
│   ├── PDD.md                 # Business Product Design Document
│   └── task-sheet.md          # Session-by-session task log
├── PDD.md                     # Technical Product Design Document
├── .env.example
└── .env                       # Local config (git-ignored)
```

---

## API Endpoints

### Customers

| Method | Endpoint | Description |
| -------- | ---------- | ----------- |
| GET | `/api/v1/customers` | List with pagination and search |
| POST | `/api/v1/customers` | Create customer |
| GET | `/api/v1/customers/{id}` | Customer detail |
| PATCH | `/api/v1/customers/{id}` | Update customer |
| GET | `/api/v1/customers/{id}/purchase-orders` | Customer's PO list |

### Purchase Orders

| Method | Endpoint | Description |
| -------- | ---------- | ----------- |
| GET | `/api/v1/purchase-orders` | List with filters (date, SO, chain, doc gap, sort) |
| POST | `/api/v1/purchase-orders` | Create PO |
| GET | `/api/v1/purchase-orders/{id}` | PO detail with chain status |
| PATCH | `/api/v1/purchase-orders/{id}` | Update PO including SO number |
| DELETE | `/api/v1/purchase-orders/{id}` | Delete PO and all documents |
| GET | `/api/v1/purchase-orders/{id}/chain-status` | Chain completeness per slot |
| POST | `/api/v1/purchase-orders/{id}/documents` | Upload document to a PO |
| GET | `/api/v1/purchase-orders/{id}/documents` | List documents for a PO |

### Documents

| Method | Endpoint | Description |
| -------- | ---------- | ----------- |
| GET | `/api/v1/documents` | List with filters (type, status, customer, date) |
| GET | `/api/v1/documents/{id}` | Document detail with metadata |
| DELETE | `/api/v1/documents/{id}` | Delete document |
| GET | `/api/v1/documents/{id}/preview` | In-browser preview (streaming) |
| GET | `/api/v1/documents/{id}/download` | Download original file |
| POST | `/api/v1/documents/{id}/rotate` | Rotate document pages |

### Extraction

| Method | Endpoint | Description |
| -------- | ---------- | ----------- |
| GET | `/api/v1/documents/{id}/metadata/template` | Empty schema for manual entry |
| POST | `/api/v1/documents/{id}/metadata/manual` | Submit manually entered data |
| POST | `/api/v1/documents/{id}/re-extract` | Re-trigger extraction (version-safe) |
| GET | `/api/v1/documents/{id}/metadata` | Get extracted metadata |
| PUT | `/api/v1/documents/{id}/metadata/verify` | Operator verifies extracted data |
| PUT | `/api/v1/documents/{id}/metadata/reject` | Reject — marks for re-upload |
| POST | `/api/v1/documents/{id}/corrections` | Save field-level corrections (audit trail) |

### Search

| Method | Endpoint | Description |
| -------- | ---------- | ----------- |
| GET | `/api/v1/search` | Full-text search |
| GET | `/api/v1/search/by-ref/{ref}` | Reference number exact lookup |
| GET | `/api/v1/search/advanced` | Filtered multi-param search |

### Admin

| Method | Endpoint | Description |
| -------- | ---------- | ----------- |
| GET | `/api/v1/admin/health` | DB / Redis / Ollama / Storage status (cached 30s) |
| GET | `/api/v1/admin/stats` | Document and PO counts by all statuses |
| GET | `/api/v1/admin/queue` | Celery worker count + active and queued tasks |
| POST | `/api/v1/admin/requeue-pending-models` | Re-enqueue PENDING_MODEL documents |

---

## Extraction Pipeline

```text
Document upload (PDF only)
        |
        v
NAS availability check — fail fast with 503 if storage unreachable
        |
        v
Celery task — async (non-blocking)
        |
        v
Pre-flight: model/endpoint check
  If model unavailable → status PENDING_MODEL (held, retried when service recovers)
        |
        v
Hybrid router — digital vs scanned detection
        |
        +─ Digital path (no GPU): PyMuPDF text extraction → Layer 2 structuring
        |
        +─ Scanned path:
              PDF → images (Ghostscript, 200 DPI)
              OpenCV preprocessing (grayscale, contrast, deskew)
              Layer 1: glm-ocr:latest — image → Markdown
              Layer 2: qwen2.5:7b — Markdown → structured JSON
        |
        v
Validation
  Invoice math check (line items × qty vs total)
  SO number cross-check (COMPANY_DC and COMPANY_INVOICE)
  Errors saved to extracted_data._validation_errors
        |
        v
Document status → PENDING_REVIEW
Operator reviews, corrects, and verifies
```

**On failure:** exception saved to `DocumentMetadata.last_error`, status → `EXTRACTION_FAILED`, partial data preserved.

---

## Document Status Flow

```text
UPLOADED → EXTRACTING → PENDING_REVIEW → VERIFIED
               |                |
               |                +→ REJECTED
               |
               +→ EXTRACTION_FAILED
               +→ PENDING_MODEL  (model offline — retried on requeue)
```

---

## Frontend Pages

| Route | Page |
| ----- | ---- |
| `/` | Dashboard — stats overview + top 10 pending queue |
| `/purchase-orders` | PO list with full filter system |
| `/purchase-orders/:id` | PO detail — chain status + document cards |
| `/documents` | Cross-PO document search |
| `/customers` | Customer management |
| `/search` | Global search |
| `/admin` | System health + pipeline monitoring |

---

## Branches

| Branch | Purpose |
| -------- | ------- |
| `master` | Stable production baseline |
| `staging` | Demo-ready — frozen at DPP-2.4.0 |
| `development` | Active development (next version) |

---

## License

Private — Internal use only.
