# DPP 2.2.0 Technical Feature Report

Date: 2026-04-02

## 1. Scope And Method

This report is a source-backed technical inventory of implemented application capabilities across backend, frontend, data model, extraction pipeline, infrastructure, operations, integrations, and test coverage.

Primary evidence sources:
- Backend app boot and routing: [../backend/app/main.py](../backend/app/main.py), [../backend/app/api/router.py](../backend/app/api/router.py)
- API modules: [../backend/app/api/v1](../backend/app/api/v1)
- Service layer and extraction pipeline: [../backend/app/services](../backend/app/services)
- Persistence model: [../backend/app/models](../backend/app/models)
- Frontend routes, pages, components, hooks, API clients: [../frontend/src](../frontend/src)
- Runtime and deployment files: [../docker-compose.dev.yml](../docker-compose.dev.yml), [../docker-compose.prod.yml](../docker-compose.prod.yml), [../backend/Dockerfile](../backend/Dockerfile), [../frontend/Dockerfile](../frontend/Dockerfile), [../nginx/nginx.conf](../nginx/nginx.conf)
- Operations scripts: [../start.ps1](../start.ps1), [../stop_all.ps1](../stop_all.ps1), [../reset.ps1](../reset.ps1)
- CI/CD: [../.github/workflows/test.yml](../.github/workflows/test.yml), [../.github/workflows/deploy.yml](../.github/workflows/deploy.yml)
- Tests: [../tests/backend](../tests/backend), [../tests/frontend](../tests/frontend)

## 2. Platform Overview

### 2.1 Core Architecture

- API platform built on FastAPI with centralized v1 router mounting.
- Async PostgreSQL access for API requests and sync DB access for Celery workers.
- Redis used as Celery broker/backend and operational cache.
- Two-layer extraction pipeline:
  - Layer 1 OCR to markdown/text.
  - Layer 2 structured field extraction.
- React + TypeScript frontend with React Router and React Query.
- Document lifecycle states drive review workflow and chain completion.

Evidence:
- [../backend/app/main.py](../backend/app/main.py)
- [../backend/app/config.py](../backend/app/config.py)
- [../backend/celery_app.py](../backend/celery_app.py)
- [../backend/app/services/extraction/pipeline.py](../backend/app/services/extraction/pipeline.py)
- [../frontend/src/App.tsx](../frontend/src/App.tsx)

### 2.2 Technology Stack

Backend stack:
- FastAPI, Uvicorn, SQLAlchemy 2.x, Alembic, AsyncPG, Psycopg2.
- Celery with Redis transport.
- PDF and OCR support libraries: PyMuPDF, pdfplumber, Pillow, numpy, OpenCV.
- Excel export via openpyxl.

Frontend stack:
- React 18, TypeScript, Vite.
- React Router, React Query, Axios, Zustand.
- react-pdf, react-dropzone.
- Tailwind CSS.

Dependencies evidence:
- [../backend/requirements.txt](../backend/requirements.txt)
- [../frontend/package.json](../frontend/package.json)

## 3. Backend Feature Inventory

### 3.1 API Surface Summary

Total endpoints in v1 routers: 35

Router modules:
- Customers: [../backend/app/api/v1/customers.py](../backend/app/api/v1/customers.py)
- Purchase orders: [../backend/app/api/v1/purchase_orders.py](../backend/app/api/v1/purchase_orders.py)
- Documents: [../backend/app/api/v1/documents.py](../backend/app/api/v1/documents.py)
- Extraction: [../backend/app/api/v1/extraction.py](../backend/app/api/v1/extraction.py)
- Search: [../backend/app/api/v1/search.py](../backend/app/api/v1/search.py)
- Admin: [../backend/app/api/v1/admin.py](../backend/app/api/v1/admin.py)

### 3.2 Customer Domain Features

Implemented features:
- Create customer.
- List customers with pagination and search.
- Get customer by ID.
- Patch customer details.
- List purchase orders per customer.

Evidence:
- [../backend/app/api/v1/customers.py](../backend/app/api/v1/customers.py)
- [../backend/app/services/customer_service.py](../backend/app/services/customer_service.py)

### 3.3 Purchase Order Domain Features

Implemented features:
- Create PO with uniqueness checks.
- List POs with advanced filtering:
  - customer_id, status, search over PO/SO.
  - date range.
  - sort_by and sort_order.
  - chain completion filter.
  - missing document type filter.
