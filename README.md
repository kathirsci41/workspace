# DocPlatform V3.0

PO-centric document management system with OCR-powered data extraction.
Manages the full logistics document chain — Customer PO, Vendor DC, Vendor Invoice, Company DC, Company Invoice, and POD — under each Purchase Order.

## Architecture

| Component | Technology | Port |
|-----------|------------|------|
| Backend | FastAPI (Python 3.12) | 8000 |
| Frontend | React 18 + Vite + TypeScript | 5173 |
| Database | PostgreSQL 16 | 5433 |
| Cache/Broker | Redis 7 | 6379 |
| Task Queue | Celery (solo pool) | — |
| OCR Engine | Ollama + glm-ocr (2.2 GB) | 11434 |

## Features

- **Customer & PO management** — CRUD with status tracking
- **Document upload pipeline** — PDF upload → Celery task → OCR extraction → auto-verify
- **OCR extraction** — Vision model reads invoice/DC fields into structured JSON
- **Document chain** — 6 document types per PO with completion percentage
- **Search** — Inline header search + dedicated search page across documents, POs, customers
- **Preview** — In-browser PDF viewer with download
- **Delete & re-upload** — Replace documents and re-run extraction
- **Manual entry** — POD and other document types without OCR

## Quick Start (Without Docker)

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker Desktop (for PostgreSQL & Redis containers)
- Ollama with `glm-ocr` model

### 1. Start infrastructure

```bash
docker compose -f docker-compose.dev.yml up -d postgres redis
```

### 2. Install Ollama model

```bash
ollama pull glm-ocr
```

### 3. Backend

```bash
cd backend
python -m venv venv
# Windows
.\venv\Scripts\Activate.ps1
# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start API
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 4. Celery worker (separate terminal)

```bash
cd backend
.\venv\Scripts\Activate.ps1  # or source venv/bin/activate
celery -A celery_app worker --loglevel=info --pool=solo
```

### 5. Frontend (separate terminal)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Docker Compose (Full Stack)

```bash
# Start everything except Ollama (runs natively on host)
docker compose -f docker-compose.dev.yml up -d

# Ollama must be running on the host at localhost:11434
ollama serve
```

## Environment Variables

Copy `.env.example` to `.env` and adjust values. Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `...@localhost:5433/docplatform` | Async PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis broker URL |
| `NAS_BASE_PATH` | `/nas/documents` | Document storage root |
| `OCR_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OCR_MODEL_NAME` | `glm-ocr` | Vision model for OCR |
| `OCR_TIMEOUT` | `120` | Seconds per OCR request |
| `OCR_PDF_DPI` | `200` | PDF-to-image render DPI |
| `OCR_MAX_PAGES` | `10` | Max pages to process per document |

## Project Structure

```
docplatform-v3/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # FastAPI route handlers
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # Business logic
│   │   │   └── extraction/  # OCR pipeline (ocr_client, prompts, parser)
│   │   ├── config.py        # Settings from env
│   │   └── main.py          # FastAPI app entry
│   ├── celery_app.py        # Celery configuration
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── pages/           # Route pages
│   │   ├── api/             # API client
│   │   └── App.tsx
│   ├── Dockerfile
│   └── package.json
├── storage/documents/       # Local document storage
├── .plan/                   # Architecture docs & benchmarks
├── docker-compose.dev.yml   # Dev compose (postgres + redis + app)
├── .env.example
└── .env                     # Local config (git-ignored)
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/api/v1/customers` | List customers |
| POST | `/api/v1/customers` | Create customer |
| GET | `/api/v1/purchase-orders` | List POs |
| POST | `/api/v1/purchase-orders` | Create PO |
| GET | `/api/v1/purchase-orders/{id}` | PO detail with documents |
| POST | `/api/v1/purchase-orders/{id}/documents` | Upload document |
| GET | `/api/v1/documents/{id}` | Document detail |
| GET | `/api/v1/documents/{id}/preview` | PDF preview |
| GET | `/api/v1/documents/{id}/download` | PDF download |
| DELETE | `/api/v1/documents/{id}` | Delete document |
| POST | `/api/v1/extraction/{id}/re-extract` | Re-run OCR |
| POST | `/api/v1/extraction/{id}/manual` | Manual metadata entry |
| GET | `/api/v1/search?q=` | Global search |
| GET | `/api/v1/dashboard/stats` | Dashboard statistics |

## OCR Pipeline

1. PDF uploaded → stored in `NAS_BASE_PATH/{customer}/{po}/{doc_type}/`
2. Celery task converts PDF pages to images (max 768px, 200 DPI)
3. Each page sent to Ollama `glm-ocr` with document-type-specific prompt
4. Response parsed into structured JSON (4-strategy parser with fallbacks)
5. Fields extracted: reference numbers, dates, amounts, quantities, vendor/customer names
6. Confidence score calculated from field fill rate
7. Document auto-verified if parsing succeeds

### OCR Performance (glm-ocr)

- **JSON parse rate**: 100%
- **Fill rate**: 94–95%
- **Speed**: ~7s per single-page document
- **Character similarity**: ~80% on reference numbers

See [.plan/OCR_BENCHMARK_REPORT.md](.plan/OCR_BENCHMARK_REPORT.md) for full benchmark results across 5 models.

## License

Private — Internal use only.
