# Document Platform V3.0 — Implementation Guide (Dev Build)

**Focus:** Core flow only — no authentication, no production hardening  
**Approach:** Build with Claude, phase by phase  
**Stack:** FastAPI + PostgreSQL + Celery + Redis + Ollama (GLM-OCR) + React

---

## What We're Building (Core Flow)

```
Create Customer → Create PO → Upload PDF → Auto-Extract (OCR) → Review/Verify → Search by Any Ref ID
      │                │            │              │                    │               │
   SKY-AB1234      PO-2026-001   NAS storage   GLM-OCR via       Human edits      invoice#, DC#,
   master data     anchor        auto-folder    Ollama+Celery     extracted data   PO#, SO# etc.
```

**What's IN:** Customer CRUD, PO CRUD, document upload, NAS storage, OCR pipeline, extraction verify/reject, search by any reference, React frontend with chain status.

**What's OUT (for now):** Authentication, JWT, roles, rate limiting, SSL, monitoring, WebSocket notifications, audit logs with actor tracking.

---

## Pre-Setup

### Step 1: Create project structure

```bash
mkdir -p docplatform-v3/{backend/app/{api/v1,models,schemas,services/extraction,utils},frontend/src/{api,components,hooks,pages,stores,types,utils},nginx}
cd docplatform-v3
```

### Step 2: Docker Compose

**Claude Prompt:**

```
Create a docker-compose.dev.yml for a document management platform. 
Development only — no auth, no SSL, no monitoring.

Services:

1. postgres: PostgreSQL 16 Alpine
   - Env: POSTGRES_USER=docplatform, POSTGRES_PASSWORD=docplatform, POSTGRES_DB=docplatform
   - Port: 5432, Volume: postgres_data
   - Healthcheck: pg_isready -U docplatform

2. redis: Redis 7 Alpine
   - Port: 6379
   - Command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
   - Healthcheck: redis-cli ping

3. ollama: ollama/ollama:latest
   - GPU: nvidia, count 1, capabilities [gpu]
   - Port: 11434, Volume: ollama_models
   - Healthcheck: curl -f http://localhost:11434/api/tags (interval 30s)

4. backend: Build from ./backend/Dockerfile
   - Port: 8000:8000
   - Environment:
     DATABASE_URL=postgresql+asyncpg://docplatform:docplatform@postgres:5432/docplatform
     SYNC_DATABASE_URL=postgresql://docplatform:docplatform@postgres:5432/docplatform
     REDIS_URL=redis://redis:6379/0
     NAS_BASE_PATH=/nas/documents
     OCR_BASE_URL=http://ollama:11434
     OCR_MODEL_NAME=glm-ocr
     OCR_TIMEOUT=120
     OCR_MAX_PAGES=10
     OCR_PDF_DPI=200
     CORS_ORIGINS=["http://localhost:5173"]
   - Volumes: ./storage/documents:/nas/documents
   - depends_on: postgres (healthy), redis (healthy)
   - Command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   - Mount ./backend:/app for hot reload

5. celery-worker: Same build context as backend
   - Command: celery -A celery_app worker --loglevel=info --concurrency=2
   - Same environment + volumes as backend
   - depends_on: backend, redis, ollama

6. frontend: Build from ./frontend/Dockerfile
   - Port: 5173:5173
   - depends_on: backend
   - For dev: mount ./frontend:/app and use vite dev server

Volumes: postgres_data, redis_data, ollama_models

Also create .env.example with all variables listed.
Also create backend/Dockerfile:
  FROM python:3.12-slim
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY . .
  CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

Also create frontend/Dockerfile:
  FROM node:20-slim
  WORKDIR /app
  COPY package*.json .
  RUN npm install
  COPY . .
  CMD ["npm", "run", "dev", "--", "--host"]
```

### Step 3: Pull GLM-OCR model

```bash
docker compose -f docker-compose.dev.yml up -d ollama
docker exec -it docplatform-v3-ollama-1 ollama pull glm-ocr
docker exec -it docplatform-v3-ollama-1 ollama list
```

---

## Phase 1: Database + Models + Config

**Goal:** PostgreSQL running, all tables created, FastAPI serving requests.

### Phase 1.1 — Config + Database Connection

**Claude Prompt:**

```
Create the backend configuration and database setup for a document management 
platform. This is a dev build — NO authentication needed.

File: backend/app/config.py
  Use pydantic-settings to create a Settings class loading from env vars:
  
  - database_url: str = "postgresql+asyncpg://docplatform:docplatform@localhost:5432/docplatform"
  - sync_database_url: str = "postgresql://docplatform:docplatform@localhost:5432/docplatform"
    (needed for Celery tasks which run synchronously)
  - redis_url: str = "redis://localhost:6379/0"
  - nas_base_path: str = "/nas/documents"
  - ocr_base_url: str = "http://localhost:11434"
  - ocr_model_name: str = "glm-ocr"
  - ocr_timeout: int = 120
  - ocr_max_retries: int = 3
  - ocr_pdf_dpi: int = 200
  - ocr_max_pages: int = 10
  - cors_origins: list[str] = ["http://localhost:5173"]
  - debug: bool = True

  Export singleton: settings = Settings()

File: backend/app/database.py
  Two engines:
  1. Async engine (for FastAPI endpoints): create_async_engine(settings.database_url)
     AsyncSession via async_sessionmaker
     get_db dependency: async generator yielding AsyncSession
  2. Sync engine (for Celery tasks): create_engine(settings.sync_database_url)
     SyncSession via sessionmaker
     get_sync_db: context manager yielding sync Session

File: backend/requirements.txt
  fastapi==0.115.0
  uvicorn[standard]==0.32.0
  sqlalchemy==2.0.36
  alembic==1.14.0
  asyncpg==0.30.0
  psycopg2-binary==2.9.9
  python-multipart==0.0.18
  pydantic==2.10.0
  pydantic-settings==2.7.0
  python-dotenv==1.0.1
  aiofiles==24.1.0
  httpx>=0.27.0
  pymupdf>=1.25.0
  Pillow>=11.0.0
  celery[redis]==5.4.0
  redis==5.2.0
```

### Phase 1.2 — SQLAlchemy Models

**Claude Prompt:**