- Update PO including SO number and fulfillment type implications.
- Delete PO with cascading cleanup of documents, metadata, references, corrections, and storage files.
- Chain status retrieval by document type slots.
- PO profile endpoint for consolidated document/timeline/discrepancy view.
- PO export endpoint to XLSX with mode options.
- Nested PO document upload and listing.

Evidence:
- [../backend/app/api/v1/purchase_orders.py](../backend/app/api/v1/purchase_orders.py)
- [../backend/app/services/po_service.py](../backend/app/services/po_service.py)
- [../backend/app/services/export_service.py](../backend/app/services/export_service.py)

### 3.4 Document Domain Features

Implemented features:
- Global document list with filters by status, type, customer, date range.
- Get document by ID.
- Delete document.
- Preview document stream.
- Download document stream.
- Rotate document metadata state by 90/180/270 degrees.

Evidence:
- [../backend/app/api/v1/documents.py](../backend/app/api/v1/documents.py)
- [../backend/app/services/document_service.py](../backend/app/services/document_service.py)

### 3.5 Extraction And Metadata Features

Implemented features:
- Get extraction template fields per document type.
- Manual metadata stub creation for operator-first entry.
- Re-extract endpoint with version-safe behavior:
  - increments extraction_version.
  - clears extraction payload fields.
  - keeps correction history table.
- Fetch metadata.
- Verify metadata flow with business rules:
  - preserves array fields from existing metadata.
  - rebuilds ReferenceIndex entries from edited values.
  - enforces SO entry gate for CUSTOMER_PO.
  - enforces SO mismatch gate for COMPANY_DC and COMPANY_INVOICE.
- Reject metadata.
- Save corrections for active-learning style audit trail.

Evidence:
- [../backend/app/api/v1/extraction.py](../backend/app/api/v1/extraction.py)
- [../backend/app/models/extraction_correction.py](../backend/app/models/extraction_correction.py)

### 3.6 Search Features

Implemented features:
- Global search with minimum query threshold.
- Exact by-reference lookup.
- Advanced multi-field search including invoice/dc/po/so/customer/address/date/type.

Evidence:
- [../backend/app/api/v1/search.py](../backend/app/api/v1/search.py)
- [../backend/app/services/search_service.py](../backend/app/services/search_service.py)

### 3.7 Admin And Operations Endpoints

Implemented features:
- Health endpoint with parallel checks and Redis TTL cache.
- Stats endpoint with conditional aggregation for document states.
- Queue endpoint using Celery inspect active/reserved/stats.
- Requeue endpoint for PENDING_MODEL documents.

Health checks cover:
- Database.
- Redis.
- OCR endpoint tags availability.
- Required models presence.
- Storage path accessibility/writability.

Evidence:
- [../backend/app/api/v1/admin.py](../backend/app/api/v1/admin.py)

## 4. Complete API Catalog

Base prefix: /api/v1

### 4.1 Customers

- POST /customers
- GET /customers
- GET /customers/{id}
- PATCH /customers/{id}
- GET /customers/{id}/purchase-orders

Source: [../backend/app/api/v1/customers.py](../backend/app/api/v1/customers.py)

### 4.2 Purchase Orders

- POST /purchase-orders
- GET /purchase-orders
- GET /purchase-orders/{id}
- PATCH /purchase-orders/{id}
- DELETE /purchase-orders/{id}
- GET /purchase-orders/{id}/chain-status
- GET /purchase-orders/{id}/profile
- GET /purchase-orders/{id}/export
- POST /purchase-orders/{po_id}/documents
- GET /purchase-orders/{po_id}/documents

Source: [../backend/app/api/v1/purchase_orders.py](../backend/app/api/v1/purchase_orders.py)

### 4.3 Documents

- GET /documents
- GET /documents/{id}
- DELETE /documents/{id}
- GET /documents/{id}/preview
- GET /documents/{id}/download
- POST /documents/{id}/rotate

Source: [../backend/app/api/v1/documents.py](../backend/app/api/v1/documents.py)

### 4.4 Extraction

- GET /documents/{document_id}/metadata/template
- POST /documents/{document_id}/metadata/manual
- POST /documents/{document_id}/re-extract
- GET /documents/{document_id}/metadata
- PUT /documents/{document_id}/metadata/verify
- PUT /documents/{document_id}/metadata/reject
- POST /documents/{document_id}/corrections

Source: [../backend/app/api/v1/extraction.py](../backend/app/api/v1/extraction.py)

### 4.5 Search

- GET /search
- GET /search/by-ref/{ref_value}
- GET /search/advanced

