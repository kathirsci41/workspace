# DPP Backend Architecture
**Last Updated:** 2026-04-19

---

## 1. Backend Role

The backend is responsible for the business workflow of the platform.

It is not just a transport layer for the frontend. It owns:

- entity creation and persistence
- document upload and storage coordination
- extraction orchestration
- validation and chain computation
- PO profiling and discrepancy generation
- search and admin APIs
- assistant chat streaming

The API layer is intentionally thinner than the service layer.

---

## 2. Main Backend Structure

### Entry points

- `backend/app/main.py`
- `backend/app/api/router.py`
- `backend/app/database.py`
- `backend/app/config.py`

### Main folders

- `backend/app/api/`: FastAPI routers
- `backend/app/models/`: SQLAlchemy models
- `backend/app/schemas/`: Pydantic API schemas
- `backend/app/services/`: domain and workflow logic
- `backend/app/services/extraction/`: OCR and extraction pipeline
- `backend/alembic/`: schema migrations
- `backend/celery_app.py`: worker and broker configuration

---

## 3. API Layer

### Router groups

- `customers`
- `purchase_orders`
- `documents`
- `extraction`
- `search`
- `admin`
- `chat`

### Architectural behavior

Routers generally do three things:

- receive and validate request parameters
- call a service or execute narrow orchestration logic
- translate domain objects into response schemas

Heavy business logic is not supposed to live in route handlers, although some endpoints still contain targeted orchestration logic where data aggregation is tightly bound to the response shape.

---

## 4. Database Access Pattern

The backend uses two SQLAlchemy access modes.

### Async path

FastAPI endpoints use:

- async engine
- async session maker
- dependency-injected sessions

This is the normal request/response path.

### Sync path

Celery tasks use:

- sync engine
- sync session maker

This keeps the worker path simple and avoids mixing async task internals with Celery task execution directly.

---

## 5. Main Domain Services

### `po_service.py`

This is one of the most important files in the backend.

It owns much of the PO-centric domain logic, including:

- PO creation and update
- list filtering and sorting
- scenario derivation support
- GST detection support
- profile assembly
- chain completeness updates
- closure behavior

### `document_service.py`

This owns document-oriented operations, especially:

- upload validation
- checksum handling
- duplicate detection
- storage path generation
- file persistence coordination
- queue dispatch for extraction
- preview and download helpers
- deletion behavior

### Additional supporting services

- `chain_validator.py`
- `cross_doc_validator.py`
- `reference_validator.py`
- `billing_tracker.py`
- `search_service.py`
- `address_parser.py`
- `item_matcher.py`
- `export_service.py`
- `chat_service.py`

These provide narrower pieces of workflow-specific logic on top of the PO/document core.

---

## 6. Upload Path

Document upload is one of the main write paths in the entire system.

### Request path

The upload flow is:

1. receive multipart file and document type
2. validate document type
3. load the target PO
4. read and validate PDF bytes
5. enforce size limits
6. compute checksum
7. prevent duplicate upload within the PO
8. generate customer/PO/type-based storage path
9. save the file via `StorageService`
10. create the `Document` row
11. update chain completeness
12. enqueue asynchronous extraction

### Why this matters

This path connects all major system concerns:

- database integrity
- file storage integrity
- workflow state
- async task scheduling

---

## 7. Storage Model

`StorageService` abstracts filesystem-backed document storage.

### Responsibilities

- generate deterministic relative paths
- sanitize filenames
- block path traversal
- check storage accessibility
- save files
- read files
- delete files
- compute checksums

### Architectural implication

The backend treats storage health as an operational dependency, not an implementation detail. Uploads can fail fast with a storage-related error instead of silently corrupting workflow state.

---

## 8. Extraction Subsystem

The extraction subsystem is the most operationally complex part of the backend.

### Main files

- `backend/app/services/extraction/tasks.py`
- `backend/app/services/extraction/pipeline.py`
- `backend/app/services/extraction/hybrid_router.py`
- `backend/app/services/extraction/digital_extractor.py`
- `backend/app/services/extraction/providers/`

### Architectural shape

The backend now uses a provider-agnostic extraction pipeline:

- Layer 1: OCR or digital text extraction
- Layer 2: structured field extraction
- post-processing validators

This means extraction behavior can vary by deployment config without changing the rest of the application flow.

---

## 9. Extraction Execution Flow

The `extract_document` Celery task is the main background process.

### Step-by-step

1. load the document from the database
2. build the extraction pipeline from config
3. mark the document as `EXTRACTING`
4. resolve the storage path
5. choose digital vs scanned route
6. perform health checks on configured providers
7. extract markdown/text
8. run structured extraction if Layer 2 is enabled
9. validate the result
10. create or update `DocumentMetadata`
11. rebuild `ReferenceIndex` entries
12. move the document into the next operational status
13. trigger PO chain recomputation

### Important statuses

- `UPLOADED`
- `EXTRACTING`
- `PENDING_REVIEW`
- `PENDING_MODEL`
- `EXTRACTION_FAILED`
- `VERIFIED`
- `REJECTED`

`PENDING_MODEL` is especially important because it captures operational dependency failure without treating the document as broken.

---

## 10. Validation Layers

Validation does not happen only at review time. It already starts in the extraction pipeline.

### Main validation types

- field normalization and coercion
- invoice math checks
- SO-number checks against the parent PO

### Where validation lands

Validation errors and warnings are stored inside extracted payload metadata and then surfaced to the frontend review flow.

This means the backend produces review-ready operational context, not just raw model output.

---

## 11. Search Architecture

The search system is built on top of persisted extracted data rather than direct filesystem search.

### Search inputs

- customer data
- PO data
- document metadata
- denormalized reference rows
- extracted address-related fields

### Important architectural decision

The existence of `ReferenceIndex` means the search layer is optimized for operational lookups across heterogeneous document types without forcing every query through raw JSON payload scans.

---

## 12. PO Profile And Validation Aggregation

The backend assembles a PO-level profile view that combines:

- document slots
- discrepancies
- cross-reference checks
- timeline events
- field comparisons
- item comparisons
- item matches
- vendor groups

This is one of the strongest signals that the product is a workflow engine around orders, not a loose collection of document APIs.

---

## 13. Chat And Admin

### Chat

The chat router streams assistant responses over SSE and can optionally scope context to a PO.

### Admin

The admin APIs expose:

- service health
- queue state
- counters and status breakdowns
- requeue operations for held documents

These are operational platform capabilities, not just developer tools.

---

## 14. Backend Design Constraints

When changing the backend, preserve these assumptions:

- `PurchaseOrder` remains the main aggregate
- document processing must not block user-facing upload requests
- extraction providers can change by environment
- human review remains the trust boundary
- PO-level validation must remain derivable from stored document state

Breaking any of those assumptions would change the product model, not just implementation details.
