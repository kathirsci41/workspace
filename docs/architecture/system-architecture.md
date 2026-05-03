# DPP System Architecture
**Last Updated:** 2026-04-19

---

## 1. System Purpose

DPP is a PO-centric logistics document operations platform.

The product is built around a single business anchor, the purchase order, and manages the document chain attached to that order:

- Customer PO
- Company PO
- Vendor DC
- Vendor Invoice
- Company DC
- Company Invoice
- Installation Report when required

The system does more than store documents or extract OCR text. Its actual job is to help operators and managers:

- collect the right documents for each order scenario
- extract structured data from PDFs
- verify and correct extracted fields
- validate document-to-order consistency
- measure chain completeness
- assess billing and cross-document integrity
- close orders safely when operations are complete

---

## 2. Architectural Style

The codebase is a modular monolith with one asynchronous worker tier.

### Main runtime pieces

- Frontend: React 18 + Vite + TypeScript
- Backend API: FastAPI on Python 3.12
- Database: PostgreSQL
- Broker/cache: Redis
- Worker: Celery
- Storage: NAS-style filesystem path or local dev storage
- Extraction endpoints: Ollama, RunPod-hosted compatible endpoint, Datalab, or OpenAI-compatible endpoints

### Architectural pattern

- frontend sends HTTP requests and renders operational state
- FastAPI owns synchronous product behavior and API contracts
- PostgreSQL stores business entities and extracted metadata
- storage keeps source PDF files
- Celery performs extraction work outside request/response paths
- Redis backs queueing and selected caching use cases

---

## 3. Runtime Topology

```text
Browser (React)
  -> FastAPI API
     -> PostgreSQL
     -> Redis
     -> Storage
     -> Celery worker
        -> Extraction providers
```

### Responsibility split

- Browser: operator workflows, dashboards, review, search, admin, assistant UI
- FastAPI: CRUD, workflow orchestration, validation, exports, search, admin APIs, chat streaming
- PostgreSQL: persistent business state
- Redis: queue backend and operational caching
- Celery: long-running extraction tasks
- Storage: PDF source of record
- Extraction providers: OCR and structured extraction execution

---

## 4. Core Business Aggregate

The primary aggregate is `PurchaseOrder`.

Everything important in the system is ultimately attached to or summarized under a PO:

- uploaded documents
- extraction status
- reference validation
- billing status
- scenario-specific completeness
- discrepancies
- manual completion state

`Document` and `DocumentMetadata` are operational sub-records that enrich the PO lifecycle rather than forming a separate product domain.

---

## 5. Core Data Model

### `Customer`

Represents the commercial entity the order belongs to.

Important fields:

- `id`
- `customer_id`
- `name`
- contact and GST details

Relationship:

- one customer to many purchase orders

### `PurchaseOrder`

Represents the main business record.

Important fields:

- `po_number`
- `customer_id`
- `po_date`
- `total_amount`
- `status`
- `so_number`
- `order_scenario`
- `gst_type`
- `invoice_split`
- `billing_type`
- `billing_milestones`
- `requires_install_report`
- `chain_completeness`
- `chain_status`
- `manually_completed`
- `completion_note`
- `items_verified`

Relationship:

- one PO to many documents

### `Document`

Represents the uploaded source file and its operational extraction state.

Important fields:

- `document_type`
- `original_filename`
- `file_path`
- `checksum`
- `page_count`
- `status`
- `rotation`
- `so_number`
- `vpo_numbers`
- `billing_stage`

Relationship:

- one document to one metadata record
- one document to many correction records

### `DocumentMetadata`

Represents structured extraction output and review-related metadata.

Important fields:

- `extracted_data`
- `primary_ref_no`
- `po_ref_no`
- `doc_date`
- `total_amount`
- `confidence_score`
- `raw_ocr_text`
- `model_version`
- `processing_time_ms`
- `field_confidences`
- `extraction_route`
- `last_error`

### `ExtractionCorrection`

Audit trail of operator edits made to extracted content.

### `ReferenceIndex`

Denormalized search layer used for cross-document and reference lookups.

---

## 6. Product Modules

The visible product is organized around the following functional modules:

- customer management
- purchase order management
- document intake
- extraction and re-extraction
- human review
- chain validation
- PO profile and discrepancy analysis
- search and address search
- admin monitoring and recovery
- assistant chat
- export

These modules share one codebase and one database, but each maps to a distinct operational concern.

---

## 7. Document Chain Model

Required documents depend on the PO scenario.

### Main scenarios

- `procurement`
- `stock`
- `drop_ship`
- `service_amc`
- `unknown`

### Why this matters

The system does not calculate completeness with a fixed six-document rule anymore. Instead it evaluates the chain against scenario-specific requirements. That affects:

- missing-slot detection
- completeness percentage
- profile views
- manager decisions
- order closure readiness

Optional documents can still exist and be tracked without blocking completeness.

---

## 8. Trust Boundary

The trust boundary in the system is human verification.

AI extraction produces draft structured data. The platform is designed around the assumption that:

- extraction may be incomplete
- extraction may be wrong
- models may be offline
- operators need traceable correction and review tools

That is why review, correction logging, SO prompting, validation errors, and manual completion exist as first-class features.

---

## 9. Where Complexity Really Lives

The most important complexity in DPP is not in simple CRUD.

It sits in:

- scenario-aware chain logic
- extraction pipeline routing and provider variability
- reference and billing validation
- PO-level aggregation of many document records
- cross-document comparison and discrepancy surfacing
- operational recovery when storage or models fail

Anyone extending the system should understand those areas before making structural changes.

---

## 10. Current Documentation Rule

There is version drift elsewhere in the repository.

Known examples:

- `README.md` still uses an older version label
- the frontend shell shows an older version string
- the backend runtime title is newer

For architecture work, use this folder as the maintained current-state documentation set.