Source: [../backend/app/api/v1/search.py](../backend/app/api/v1/search.py)

### 4.6 Admin

- GET /admin/health
- GET /admin/stats
- GET /admin/queue
- POST /admin/requeue-pending-models

Source: [../backend/app/api/v1/admin.py](../backend/app/api/v1/admin.py)

## 5. Data Model And Persistence Features

Model package: [../backend/app/models](../backend/app/models)

### 5.1 Core Entities

Customer:
- Master customer identity and contact profile.
- Unique customer_id indexing.

PurchaseOrder:
- PO header and lifecycle status.
- chain_completeness numeric progress.
- so_number support.
- fulfillment_type enum with procurement and stock behavior.

Document:
- Document type enum for six-chain docs.
- Document processing status enum including PENDING_MODEL.
- Unique constraint across po_id + document_type + checksum.

DocumentMetadata:
- JSONB extracted_data payload.
- metadata status enum pending/extracted/verified/failed.
- extraction_version for re-extraction history semantics.
- field_confidences JSONB.
- extraction_route persisted as digital/scanned marker.

ReferenceIndex:
- Denormalized references per document for search acceleration.

ExtractionCorrection:
- Field-level original and corrected values.
- operator and extraction version audit capture.

Evidence:
- [../backend/app/models/customer.py](../backend/app/models/customer.py)
- [../backend/app/models/purchase_order.py](../backend/app/models/purchase_order.py)
- [../backend/app/models/document.py](../backend/app/models/document.py)
- [../backend/app/models/document_metadata.py](../backend/app/models/document_metadata.py)
- [../backend/app/models/reference_index.py](../backend/app/models/reference_index.py)
- [../backend/app/models/extraction_correction.py](../backend/app/models/extraction_correction.py)

### 5.2 Lifecycle State Features

DocumentStatus enum states:
- UPLOADED, EXTRACTING, PENDING_REVIEW, VERIFIED, REJECTED, EXTRACTION_FAILED, PENDING_MODEL.

POStatus enum states:
- INITIATED, IN_PROGRESS, NEAR_COMPLETE, COMPLETE, CANCELLED.

MetadataStatus enum states:
- PENDING, EXTRACTED, VERIFIED, FAILED.

Evidence:
- [../backend/app/models/document.py](../backend/app/models/document.py)
- [../backend/app/models/purchase_order.py](../backend/app/models/purchase_order.py)
- [../backend/app/models/document_metadata.py](../backend/app/models/document_metadata.py)

## 6. Extraction Pipeline Technical Features

Core orchestration:
- Celery task extract_document handles preflight, route selection, OCR, extraction, validation, metadata persistence, indexing, status updates.

Pipeline capabilities:
- Provider-agnostic abstraction for Layer1 and Layer2.
- Digital fast-path extraction fallback to scanned OCR path.
- OCR page loop with per-page failure tolerance.
- Layer2 extraction pass with validation and page merge strategy.
- VRAM release and readiness wait between phases.
- Preflight health check that routes blocked docs to PENDING_MODEL.

Validation capabilities:
- Field normalization and schema validation.
- Invoice math validation with warnings/errors.
- SO-number cross-document validation.

Persistence capabilities:
- metadata update with confidence/model_version/processing_time.
- extraction_route and field_confidences persistence.
- ReferenceIndex rebuild from searchable fields.

Evidence:
- [../backend/app/services/extraction/tasks.py](../backend/app/services/extraction/tasks.py)
- [../backend/app/services/extraction/pipeline.py](../backend/app/services/extraction/pipeline.py)
- [../backend/app/services/extraction/providers](../backend/app/services/extraction/providers)
- [../backend/app/services/extraction/field_validator.py](../backend/app/services/extraction/field_validator.py)
- [../backend/app/services/extraction/invoice_validator.py](../backend/app/services/extraction/invoice_validator.py)
- [../backend/app/services/extraction/so_validator.py](../backend/app/services/extraction/so_validator.py)

## 7. Frontend Feature Inventory

Frontend root: [../frontend/src](../frontend/src)

### 7.1 Route-Level Features

Route map:
- / dashboard
- /customers
- /purchase-orders
- /purchase-orders/:id/profile
- /purchase-orders/:id
- /documents
- /search
- /admin

Evidence:
- [../frontend/src/App.tsx](../frontend/src/App.tsx)

### 7.2 Layout And Navigation Features

AppShell features:
- Sidebar navigation with collapse persistence in localStorage.
- Mobile overlay behavior.
- Inline top-bar search component container.
- Route outlet layout.