```
Create all SQLAlchemy ORM models for a PO-centric document management platform.
Use SQLAlchemy 2.0 style with Mapped[] type annotations, UUID primary keys.
NO user/auth model needed — this is dev only.

File: backend/app/models/base.py
  - DeclarativeBase
  - TimestampMixin: created_at (server_default=func.now()), 
    updated_at (server_default=func.now(), onupdate=func.now())

File: backend/app/models/customer.py
  Table: customers
  Fields:
    id: UUID PK (default uuid4)
    customer_id: String(50), unique, not null — business ID like "SKY-AB1234"
      This is used as the NAS folder name
    name: String(255), not null — display name like "Acme Corp"
    contact_email: String(255), nullable
    contact_phone: String(50), nullable
    address: Text, nullable
    gst_number: String(50), nullable
    notes: Text, nullable
    is_active: Boolean, default True
  Relationship: purchase_orders = relationship("PurchaseOrder", back_populates="customer")
  Index on: customer_id (unique), name, gst_number

File: backend/app/models/purchase_order.py
  Table: purchase_orders
  
  POStatus enum (Python str Enum + SQLAlchemy): 
    INITIATED, IN_PROGRESS, NEAR_COMPLETE, COMPLETE, CANCELLED
  
  Fields:
    id: UUID PK
    customer_id: UUID FK → customers.id, not null
    po_number: String(100), unique, not null
    po_date: Date, nullable
    total_amount: Numeric(15,2), nullable
    status: Enum(POStatus), default INITIATED
    chain_completeness: Float, default 0.0
    notes: Text, nullable
  Relationships: 
    customer = relationship("Customer", back_populates="purchase_orders")
    documents = relationship("Document", back_populates="purchase_order")
  Index on: po_number (unique), customer_id, status, po_date

File: backend/app/models/document.py
  Table: documents
  
  DocumentType enum: CUSTOMER_PO, VENDOR_DC, VENDOR_INVOICE, 
                     COMPANY_DC, COMPANY_INVOICE, POD
  DocumentStatus enum: UPLOADED, EXTRACTING, PENDING_REVIEW, 
                       VERIFIED, REJECTED, EXTRACTION_FAILED
  
  Fields:
    id: UUID PK
    po_id: UUID FK → purchase_orders.id, not null
    document_type: Enum(DocumentType), not null
    filename: String(255), not null — UUID-prefixed stored name
    original_filename: String(255), not null — user's original name
    file_path: String(500), not null — relative NAS path
    file_size: Integer, not null — bytes
    mime_type: String(100), default "application/pdf"
    page_count: Integer, nullable
    checksum: String(64), not null — SHA-256 hex
    status: Enum(DocumentStatus), default UPLOADED
    rotation: Integer, default 0
  Relationships:
    purchase_order = relationship("PurchaseOrder", back_populates="documents")
    metadata = relationship("DocumentMetadata", back_populates="document", uselist=False)
  UniqueConstraint: (po_id, document_type, checksum), name="uq_doc_per_po_type"
  Index on: po_id, document_type, checksum, status

File: backend/app/models/document_metadata.py
  Table: document_metadata
  
  MetadataStatus enum: PENDING, EXTRACTED, VERIFIED, FAILED
  
  Fields:
    id: UUID PK
    document_id: UUID FK → documents.id, unique, not null
    document_type: Enum(DocumentType), not null
    extracted_data: JSONB, nullable — the full extracted JSON
    raw_ocr_text: Text, nullable — raw OCR output for debugging
    primary_ref_no: String(100), nullable — main ref (invoice#, DC#, PO#)
    po_ref_no: String(100), nullable — PO reference extracted from doc
    doc_date: Date, nullable — document date
    total_amount: Numeric(15,2), nullable
    confidence_score: Float, nullable — 0-100%
    status: Enum(MetadataStatus), default PENDING
    extraction_attempts: Integer, default 0
    last_error: Text, nullable
    extracted_at: DateTime, nullable
    verified_at: DateTime, nullable
    model_version: String(50), nullable
    processing_time_ms: Integer, nullable
  Relationship:
    document = relationship("Document", back_populates="metadata")
  Index on: document_id (unique), primary_ref_no, po_ref_no, doc_date, 
            extracted_data (GIN for JSONB), status

File: backend/app/models/reference_index.py
  Table: reference_index
  Purpose: Every extracted reference number becomes searchable.
  When OCR extracts invoice_number="INV-123", a row is inserted with
  ref_type="invoice_number", ref_value="INV-123" so searching "INV-123" 
  finds the document instantly.
  
  Fields:
    id: UUID PK
    document_id: UUID FK → documents.id, not null
    po_id: UUID FK → purchase_orders.id, not null (denormalized for speed)
    ref_type: String(50), not null — "invoice_number", "dc_number", "po_number", etc.
    ref_value: String(255), not null — the actual reference value
    document_type: Enum(DocumentType), not null
  Index on: ref_value (B-Tree — the main search index), 
            (ref_type, ref_value) composite, document_id, po_id

File: backend/app/models/__init__.py
  Import all models so Alembic can see them:
  from .base import Base
  from .customer import Customer
  from .purchase_order import PurchaseOrder
  from .document import Document, DocumentType, DocumentStatus
  from .document_metadata import DocumentMetadata, MetadataStatus
  from .reference_index import ReferenceIndex
```

### Phase 1.3 — Alembic Migrations

**Claude Prompt:**

```
Set up Alembic for async database migrations.

File: backend/alembic.ini
  script_location = alembic
  sqlalchemy.url will be overridden in env.py

File: backend/alembic/env.py
  - Import Base and all models from app.models
  - Use settings.database_url from app.config
  - Configure for async (run_async_migrations pattern with asyncpg)
  - Set target_metadata = Base.metadata
  - Include render_as_batch=True for better SQLite compatibility (optional)

File: backend/alembic/script.py.mako (standard template)

After creating these files, generate and run the initial migration:
  cd backend
  alembic revision --autogenerate -m "initial_schema"
  alembic upgrade head

This should create tables: customers, purchase_orders, documents, 
document_metadata, reference_index, with all enums and indexes.
```

### Phase 1.4 — Pydantic Schemas

**Claude Prompt:**

```
Create Pydantic v2 request/response schemas. No auth schemas needed.

File: backend/app/schemas/customer.py
  CustomerCreate:
    customer_id: str (required, pattern r"^[A-Z]{2,5}-[A-Z0-9]+$" to match "SKY-AB1234" style)
    name: str (required, min_length=1)
    contact_email: str | None = None
    contact_phone: str | None = None
    address: str | None = None
    gst_number: str | None = None
    notes: str | None = None
  
  CustomerUpdate: (all optional)
    name, contact_email, contact_phone, address, gst_number, notes
  
  CustomerResponse:
    id: UUID, customer_id, name, contact_email, contact_phone, address, 
    gst_number, notes, is_active, created_at, updated_at, po_count: int = 0
    model_config = ConfigDict(from_attributes=True)
  
  CustomerListResponse:
    items: list[CustomerResponse]
    total: int
    page: int
    per_page: int

File: backend/app/schemas/purchase_order.py
  POCreate:
    customer_id: UUID (required — the internal UUID, not SKY-xxx)
    po_number: str (required)
    po_date: date | None = None
    total_amount: float | None = None
    notes: str | None = None
  
  POUpdate: all optional
  
  POResponse:
    id, customer_id, po_number, po_date, total_amount, status, 
    chain_completeness, notes, created_at, updated_at,
    customer_name: str = "" (populated from join),
    customer_sky_id: str = "" (populated from join)
    model_config = ConfigDict(from_attributes=True)
  
  POListResponse: items, total, page, per_page
  
  ChainSlot:
    status: str  (document status or "NOT_UPLOADED")
    document_id: UUID | None
    ref_no: str | None  (primary_ref_no from metadata)
    uploaded_at: datetime | None
    confidence: float | None
  
  ChainStatusResponse:
    po_id: UUID, po_number: str, completeness_pct: float
    chain: dict[str, ChainSlot | None]  
    # Keys: CUSTOMER_PO, VENDOR_DC, VENDOR_INVOICE, COMPANY_DC, COMPANY_INVOICE, POD
    # Value is ChainSlot if document exists, None if not uploaded

File: backend/app/schemas/document.py
  DocumentUploadResponse:
    id, po_id, document_type, filename, original_filename, file_size, 
    page_count, checksum, status, created_at
  
  DocumentResponse:
    All above + file_path, rotation, updated_at,
    po_number: str = "", customer_name: str = "",
    metadata: ExtractionResponse | None = None
  
  DocumentListResponse: items: list[DocumentResponse], total: int

File: backend/app/schemas/extraction.py
  ExtractionResponse:
    id, document_id, document_type, extracted_data: dict | None,
    primary_ref_no, po_ref_no, doc_date, total_amount,
    confidence_score, status, extraction_attempts,
    last_error, extracted_at, model_version, processing_time_ms
  
  VerifyRequest:
    extracted_data: dict  (user-edited fields)
  
  SearchResult:
    result_type: str  ("customer" | "purchase_order" | "document")
    id: UUID
    ref_number: str  (the matched reference)
    display_name: str  (human-readable label)
    document_type: str | None
    po_number: str | None
    customer_name: str | None
    confidence: float | None
  
  SearchResponse:
    results: list[SearchResult]
    total: int
    query: str
```

### Phase 1.5 — Main App + Health Check + Seed Data

**Claude Prompt:**

```
Create the FastAPI app entry point, health check, and seed script.
NO authentication — all endpoints are open.

File: backend/app/main.py
  - Create FastAPI app (title="Document Platform V3.0")
  - Add CORSMiddleware: allow origins from settings.cors_origins, 
    allow all methods, allow all headers, allow credentials
  - Include API router at prefix /api/v1
  - Root GET "/" → {"status": "ok", "app": "Document Platform V3.0"}

File: backend/app/api/router.py
  - Create main APIRouter
  - Include sub-routers with prefixes and tags:
    /customers (tag: Customers)
    /purchase-orders (tag: Purchase Orders)
    /documents (tag: Documents) — for single doc endpoints
    /search (tag: Search)
    /admin (tag: Admin)
  - NOTE: document upload goes under /purchase-orders/{po_id}/documents
    so include that in the purchase_orders router

File: backend/app/api/v1/admin.py
  GET /api/v1/admin/health
    Check connectivity to: PostgreSQL, Redis, Ollama, NAS path
    Return: {
      "database": "ok" or "error: ...",
      "redis": "ok" or "error: ...", 
      "ollama": "ok" or "unavailable",
      "storage": "ok" or "error: ..."  (check NAS path is writable)
    }
  
  GET /api/v1/admin/stats
    Query DB and return:
    {
      "total_customers": int,
      "total_purchase_orders": int,
      "total_documents": int,
      "pending_reviews": int (documents with status PENDING_REVIEW),
      "verified": int,
      "extraction_failures": int
    }

File: backend/app/seed.py
  Async script that:
  1. Creates 3 sample customers:
     - SKY-AB1234 "Acme Corp" (gst: "29AABCA1234A1Z5")
     - SKY-CD5678 "TechVision Ltd" (gst: "07AABCT5678B1Z3")
     - SKY-EF9012 "Global Traders" (gst: "27AABCG9012C1Z1")
  2. Creates 2 sample POs:
     - PO-2026-0001 for SKY-AB1234 (date: 2026-01-05, amount: 450000)
     - PO-2026-0002 for SKY-CD5678 (date: 2026-01-12, amount: 225000)
  3. Skips if data already exists (check by customer_id)
  
  Run with: python -m app.seed
  (use asyncio.run and the async engine)

Create placeholder files for routes that don't exist yet 
(so the router import doesn't fail):
  backend/app/api/v1/customers.py — empty router
  backend/app/api/v1/purchase_orders.py — empty router
  backend/app/api/v1/documents.py — empty router
  backend/app/api/v1/extraction.py — empty router
  backend/app/api/v1/search.py — empty router
  
  Each just exports: router = APIRouter()
```

