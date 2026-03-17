# Document Processing Platform (DPP) — v2.2.0

PO-centric logistics document management with two-layer AI extraction.
Handles the full document chain — Customer PO, Company PO, Vendor DC, Vendor Invoice, Company DC, Company Invoice — grouped under each Purchase Order with chain completeness tracking.

---

## Architecture

| Component | Technology | Port |
|-----------|------------|------|
| Backend | FastAPI (Python 3.12) | 8000 |
| Frontend | React 18 + Vite + TypeScript | 5173 |
| Database | PostgreSQL 16 | 5433 |
| Cache / Broker | Redis 7 | 6379 |
| Task Queue | Celery (solo pool) | — |
| OCR — Layer 1 | Ollama + `glm-ocr:latest` | 11434 |
| OCR — Layer 2 | Ollama + `qwen2.5:7b` | 11434 |

**OCR endpoint:** RunPod remote (`https://<id>.proxy.runpod.net/`) or local Ollama at `http://localhost:11434`

---

## Features

- **Customer and PO management** — CRUD with status tracking and chain completeness score
- **Two-layer AI extraction** — `glm-ocr` converts document to Markdown, `qwen2.5:7b` extracts structured JSON
- **Document chain** — 6 document types per PO with 0.0–1.0 completeness score
- **SO number validation** — COMPANY_DC and COMPANY_INVOICE auto-validated against stored SO number
- **Human review workflow** — Operators verify or correct extracted fields with full audit trail
- **Filter system (PO List)** — Date range, SO search, chain completeness, missing doc type, sort options
- **Documents page** — Cross-PO document search by type, status, customer, date range
- **Admin console** — Live system health, pipeline counters, extraction failure table, Celery queue status
- **Search** — Global full-text search + reference number lookup across all extracted data
- **PDF preview** — In-browser viewer with page rotation and download
- **Re-extraction** — Re-run OCR on any document without losing manual corrections

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

Open http://localhost:5173

---

## Environment Variables

Copy `.env.example` to `.env` and adjust. Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `...@localhost:5433/docplatform` | Async PostgreSQL connection |
| `SYNC_DATABASE_URL` | `...@localhost:5433/docplatform` | Sync connection for Alembic |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis broker URL |
| `NAS_BASE_PATH` | `./storage/documents` | Document file storage root |
| `OCR_BASE_URL` | `http://localhost:11434` | Ollama endpoint (local or RunPod) |
| `OCR_MODEL_NAME` | `glm-ocr:latest` | Layer 1 OCR model |
| `OCR_TWO_LAYER_ENABLED` | `true` | Enable two-layer pipeline |
| `OCR_EXTRACTOR_BASE_URL` | same as `OCR_BASE_URL` | Layer 2 model endpoint |
| `OCR_EXTRACTOR_MODEL` | `qwen2.5:7b` | Layer 2 extraction model |
| `OCR_EXTRACTOR_NUM_CTX` | `8192` | Context window for Layer 2 |
| `OCR_TIMEOUT` | `120` | Seconds per OCR request |
| `OCR_PDF_DPI` | `200` | PDF-to-image render DPI |
| `OCR_MAX_PAGES` | `10` | Max pages per document |
| `OCR_SAVE_DEBUG_MARKDOWN` | `false` | Save raw OCR output to disk |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed frontend origins |
| `DEBUG` | `false` | FastAPI debug mode |

---

## Project Structure

```
DPP 2.2.0/
├── backend/
│   ├── app/
│   │   ├── api/v1/            # FastAPI route handlers
│   │   │   ├── admin.py       # Health, stats, queue
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
│   │   │   │   ├── parser.py
│   │   │   │   └── so_validator.py
│   │   │   └── po_service.py
│   │   ├── config.py          # Settings (pydantic-settings)
│   │   └── main.py            # FastAPI app entry
│   ├── celery_app.py          # Celery configuration
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/               # Axios API functions
│   │   ├── components/        # Shared React components
│   │   │   └── layout/        # AppShell, navigation
│   │   ├── hooks/             # TanStack Query hooks
│   │   ├── pages/             # Route pages (7 pages)
│   │   └── App.tsx
│   └── package.json
├── storage/                   # Local document storage
├── docker-compose.dev.yml
├── PDD.md                     # Product Design Document
├── .env.example
└── .env                       # Local config (git-ignored)
```

---

## API Endpoints

### Customers

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/customers` | List with pagination and search |
| POST | `/api/v1/customers` | Create customer |
| GET | `/api/v1/customers/{id}` | Customer detail |
| PATCH | `/api/v1/customers/{id}` | Update customer |
| DELETE | `/api/v1/customers/{id}` | Delete customer |
| GET | `/api/v1/customers/{id}/purchase-orders` | Customer's PO list |

### Purchase Orders

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/purchase-orders` | List with filters (date, SO, chain, doc gap, sort) |
| POST | `/api/v1/purchase-orders` | Create PO |
| GET | `/api/v1/purchase-orders/{id}` | PO detail with chain status |
| PATCH | `/api/v1/purchase-orders/{id}` | Update PO including SO number |
| DELETE | `/api/v1/purchase-orders/{id}` | Delete PO and all documents |

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/documents` | List with filters (type, status, customer, date) |
| POST | `/api/v1/documents/upload` | Upload document to a PO |
| GET | `/api/v1/documents/{id}` | Document detail with metadata |
| DELETE | `/api/v1/documents/{id}` | Delete document |
| GET | `/api/v1/documents/{id}/preview` | In-browser preview |
| GET | `/api/v1/documents/{id}/download` | Download original file |
| POST | `/api/v1/documents/{id}/rotate` | Rotate pages |

### Extraction

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/metadata-template/{doc_type}` | Empty schema for manual entry |
| POST | `/api/v1/documents/{id}/extract/manual` | Submit manually entered data |
| POST | `/api/v1/documents/{id}/extract/reextract` | Re-trigger extraction |
| POST | `/api/v1/documents/{id}/verify` | Operator verifies extracted data |
| POST | `/api/v1/documents/{id}/reject` | Reject — marks for re-upload |
| PATCH | `/api/v1/documents/{id}/corrections` | Save field-level corrections |

### Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/search` | Full-text search |
| GET | `/api/v1/search/reference/{ref}` | Reference number lookup |
| GET | `/api/v1/search/advanced` | Filtered multi-param search |

### Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/admin/health` | DB / Redis / Ollama / Storage status |
| GET | `/api/v1/admin/stats` | Document and PO counts by all statuses |
| GET | `/api/v1/admin/queue` | Celery worker count + active and queued tasks |

---

## Extraction Pipeline

```text
Document upload (PDF / PNG / TIFF)
        |
        v
Celery task — async (non-blocking)
        |
        v
Layer 1: glm-ocr:latest
  Pages converted to images (PyMuPDF, 200 DPI)
  Each page sent to Ollama vision model
  Output: raw Markdown preserving tables and layout
        |
        v
Layer 2: qwen2.5:7b
  Markdown + document-type-specific JSON schema prompt
  Output: structured JSON with all extracted fields
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

**On failure:** exception string saved to `DocumentMetadata.last_error`, status set to `EXTRACTION_FAILED`, partial data preserved.

---

## Document Status Flow

```text
UPLOADED → EXTRACTING → PENDING_REVIEW → VERIFIED
                      |
                      +→ EXTRACTION_FAILED
                      +→ REJECTED
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

## License

Private — Internal use only.
