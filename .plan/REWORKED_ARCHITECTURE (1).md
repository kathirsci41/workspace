# Document Management Platform V3.0 — Reworked Architecture

**Date:** February 2026  
**Status:** Architecture Proposal  
**Scope:** Complete Redesign — PO-Centric Document Lifecycle  
**Deployment:** Fully Self-Hosted (On-Premise GPU)

---

## Table of Contents

1. [Design Philosophy](#1-design-philosophy)
2. [Core Concept: PO-Centric Document Chain](#2-core-concept-po-centric-document-chain)
3. [Reworked Document Flow](#3-reworked-document-flow)
4. [System Architecture](#4-system-architecture)
5. [Database Schema (Redesigned)](#5-database-schema-redesigned)
6. [OCR Pipeline V2 (GLM-OCR via Ollama)](#6-ocr-pipeline-v2-glm-ocr-via-ollama)
7. [API Design](#7-api-design)
8. [Frontend Architecture](#8-frontend-architecture)
9. [File Storage (Reworked)](#9-file-storage-reworked)
10. [Authentication & Security](#10-authentication--security)
11. [Infrastructure & Deployment](#11-infrastructure--deployment)
12. [Migration Strategy from V2](#12-migration-strategy-from-v2)
13. [Implementation Phases](#13-implementation-phases)

---

## 1. Design Philosophy

### What Changed and Why

The V2 system had a **Case-centric** model where documents floated between Case-level and Sales Order-level storage, creating confusion. Customer PO was an orphan at the Case level while all other documents lived under Sales Orders.

**V3 inverts this entirely:**

```
V2 (Old — Broken Hierarchy):
  Case → Sales Order → Documents (but PO lives at Case level... awkward)

V3 (New — PO-Centric Chain):
  Customer → Purchase Order (anchor) → Document Chain
                                        ├── Vendor DC
                                        ├── Vendor Invoice
                                        ├── Company DC
                                        ├── Company Invoice
                                        └── POD / Acknowledgement
```

### Design Principles

| Principle | Description |
|-----------|-------------|
| **PO is the Root** | Every document in the system traces back to a Customer PO. No orphan documents. |
| **Document Chain** | Documents follow a logical business flow: PO → Vendor DC → Vendor Invoice → Company DC → Company Invoice → POD |
| **Extract on Upload** | OCR runs automatically when a document is uploaded — no manual "Extract" button needed. |
| **Self-Hosted First** | Everything runs on-premise. No cloud dependencies. GPU inference via Ollama. |
| **Verify Before Trust** | All OCR extractions start as `PENDING_REVIEW`. Humans verify before data becomes authoritative. |

---

## 2. Core Concept: PO-Centric Document Chain

### The Business Reality

In a typical sales/procurement flow, the Customer PO is the single source of truth that spawns all downstream documents:

```
Customer sends PO (PO-2026-001)
    │
    ├──► Vendor receives order, ships goods
    │    ├── Vendor DC (delivery challan proving shipment)
    │    └── Vendor Invoice (billing for goods shipped)
    │
    ├──► Company receives goods, dispatches to customer
    │    ├── Company DC (delivery challan to customer)
    │    └── Company Invoice (billing to customer)
    │
    └──► Customer receives goods
         └── POD / Acknowledgement (proof of delivery)
```

### Document Chain Status Tracking

Each PO has a **completeness status** based on which documents are present:

```
PO Completeness = (uploaded documents / required documents) × 100%

Required chain: [VENDOR_DC, VENDOR_INVOICE, COMPANY_DC, COMPANY_INVOICE, POD]

Status mapping:
  0%    → INITIATED     (only PO uploaded)
  1-49% → IN_PROGRESS   (some chain docs)
  50-99%→ NEAR_COMPLETE  (most chain docs)
  100%  → COMPLETE       (full chain)
```

---

## 3. Reworked Document Flow

### 3.1 Document Types (Revised)

| Document Type | Code | Role in Chain | Required | Extracted Fields |
|---------------|------|---------------|----------|-----------------|
| Customer Purchase Order | `CUSTOMER_PO` | **Root Anchor** | Yes (always first) | po_no, po_date, customer_name, total_amount, items |
| Vendor Delivery Challan | `VENDOR_DC` | Proof of vendor shipment | Yes | dc_no, dc_date, po_ref, items_shipped |
| Vendor Invoice | `VENDOR_INVOICE` | Vendor billing | Yes | invoice_no, invoice_date, po_ref, amount, tax |
| Company Delivery Challan | `COMPANY_DC` | Proof of dispatch to customer | Yes | dc_no, dc_date, po_ref, items_dispatched |
| Company Invoice | `COMPANY_INVOICE` | Customer billing | Yes | invoice_no, invoice_date, po_ref, amount, tax |
| POD / Acknowledgement | `POD` | Delivery confirmation | Yes | pod_no, delivery_date, received_by, dc_ref |

> **Removed:** `PURCHASE_BILL` (merged into `VENDOR_INVOICE` — they serve the same purpose in this context)

### 3.2 Upload Flow (Reworked)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DOCUMENT UPLOAD FLOW V3                            │
│                                                                             │
│   ┌──────────┐                                                              │
│   │  User    │                                                              │
│   │  Upload  │                                                              │
│   └────┬─────┘                                                              │
│        │                                                                    │
│        ▼                                                                    │
│   ┌──────────────────────────┐                                              │
│   │ Step 1: Select Customer  │  (autocomplete from Customer master)         │
│   └────────────┬─────────────┘                                              │
│                │                                                            │
│                ▼                                                            │
│   ┌──────────────────────────────────────────────┐                          │
│   │ Step 2: Select or Create PO                   │                         │
│   │  ├── Existing PO (dropdown of customer's POs) │                         │
│   │  └── New PO (if uploading Customer PO doc)     │                        │
│   └────────────┬─────────────────────────────────┘                          │
│                │                                                            │
│                ▼                                                            │
│   ┌──────────────────────────┐                                              │
│   │ Step 3: Select Doc Type  │  (dropdown: one of 6 types)                  │
│   └────────────┬─────────────┘                                              │
│                │                                                            │
│                ▼                                                            │
│   ┌──────────────────────────┐                                              │
│   │ Step 4: Drop PDF file(s) │  (drag & drop zone)                          │
│   └────────────┬─────────────┘                                              │
│                │                                                            │
│                ▼                                                            │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                     BACKEND PROCESSING                                │  │
│   │                                                                       │  │
│   │  1. Validate file (PDF, ≤ 25MB)                                      │  │
│   │  2. Calculate SHA-256 checksum                                       │  │
│   │  3. Check duplicates (checksum + doc_type + po_id)                   │  │
│   │  4. Store file to NAS                                                │  │
│   │  5. Create Document record (status: UPLOADED)                        │  │
│   │  6. ═══════════════════════════════════════════════                   │  │
│   │     ║  QUEUE OCR EXTRACTION (automatic)          ║                   │  │
│   │     ║  - Enqueue to background worker            ║                   │  │
│   │     ║  - No manual "Extract" button needed       ║                   │  │
│   │     ═══════════════════════════════════════════════                   │  │
│   │  7. Return 201 with document record                                  │  │
│   │  8. Background worker picks up job:                                  │  │
│   │     a. Convert PDF → images (PyMuPDF)                                │  │
│   │     b. Send to GLM-OCR (Ollama)                                      │  │
│   │     c. Parse response → structured JSON                              │  │
│   │     d. Save metadata (status: PENDING_REVIEW)                        │  │
│   │     e. Notify frontend via WebSocket                                 │  │
│   │  9. Audit log entry                                                  │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                │                                                            │
│                ▼                                                            │
│   ┌──────────────────────────┐                                              │
│   │ Frontend: Review Modal   │  (auto-opens when extraction completes)      │
│   │  PDF (left) + Form (right)│                                             │
│   │  User verifies/edits     │                                              │
│   │  → Status: VERIFIED      │                                              │
│   └──────────────────────────┘                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Document Lifecycle States

```
UPLOADED ──► EXTRACTING ──► PENDING_REVIEW ──► VERIFIED
                │                                  │
                ▼                                  ▼
          EXTRACTION_FAILED                   REJECTED
                │                                  │
                └──── (retry) ─────────────────────┘
```

---

## 4. System Architecture

### 4.1 Technology Stack (V3)

| Layer | Technology | Version | Change from V2 |
|-------|------------|---------|-----------------|
| **Backend Framework** | FastAPI | 0.115+ | Upgraded |
| **Language** | Python | 3.12 | Upgraded |
| **Database** | PostgreSQL | 16 | Upgraded |
| **ORM** | SQLAlchemy | 2.0+ | Same |
| **Migrations** | Alembic | 1.13+ | Same |
| **Task Queue** | Celery + Redis | 5.4+ / 7+ | **NEW** — background OCR processing |
| **WebSocket** | FastAPI WebSocket | native | **NEW** — real-time extraction status |
| **Cache** | Redis | 7+ | **NEW** — preview cache, session store |
| **Auth** | FastAPI + JWT | python-jose | **NEW** — user authentication |
| **Frontend** | React + TypeScript | 19 / 5.5+ | Upgraded |
| **Build Tool** | Vite | 6+ | Upgraded |
| **CSS Framework** | TailwindCSS | 4+ | Upgraded |
| **State Management** | TanStack React Query + Zustand | 5+ / 5+ | Zustand added for local state |
| **Real-time** | Socket.IO client | 4+ | **NEW** |
| **OCR Model** | GLM-OCR (0.9B) | via Ollama | Same model, improved pipeline |
| **OCR Runtime** | Ollama (dev+prod) / vLLM (high-throughput) | latest | Simplified |
| **PDF Processing** | PyMuPDF (fitz) | ≥1.24 | Upgraded |
| **Monitoring** | Prometheus + Grafana | latest | **NEW** |
| **Containerization** | Docker Compose | v2 | Same |

### 4.2 System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                FRONTEND                                      │
│  ┌────────────┐  ┌────────────┐  ┌──────────────┐  ┌─────────────────────┐  │
│  │ Dashboard  │  │  PO Detail │  │  Upload Flow │  │  Admin / Settings  │  │
│  └─────┬──────┘  └─────┬──────┘  └──────┬───────┘  └──────────┬─────────┘  │
│        └───────────────┴────────────────┴──────────────────────┘            │
│                                  │                                           │
│                    TanStack Query + Zustand + Socket.IO                      │
│                                  │                                           │
│                            Axios Client (JWT)                                │
└──────────────────────────────────┼───────────────────────────────────────────┘
                                   │ HTTPS (Port 443 → 8000)
┌──────────────────────────────────┼───────────────────────────────────────────┐
│                           NGINX (Reverse Proxy)                              │
│                    SSL Termination + Static File Serving                      │
└──────────────────────────────────┼───────────────────────────────────────────┘
                                   │
┌──────────────────────────────────┼───────────────────────────────────────────┐
│                          BACKEND (FastAPI)                                    │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │                          API Layer (/api/v1)                          │   │
│  │  ┌───────────┐ ┌────────────┐ ┌─────────────┐ ┌──────┐ ┌─────────┐  │   │
│  │  │/customers │ │/purchase-  │ │ /documents  │ │/auth │ │ /admin  │  │   │
│  │  │           │ │ orders     │ │             │ │      │ │         │  │   │
│  │  └─────┬─────┘ └─────┬──────┘ └──────┬──────┘ └──┬───┘ └────┬────┘  │   │
│  └────────┼─────────────┼───────────────┼───────────┼──────────┼────────┘   │
│           │             │               │           │          │            │
│  ┌────────┴─────────────┴───────────────┴───────────┴──────────┴────────┐   │
│  │                         Service Layer                                 │   │
│  │  ┌──────────────┐ ┌────────────────┐ ┌─────────────────────────────┐  │   │
│  │  │ CustomerSvc  │ │PurchaseOrderSvc│ │      DocumentService       │  │   │
│  │  └──────────────┘ └────────────────┘ └──────────────┬──────────────┘  │   │
│  │                                                     │                 │   │
│  │  ┌───────────────┐ ┌──────────────┐ ┌───────────────┴──────────────┐  │   │
│  │  │ StorageService│ │  AuthService │ │     ExtractionService       │  │   │
│  │  └───────┬───────┘ └──────────────┘ └──────────────┬───────────────┘  │   │
│  │          │                                         │                  │   │
│  └──────────┼─────────────────────────────────────────┼──────────────────┘   │
│             │                                         │                      │
│             │              ┌───────────────────────────┴─────────────┐       │
│             │              │         Celery Worker (Background)      │       │
│             │              │  ┌──────────┐ ┌────────────┐ ┌───────┐ │       │
│             │              │  │OCRClient │ │PDFConverter│ │Parser │ │       │
│             │              │  └────┬─────┘ └────────────┘ └───────┘ │       │
│             │              └───────┼────────────────────────────────-┘       │
│             │                      │                                         │
└─────────────┼──────────────────────┼─────────────────────────────────────────┘
              │                      │
    ┌─────────▼──────────┐   ┌───────▼──────────────────────┐
    │   NAS Storage      │   │   GLM-OCR (Ollama)           │
    │   /nas/documents/  │   │   Port 11434                  │
    └────────────────────┘   │   GPU: NVIDIA (8GB+ VRAM)     │
              │              └──────────────────────────────┘
    ┌─────────▼──────────┐          │
    │   PostgreSQL 16    │   ┌──────▼──────────────┐
    │   Port 5432        │   │   Redis 7           │
    └────────────────────┘   │   Port 6379         │
                              │   (Queue + Cache)   │
                              └─────────────────────┘
```

### 4.3 Project Structure (Reworked)

```
docplatform-v3/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app + lifespan events
│   │   ├── config.py                  # Pydantic Settings (env-driven)
│   │   ├── database.py                # SQLAlchemy engine + session
│   │   ├── dependencies.py            # Dependency injection (auth, db session)
│   │   │
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── auth.py            # Login, token refresh
│   │   │   │   ├── customers.py       # Customer CRUD
│   │   │   │   ├── purchase_orders.py # PO management
│   │   │   │   ├── documents.py       # Upload, download, preview
│   │   │   │   ├── extraction.py      # Re-extract, verify, reject
│   │   │   │   ├── search.py          # Global search across entities
│   │   │   │   ├── admin.py           # Stats, health, audit logs
│   │   │   │   └── websocket.py       # Real-time extraction status
│   │   │   └── router.py              # Aggregate all v1 routes
│   │   │
│   │   ├── models/
│   │   │   ├── customer.py            # Customer model
│   │   │   ├── purchase_order.py      # PO model (the anchor)
│   │   │   ├── document.py            # Document model
│   │   │   ├── document_metadata.py   # Extracted data model
│   │   │   ├── user.py                # User/auth model
│   │   │   └── audit_log.py           # Audit trail
│   │   │
│   │   ├── schemas/
│   │   │   ├── customer.py
│   │   │   ├── purchase_order.py
│   │   │   ├── document.py
│   │   │   ├── extraction.py
│   │   │   └── auth.py
│   │   │
│   │   ├── services/
│   │   │   ├── customer_service.py
│   │   │   ├── po_service.py
│   │   │   ├── document_service.py
│   │   │   ├── storage_service.py
│   │   │   ├── auth_service.py
│   │   │   └── extraction/
│   │   │       ├── __init__.py
│   │   │       ├── ocr_client.py      # GLM-OCR API client (Ollama/vLLM)
│   │   │       ├── pdf_converter.py   # PDF → image conversion
│   │   │       ├── response_parser.py # JSON extraction + validation
│   │   │       ├── prompts.py         # Document-type-specific prompts
│   │   │       └── tasks.py           # Celery async tasks
│   │   │
│   │   └── utils/
│   │       ├── security.py            # JWT, password hashing
│   │       └── validators.py          # File validation, checksum
│   │
│   ├── alembic/                       # DB migrations
│   ├── tests/
│   │   ├── conftest.py                # Fixtures, test DB
│   │   ├── test_api/
│   │   ├── test_services/
│   │   └── test_extraction/
│   ├── celery_app.py                  # Celery configuration
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts              # Axios instance + JWT interceptor
│   │   │   ├── customers.ts
│   │   │   ├── purchaseOrders.ts
│   │   │   ├── documents.ts
│   │   │   ├── extraction.ts
│   │   │   └── auth.ts
│   │   ├── components/
│   │   │   ├── layout/                # Shell, Sidebar, Header
│   │   │   ├── customers/             # Customer list, detail
│   │   │   ├── purchase-orders/       # PO list, detail, chain view
│   │   │   ├── documents/             # Upload, preview, review
│   │   │   └── common/                # Shared UI components
│   │   ├── hooks/
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── CustomersPage.tsx
│   │   │   ├── PODetailPage.tsx       # The main work view
│   │   │   ├── SearchPage.tsx
│   │   │   ├── LoginPage.tsx
│   │   │   └── AdminPage.tsx
│   │   ├── stores/                    # Zustand stores
│   │   │   ├── authStore.ts
│   │   │   └── uiStore.ts
│   │   ├── types/
│   │   └── utils/
│   ├── Dockerfile
│   └── package.json
│
├── nginx/
│   ├── nginx.conf
│   └── ssl/                           # Self-signed or org certs
│
├── docker-compose.yml                 # Full stack
├── docker-compose.dev.yml             # Dev overrides
├── .env.example
└── README.md
```

---

## 5. Database Schema (Redesigned)

### 5.1 Entity Relationship Diagram

```
┌─────────────────────────────┐
│           User              │
├─────────────────────────────┤
│ id (UUID, PK)               │
│ username (VARCHAR, UNIQUE)   │
│ email (VARCHAR, UNIQUE)      │
│ hashed_password (VARCHAR)    │
│ full_name (VARCHAR)          │
│ role (ENUM: admin/user/viewer)│
│ is_active (BOOLEAN)          │
│ created_at                   │
│ updated_at                   │
└─────────────────────────────┘

┌─────────────────────────────┐       ┌──────────────────────────────────┐
│         Customer            │       │        PurchaseOrder             │
├─────────────────────────────┤       ├──────────────────────────────────┤
│ id (UUID, PK)               │◀──────│ customer_id (UUID, FK)          │
│ customer_id (VARCHAR,UNIQUE)│  1:N  │ id (UUID, PK)                   │
│ name (VARCHAR)              │       │ po_number (VARCHAR, UNIQUE)     │
│ contact_email (VARCHAR)     │       │ po_date (DATE)                  │
│ contact_phone (VARCHAR)     │       │ total_amount (DECIMAL)          │
│ address (TEXT)              │       │ status (ENUM)                   │
│ gst_number (VARCHAR)        │       │ chain_completeness (FLOAT)      │
│ notes (TEXT)                │       │ notes (TEXT)                    │
│ is_active (BOOLEAN)         │       │ created_by (UUID, FK → User)   │
│ created_at                  │       │ created_at                     │
│ updated_at                  │       │ updated_at                     │
└─────────────────────────────┘       └───────────────┬────────────────┘
                                                      │
                                                      │ 1:N
                                                      ▼
                                      ┌──────────────────────────────────┐
                                      │          Document                │
                                      ├──────────────────────────────────┤
                                      │ id (UUID, PK)                   │
                                      │ po_id (UUID, FK) ───────────────┼──► PurchaseOrder
                                      │ document_type (ENUM)            │
                                      │ filename (VARCHAR)              │
                                      │ original_filename (VARCHAR)     │
                                      │ file_path (VARCHAR)             │
                                      │ file_size (INTEGER)             │
                                      │ mime_type (VARCHAR)             │
                                      │ page_count (INTEGER)            │
                                      │ checksum (VARCHAR, SHA-256)     │
                                      │ status (ENUM)                   │
                                      │ rotation (INTEGER, default 0)   │
                                      │ uploaded_by (UUID, FK → User)  │
                                      │ created_at                      │
                                      │ updated_at                      │
                                      └───────────────┬────────────────┘
                                                      │
                                                      │ 1:1
                                                      ▼
                                      ┌──────────────────────────────────┐
                                      │      DocumentMetadata            │
                                      ├──────────────────────────────────┤
                                      │ id (UUID, PK)                   │
                                      │ document_id (UUID, FK, UNIQUE)  │
                                      │ document_type (ENUM)            │
                                      │ extracted_data (JSONB)          │
                                      │ raw_ocr_text (TEXT)             │
                                      │ primary_ref_no (VARCHAR)        │
                                      │ po_ref_no (VARCHAR) ────────────┼──► Cross-ref to PO
                                      │ doc_date (DATE)                 │
                                      │ total_amount (DECIMAL)          │
                                      │ confidence_score (FLOAT)        │
                                      │ status (ENUM)                   │
                                      │ extraction_attempts (INT)       │
                                      │ last_error (TEXT)               │
                                      │ extracted_at (TIMESTAMP)        │
                                      │ verified_at (TIMESTAMP)         │
                                      │ verified_by (UUID, FK → User)  │
                                      │ model_version (VARCHAR)         │
                                      │ processing_time_ms (INTEGER)    │
                                      └──────────────────────────────────┘

┌──────────────────────────────────┐
│          AuditLog                │
├──────────────────────────────────┤
│ id (UUID, PK)                   │
│ entity_type (VARCHAR)           │
│ entity_id (UUID)                │
│ action (VARCHAR)                │
│ actor_id (UUID, FK → User)     │
│ details (JSONB)                 │
│ ip_address (VARCHAR)            │
│ created_at (TIMESTAMP)          │
└──────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│                     ReferenceIndex                                │
│  (Fast lookup table — every extracted ID becomes searchable)      │
├───────────────────────────────────────────────────────────────────┤
│ id (UUID, PK)                                                    │
│ document_id (UUID, FK → Document)                                │
│ po_id (UUID, FK → PurchaseOrder)   ← denormalized for speed     │
│ ref_type (VARCHAR)                  ← "invoice_number", "dc_number", │
│                                       "po_number", "so_number",  │
│                                       "pod_number", "irn_number" │
│ ref_value (VARCHAR, INDEXED)        ← "INV-2026-1234"           │
│ document_type (ENUM)                ← which doc this came from   │
│ created_at (TIMESTAMP)                                           │
└───────────────────────────────────────────────────────────────────┘

How ReferenceIndex works:
  When OCR extracts a VENDOR_INVOICE and finds:
    invoice_number: "INV-2026-1234"
    po_reference: "PO-2026-0001"
    ack_number: "ACK-5678"
    irn_number: "IRN-98765"

  → 4 rows are inserted into ReferenceIndex:
    | ref_type       | ref_value       | document_type  |
    |----------------|-----------------|----------------|
    | invoice_number | INV-2026-1234   | VENDOR_INVOICE |
    | po_reference   | PO-2026-0001    | VENDOR_INVOICE |
    | ack_number     | ACK-5678        | VENDOR_INVOICE |
    | irn_number     | IRN-98765       | VENDOR_INVOICE |

  Now searching "INV-2026-1234" OR "ACK-5678" OR "IRN-98765"
  all find the same document instantly via B-Tree index.
```

### 5.2 Key Schema Changes from V2

| Change | V2 | V3 | Reason |
|--------|----|----|--------|
| Customer entity | Free-text `customer_name` on Case | Dedicated `Customer` table with FK | Reliable querying, deduplication |
| PO as anchor | PO was just a document type at Case level | `PurchaseOrder` is a first-class entity | Central to all business logic |
| Case removed | Cases grouped POs loosely | Removed entirely — Customer → PO is the hierarchy | Simpler, matches business reality |
| Sales Order removed | SO sat between Case and Documents | Removed — PO directly owns documents | PO already IS the order reference |
| Document links to PO | `document.case_id` + optional `sales_order_id` | `document.po_id` (required, non-null) | Every doc belongs to exactly one PO |
| Chain completeness | Not tracked | `purchase_order.chain_completeness` (computed) | Quick dashboard status |
| Raw OCR text | Not stored | `document_metadata.raw_ocr_text` | Debugging, full-text search |
| PO cross-reference | Not extracted | `document_metadata.po_ref_no` | Links chain docs back to PO |
| User tracking | `uploaded_by` as free text | FK to `User` table | Proper auth + audit |
| Reference search | No cross-document search | `ReferenceIndex` table indexes every extracted ID | Search by any ref number |

### 5.3 Indexes (V3)

| Table | Index | Columns | Type |
|-------|-------|---------|------|
| customers | ix_customer_id | customer_id | B-Tree (UNIQUE) |
| customers | ix_customer_name | name | B-Tree |
| customers | ix_customer_gst | gst_number | B-Tree |
| purchase_orders | ix_po_number | po_number | B-Tree (UNIQUE) |
| purchase_orders | ix_po_customer | customer_id | B-Tree |
| purchase_orders | ix_po_status | status | B-Tree |
| purchase_orders | ix_po_date | po_date | B-Tree |
| documents | ix_doc_po_id | po_id | B-Tree |
| documents | ix_doc_type | document_type | B-Tree |
| documents | ix_doc_checksum | checksum | B-Tree |
| documents | ix_doc_status | status | B-Tree |
| document_metadata | ix_meta_doc_id | document_id | B-Tree (UNIQUE) |
| document_metadata | ix_meta_primary_ref | primary_ref_no | B-Tree |
| document_metadata | ix_meta_po_ref | po_ref_no | B-Tree |
| document_metadata | ix_meta_doc_date | doc_date | B-Tree |
| document_metadata | ix_meta_extracted | extracted_data | GIN (JSONB) |
| document_metadata | ix_meta_status | status | B-Tree |
| audit_logs | ix_audit_entity | entity_type, entity_id | B-Tree |
| audit_logs | ix_audit_actor | actor_id | B-Tree |
| audit_logs | ix_audit_time | created_at | B-Tree |
| **reference_index** | **ix_ref_value** | **ref_value** | **B-Tree (the main search index)** |
| **reference_index** | **ix_ref_type_value** | **ref_type, ref_value** | **Composite B-Tree** |
| **reference_index** | **ix_ref_document** | **document_id** | **B-Tree** |
| **reference_index** | **ix_ref_po** | **po_id** | **B-Tree** |

### 5.4 Enums (V3)

```python
class DocumentType(str, Enum):
    CUSTOMER_PO = "CUSTOMER_PO"
    VENDOR_DC = "VENDOR_DC"
    VENDOR_INVOICE = "VENDOR_INVOICE"
    COMPANY_DC = "COMPANY_DC"
    COMPANY_INVOICE = "COMPANY_INVOICE"
    POD = "POD"

class DocumentStatus(str, Enum):
    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    PENDING_REVIEW = "PENDING_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"

class MetadataStatus(str, Enum):
    PENDING = "PENDING"
    EXTRACTED = "EXTRACTED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"

class POStatus(str, Enum):
    INITIATED = "INITIATED"
    IN_PROGRESS = "IN_PROGRESS"
    NEAR_COMPLETE = "NEAR_COMPLETE"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    USER = "USER"
    VIEWER = "VIEWER"
```

---

## 6. OCR Pipeline V2 (GLM-OCR via Ollama)

### 6.1 What Changed from V1 Pipeline

| Issue in V1 | Fix in V2 |
|-------------|-----------|
| Manual "Extract" button required | Auto-extract on upload via Celery background task |
| `timeout=None` — could hang forever | Configurable timeout (default 120s) with hard kill |
| Max 3 pages — truncates long docs | Configurable limit (default 10 pages), with smart page selection |
| No retry visibility | `extraction_attempts` counter + `last_error` stored |
| No batch processing | Celery allows parallel extraction across documents |
| No raw text preserved | `raw_ocr_text` saved for debugging + full-text search |
| No WebSocket feedback | Real-time status updates to frontend |
| Single-threaded | Celery workers scale horizontally |

### 6.2 GLM-OCR Model Setup via Ollama

```bash
# Pull the GLM-OCR model
ollama pull glm-ocr

# Verify it's available
ollama list
# NAME        ID          SIZE    MODIFIED
# glm-ocr     abc123...   1.8GB   Just now

# Test inference
ollama run glm-ocr "Extract text from this document"
```

**Ollama API endpoint:**
```
POST http://localhost:11434/api/chat
Content-Type: application/json

{
  "model": "glm-ocr",
  "messages": [
    {
      "role": "user",
      "content": "Extract the following fields as JSON...",
      "images": ["<base64_encoded_image>"]
    }
  ],
  "stream": false,
  "options": {
    "temperature": 0.01,
    "num_predict": 4096
  }
}
```

### 6.3 Extraction Pipeline (Reworked)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     OCR EXTRACTION PIPELINE V2                               │
│                                                                              │
│   Document Upload Complete                                                   │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────┐                                        │
│   │ Celery Task: extract_document   │                                        │
│   │                                  │                                       │
│   │  1. Set document.status = EXTRACTING                                     │
│   │  2. Notify frontend via WebSocket                                        │
│   │  3. Read PDF from NAS                                                    │
│   │                                  │                                       │
│   │  4. ┌──── PDF → Image Conversion ────┐                                   │
│   │     │ PyMuPDF @ configurable DPI     │                                   │
│   │     │ Default: 200 DPI              │                                    │
│   │     │ Max pages: 10 (configurable)  │                                    │
│   │     │                                │                                   │
│   │     │ Smart page selection:          │                                   │
│   │     │  - If pages ≤ max: all pages  │                                    │
│   │     │  - If pages > max: first 5    │                                    │
│   │     │    + last 5 (covers header     │                                   │
│   │     │    and totals sections)        │                                   │
│   │     └────────────────────────────────┘                                   │
│   │                                  │                                       │
│   │  5. Select extraction prompt based on document_type                      │
│   │                                  │                                       │
│   │  6. ┌──── OCR Inference ─────────────┐                                   │
│   │     │ FOR each page image:           │                                   │
│   │     │   ├── Encode as Base64         │                                   │
│   │     │   ├── POST to Ollama API       │                                   │
│   │     │   │   ├── Timeout: 120s/page  │                                    │
│   │     │   │   ├── Retry: 3x exp backoff│                                  │
│   │     │   │   └── Circuit breaker      │                                   │
│   │     │   └── Collect raw response     │                                   │
│   │     └────────────────────────────────┘                                   │
│   │                                  │                                       │
│   │  7. ┌──── Response Parsing ──────────┐                                   │
│   │     │ Merge multi-page results       │                                   │
│   │     │ Extract JSON from text wrapper │                                   │
│   │     │ Handle: trailing commas,       │                                   │
│   │     │   single quotes, markdown      │                                   │
│   │     │   code blocks                  │                                   │
│   │     │ Parse dates (12+ formats)     │                                    │
│   │     │ Validate against type schema  │                                    │
│   │     └────────────────────────────────┘                                   │
│   │                                  │                                       │
│   │  8. Calculate confidence:                                                │
│   │     confidence = (filled_fields / total_fields) × 100                    │
│   │                                  │                                       │
│   │  9. Save to DocumentMetadata:                                            │
│   │     ├── extracted_data (JSONB)                                           │
│   │     ├── raw_ocr_text (TEXT)                                              │
│   │     ├── primary_ref_no (indexed)                                         │
│   │     ├── po_ref_no (indexed)                                              │
│   │     ├── doc_date (indexed)                                               │
│   │     ├── confidence_score                                                 │
│   │     ├── processing_time_ms                                               │
│   │     └── status = EXTRACTED                                               │
│   │                                  │                                       │
│   │ 10. Set document.status = PENDING_REVIEW                                 │
│   │ 11. Notify frontend via WebSocket                                        │
│   │ 12. Audit log entry                                                      │
│   │                                  │                                       │
│   │ ON ERROR:                                                                │
│   │   ├── Increment extraction_attempts                                      │
│   │   ├── Store error in last_error                                          │
│   │   ├── Set document.status = EXTRACTION_FAILED                            │
│   │   ├── Notify frontend via WebSocket                                      │
│   │   └── If attempts < max_retries: auto-retry with backoff                │
│   └─────────────────────────────────┘                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.4 Extraction Prompts (V2 — Improved)

Each prompt now explicitly asks for the PO reference number and instructs the model to return clean JSON:

```python
# extraction/prompts.py

SYSTEM_PROMPT = """You are a document OCR extraction system. Extract the requested 
fields from the document image. Return ONLY valid JSON with no additional text, 
no markdown, no explanation. If a field cannot be found, use null."""

EXTRACTION_PROMPTS = {
    "CUSTOMER_PO": {
        "instruction": "Extract purchase order details from this document.",
        "schema": {
            "po_number": "string - The purchase order number",
            "po_date": "string - Date in YYYY-MM-DD format",
            "customer_name": "string - Customer/buyer name",
            "billing_address": "string - Billing address",
            "shipping_address": "string - Shipping/delivery address",
            "total_amount": "number - Total order value",
            "currency": "string - Currency code (INR, USD, etc.)",
            "payment_terms": "string - Payment terms",
            "line_items_count": "number - Number of line items",
            "gst_number": "string - GST/Tax registration number"
        }
    },
    "VENDOR_DC": {
        "instruction": "Extract delivery challan details from this vendor document.",
        "schema": {
            "dc_number": "string - Delivery challan number",
            "dc_date": "string - Date in YYYY-MM-DD format",
            "po_reference": "string - Related purchase order number",
            "vendor_name": "string - Vendor/supplier name",
            "items_description": "string - Brief description of items shipped",
            "quantity": "string - Total quantity shipped",
            "vehicle_number": "string - Transport vehicle number if visible",
            "receiver_name": "string - Name of goods receiver"
        }
    },
    "VENDOR_INVOICE": {
        "instruction": "Extract invoice details from this vendor/supplier invoice.",
        "schema": {
            "invoice_number": "string - Invoice number",
            "invoice_date": "string - Date in YYYY-MM-DD format",
            "po_reference": "string - Related purchase order number",
            "vendor_name": "string - Vendor/supplier name",
            "subtotal": "number - Subtotal before tax",
            "tax_amount": "number - Total tax amount",
            "total_amount": "number - Grand total",
            "payment_terms": "string - Payment terms/due date",
            "gst_number": "string - Vendor GST number",
            "irn_number": "string - IRN/e-invoice number if visible",
            "ack_number": "string - Acknowledgement number",
            "ack_date": "string - Acknowledgement date in YYYY-MM-DD"
        }
    },
    "COMPANY_DC": {
        "instruction": "Extract delivery challan details from this company outward document.",
        "schema": {
            "dc_number": "string - Delivery challan number",
            "dc_date": "string - Date in YYYY-MM-DD format",
            "po_reference": "string - Customer PO reference",
            "customer_name": "string - Customer name",
            "items_description": "string - Brief description of items dispatched",
            "quantity": "string - Total quantity dispatched",
            "dispatch_from": "string - Dispatch location/warehouse"
        }
    },
    "COMPANY_INVOICE": {
        "instruction": "Extract invoice details from this company-issued invoice.",
        "schema": {
            "invoice_number": "string - Invoice number",
            "invoice_date": "string - Date in YYYY-MM-DD format",
            "po_reference": "string - Customer PO reference",
            "customer_name": "string - Customer/buyer name",
            "subtotal": "number - Subtotal before tax",
            "tax_amount": "number - Total tax (GST/IGST)",
            "total_amount": "number - Grand total",
            "so_number": "string - Sales order number if visible",
            "account_manager": "string - Account manager name",
            "irn_number": "string - IRN/e-invoice number"
        }
    },
    "POD": {
        "instruction": "Extract proof of delivery details from this acknowledgement document.",
        "schema": {
            "pod_number": "string - POD/acknowledgement number",
            "delivery_date": "string - Date in YYYY-MM-DD format",
            "received_by": "string - Name of person who received goods",
            "dc_reference": "string - Related delivery challan number",
            "po_reference": "string - Related purchase order number",
            "delivery_location": "string - Delivery address/location",
            "condition_notes": "string - Any notes on goods condition",
            "signature_present": "boolean - Whether signature is visible"
        }
    }
}
```

### 6.5 OCR Client (V2 — With Timeout + Circuit Breaker)

```python
# extraction/ocr_client.py

import httpx
import asyncio
import base64
import time
from app.config import settings

class OCRClient:
    def __init__(self):
        self.base_url = settings.ocr_base_url
        self.model = settings.ocr_model_name
        self.timeout = settings.ocr_timeout  # default: 120s
        self.max_retries = settings.ocr_max_retries  # default: 3
        self._consecutive_failures = 0
        self._circuit_open_until = 0

    async def extract_from_image(
        self, image_data: bytes, prompt: str
    ) -> dict:
        """Extract data from a single page image using GLM-OCR."""
        
        # Circuit breaker check
        if self._is_circuit_open():
            raise OCRServiceUnavailable("OCR circuit breaker is open")
        
        encoded_image = base64.b64encode(image_data).decode("utf-8")
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [encoded_image]
                }
            ],
            "stream": False,
            "options": {
                "temperature": 0.01,
                "num_predict": 4096
            }
        }
        
        for attempt in range(self.max_retries):
            try:
                start = time.monotonic()
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout)
                ) as client:
                    response = await client.post(
                        f"{self.base_url}/api/chat",
                        json=payload
                    )
                    response.raise_for_status()
                
                elapsed_ms = int((time.monotonic() - start) * 1000)
                self._consecutive_failures = 0  # Reset on success
                
                result = response.json()
                return {
                    "text": result["message"]["content"],
                    "processing_time_ms": elapsed_ms
                }
                
            except httpx.TimeoutException:
                if attempt == self.max_retries - 1:
                    self._record_failure()
                    raise OCRTimeoutError(
                        f"OCR timed out after {self.timeout}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                await asyncio.sleep(2 ** attempt)
                
            except httpx.HTTPStatusError as e:
                if attempt == self.max_retries - 1:
                    self._record_failure()
                    raise OCRServiceError(f"OCR API error: {e.response.status_code}")
                await asyncio.sleep(2 ** attempt)

    def _is_circuit_open(self) -> bool:
        if self._consecutive_failures >= 5:
            if time.monotonic() < self._circuit_open_until:
                return True
            # Half-open: allow one attempt
            self._consecutive_failures = 4
        return False

    def _record_failure(self):
        self._consecutive_failures += 1
        if self._consecutive_failures >= 5:
            self._circuit_open_until = time.monotonic() + 60  # 60s cooldown
```

### 6.6 Celery Task for Background Extraction

```python
# extraction/tasks.py

from celery import shared_task
from app.database import get_session
from app.services.extraction.ocr_client import OCRClient
from app.services.extraction.pdf_converter import PDFConverter
from app.services.extraction.response_parser import ResponseParser
from app.services.extraction.prompts import EXTRACTION_PROMPTS, SYSTEM_PROMPT

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    soft_time_limit=600,   # 10 min soft limit
    time_limit=660,        # 11 min hard kill
)
def extract_document(self, document_id: str):
    """Background task: Run OCR extraction on uploaded document."""
    
    with get_session() as db:
        document = db.query(Document).get(document_id)
        if not document:
            return {"error": "Document not found"}
        
        # Update status
        document.status = DocumentStatus.EXTRACTING
        db.commit()
        
        # Notify frontend
        notify_ws(document_id, "extracting")
        
        try:
            # 1. Convert PDF to images
            converter = PDFConverter(
                dpi=settings.ocr_pdf_dpi,
                max_pages=settings.ocr_max_pages
            )
            images = converter.convert(document.file_path)
            
            # 2. Get prompt for document type
            prompt_config = EXTRACTION_PROMPTS[document.document_type.value]
            prompt = build_prompt(SYSTEM_PROMPT, prompt_config)
            
            # 3. Run OCR on each page
            ocr = OCRClient()
            raw_texts = []
            total_time_ms = 0
            
            for page_image in images:
                result = asyncio.run(
                    ocr.extract_from_image(page_image, prompt)
                )
                raw_texts.append(result["text"])
                total_time_ms += result["processing_time_ms"]
            
            # 4. Parse and merge results
            parser = ResponseParser()
            extracted_data = parser.parse_and_merge(
                raw_texts, document.document_type
            )
            
            # 5. Calculate confidence
            schema_fields = list(prompt_config["schema"].keys())
            confidence = parser.calculate_confidence(
                extracted_data, schema_fields
            )
            
            # 6. Save metadata
            metadata = DocumentMetadata(
                document_id=document.id,
                document_type=document.document_type,
                extracted_data=extracted_data,
                raw_ocr_text="\n---PAGE---\n".join(raw_texts),
                primary_ref_no=extracted_data.get(
                    parser.get_primary_field(document.document_type)
                ),
                po_ref_no=extracted_data.get("po_reference"),
                doc_date=parser.parse_date(
                    extracted_data.get(
                        parser.get_date_field(document.document_type)
                    )
                ),
                confidence_score=confidence,
                status=MetadataStatus.EXTRACTED,
                extraction_attempts=(
                    document.metadata.extraction_attempts + 1
                    if document.metadata else 1
                ),
                extracted_at=datetime.utcnow(),
                model_version=settings.ocr_model_name,
                processing_time_ms=total_time_ms,
            )
            
            db.merge(metadata)
            document.status = DocumentStatus.PENDING_REVIEW
            db.commit()
            
            # 7. Update PO chain completeness
            update_po_completeness(db, document.po_id)
            
            # 8. Notify frontend
            notify_ws(document_id, "pending_review", extracted_data)
            
            return {"status": "success", "confidence": confidence}
            
        except Exception as e:
            document.status = DocumentStatus.EXTRACTION_FAILED
            if document.metadata:
                document.metadata.last_error = str(e)
                document.metadata.extraction_attempts += 1
            db.commit()
            notify_ws(document_id, "extraction_failed", str(e))
            
            # Auto-retry via Celery
            raise self.retry(exc=e)
```

---

## 7. API Design

### 7.1 API Versioning

All endpoints under `/api/v1/` — allows future breaking changes under `/api/v2/`.

### 7.2 Endpoints

#### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/login` | Login → returns JWT access + refresh tokens |
| `POST` | `/api/v1/auth/refresh` | Refresh access token |
| `POST` | `/api/v1/auth/logout` | Invalidate refresh token |
| `GET` | `/api/v1/auth/me` | Get current user profile |

#### Customers

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/customers` | Create customer |
| `GET` | `/api/v1/customers` | List customers (paginated, searchable) |
| `GET` | `/api/v1/customers/{id}` | Get customer with PO summary |
| `PATCH` | `/api/v1/customers/{id}` | Update customer |
| `GET` | `/api/v1/customers/{id}/purchase-orders` | List POs for customer |

#### Purchase Orders

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/purchase-orders` | Create PO (requires customer_id) |
| `GET` | `/api/v1/purchase-orders` | List POs (paginated, filterable) |
| `GET` | `/api/v1/purchase-orders/{id}` | Get PO with full document chain |
| `PATCH` | `/api/v1/purchase-orders/{id}` | Update PO |
| `GET` | `/api/v1/purchase-orders/{id}/chain-status` | Get document chain completeness |

#### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/purchase-orders/{po_id}/documents` | Upload document to PO (triggers auto-extract) |
| `GET` | `/api/v1/purchase-orders/{po_id}/documents` | List documents for PO |
| `GET` | `/api/v1/documents/{id}` | Get document detail |
| `DELETE` | `/api/v1/documents/{id}` | Soft-delete document |
| `GET` | `/api/v1/documents/{id}/preview` | Stream PDF for preview |
| `GET` | `/api/v1/documents/{id}/download` | Download original file |
| `POST` | `/api/v1/documents/{id}/rotate` | Rotate PDF |
| `POST` | `/api/v1/documents/{id}/re-extract` | Manually trigger re-extraction |

#### Extraction & Metadata

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/documents/{id}/metadata` | Get extraction results |
| `PUT` | `/api/v1/documents/{id}/metadata/verify` | Verify extraction (with optional edits) |
| `PUT` | `/api/v1/documents/{id}/metadata/reject` | Reject extraction |

#### Search (By Any Reference ID)

Every document has its own unique reference number extracted by OCR. While PO is the **hierarchy anchor**, users can search by **any** reference number to find documents:

| Method | Endpoint | Description | Example Query |
|--------|----------|-------------|---------------|
| `GET` | `/api/v1/search` | **Global search** — searches across ALL reference numbers, customer names, PO numbers | `?q=INV-2026-001` |
| `GET` | `/api/v1/search/by-ref/{ref_number}` | Find any document by its primary reference number | `/by-ref/DC-4567` |
| `GET` | `/api/v1/search/po/{po_number}` | Find PO + entire document chain | `/po/PO-2026-001` |
| `GET` | `/api/v1/search/invoice/{invoice_number}` | Find by vendor or company invoice number | `/invoice/INV-2026-001` |
| `GET` | `/api/v1/search/dc/{dc_number}` | Find by vendor or company DC number | `/dc/DC-4567` |
| `GET` | `/api/v1/search/pod/{pod_number}` | Find by POD/acknowledgement number | `/pod/POD-890` |
| `GET` | `/api/v1/search/so/{so_number}` | Find by Sales Order number (extracted from docs) | `/so/SO-12345` |
| `GET` | `/api/v1/search/advanced` | Multi-field search with filters | `?invoice_no=X&date_from=Y&customer=Z` |

**How search works internally:**

```
User types "INV-2026-001" in search bar
       │
       ▼
GET /api/v1/search?q=INV-2026-001
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Search Service queries these tables in parallel:                │
│                                                                   │
│  1. purchase_orders.po_number       ILIKE '%INV-2026-001%'       │
│  2. document_metadata.primary_ref_no ILIKE '%INV-2026-001%'      │
│  3. document_metadata.po_ref_no      ILIKE '%INV-2026-001%'      │
│  4. document_metadata.extracted_data  @> (JSONB GIN search)      │
│  5. customers.name                   ILIKE '%INV-2026-001%'      │
│                                                                   │
│  Results merged, deduplicated, ranked by relevance               │
└──────────────────────────────────────────────────────────────────┘
       │
       ▼
Returns: [
  {
    "type": "document",
    "document_type": "VENDOR_INVOICE",
    "ref_number": "INV-2026-001",
    "po_number": "PO-2026-0042",        ← parent PO
    "customer": "Acme Corp",
    "extracted_date": "2026-01-15",
    "confidence": 92.5,
    "status": "VERIFIED"
  }
]
```

**Searchable reference IDs per document type:**

| Document Type | Primary Ref ID | Other Searchable IDs |
|---------------|----------------|----------------------|
| CUSTOMER_PO | `po_number` | customer_name, gst_number |
| VENDOR_DC | `dc_number` | po_reference, vendor_name |
| VENDOR_INVOICE | `invoice_number` | po_reference, ack_number, irn_number, vendor_name |
| COMPANY_DC | `dc_number` | po_reference, customer_name |
| COMPANY_INVOICE | `invoice_number` | po_reference, so_number, irn_number, account_manager |
| POD | `pod_number` | dc_reference, po_reference, received_by |

#### Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/admin/health` | Health check (DB, Redis, Ollama, NAS) |
| `GET` | `/api/v1/admin/stats` | Dashboard statistics |
| `GET` | `/api/v1/admin/audit-logs` | Query audit logs |
| `GET` | `/api/v1/admin/extraction-queue` | View Celery queue status |
| `POST` | `/api/v1/admin/users` | Create user (admin only) |
| `GET` | `/api/v1/admin/users` | List users |

#### WebSocket

| Endpoint | Description |
|----------|-------------|
| `WS /api/v1/ws/{user_id}` | Real-time extraction status updates |

### 7.3 Response Envelope

All API responses follow a consistent structure:

```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "pages": 8
  }
}
```

Error responses:

```json
{
  "success": false,
  "error": {
    "code": "DUPLICATE_DOCUMENT",
    "message": "A VENDOR_INVOICE with the same checksum already exists for this PO",
    "details": { "existing_document_id": "uuid" }
  }
}
```

---

## 8. Frontend Architecture

### 8.1 Page Structure

```
App (AuthProvider + QueryProvider + SocketProvider)
│
├── LoginPage
│
├── AppShell (authenticated layout: sidebar + header + main)
│   │
│   ├── DashboardPage
│   │   ├── Stats cards (total POs, pending reviews, extraction success rate)
│   │   ├── Recent activity feed
│   │   └── POs needing attention (incomplete chains)
│   │
│   ├── CustomersPage
│   │   ├── Customer list (searchable, paginated)
│   │   └── Customer detail → links to their POs
│   │
│   ├── POListPage
│   │   ├── PO table with chain completeness indicators
│   │   ├── Filters: customer, status, date range
│   │   └── Quick search by PO number
│   │
│   ├── PODetailPage  ← THE MAIN WORK VIEW
│   │   ├── Header: PO info (number, date, customer, total)
│   │   ├── Chain Status Bar (visual: 6 circles showing which docs are present)
│   │   ├── Document Grid:
│   │   │   ├── CUSTOMER_PO card (the root document)
│   │   │   ├── VENDOR_DC card
│   │   │   ├── VENDOR_INVOICE card
│   │   │   ├── COMPANY_DC card
│   │   │   ├── COMPANY_INVOICE card
│   │   │   └── POD card
│   │   │   (each card shows: status, extracted ref, confidence, actions)
│   │   │
│   │   ├── Upload Zone (drag-drop, auto-selects doc type slot)
│   │   │
│   │   └── Side Panel:
│   │       ├── PDF Preview (click any doc card to preview)
│   │       └── Review Modal (split: PDF left, extracted fields right)
│   │
│   ├── SearchPage
│   │   └── Global search with result type tabs
│   │
│   └── AdminPage (admin role only)
│       ├── User management
│       ├── System stats
│       ├── Extraction queue monitor
│       └── Audit log viewer
```

### 8.2 Chain Status Bar Component

The signature UI element — a visual representation of PO document completeness:

```
 PO-2026-0001  |  Acme Corp  |  Chain: 4/6 (67%)

 ● ──── ● ──── ● ──── ● ──── ○ ──── ○
 PO    V.DC  V.Inv  C.DC  C.Inv   POD
 ✓      ✓      ✓      ✓    missing  missing
```

Color coding:
- 🟢 Green filled circle: Document uploaded + verified
- 🟡 Yellow filled circle: Document uploaded, pending review
- 🔴 Red filled circle: Extraction failed
- ⚪ Grey empty circle: Not yet uploaded

---

## 9. File Storage (Reworked)

### 9.1 Directory Structure

PO-centric, no more Case/SO nesting. The NAS follows a clean hierarchy:

```
/nas/documents/                          ← NAS root mount
│
├── SKY-AB1234/                                ← Customer ID from CRM (e.g., SKY-AB1234)
│   │
│   ├── PO-2026-0001/                    ← Purchase Order number (the anchor folder)
│   │   ├── CUSTOMER_PO/                 ← One folder per document type
│   │   │   └── a1b2c3d4_Acme_PO_001.pdf
│   │   ├── VENDOR_DC/
│   │   │   └── e5f6g7h8_DC_Shipment_Jan.pdf
│   │   ├── VENDOR_INVOICE/
│   │   │   └── i9j0k1l2_Vendor_Inv_1234.pdf
│   │   ├── COMPANY_DC/
│   │   │   └── m3n4o5p6_Our_DC_5678.pdf
│   │   ├── COMPANY_INVOICE/
│   │   │   └── q7r8s9t0_Invoice_9012.pdf
│   │   └── POD/
│   │       └── u1v2w3x4_POD_Signed.pdf
│   │
│   ├── PO-2026-0002/                    ← Another PO for same customer
│   │   ├── CUSTOMER_PO/
│   │   │   └── ...
│   │   └── ...  (chain documents as they arrive)
│   │
│   └── PO-2026-0015/
│       └── ...
│
├── SKY-CD5678/                         ← Tata Motors (SKY-CD5678)
│   ├── PO-2026-0050/
│   │   └── ...
│   └── ...
│
└── SKY-EF9012/                         ← Reliance (SKY-EF9012)
    └── ...
```

### 9.2 Step-by-Step: How Files Get Saved (Real Example)

Let's walk through the complete lifecycle for customer **"Acme Corp"** (customer_id: `SKY-AB1234`) with PO number **`PO-2026-0001`**.

---

**STEP 1 — User uploads Customer PO (the first document, creates the PO folder)**

```
User action:  Select customer "Acme Corp" → Create new PO → Upload PO PDF
File uploaded: "Acme_Purchase_Order_Jan.pdf"

Backend processing:
  1. Validate PDF (type, size ≤ 25MB)
  2. Calculate SHA-256 checksum → "sha256:abc123..."
  3. Check duplicates (no match found)
  4. Generate UUID filename → "a1b2c3d4_Acme_Purchase_Order_Jan.pdf"
  5. Generate storage path:
     /nas/documents/SKY-AB1234/PO-2026-0001/CUSTOMER_PO/a1b2c3d4_Acme_Purchase_Order_Jan.pdf
  6. Create directories if not exist:
     mkdir -p /nas/documents/SKY-AB1234/PO-2026-0001/CUSTOMER_PO/
  7. Write file to NAS
  8. Save Document record to DB (status: UPLOADED)
  9. Queue Celery OCR task

NAS state after Step 1:
/nas/documents/
└── SKY-AB1234/
    └── PO-2026-0001/
        └── CUSTOMER_PO/
            └── a1b2c3d4_Acme_Purchase_Order_Jan.pdf       ✅ saved

Chain: [● ○ ○ ○ ○ ○]  (1/6 = 17%)
        PO
```

**Background OCR runs automatically:**
```
Celery worker picks up task:
  1. Read PDF from NAS path
  2. Convert PDF → images (PyMuPDF @ 200 DPI)
  3. Send each page image to GLM-OCR (Ollama)
  4. GLM-OCR returns:
     {
       "po_number": "PO-2026-0001",
       "po_date": "2026-01-05",
       "customer_name": "Acme Corp",
       "total_amount": 450000,
       "currency": "INR",
       "payment_terms": "Net 30"
     }
  5. Save to DocumentMetadata (status: PENDING_REVIEW)
  6. Notify frontend via WebSocket → Review modal opens
  7. User verifies/edits → status: VERIFIED
```

---

**STEP 2 — Vendor ships goods, user uploads Vendor DC**

```
User action:  Select PO "PO-2026-0001" → Doc type: Vendor DC → Upload PDF
File uploaded: "DC_Shipment_Jan15.pdf"

Storage path generated:
  /nas/documents/SKY-AB1234/PO-2026-0001/VENDOR_DC/e5f6g7h8_DC_Shipment_Jan15.pdf

NAS state after Step 2:
/nas/documents/
└── SKY-AB1234/
    └── PO-2026-0001/
        ├── CUSTOMER_PO/
        │   └── a1b2c3d4_Acme_Purchase_Order_Jan.pdf       ✅ verified
        └── VENDOR_DC/
            └── e5f6g7h8_DC_Shipment_Jan15.pdf              ✅ saved → extracting...

Chain: [● ● ○ ○ ○ ○]  (2/6 = 33%)
        PO V.DC

OCR extracts:
  {
    "dc_number": "DC-7890",
    "dc_date": "2026-01-15",
    "po_reference": "PO-2026-0001",     ← links back to PO!
    "vendor_name": "Supplier Pvt Ltd",
    "items_description": "Server Hardware x 10"
  }
```

---

**STEP 3 — Vendor sends invoice, user uploads Vendor Invoice**

```
Storage path:
  /nas/documents/SKY-AB1234/PO-2026-0001/VENDOR_INVOICE/i9j0k1l2_Vendor_Inv_1234.pdf

NAS state after Step 3:
/nas/documents/
└── SKY-AB1234/
    └── PO-2026-0001/
        ├── CUSTOMER_PO/
        │   └── a1b2c3d4_Acme_Purchase_Order_Jan.pdf       ✅ verified
        ├── VENDOR_DC/
        │   └── e5f6g7h8_DC_Shipment_Jan15.pdf              ✅ verified
        └── VENDOR_INVOICE/
            └── i9j0k1l2_Vendor_Inv_1234.pdf                ✅ saved → extracting...

Chain: [● ● ● ○ ○ ○]  (3/6 = 50%)
        PO V.DC V.Inv

OCR extracts:
  {
    "invoice_number": "INV-2026-1234",     ← searchable by this!
    "invoice_date": "2026-01-18",
    "po_reference": "PO-2026-0001",
    "vendor_name": "Supplier Pvt Ltd",
    "total_amount": 425000,
    "tax_amount": 76500,
    "gst_number": "29AABCS1234A1Z5",
    "irn_number": "IRN-98765"             ← also searchable!
  }
```

---

**STEP 4 — Company dispatches to customer, user uploads Company DC**

```
Storage path:
  /nas/documents/SKY-AB1234/PO-2026-0001/COMPANY_DC/m3n4o5p6_Our_DC_5678.pdf

Chain: [● ● ● ● ○ ○]  (4/6 = 67%)
        PO V.DC V.Inv C.DC

OCR extracts:
  {
    "dc_number": "CDC-5678",              ← searchable!
    "dc_date": "2026-01-22",
    "po_reference": "PO-2026-0001"
  }
```

---

**STEP 5 — Company sends invoice to customer, user uploads Company Invoice**

```
Storage path:
  /nas/documents/SKY-AB1234/PO-2026-0001/COMPANY_INVOICE/q7r8s9t0_Invoice_9012.pdf

Chain: [● ● ● ● ● ○]  (5/6 = 83%)
        PO V.DC V.Inv C.DC C.Inv

OCR extracts:
  {
    "invoice_number": "CINV-9012",        ← searchable!
    "invoice_date": "2026-01-25",
    "po_reference": "PO-2026-0001",
    "so_number": "SO-12345",              ← also searchable!
    "total_amount": 531000
  }
```

---

**STEP 6 — Customer confirms delivery, user uploads POD**

```
Storage path:
  /nas/documents/SKY-AB1234/PO-2026-0001/POD/u1v2w3x4_POD_Signed.pdf

Chain: [● ● ● ● ● ●]  (6/6 = 100%) ✅ COMPLETE!
        PO V.DC V.Inv C.DC C.Inv POD

OCR extracts:
  {
    "pod_number": "POD-3456",             ← searchable!
    "delivery_date": "2026-01-28",
    "received_by": "Rajesh Kumar",
    "dc_reference": "CDC-5678",           ← cross-references Company DC!
    "po_reference": "PO-2026-0001"
  }
```

---

**FINAL NAS STATE — Complete PO chain for Acme PO-2026-0001:**

```
/nas/documents/
└── SKY-AB1234/
    └── PO-2026-0001/
        ├── CUSTOMER_PO/
        │   └── a1b2c3d4_Acme_Purchase_Order_Jan.pdf      ✅ verified
        ├── VENDOR_DC/
        │   └── e5f6g7h8_DC_Shipment_Jan15.pdf             ✅ verified
        ├── VENDOR_INVOICE/
        │   └── i9j0k1l2_Vendor_Inv_1234.pdf               ✅ verified
        ├── COMPANY_DC/
        │   └── m3n4o5p6_Our_DC_5678.pdf                   ✅ verified
        ├── COMPANY_INVOICE/
        │   └── q7r8s9t0_Invoice_9012.pdf                   ✅ verified
        └── POD/
            └── u1v2w3x4_POD_Signed.pdf                     ✅ verified
```

### 9.3 Search → NAS Lookup Flow

When a user searches by **any** reference number, the system finds the file path via the database — it never scans the NAS filesystem:

```
User searches: "INV-2026-1234"
       │
       ▼
DB query: SELECT d.file_path FROM documents d
          JOIN document_metadata m ON m.document_id = d.id
          WHERE m.primary_ref_no = 'INV-2026-1234'
             OR m.extracted_data @> '{"invoice_number": "INV-2026-1234"}'
       │
       ▼
Result: file_path = "documents/SKY-AB1234/PO-2026-0001/VENDOR_INVOICE/i9j0k1l2_Vendor_Inv_1234.pdf"
       │
       ▼
NAS read: /nas/ + file_path → stream PDF to frontend for preview

Also returns: parent PO "PO-2026-0001", customer "Acme Corp", chain status
```

### 9.4 Path Generation Logic

```python
# storage_service.py

import uuid
from app.models.document import DocumentType

class StorageService:
    def __init__(self, nas_base_path: str):
        self.base_path = nas_base_path  # e.g., "/nas/documents"

    def generate_storage_path(
        self,
        customer_id: str,
        po_number: str,
        document_type: DocumentType,
        original_filename: str,
    ) -> tuple[str, str]:
        """
        Generate NAS storage path for a document.
        
        Returns:
            (relative_path, uuid_filename)
            
        Example:
            ("documents/SKY-AB1234/PO-2026-0001/VENDOR_INVOICE/a1b2c3d4_Invoice.pdf",
             "a1b2c3d4_Invoice.pdf")
        """
        # Generate collision-proof filename
        file_uuid = uuid.uuid4().hex[:8]
        safe_name = self._sanitize_filename(original_filename)
        uuid_filename = f"{file_uuid}_{safe_name}"
        
        # Build path: customer_id/po_number/doc_type/filename
        relative_path = (
            f"documents/{customer_id}/{po_number}/"
            f"{document_type.value}/{uuid_filename}"
        )
        
        return relative_path, uuid_filename

    def get_full_path(self, relative_path: str) -> str:
        """Convert relative path to absolute NAS path."""
        return f"{self.base_path}/{relative_path}"
    
    def ensure_directory(self, relative_path: str) -> None:
        """Create directory tree if it doesn't exist."""
        full_path = self.get_full_path(relative_path)
        directory = os.path.dirname(full_path)
        os.makedirs(directory, exist_ok=True)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Remove unsafe characters from filename."""
        # Keep alphanumeric, dots, hyphens, underscores
        safe = re.sub(r'[^\w.\-]', '_', name)
        return safe[:100]  # Truncate very long names
```

### 9.5 File Naming Convention

```
Format:  {8-char-uuid}_{sanitized_original_name}.pdf

Examples:
  a1b2c3d4_Acme_Purchase_Order_Jan.pdf
  e5f6g7h8_DC_Shipment_Jan15.pdf
  i9j0k1l2_Vendor_Inv_1234.pdf

Why UUID prefix?
  - Prevents filename collisions if same-named files are uploaded
  - The original name is preserved for human readability
  - Short 8-char UUID keeps paths manageable
```

---

## 10. Authentication & Security

### 10.1 Auth Strategy

JWT-based authentication with refresh tokens:

```
Login Flow:
  POST /auth/login { username, password }
    → { access_token (15min), refresh_token (7d) }

Request Auth:
  Authorization: Bearer <access_token>

Token Refresh:
  POST /auth/refresh { refresh_token }
    → { access_token (15min) }
```

### 10.2 Role-Based Access

| Role | Permissions |
|------|-------------|
| `ADMIN` | Full access + user management + system config |
| `USER` | Create/upload/extract/verify documents and POs |
| `VIEWER` | Read-only access to all data |

### 10.3 Security Measures

| Measure | Implementation |
|---------|----------------|
| Password hashing | bcrypt via passlib |
| JWT signing | HS256 with rotatable secret |
| CORS | Configurable via environment |
| Rate limiting | slowapi (100 req/min per user) |
| File validation | MIME type check + size limit (25MB) |
| SQL injection | SQLAlchemy parameterized queries |
| Input validation | Pydantic schemas on all endpoints |
| Audit trail | Every mutation logged with actor |

---

## 11. Infrastructure & Deployment

### 11.1 Docker Compose (Production)

```yaml
# docker-compose.yml
version: "3.9"

services:
  # ─── Database ────────────────────────────
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${DB_NAME}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ─── Cache + Message Broker ──────────────
  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  # ─── OCR Model Server ───────────────────
  ollama:
    image: ollama/ollama:latest
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - ollama_models:/root/.ollama
    ports:
      - "11434:11434"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ─── Backend API ─────────────────────────
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@postgres:5432/${DB_NAME}
      REDIS_URL: redis://redis:6379/0
      NAS_BASE_PATH: /nas/documents
      OCR_BACKEND: ollama
      OCR_BASE_URL: http://ollama:11434
      OCR_MODEL_NAME: glm-ocr
      OCR_TIMEOUT: 120
      OCR_MAX_PAGES: 10
      OCR_PDF_DPI: 200
      JWT_SECRET: ${JWT_SECRET}
      JWT_ALGORITHM: HS256
      JWT_ACCESS_TOKEN_EXPIRE: 900
      JWT_REFRESH_TOKEN_EXPIRE: 604800
    volumes:
      - nas_storage:/nas/documents
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      ollama:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/admin/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ─── Celery Worker ──────────────────────
  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A celery_app worker --loglevel=info --concurrency=4
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@postgres:5432/${DB_NAME}
      REDIS_URL: redis://redis:6379/0
      NAS_BASE_PATH: /nas/documents
      OCR_BACKEND: ollama
      OCR_BASE_URL: http://ollama:11434
      OCR_MODEL_NAME: glm-ocr
      OCR_TIMEOUT: 120
    volumes:
      - nas_storage:/nas/documents
    depends_on:
      - backend
      - redis
      - ollama

  # ─── Celery Beat (scheduled tasks) ──────
  celery-beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A celery_app beat --loglevel=info
    environment:
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - redis

  # ─── Frontend ───────────────────────────
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        VITE_API_URL: ""
    depends_on:
      - backend

  # ─── Reverse Proxy ─────────────────────
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - backend
      - frontend

  # ─── Monitoring ─────────────────────────
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
    ports:
      - "3000:3000"
    depends_on:
      - prometheus

volumes:
  postgres_data:
  redis_data:
  ollama_models:
  nas_storage:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/nas/documents  # Mount your actual NAS here
  prometheus_data:
  grafana_data:
```

### 11.2 Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 8 cores | 16 cores |
| RAM | 16 GB | 32 GB |
| GPU | NVIDIA with 8GB VRAM (e.g., RTX 3060) | NVIDIA with 12GB+ VRAM (e.g., RTX 4070) |
| Storage (OS) | 100 GB SSD | 250 GB NVMe |
| Storage (NAS) | 500 GB | 2 TB+ (depends on document volume) |
| Network | 1 Gbps | 1 Gbps |

### 11.3 GLM-OCR Model Pull (First-Time Setup)

```bash
# After docker-compose up, pull the model into Ollama
docker exec -it docplatform-v3-ollama-1 ollama pull glm-ocr

# Verify
docker exec -it docplatform-v3-ollama-1 ollama list
```

---

## 12. Migration Strategy from V2

### 12.1 Data Migration Steps

```
V2 Schema                          V3 Schema
─────────                          ─────────
Case.customer_name        →  Customer (deduplicated)
Case                      →  (removed, data merged into Customer + PO)
SalesOrder                →  PurchaseOrder (PO number from SO or extracted PO)
Document.case_id          →  Document.po_id
Document.sales_order_id   →  (removed, po_id replaces both)
DocumentMetadata          →  DocumentMetadata (add raw_ocr_text, po_ref_no)
AuditLog                  →  AuditLog (add actor_id FK)
```

### 12.2 Migration Script Outline

```python
# migration/migrate_v2_to_v3.py

def migrate():
    # 1. Create Customer table from unique customer_name values
    customers = deduplicate_customers(v2_cases)
    
    # 2. Create PurchaseOrder from SalesOrders + Customer PO documents
    for case in v2_cases:
        customer = find_customer(case.customer_name)
        for so in case.sales_orders:
            po = create_purchase_order(
                customer_id=customer.id,
                po_number=so.so_number,  # or extracted PO number
                po_date=so.created_at,
            )
            # 3. Re-link documents to PO
            for doc in so.documents:
                doc.po_id = po.id
            # Also re-link case-level PO documents
            for doc in case.documents.filter(type="CUSTOMER_PO"):
                doc.po_id = po.id
    
    # 4. Migrate file storage paths
    move_files_to_new_structure()
    
    # 5. Re-run extraction on migrated docs (optional)
    queue_bulk_re_extraction()
```

---

## 13. Implementation Phases

### Phase 1: Foundation (Weeks 1–3)
- [ ] Project scaffolding (backend + frontend + Docker)
- [ ] PostgreSQL schema + Alembic migrations
- [ ] Customer CRUD (model, service, API, frontend)
- [ ] Purchase Order CRUD (model, service, API, frontend)
- [ ] JWT authentication (login, roles, middleware)
- [ ] Basic frontend shell (routing, auth flow, layout)

### Phase 2: Document Management (Weeks 4–6)
- [ ] Document upload endpoint (with validation, checksum, storage)
- [ ] NAS storage service (PO-centric path generation)
- [ ] PDF preview + download endpoints
- [ ] Document rotation support
- [ ] Upload UI (drag-drop with PO context)
- [ ] Document grid on PO detail page

### Phase 3: OCR Pipeline (Weeks 7–9)
- [ ] Ollama integration + GLM-OCR model setup
- [ ] PDF → image conversion (PyMuPDF)
- [ ] OCR client with timeout + circuit breaker
- [ ] Response parser (JSON extraction, date parsing)
- [ ] Extraction prompts for all 6 document types
- [ ] Celery + Redis setup for background processing
- [ ] Auto-extract on upload
- [ ] WebSocket notifications
- [ ] Review modal (split view: PDF + extracted fields)
- [ ] Verify/reject workflow

### Phase 4: Polish & Production (Weeks 10–12)
- [ ] Chain status bar component
- [ ] Dashboard with stats + activity feed
- [ ] Global search (customers, POs, documents, metadata)
- [ ] Audit log viewer
- [ ] Rate limiting + security hardening
- [ ] Nginx reverse proxy + SSL
- [ ] Prometheus + Grafana monitoring
- [ ] Health checks on all services
- [ ] V2 → V3 data migration script
- [ ] End-to-end testing
- [ ] Documentation

---

*End of Reworked Architecture Document*