### Phase 1 — Verification

```bash
docker compose -f docker-compose.dev.yml up -d postgres redis
cd backend
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000

# Test:
curl http://localhost:8000/
# → {"status":"ok","app":"Document Platform V3.0"}

curl http://localhost:8000/api/v1/admin/health
# → {"database":"ok","redis":"ok","ollama":"unavailable","storage":"ok"}

curl http://localhost:8000/api/v1/admin/stats
# → {"total_customers":3,"total_purchase_orders":2,...}
```

---

## Phase 2: Customer + Purchase Order CRUD

**Goal:** Create/read/list customers and POs. Chain status endpoint showing 6 empty slots.

### Phase 2.1 — Customer Service + API

**Claude Prompt:**

```
Create Customer CRUD for the document platform. No auth required.

File: backend/app/services/customer_service.py

All methods are async and accept db: AsyncSession as first parameter.

async def create_customer(db, data: CustomerCreate) → Customer:
  Check customer_id uniqueness (409 if exists)
  Create and return Customer

async def get_customer(db, id: UUID) → Customer:
  Fetch by PK with selectinload(purchase_orders)
  404 if not found

async def get_customer_by_sky_id(db, customer_id: str) → Customer:
  Fetch by customer_id field

async def list_customers(db, page: int = 1, per_page: int = 20, 
                          search: str | None = None) → tuple[list[Customer], int]:
  If search provided: filter where customer_id ILIKE %search% 
    OR name ILIKE %search% OR gst_number ILIKE %search%
  Order by name ASC
  Return (items, total_count) with offset/limit pagination

async def update_customer(db, id: UUID, data: CustomerUpdate) → Customer:
  Fetch, update non-None fields, commit, return

async def get_customer_with_po_count(db, id: UUID) → tuple[Customer, int]:
  Fetch customer + count of their POs


File: backend/app/api/v1/customers.py

router = APIRouter()

POST /  → create customer
  Body: CustomerCreate
  Return: CustomerResponse (201)
  Error: 409 if customer_id exists

GET /  → list customers  
  Query: page=1, per_page=20, search=None
  Return: CustomerListResponse
  For each customer, include po_count (use a subquery or separate count)

GET /{id}  → get customer
  Return: CustomerResponse with po_count
  Error: 404

PATCH /{id}  → update customer
  Body: CustomerUpdate
  Return: CustomerResponse

GET /{id}/purchase-orders  → list POs for customer
  Query: page=1, per_page=20, status=None (optional filter)
  Return: POListResponse
```

### Phase 2.2 — Purchase Order Service + API

**Claude Prompt:**

```
Create Purchase Order CRUD with chain status tracking.

The PO is the central anchor — every document links to a PO.

File: backend/app/services/po_service.py

async def create_po(db, data: POCreate) → PurchaseOrder:
  Verify customer_id exists (400 if not)
  Check po_number uniqueness (409 if exists)
  Create PO with status=INITIATED, chain_completeness=0.0

async def get_po(db, po_id: UUID) → PurchaseOrder:
  Eager load: customer, documents, documents.metadata
  404 if not found

async def list_pos(db, page, per_page, customer_id=None, status=None, 
                    search=None) → tuple[list, int]:
  Filters: customer_id exact match, status exact match, 
           po_number ILIKE %search%
  Eager load customer (for display)
  Order by created_at DESC
  Return (items, total)

async def update_po(db, po_id: UUID, data: POUpdate) → PurchaseOrder

async def get_chain_status(db, po_id: UUID) → dict:
  Fetch PO. For each of the 6 DocumentTypes:
    Query documents where po_id=po_id AND document_type=type
    If document exists:
      Get its metadata (if any)
      Return ChainSlot: {
        status: document.status.value,
        document_id: document.id,
        ref_no: metadata.primary_ref_no if metadata else None,
        uploaded_at: document.created_at,
        confidence: metadata.confidence_score if metadata else None
      }
    If not: return None
  
  Calculate completeness: (slots_with_documents / 6) * 100
  Return ChainStatusResponse

async def update_chain_completeness(db, po_id: UUID) → float:
  Count distinct document_types for this PO 
    where document status NOT IN (EXTRACTION_FAILED)
  completeness = (count / 6) * 100
  
  Determine PO status:
    0 → INITIATED
    1-49 → IN_PROGRESS
    50-99 → NEAR_COMPLETE
    100 → COMPLETE
  
  Update PO fields, commit, return completeness


File: backend/app/api/v1/purchase_orders.py

router = APIRouter()

POST /  → create PO
  Body: POCreate → POResponse (201)

GET /  → list POs
  Query: page, per_page, customer_id, status, search
  Return: POListResponse
  Each item should include customer_name and customer_sky_id
  (either via join or by populating in the endpoint)

GET /{id}  → get PO detail
  Return: POResponse with customer info

PATCH /{id}  → update PO

GET /{id}/chain-status  → document chain completeness
  Return: ChainStatusResponse
  This is the key endpoint — shows which of the 6 document 
  types are uploaded and their extraction status.
  
  Example response:
  {
    "po_id": "uuid",
    "po_number": "PO-2026-0001",
    "completeness_pct": 33.33,
    "chain": {
      "CUSTOMER_PO": {
        "status": "VERIFIED",
        "document_id": "uuid",
        "ref_no": "PO-2026-0001",
        "uploaded_at": "2026-01-05T...",
        "confidence": 92.5
      },
      "VENDOR_DC": {
        "status": "PENDING_REVIEW",
        "document_id": "uuid",
        "ref_no": "DC-7890",
        "uploaded_at": "2026-01-15T...",
        "confidence": 88.0
      },
      "VENDOR_INVOICE": null,
      "COMPANY_DC": null,
      "COMPANY_INVOICE": null,
      "POD": null
    }
  }
```

### Phase 2 — Verification

```bash
# Create customer
curl -X POST http://localhost:8000/api/v1/customers \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"SKY-TEST01","name":"Test Corp"}'

# List customers
curl http://localhost:8000/api/v1/customers

# Create PO
curl -X POST http://localhost:8000/api/v1/purchase-orders \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"<UUID_FROM_ABOVE>","po_number":"PO-2026-TEST01"}'

# Check chain status (all 6 slots should be null)
curl http://localhost:8000/api/v1/purchase-orders/<PO_UUID>/chain-status
```

---

## Phase 3: Document Upload + NAS Storage

**Goal:** Upload PDFs to POs, store in correct NAS directory, preview/download.

### Phase 3.1 — Storage Service

**Claude Prompt:**