Evidence:
- [../frontend/src/components/layout/AppShell.tsx](../frontend/src/components/layout/AppShell.tsx)

### 7.3 Page-Level Features

Dashboard page:
- Stats cards from admin/stats.
- Pending review queue with quick PO navigation.
- Recent PO table with chain progress bars and status badges.

Customers page:
- Paginated customer list and create workflow.
- Search and row-to-PO navigation.

PO list page:
- Multi-filter listing with search, customer, status, date range, chain, missing doc type, sorting.

PO detail page:
- PO header and SO editing.
- Chain status visualization.
- Per-type document card actions (upload/review/re-extract/delete/manual paths).
- PDF preview panel integration.

PO profile page:
- Consolidated per-slot profile view.
- timeline display.
- field comparison and discrepancy panels.

Documents page:
- Global document listing and filtering.
- Actions integration for document operations.

Search page:
- Global and advanced search UX flows.

Admin page:
- Health, stats, queue visibility.
- Pending model requeue control.

Evidence:
- [../frontend/src/pages](../frontend/src/pages)

### 7.4 Shared Component Features

Implemented reusable feature components:
- ChainStatusBar.
- DocumentCard.
- ReviewModal.
- UploadZone.
- PDFViewer and PDFPreviewPanel.
- OrderItemsTable.
- ProfileTimeline.
- ProfileFieldComparison.
- ProfileDiscrepancyPanel.
- ProfileDocumentSection.

Evidence:
- [../frontend/src/components](../frontend/src/components)

### 7.5 Data Access And Client Behavior

Hooks and API modules:
- useCustomers, useDocuments, useExtraction, usePurchaseOrders, useSearch.
- API modules map to backend domain endpoints.

HTTP client behavior:
- Central Axios instance.
- Global response interceptor for network and server class errors.
- Toast bridge integration for app-wide feedback.

Evidence:
- [../frontend/src/hooks](../frontend/src/hooks)
- [../frontend/src/api](../frontend/src/api)
- [../frontend/src/api/client.ts](../frontend/src/api/client.ts)

## 8. Infrastructure And Operational Features

### 8.1 Development Topology

Development compose file provisions infra-only services:
- PostgreSQL on host port 5434.
- Redis on host port 6380.
- Health checks on both services.

Evidence:
- [../docker-compose.dev.yml](../docker-compose.dev.yml)

### 8.2 Production Topology

Production compose stack includes:
- postgres, redis, backend, worker, frontend, nginx.
- restart unless-stopped semantics.
- worker deploy replicas section.
- storage bind mount for backend and worker.

Evidence:
- [../docker-compose.prod.yml](../docker-compose.prod.yml)

### 8.3 Container Build Features

Backend Dockerfile:
- Multi-stage targets for api and worker.
- API startup runs alembic upgrade before serving.
- Worker startup runs celery worker.

Frontend Dockerfile:
- Build stage compiles Vite app.
- Runtime stage serves with nginx.

Evidence:
- [../backend/Dockerfile](../backend/Dockerfile)
- [../frontend/Dockerfile](../frontend/Dockerfile)

### 8.4 Runtime Script Features

start.ps1:
- Cleans old processes.
- Ensures infra up and healthy.
- Runs DB migrations.
- Checks OCR endpoint tags.
- Launches backend, worker, frontend in separate windows.
- Optional docker shutdown prompt at exit.

stop_all.ps1:
- Stops known jobs/processes and frees configured ports.

reset.ps1:
- Interactive/forced environment reset.
- Drops schema and re-applies migrations.
- Flushes Redis.
- Clears storage/debug/reports/cache artifacts.

Evidence:
- [../start.ps1](../start.ps1)
- [../stop_all.ps1](../stop_all.ps1)
- [../reset.ps1](../reset.ps1)

### 8.5 Logging And Observability Features

Central logging config provides:
- Component-specific log channels: app, celery, ai, db.
- Daily rotation with 30-day retention.
- UTF-8 safe console handler.
- Safe rotating handler for Windows file-lock behavior.

Evidence:
- [../backend/app/logging_config.py](../backend/app/logging_config.py)

### 8.6 Queue And Worker Runtime Features

Celery configuration includes:
- JSON serialization policy.
- soft/hard time limits.
- task_acks_late.
- worker_prefetch_multiplier=1.
- retry-on-startup for broker connection.
- signals for task failure and retry logging.

Evidence:
- [../backend/celery_app.py](../backend/celery_app.py)