```
Create the NAS file storage service.

File: backend/app/services/storage_service.py

NAS directory structure:
  /nas/documents/{customer_id}/{po_number}/{DOC_TYPE}/{uuid_filename}.pdf

Example:
  /nas/documents/SKY-AB1234/PO-2026-0001/VENDOR_INVOICE/a1b2c3d4_Invoice_001.pdf

Class: StorageService

def __init__(self, nas_base_path: str):
    self.base_path = nas_base_path

def generate_storage_path(self, customer_id: str, po_number: str,
                           document_type: str, original_filename: str) 
    → tuple[str, str]:
    """Returns (relative_path, uuid_filename)"""
    file_uuid = uuid.uuid4().hex[:8]
    safe_name = sanitize_filename(original_filename)
    uuid_filename = f"{file_uuid}_{safe_name}"
    relative_path = f"documents/{customer_id}/{po_number}/{document_type}/{uuid_filename}"
    return relative_path, uuid_filename

async def save_file(self, relative_path: str, file_data: bytes) → str:
    full_path = os.path.join(self.base_path, relative_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    async with aiofiles.open(full_path, 'wb') as f:
        await f.write(file_data)
    return relative_path

async def read_file(self, relative_path: str) → bytes:
    full_path = os.path.join(self.base_path, relative_path)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"File not found: {relative_path}")
    async with aiofiles.open(full_path, 'rb') as f:
        return await f.read()

async def delete_file(self, relative_path: str) → bool:
    full_path = os.path.join(self.base_path, relative_path)
    if os.path.exists(full_path):
        os.remove(full_path)
        return True
    return False

def get_full_path(self, relative_path: str) → str:
    return os.path.join(self.base_path, relative_path)

@staticmethod
def calculate_checksum(file_data: bytes) → str:
    return hashlib.sha256(file_data).hexdigest()

@staticmethod
def sanitize_filename(name: str) → str:
    safe = re.sub(r'[^\w.\-]', '_', name)
    return safe[:100]

Validate: reject any path containing ".." to prevent traversal.
```

### Phase 3.2 — Document Service + Upload API

**Claude Prompt:**

```
Create document upload, preview, and download.

File: backend/app/services/document_service.py

Dependencies: StorageService (instantiate with settings.nas_base_path)

async def upload_document(db, po_id: UUID, document_type: str, 
                           file: UploadFile) → Document:
  1. Fetch PO with customer eagerly loaded → 404 if not found
  2. Read file bytes: contents = await file.read()
  3. Validate:
     - file.content_type must be "application/pdf" or first 5 bytes == b"%PDF-"
     - len(contents) <= 25 * 1024 * 1024 (25MB) → 413 if too large
     → raise HTTPException 400 if not valid PDF
  4. checksum = StorageService.calculate_checksum(contents)
  5. Check duplicate: query documents where po_id + document_type + checksum match
     → raise 409 "Duplicate document" if found
  6. Get customer_id from PO's customer: po.customer.customer_id (the SKY-xxx)
  7. Generate path: storage_service.generate_storage_path(
       customer_id, po.po_number, document_type, file.filename)
  8. Save file: await storage_service.save_file(relative_path, contents)
  9. Count pages: open with fitz, get page_count, close
  10. Create Document record:
      po_id, document_type, filename=uuid_filename, 
      original_filename=file.filename, file_path=relative_path,
      file_size=len(contents), page_count, checksum, status=UPLOADED
  11. db.add(doc), await db.commit(), await db.refresh(doc)
  12. Update PO chain completeness: await update_chain_completeness(db, po_id)
  13. Queue extraction: extract_document.delay(str(doc.id))
  14. Return doc

async def get_document(db, document_id: UUID) → Document:
  Fetch with selectinload(metadata) and joinedload(purchase_order → customer)
  404 if not found

async def list_documents_for_po(db, po_id: UUID) → list[Document]:
  All documents for this PO, with metadata loaded, ordered by document_type

async def delete_document(db, document_id: UUID):
  Fetch doc, delete file from NAS, delete metadata + reference_index rows,
  delete document record, update PO chain completeness

async def get_preview_data(db, document_id: UUID) → tuple[bytes, str, str]:
  Fetch doc, read file from NAS
  Return (file_bytes, mime_type, original_filename)


File: backend/app/api/v1/documents.py 
(NOTE: upload endpoint is nested under /purchase-orders/{po_id}/documents)

Adjust backend/app/api/v1/purchase_orders.py to add:

POST /{po_id}/documents  → upload document to PO
  Accepts multipart form: file (UploadFile), document_type (Form field, str)
  Validates document_type is one of the 6 valid types
  Returns: DocumentUploadResponse (201)
  NOTE: Extraction auto-queued in background!

GET /{po_id}/documents  → list documents for PO
  Returns: DocumentListResponse

Then in documents.py router (mounted at /documents):

GET /{id}  → get document detail with metadata
  Returns: DocumentResponse

DELETE /{id}  → delete document
  Returns: 204

GET /{id}/preview  → stream PDF inline
  Return StreamingResponse with:
    media_type="application/pdf"
    headers: Content-Disposition: inline; filename="..."

GET /{id}/download  → stream PDF as attachment
  Return StreamingResponse with:
    media_type="application/pdf"  
    headers: Content-Disposition: attachment; filename="original_name.pdf"

POST /{id}/rotate  → rotate PDF (just update DB field, don't modify file)
  Body: {"angle": 90}  (90, 180, 270)
  Returns: DocumentResponse
```

### Phase 3 — Verification

```bash
# Upload a PDF to the seeded PO
curl -X POST http://localhost:8000/api/v1/purchase-orders/<PO_UUID>/documents \
  -F "file=@test_invoice.pdf" \
  -F "document_type=CUSTOMER_PO"

# Check NAS: ls storage/documents/SKY-AB1234/PO-2026-0001/CUSTOMER_PO/
# Should see: a1b2c3d4_test_invoice.pdf

# Check chain status now shows CUSTOMER_PO slot filled
curl http://localhost:8000/api/v1/purchase-orders/<PO_UUID>/chain-status

# Preview the PDF
curl http://localhost:8000/api/v1/documents/<DOC_UUID>/preview > preview.pdf

# Upload duplicate → should get 409
curl -X POST http://localhost:8000/api/v1/purchase-orders/<PO_UUID>/documents \
  -F "file=@test_invoice.pdf" \
  -F "document_type=CUSTOMER_PO"
```

---

## Phase 4: OCR Extraction Pipeline

**Goal:** Auto-extract data from PDFs using GLM-OCR via Ollama. Background processing with Celery.

### Phase 4.1 — PDF Converter + OCR Client + Prompts + Parser

**Claude Prompt:**

```
Create the complete OCR extraction pipeline. This is 4 files.

=== FILE 1: backend/app/services/extraction/pdf_converter.py ===

Class: PDFConverter(dpi: int = 200, max_pages: int = 10)

def convert_to_images(self, pdf_path: str) → list[bytes]:
    Uses PyMuPDF (fitz):
    - Open PDF
    - If pages <= max_pages: process all
    - If pages > max_pages: first half + last half (captures headers and totals)
    - For each page: get_pixmap(dpi=self.dpi) → tobytes("png")
    - Return list of PNG bytes

def get_page_count(self, pdf_path: str) → int

Raise PDFConversionError on corrupt/password-protected PDFs.


=== FILE 2: backend/app/services/extraction/ocr_client.py ===

Class: OCRClient(base_url, model, timeout=120, max_retries=3)

Tracks consecutive failures for circuit breaker pattern.

async def extract_from_image(self, image_data: bytes, prompt: str) → dict:
    1. Circuit breaker: if 5+ failures and 60s cooldown not elapsed → raise
    2. Base64 encode image
    3. Build Ollama payload:
       {
         "model": self.model,
         "messages": [{"role":"user","content":prompt,"images":[base64_img]}],
         "stream": false,
         "options": {"temperature": 0.01, "num_predict": 4096}
       }
    4. Retry loop (max_retries):
       POST {base_url}/api/chat with httpx.Timeout(timeout)
       Success → return {"text": content, "processing_time_ms": elapsed}
       Timeout/error → sleep 2^attempt, retry
    5. After all retries fail → record failure, raise

Use httpx.AsyncClient. 
Define custom exceptions: OCRTimeoutError, OCRServiceError, OCRServiceUnavailable.


=== FILE 3: backend/app/services/extraction/prompts.py ===

SYSTEM_PROMPT = (
    "You are a document OCR extraction system. "
    "Extract the requested fields from the document image. "
    "Return ONLY valid JSON with no markdown, no code blocks, no explanation. "
    "If a field cannot be found, use null."
)

EXTRACTION_PROMPTS = dict mapping DocumentType string values to configs:

"CUSTOMER_PO":
  instruction: "Extract purchase order details from this document."
  schema: po_number(str), po_date(YYYY-MM-DD), customer_name(str), 
          billing_address(str), shipping_address(str), total_amount(number),
          currency(str), payment_terms(str), line_items_count(number), gst_number(str)

"VENDOR_DC":
  instruction: "Extract delivery challan details from this vendor document."
  schema: dc_number, dc_date, po_reference, vendor_name, 
          items_description, quantity, vehicle_number, receiver_name

"VENDOR_INVOICE":
  instruction: "Extract invoice details from this vendor/supplier invoice."
  schema: invoice_number, invoice_date, po_reference, vendor_name,
          subtotal(number), tax_amount(number), total_amount(number),
          payment_terms, gst_number, irn_number, ack_number, ack_date

"COMPANY_DC":
  instruction: "Extract delivery challan details from this dispatch document."
  schema: dc_number, dc_date, po_reference, customer_name,
          items_description, quantity, dispatch_from

"COMPANY_INVOICE":
  instruction: "Extract invoice details from this company-issued invoice."
  schema: invoice_number, invoice_date, po_reference, customer_name,
          subtotal(number), tax_amount(number), total_amount(number),
          so_number, account_manager, irn_number

"POD":
  instruction: "Extract proof of delivery details from this document."
  schema: pod_number, delivery_date, received_by, dc_reference,
          po_reference, delivery_location, condition_notes, 
          signature_present(boolean)

Helper functions:

def build_prompt(document_type: str) → str:
    Combines SYSTEM_PROMPT + instruction + 
    "Extract these fields as a JSON object:\n" +
    each field with description, one per line

def get_primary_field(doc_type: str) → str:
    Maps: CUSTOMER_PO→po_number, VENDOR_DC→dc_number, 
    VENDOR_INVOICE→invoice_number, COMPANY_DC→dc_number,
    COMPANY_INVOICE→invoice_number, POD→pod_number

def get_date_field(doc_type: str) → str:
    Maps: CUSTOMER_PO→po_date, VENDOR_DC→dc_date,
    VENDOR_INVOICE→invoice_date, COMPANY_DC→dc_date,
    COMPANY_INVOICE→invoice_date, POD→delivery_date

def get_searchable_fields(doc_type: str) → list[tuple[str, str]]:
    Returns (ref_type, field_name) pairs for ReferenceIndex.
    
    CUSTOMER_PO: [("po_number","po_number"), ("gst_number","gst_number")]
    VENDOR_DC: [("dc_number","dc_number"), ("po_reference","po_reference")]
    VENDOR_INVOICE: [("invoice_number","invoice_number"), ("po_reference","po_reference"),
                     ("ack_number","ack_number"), ("irn_number","irn_number")]
    COMPANY_DC: [("dc_number","dc_number"), ("po_reference","po_reference")]
    COMPANY_INVOICE: [("invoice_number","invoice_number"), ("po_reference","po_reference"),
                      ("so_number","so_number"), ("irn_number","irn_number")]
    POD: [("pod_number","pod_number"), ("dc_reference","dc_reference"),
          ("po_reference","po_reference")]


=== FILE 4: backend/app/services/extraction/response_parser.py ===

Class: ResponseParser

def parse_response(self, raw_text: str) → dict:
    Tries multiple strategies to extract JSON from OCR output:
    1. Direct json.loads(raw_text.strip())
    2. Regex for ```json ... ``` code blocks
    3. Find first { and last }, extract substring
    4. Clean: remove trailing commas before } or ], 
       handle single quotes carefully
    5. json.loads on cleaned string
    6. If all fail: raise ParseError(f"Could not parse: {raw_text[:200]}")

def parse_and_merge(self, raw_texts: list[str], document_type: str) → dict:
    Parse each raw_text, merge dicts taking first non-null per field

def calculate_confidence(self, extracted: dict, schema_fields: list[str]) → float:
    filled = sum(1 for f in schema_fields if extracted.get(f) is not None)
    return round((filled / len(schema_fields)) * 100, 1)

def parse_date(self, date_str: str | None) → date | None:
    Try formats: DD-MM-YYYY, DD/MM/YYYY, DD.MM.YYYY, YYYY-MM-DD,
    DD-Mon-YYYY (e.g. 15-Jan-2026), DD Mon YYYY, Month DD YYYY,
    DD-MM-YY, DD/MM/YY, YYYY/MM/DD, MM-DD-YYYY, MM/DD/YYYY
    Return None on failure (never raise)


Also create: backend/app/services/extraction/__init__.py (empty)
```

### Phase 4.2 — Celery Task

**Claude Prompt:**

```
Create Celery configuration and the extraction background task.

File: backend/celery_app.py
  from celery import Celery
  from app.config import settings
  
  celery_app = Celery("docplatform")
  celery_app.config_from_object({
      "broker_url": settings.redis_url,
      "result_backend": settings.redis_url,
      "task_serializer": "json",
      "result_serializer": "json",
      "accept_content": ["json"],
      "timezone": "UTC",
      "task_soft_time_limit": 600,
      "task_time_limit": 660,
      "task_acks_late": True,
      "worker_prefetch_multiplier": 1,
  })
  celery_app.autodiscover_tasks(["app.services.extraction"])

File: backend/app/services/extraction/tasks.py

IMPORTANT: Celery tasks run synchronously (not async). 
Use the SYNC database session (settings.sync_database_url).
For the async OCR client, wrap calls with asyncio.run().

from celery import shared_task
import asyncio
from app.database import get_sync_db  
from app.models import Document, DocumentMetadata, ReferenceIndex, DocumentStatus, MetadataStatus
from app.services.extraction.pdf_converter import PDFConverter
from app.services.extraction.ocr_client import OCRClient
from app.services.extraction.response_parser import ResponseParser
from app.services.extraction.prompts import (
    build_prompt, get_primary_field, get_date_field, get_searchable_fields,
    EXTRACTION_PROMPTS
)
from app.config import settings
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def extract_document(self, document_id: str):
    """Run OCR extraction on uploaded document."""
    
    with get_sync_db() as db:
        # 1. Fetch document with relationships
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.error(f"Document {document_id} not found")
            return {"error": "not_found"}
        
        po = doc.purchase_order
        
        # 2. Update status
        doc.status = DocumentStatus.EXTRACTING
        db.commit()
        
        try:
            # 3. Get full file path
            storage_path = os.path.join(settings.nas_base_path, doc.file_path)
            
            # 4. Convert PDF → images
            converter = PDFConverter(
                dpi=settings.ocr_pdf_dpi, 
                max_pages=settings.ocr_max_pages
            )
            images = converter.convert_to_images(storage_path)
            logger.info(f"Converted {len(images)} pages for doc {document_id}")
            
            # 5. Build prompt
            doc_type = doc.document_type.value
            prompt = build_prompt(doc_type)
            
            # 6. OCR each page
            ocr = OCRClient(
                base_url=settings.ocr_base_url,
                model=settings.ocr_model_name,
                timeout=settings.ocr_timeout,
                max_retries=settings.ocr_max_retries
            )
            
            raw_texts = []
            total_time_ms = 0
            for i, img in enumerate(images):
                logger.info(f"OCR page {i+1}/{len(images)} for doc {document_id}")
                result = asyncio.run(ocr.extract_from_image(img, prompt))
                raw_texts.append(result["text"])
                total_time_ms += result["processing_time_ms"]
            
            # 7. Parse + merge
            parser = ResponseParser()
            extracted_data = parser.parse_and_merge(raw_texts, doc_type)
            
            # 8. Confidence
            schema_fields = list(EXTRACTION_PROMPTS[doc_type]["schema"].keys())
            confidence = parser.calculate_confidence(extracted_data, schema_fields)
            
            # 9. Extract key fields
            primary_field = get_primary_field(doc_type)
            date_field = get_date_field(doc_type)
            primary_ref = extracted_data.get(primary_field)
            po_ref = extracted_data.get("po_reference")
            doc_date = parser.parse_date(extracted_data.get(date_field))
            total_amt = extracted_data.get("total_amount")
            
            # 10. Create/update metadata
            existing_meta = db.query(DocumentMetadata).filter(
                DocumentMetadata.document_id == doc.id
            ).first()
            
            if existing_meta:
                meta = existing_meta
                meta.extraction_attempts += 1
            else:
                meta = DocumentMetadata(
                    document_id=doc.id,
                    document_type=doc.document_type,
                    extraction_attempts=1
                )
                db.add(meta)
            
            meta.extracted_data = extracted_data
            meta.raw_ocr_text = "\n---PAGE_BREAK---\n".join(raw_texts)
            meta.primary_ref_no = primary_ref
            meta.po_ref_no = po_ref
            meta.doc_date = doc_date
            meta.total_amount = total_amt
            meta.confidence_score = confidence
            meta.status = MetadataStatus.EXTRACTED
            meta.last_error = None
            meta.extracted_at = datetime.utcnow()
            meta.model_version = settings.ocr_model_name
            meta.processing_time_ms = total_time_ms
            
            # 11. Populate ReferenceIndex
            # Clear old entries for this document
            db.query(ReferenceIndex).filter(
                ReferenceIndex.document_id == doc.id
            ).delete()
            
            searchable = get_searchable_fields(doc_type)
            for ref_type, field_name in searchable:
                value = extracted_data.get(field_name)
                if value and str(value).strip():
                    ref = ReferenceIndex(
                        document_id=doc.id,
                        po_id=doc.po_id,
                        ref_type=ref_type,
                        ref_value=str(value).strip(),
                        document_type=doc.document_type
                    )
                    db.add(ref)
            
            # 12. Update document status
            doc.status = DocumentStatus.PENDING_REVIEW
            db.commit()
            
            # 13. Update PO chain completeness
            # (import and call the sync version of update_chain_completeness)
            _update_chain_sync(db, doc.po_id)
            
            logger.info(
                f"Extraction complete: doc={document_id}, "
                f"confidence={confidence}%, time={total_time_ms}ms"
            )
            return {"status": "success", "confidence": confidence}
            
        except Exception as e:
            logger.error(f"Extraction failed for {document_id}: {e}")
            doc.status = DocumentStatus.EXTRACTION_FAILED
            
            # Update metadata with error
            meta = db.query(DocumentMetadata).filter(
                DocumentMetadata.document_id == doc.id
            ).first()
            if meta:
                meta.last_error = str(e)
                meta.extraction_attempts += 1
                meta.status = MetadataStatus.FAILED
            else:
                meta = DocumentMetadata(
                    document_id=doc.id,
                    document_type=doc.document_type,
                    extraction_attempts=1,
                    last_error=str(e),
                    status=MetadataStatus.FAILED
                )
                db.add(meta)
            
            db.commit()
            raise self.retry(exc=e)


def _update_chain_sync(db, po_id):
    """Sync version of chain completeness update for Celery."""
    from app.models import PurchaseOrder
    from sqlalchemy import func, distinct
    
    count = db.query(func.count(distinct(Document.document_type))).filter(
        Document.po_id == po_id,
        Document.status != DocumentStatus.EXTRACTION_FAILED
    ).scalar() or 0
    
    completeness = round((count / 6) * 100, 1)
    
    po = db.query(PurchaseOrder).get(po_id)
    if po:
        po.chain_completeness = completeness
        if completeness == 0:
            po.status = "INITIATED"
        elif completeness < 50:
            po.status = "IN_PROGRESS"
        elif completeness < 100:
            po.status = "NEAR_COMPLETE"
        else:
            po.status = "COMPLETE"
        db.commit()
```