## 9. External Integration Features

### 9.1 OCR And Model Integrations

Config supports:
- Local Ollama base URL flow.
- Two-layer mode toggles.
- Separate extractor endpoint override.
- Provider abstraction modes:
  - ollama
  - datalab
  - openai_compat
  - digital (layer1)

Evidence:
- [../backend/app/config.py](../backend/app/config.py)
- [../backend/app/services/extraction/providers](../backend/app/services/extraction/providers)

### 9.2 Data And Cache Integrations

- PostgreSQL integration via async and sync URLs.
- Redis integration for queue and health cache.
- Storage integration via configurable NAS/local path.

Evidence:
- [../backend/app/config.py](../backend/app/config.py)
- [../backend/app/database.py](../backend/app/database.py)
- [../backend/app/services/storage_service.py](../backend/app/services/storage_service.py)

## 10. Configuration Surface

Primary runtime config surface:
- [.env.example](../.env.example)
- [../backend/app/config.py](../backend/app/config.py)

Key categories:
- database URLs.
- redis URL.
- storage path.
- OCR base model and timeout/retries/page limits.
- two-layer extraction model settings.
- provider selection and API credentials.
- CORS origins.
- debug mode.

## 11. CI/CD And Delivery Features

Test workflow:
- Backend pytest on pushes/PRs to main with PostgreSQL service.
- Frontend vitest on pushes/PRs to main.

Deploy workflow:
- Trigger on branch DPP-2.3.0.
- SSH setup and rsync to Azure VM target.
- Writes env from secret and starts compose prod stack.

Evidence:
- [../.github/workflows/test.yml](../.github/workflows/test.yml)
- [../.github/workflows/deploy.yml](../.github/workflows/deploy.yml)

## 12. Test Coverage Inventory

Backend tests (10 modules):
- test_admin_helpers.py
- test_chain_completeness.py
- test_extraction_error_messages.py
- test_field_validator.py
- test_hybrid_router.py
- test_invoice_validator.py
- test_ocr_cleaning.py
- test_pdf_validation.py
- test_response_parser.py
- test_so_validator.py

Frontend tests (3 modules):
- test_extraction_error_messages.test.ts
- test_friendly_extraction_error.test.ts
- test_types_constants.test.ts

Evidence:
- [../tests/backend](../tests/backend)
- [../tests/frontend](../tests/frontend)

## 13. Known Gaps, Risks, And Constraints

### 13.1 Confirmed Gaps

- No authentication/authorization or role gating visible in frontend routes and current backend endpoint layer.
- Frontend test coverage is utility-focused; limited component/e2e coverage in repository.
- stop_all.ps1 targets ports 8000 and 5173 while start.ps1 uses 8002 and 5174, which may leave dev processes running depending on session state.
- No built-in real-time push channel; status refresh is polling-based.

Evidence:
- [../frontend/src/App.tsx](../frontend/src/App.tsx)
- [../tests/frontend](../tests/frontend)
- [../start.ps1](../start.ps1)
- [../stop_all.ps1](../stop_all.ps1)

### 13.2 Operational Risks

- OCR/model endpoint failures can interrupt extraction; system mitigates by parking documents in PENDING_MODEL and supporting admin requeue.
- Storage path availability remains critical for document preview/download/upload operations.
- Extraction quality depends on model availability and document quality; manual entry/review flows are required fallback.

Evidence:
- [../backend/app/api/v1/admin.py](../backend/app/api/v1/admin.py)
- [../backend/app/api/v1/documents.py](../backend/app/api/v1/documents.py)
- [../backend/app/api/v1/extraction.py](../backend/app/api/v1/extraction.py)

## 14. Feature Totals Snapshot

- Backend v1 endpoints: 35
- Frontend routed pages: 8
- Core persistence entities: 6
- Background extraction task flow: 1 primary Celery task with multi-stage orchestration
- Dev infra services via compose: 2
- Prod stack services via compose: 6
- Backend test modules: 10
- Frontend test modules: 3

## 15. Implementation Readiness Summary

The codebase currently implements a full document processing platform with end-to-end flows for:
- customer and purchase-order operations,
- controlled document upload and lifecycle management,
- two-layer extraction with operator review and correction capture,
- searchable reference indexing,
- profile and export views,
- admin health/queue observability,
- and scripted local/prod operations.

Primary next technical hardening priorities are:
- security controls (auth/rbac),
- expanded frontend integration/e2e testing,
- and script/port consistency cleanup across local operational tooling.