### Phase 4.3 — Extraction API Endpoints

**Claude Prompt:**

```
Create the extraction management endpoints. No auth needed.

File: backend/app/api/v1/extraction.py

router = APIRouter()

POST /documents/{document_id}/re-extract
  Manually trigger re-extraction.
  1. Fetch document → 404
  2. Delete existing metadata and reference_index entries
  3. Set document.status = UPLOADED
  4. Queue: extract_document.delay(str(document_id))
  5. Return {"message": "Extraction queued", "document_id": str(id)}

GET /documents/{document_id}/metadata
  Fetch DocumentMetadata for this document.
  Return: ExtractionResponse
  404 if no metadata exists yet.

PUT /documents/{document_id}/metadata/verify
  Body: VerifyRequest (user-edited extracted_data dict)
  Steps:
  1. Fetch metadata → 404
  2. Update metadata.extracted_data with the edited data
  3. Re-derive: primary_ref_no, po_ref_no, doc_date, total_amount
     from the new extracted_data using the same field mappings
  4. Set metadata.status = VERIFIED, verified_at = now()
  5. Refresh ReferenceIndex:
     - Delete old entries for this document
     - Re-insert based on new extracted_data
  6. Set document.status = VERIFIED
  7. Update PO chain completeness
  8. Return: ExtractionResponse

PUT /documents/{document_id}/metadata/reject
  1. Set metadata.status = FAILED
  2. Set document.status = REJECTED
  3. Update PO chain completeness
  4. Return: ExtractionResponse

Make sure these routes are included in the main router.
Mount extraction routes at /api/v1/ (they already have /documents/ in path).
```

### Phase 4 — Verification

```bash
# Start celery worker
docker compose up -d celery-worker

# Upload a real PDF (should auto-extract)
curl -X POST http://localhost:8000/api/v1/purchase-orders/<PO_UUID>/documents \
  -F "file=@real_invoice.pdf" \
  -F "document_type=VENDOR_INVOICE"

# Watch celery logs
docker compose logs -f celery-worker

# After extraction completes, check metadata
curl http://localhost:8000/api/v1/documents/<DOC_UUID>/metadata

# Check chain status (should show the slot filled)
curl http://localhost:8000/api/v1/purchase-orders/<PO_UUID>/chain-status

# Verify with edits
curl -X PUT http://localhost:8000/api/v1/documents/<DOC_UUID>/metadata/verify \
  -H "Content-Type: application/json" \
  -d '{"extracted_data":{"invoice_number":"INV-CORRECTED-001","invoice_date":"2026-01-18"}}'

# Search should find it now
curl "http://localhost:8000/api/v1/search?q=INV-CORRECTED-001"
```

---

## Phase 5: Search + React Frontend

**Goal:** Search by any reference number. Complete React UI with PO detail as main view.

### Phase 5.1 — Search API

**Claude Prompt:**

```
Create the search service and API. No auth needed.
Users can search by ANY extracted reference: PO number, invoice number, 
DC number, SO number, POD number, IRN number, customer name/ID.

File: backend/app/services/search_service.py

async def global_search(db: AsyncSession, query: str, 
                         page: int = 1, per_page: int = 20) → dict:
    
    The search query goes through these sources (in parallel or sequential):
    
    1. ReferenceIndex: ref_value ILIKE %query%
       → Returns documents with matched ref_type
    
    2. Customers: customer_id ILIKE %query% OR name ILIKE %query%
       → Returns customer results
    
    3. Purchase Orders: po_number ILIKE %query%
       → Returns PO results
    
    Build unified SearchResult list. Each result has:
      result_type: "customer" | "purchase_order" | "document"
      id: the entity UUID
      ref_number: the matched reference string
      display_name: human-readable (e.g. "Vendor Invoice — INV-2026-1234")
      document_type: (for documents only)
      po_number: (for documents and POs)
      customer_name: (for all)
      confidence: (for documents only)
    
    Deduplicate: same document_id shouldn't appear twice.
    Sort: exact match first, then starts-with, then contains.
    Paginate the merged results.
    
    Return SearchResponse: {results, total, query}


File: backend/app/api/v1/search.py

router = APIRouter()

GET /?q={query}&page=1&per_page=20
  If q is empty or less than 2 chars → return empty results
  Call global_search
  Return: SearchResponse

GET /by-ref/{ref_value}
  Direct lookup in reference_index where ref_value = exact match
  Return: list of matching documents with PO and customer info

GET /advanced
  Query params: invoice_no, dc_no, po_no, so_no, pod_no,
                customer_name, date_from, date_to, document_type
  All optional. Filter document_metadata + reference_index.
  Return: SearchResponse
```

### Phase 5.2 — Frontend Setup

**Claude Prompt:**

```
Set up the React + TypeScript frontend. No auth — no login page needed.
App loads directly into the main shell.

Stack: React 18, TypeScript 5, Vite 5, TailwindCSS 3.4, 
TanStack React Query 5, Axios, React Router 6, Zustand, 
Lucide React icons, react-dropzone

Create these foundational files:

File: frontend/package.json — all dependencies
File: frontend/tsconfig.json — strict, paths: {"@/*": ["./src/*"]}
File: frontend/vite.config.ts — proxy /api to http://localhost:8000, 
  resolve alias @ → src
File: frontend/tailwind.config.js — content: ["./src/**/*.{ts,tsx}"]
File: frontend/postcss.config.js
File: frontend/index.html — root div
File: frontend/src/main.tsx — render App with QueryClientProvider

File: frontend/src/types/index.ts
  TypeScript interfaces matching backend schemas:
  
  Customer, PurchaseOrder (with customer_name, customer_sky_id),
  Document (with metadata nested), DocumentMetadata,
  ChainSlot, ChainStatus, SearchResult, 
  PaginatedResponse<T> (items, total, page, per_page)
  
  Enums as string unions:
  DocumentType = "CUSTOMER_PO" | "VENDOR_DC" | "VENDOR_INVOICE" | ...
  DocumentStatus = "UPLOADED" | "EXTRACTING" | "PENDING_REVIEW" | ...
  POStatus = "INITIATED" | "IN_PROGRESS" | "NEAR_COMPLETE" | "COMPLETE" | ...

File: frontend/src/api/client.ts
  Axios instance, baseURL empty (Vite proxy handles /api).
  No auth interceptor needed.

File: frontend/src/api/customers.ts
  getCustomers(page, per_page, search) → PaginatedResponse<Customer>
  getCustomer(id) → Customer
  createCustomer(data) → Customer
  updateCustomer(id, data) → Customer

File: frontend/src/api/purchaseOrders.ts
  getPurchaseOrders(page, per_page, filters) → PaginatedResponse<PurchaseOrder>
  getPurchaseOrder(id) → PurchaseOrder
  createPO(data) → PurchaseOrder
  getChainStatus(poId) → ChainStatus
  getDocumentsForPO(poId) → Document[]

File: frontend/src/api/documents.ts
  uploadDocument(poId, file, documentType) → Document
    Use FormData with file and document_type
  getDocument(id) → Document
  deleteDocument(id) → void
  getPreviewUrl(id) → string (construct /api/v1/documents/{id}/preview)
  getDownloadUrl(id) → string
  rotateDocument(id, angle) → Document

File: frontend/src/api/extraction.ts
  getMetadata(documentId) → DocumentMetadata
  verifyMetadata(documentId, editedData) → DocumentMetadata
  rejectMetadata(documentId) → DocumentMetadata
  reExtract(documentId) → void

File: frontend/src/api/search.ts
  globalSearch(query, page, per_page) → SearchResponse

File: frontend/src/hooks/useCustomers.ts
  useCustomers(page, per_page, search) — useQuery
  useCustomer(id) — useQuery
  useCreateCustomer() — useMutation (invalidate customers list)
  useUpdateCustomer() — useMutation

File: frontend/src/hooks/usePurchaseOrders.ts
  usePurchaseOrders(filters) — useQuery
  usePurchaseOrder(id) — useQuery
  useCreatePO() — useMutation
  useChainStatus(poId) — useQuery
  useDocumentsForPO(poId) — useQuery

File: frontend/src/hooks/useDocuments.ts
  useUploadDocument() — useMutation (invalidate documents + chain status)
  useDocument(id) — useQuery
  useDeleteDocument() — useMutation

File: frontend/src/hooks/useExtraction.ts
  useMetadata(docId) — useQuery (enabled only when docId provided)
  useVerifyMetadata() — useMutation (invalidate metadata + chain + documents)
  useRejectMetadata() — useMutation
  useReExtract() — useMutation

File: frontend/src/hooks/useSearch.ts
  useSearch(query) — useQuery (enabled only when query.length >= 2)
```

### Phase 5.3 — App Shell + Pages

**Claude Prompt:**

```
Create the application shell and all pages. No login page needed.
Use TailwindCSS, Lucide React icons. Clean functional UI — not fancy.

File: frontend/src/App.tsx
  React Router setup (no auth wrapper needed):
    / → DashboardPage
    /customers → CustomersPage
    /purchase-orders → POListPage
    /purchase-orders/:id → PODetailPage  ← THE MAIN VIEW
    /search → SearchPage

File: frontend/src/components/layout/AppShell.tsx
  Full page layout:
  - Left sidebar (w-64, fixed):
    Logo/title at top: "DocPlatform"
    Nav links with Lucide icons:
      LayoutDashboard → / (Dashboard)
      Users → /customers (Customers)
      FileText → /purchase-orders (Purchase Orders)
      Search → /search (Search)
    Active link highlighted
  - Top header bar:
    Search input (navigates to /search?q=xxx on Enter)
  - Main content area (ml-64, p-6)
  - Outlet for page content

File: frontend/src/pages/DashboardPage.tsx
  Fetch /api/v1/admin/stats
  Show 4 stat cards in a grid:
    Total Customers, Total POs, Pending Reviews, Verified Documents
  Show recent POs (fetch purchase-orders?per_page=10, sorted newest first)
    Table: PO Number, Customer, Date, Chain %, Status
    Chain % shown as a colored progress bar
    Click row → navigate to /purchase-orders/{id}

File: frontend/src/pages/CustomersPage.tsx
  Top bar: Search input + "Add Customer" button
  Table: Customer ID (SKY-xxx), Name, GST, PO Count, Actions
  Click row → /purchase-orders?customer_id={id}
  "Add Customer" opens a modal/dialog with form:
    customer_id (required, placeholder: SKY-XXXXX), name (required),
    contact_email, gst_number
    Submit → createCustomer API

File: frontend/src/pages/POListPage.tsx
  Top bar: 
    Search input (PO number), Customer dropdown filter, 
    Status dropdown filter, "Create PO" button
  Table: PO Number, Customer (SKY-id + name), Date, Amount,
         Chain % (progress bar), Status badge
  Click row → /purchase-orders/{id}
  "Create PO" modal: select customer (dropdown), PO number, date, amount
```

### Phase 5.4 — PO Detail Page (The Main Work View)

**Claude Prompt:**

```
Create the PO Detail Page — this is the heart of the application.
Shows a single Purchase Order with its complete 6-document chain.

File: frontend/src/pages/PODetailPage.tsx

Use useParams to get PO id from URL. Fetch PO detail + chain status.

LAYOUT (responsive two-column on desktop):

┌─────────────────────────────────────────────────────────────────┐
│ Back button (←) │ PO-2026-0001 │ Acme Corp (SKY-AB1234)        │
│ Status badge: IN_PROGRESS │ Amount: ₹4,50,000                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──── Chain Status Bar ─────────────────────────────────────┐  │
│  │  ● ──── ● ──── ● ──── ○ ──── ○ ──── ○                    │  │
│  │  PO    V.DC  V.Inv  C.DC  C.Inv  POD                     │  │
│  │  ✓ 92%  ✓ 88%  ⏳     —      —      —                    │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
├───────────────────────────────┬──────────────────────────────────┤
│  Document Cards (left 55%)    │  Preview Panel (right 45%)       │
│                               │                                  │
│  ┌──────────────────────┐    │  ┌────────────────────────────┐  │
│  │ CUSTOMER_PO       ✅  │    │  │   PDF Preview (iframe)     │  │
│  │ PO-2026-0001         │    │  │                            │  │
│  │ 2026-01-05 │ 92.5%   │    │  │   Shows whichever doc     │  │
│  │ [Preview] [Re-extract]│    │  │   card is selected        │  │
│  └──────────────────────┘    │  │                            │  │
│                               │  │                            │  │
│  ┌──────────────────────┐    │  │                            │  │
│  │ VENDOR_DC         ✅  │    │  │                            │  │
│  │ DC-7890              │    │  │                            │  │
│  │ 2026-01-15 │ 88.0%   │    │  │                            │  │
│  │ [Preview] [Review]   │    │  └────────────────────────────┘  │
│  └──────────────────────┘    │                                  │
│                               │  Download button                 │
│  ┌──────────────────────┐    │                                  │
│  │ VENDOR_INVOICE    ⏳  │    │                                  │
│  │ Extracting...        │    │                                  │
│  │ ████████░░░░ spinner │    │                                  │
│  └──────────────────────┘    │                                  │
│                               │                                  │
│  ┌──────────────────────┐    │                                  │
│  │ COMPANY_DC        ○  │    │                                  │
│  │ Not uploaded yet     │    │                                  │
│  │ [Upload Document]    │    │                                  │
│  └──────────────────────┘    │                                  │
│                               │                                  │
│  (same for COMPANY_INVOICE    │                                  │
│   and POD cards)              │                                  │
└───────────────────────────────┴──────────────────────────────────┘

COMPONENTS TO CREATE:

1. frontend/src/components/ChainStatusBar.tsx
   Props: chain (from ChainStatusResponse)
   Renders 6 circles connected by lines horizontally.
   Each circle: 
     ● green (filled) = VERIFIED
     ● yellow = PENDING_REVIEW  
     ● blue + pulse animation = EXTRACTING
     ● red = EXTRACTION_FAILED / REJECTED
     ○ gray (empty) = not uploaded
   Below each circle: short label (PO, V.DC, V.Inv, C.DC, C.Inv, POD)
   Below label: confidence % if available

2. frontend/src/components/DocumentCard.tsx
   Props: documentType (string), slot (ChainSlot | null), 
          onSelect (callback), onUpload (callback), isSelected (boolean)
   
   Renders differently based on state:
   
   NOT UPLOADED (slot is null):
     Gray border, document type name, "Not uploaded" text
     Upload button (opens file picker)
   
   UPLOADED / EXTRACTING:
     Blue border, "Extracting..." with animated spinner
     Auto-refetch every 3 seconds until status changes
   
   PENDING_REVIEW:
     Yellow/amber border, ref_no, date, confidence badge
     [Preview] and [Review] buttons
     Review button opens ReviewModal
   
   VERIFIED:
     Green border, ref_no, date, confidence badge
     [Preview] and [Re-extract] buttons
   
   EXTRACTION_FAILED / REJECTED:
     Red border, error message (truncated)
     [Re-extract] button
   
   Click card → calls onSelect(documentId) → shows PDF in preview panel

3. frontend/src/components/UploadZone.tsx
   Props: poId, documentType, onSuccess callback
   Uses react-dropzone: accept only .pdf, maxFiles 1
   Shows drag area with dashed border
   On drop: call uploadDocument API, show progress
   On success: call onSuccess (triggers refetch)

4. frontend/src/components/PDFPreviewPanel.tsx
   Props: documentId (UUID | null)
   If null: show placeholder "Select a document to preview"
   If set: render iframe with src=/api/v1/documents/{id}/preview
   Show document type and ref_no header
   Download button linking to /api/v1/documents/{id}/download

5. frontend/src/components/ReviewModal.tsx
   Props: documentId, onClose, onVerified
   Full-screen modal overlay.
   
   Fetches metadata via useMetadata(documentId).
   
   Split view:
     LEFT (50%): iframe with PDF preview
     RIGHT (50%): 
       Confidence badge at top
       Form with all extracted fields as editable inputs
       Each field: label + text/number/date input, pre-filled from extracted_data
       For null fields: empty input with placeholder
       
       Buttons at bottom:
         [Verify ✓] → calls verifyMetadata with form data, then onVerified()
         [Reject ✗] → calls rejectMetadata, then onClose()
         [Cancel] → onClose()
   
   Form fields depend on document_type:
     CUSTOMER_PO: po_number, po_date, customer_name, total_amount, currency, ...
     VENDOR_INVOICE: invoice_number, invoice_date, po_reference, total_amount, ...
     (use EXTRACTION_PROMPTS schema keys as field list)
     
   Simple approach: iterate over Object.entries(extracted_data) and render 
   an input for each key. Label = key formatted nicely (snake_case → Title Case).

BEHAVIOR:
  - On page load: fetch PO + chain status
  - Document cards rendered for all 6 types from chain status
  - Clicking a card shows its PDF in preview panel
  - Upload button on empty slots opens file picker
  - After upload: card shows "Extracting..." with auto-refetch (refetchInterval: 3000)
  - After extraction: card shows "Pending Review" with Review button
  - Review modal: edit fields → Verify → chain status refreshes
  - Use React Query invalidation: after verify/upload/reject, 
    invalidate ["chainStatus", poId] and ["documents", poId]
```

### Phase 5.5 — Search Page

**Claude Prompt:**

```
Create the Search Page.

File: frontend/src/pages/SearchPage.tsx

Reads initial query from URL: /search?q=xxx (using useSearchParams).

Layout:
  Large search input at top with search icon
  Below: result count ("Found 5 results for 'INV-2026-1234'")
  Results as cards, grouped by type:
  
  Customer results:
    Icon: Users
    Title: customer name
    Subtitle: customer_id (SKY-xxx)
    Click → /purchase-orders?customer_id={id}
  
  Purchase Order results:
    Icon: FileText  
    Title: PO number
    Subtitle: customer name + chain % + status badge
    Click → /purchase-orders/{id}
  
  Document results:
    Icon: File (colored by doc type)
    Title: "Vendor Invoice — INV-2026-1234" (type + ref_number)
    Subtitle: PO: PO-xxx | Customer: Name | Confidence: 92%
    Click → /purchase-orders/{po_id} (navigate to PO detail, ideally selecting this doc)

  Empty state: "No results found. Try a different search term."
  Loading state: spinner

Search triggers on Enter key or when URL query param changes.
Use useSearch hook with enabled: query.length >= 2.
Show "Type at least 2 characters to search" if query too short.
```

### Phase 5 — Verification

```
□ Dashboard shows correct stat counts
□ Create customer with SKY-xxx ID → appears in list
□ Create PO linked to customer → appears in PO list with 0% chain
□ PO detail page: 6 document slots all gray (empty)
□ Click empty slot → upload PDF → card turns blue "Extracting..."
□ After extraction (~10-30s): card turns yellow "Pending Review"
□ Chain status bar updates: 1 circle filled
□ Click card → PDF shows in preview panel on right
□ Click Review → modal opens with PDF left + form right
□ Edit a field → click Verify → card turns green
□ Upload more docs → chain fills up progressively
□ Search "INV-xxx" → finds the document, click navigates to PO
□ Search "SKY-AB1234" → finds customer
□ Search "PO-2026-0001" → finds PO
```

---

## Complete API Reference

```
CUSTOMERS
  POST   /api/v1/customers                           create
  GET    /api/v1/customers                           list (search, paginate)
  GET    /api/v1/customers/{id}                      detail
  PATCH  /api/v1/customers/{id}                      update
  GET    /api/v1/customers/{id}/purchase-orders       customer's POs

PURCHASE ORDERS
  POST   /api/v1/purchase-orders                      create
  GET    /api/v1/purchase-orders                      list (filter, search)
  GET    /api/v1/purchase-orders/{id}                 detail
  PATCH  /api/v1/purchase-orders/{id}                 update
  GET    /api/v1/purchase-orders/{id}/chain-status    ★ chain completeness
  POST   /api/v1/purchase-orders/{po_id}/documents    ★ upload (auto-extract!)
  GET    /api/v1/purchase-orders/{po_id}/documents    list docs for PO

DOCUMENTS
  GET    /api/v1/documents/{id}                       detail + metadata
  DELETE /api/v1/documents/{id}                       delete
  GET    /api/v1/documents/{id}/preview               stream PDF inline
  GET    /api/v1/documents/{id}/download              download PDF
  POST   /api/v1/documents/{id}/rotate                rotate

EXTRACTION
  POST   /api/v1/documents/{id}/re-extract            re-run OCR
  GET    /api/v1/documents/{id}/metadata              extraction results
  PUT    /api/v1/documents/{id}/metadata/verify       ★ verify (with edits)
  PUT    /api/v1/documents/{id}/metadata/reject       reject

SEARCH
  GET    /api/v1/search?q={query}                     ★ global search
  GET    /api/v1/search/by-ref/{ref_value}            exact ref lookup
  GET    /api/v1/search/advanced                      multi-field filter

ADMIN
  GET    /api/v1/admin/health                         service health
  GET    /api/v1/admin/stats                          dashboard stats
```

---

## NAS Directory (Final)

```
/nas/documents/{customer_id}/{po_number}/{DOC_TYPE}/{uuid}_{name}.pdf

Example:
/nas/documents/
├── SKY-AB1234/
│   ├── PO-2026-0001/
│   │   ├── CUSTOMER_PO/a1b2c3d4_Acme_PO.pdf
│   │   ├── VENDOR_DC/e5f6g7h8_DC_Ship.pdf
│   │   ├── VENDOR_INVOICE/i9j0k1l2_Inv.pdf
│   │   ├── COMPANY_DC/m3n4o5p6_CDC.pdf
│   │   ├── COMPANY_INVOICE/q7r8s9t0_CInv.pdf
│   │   └── POD/u1v2w3x4_POD.pdf
│   └── PO-2026-0002/
│       └── ...
└── SKY-CD5678/
    └── ...
```

---

## Database Tables

```
customers           → master data (SKY-xxx ID = NAS folder name)
purchase_orders     → PO anchor (linked to customer)
documents           → uploaded PDFs (linked to PO)
document_metadata   → OCR extracted data (1:1 per document)
reference_index     → every extracted ref ID, B-Tree indexed (1:N per document)
```

---

## Tips for Building with Claude

1. **Give context:** Start each phase by pasting relevant models/schemas from prior phases.
2. **One file at a time** for complex files (especially the Celery task and PO detail page).
3. **Test with curl** after each backend phase before touching the frontend.
4. **The Celery task is the hardest part** — sync vs async is tricky. If stuck, share the full error traceback with Claude.
5. **Real PDFs matter** — test OCR with your actual documents. Prompt tuning may be needed.
6. **Frontend last** — get the entire backend + extraction working via curl first.

---

*End of Implementation Guide*
