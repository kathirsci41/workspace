# Architecture Report and Capability Expansion

## 1. Executive Summary
DPP is a PO-centric logistics document operations platform that combines AI extraction, human validation, and cross-document business checks. The architecture is a modular monolith with a worker tier, which is a strong fit for your current scale and workflow complexity.

The core strength is not just OCR. The system already supports operational trust by combining:
- source-document extraction
- human/agent review
- PO-chain consistency checks
- audit-safe correction history

This gives you a strong base to evolve toward a higher-intelligence system without losing control.

## 2. Current Architecture (High-Level)
### 2.1 Runtime Topology
- Frontend: React + Vite + TypeScript workflow console
- API: FastAPI service for business workflow orchestration
- Data: PostgreSQL for domain and extraction persistence
- Broker/cache: Redis
- Worker: Celery for long-running extraction tasks
- Storage: filesystem/NAS-backed document source-of-record
- Model endpoints: configurable OCR/extraction providers

### 2.2 Core Architectural Pattern
- Request/response operations run in FastAPI
- Long-running extraction executes asynchronously in Celery
- PO is the primary aggregate; documents and metadata are subordinate evidence records
- Review and validation determine trusted business state

## 3. Domain Architecture
### 3.1 Core Aggregate
Purchase Order is the central business object. It controls:
- chain completeness
- scenario-specific required docs
- validation and mismatch context
- closure state

### 3.2 Main Domain Entities
- Customer: commercial owner of orders
- PurchaseOrder: workflow anchor and decision boundary
- Document: uploaded artifact and processing status
- DocumentMetadata: extracted fields, confidence, timings, errors
- ReferenceIndex: normalized lookup/search references
- ExtractionCorrection: human edit audit trail

## 4. Workflow Architecture
### 4.1 End-to-End Workflow
1. Customer setup
2. PO creation
3. Document upload under PO
4. Async extraction
5. Human/agent review against source
6. Cross-document validation across chain
7. Discrepancy resolution/re-extraction
8. Order closure

### 4.2 Status Architecture
Document lifecycle supports operational clarity:
- Uploaded
- Extracting
- Pending review
- Verified
- Rejected
- Extraction failed
- Pending model

This separation is important because it distinguishes document-quality issues from model-availability issues.

## 5. Data Flow Architecture
### 5.1 Ingestion and Extraction Data Flow
- UI upload request -> API validation -> storage write -> document DB row -> Celery queue
- Worker loads document -> chooses digital/scanned route -> OCR/text extraction -> structured extraction
- Validator/normalizer runs -> metadata and references persist -> status transitions -> PO recompute

### 5.2 Review and Decision Data Flow
- UI loads source PDF + extracted metadata
- Reviewer compares extracted fields with source document
- Reviewer edits/verifies/rejects
- Corrections are logged and persisted
- Chain and profile-level status are recalculated

## 6. OCR/Extraction Subsystem Architecture
### 6.1 Two-Layer Design
- Layer 1: text capture (digital or OCR)
- Layer 2: schema-bound field extraction

### 6.2 Route Strategy
- Digital route for machine-readable PDFs
- Scanned route for image-heavy PDFs

### 6.3 Reliability Controls
- provider health checks
- retry/circuit logic
- pending-model fallback
- validation and normalization before trust elevation

## 7. Trust and Validation Architecture
The trust boundary is review + validation, not extraction output alone.

### 7.1 What Makes Data Trusted
- Source-grounded review (field vs actual PDF)
- Cross-document checks (PO/DC/invoice/SO consistency)
- Chain-level business validation
- Auditable human corrections

### 7.2 Human/Agent Role
The right operational model is:
- AI does first-pass extraction and risk signals
- human/agent validates ambiguous/high-impact cases
- final business decisions remain supervised

## 8. Frontend Architecture Summary
The frontend is an operations console, not a generic dashboard.

### 8.1 Primary Work Surfaces
- Dashboard: queue and KPI visibility
- PO Detail: daily workflow center
- PO Profile: deep reconciliation and discrepancy context
- Documents: cross-PO queue
- Search: retrieval
- Admin: reliability controls
- Chat: assistant layer

### 8.2 State Pattern
- Server state with query/mutation patterns
- Local state for UI interactions
- Shared API client and global toast behavior

## 9. Backend Architecture Summary
The backend is service-led with clear workflow ownership.

### 9.1 Strength Areas
- clear API-service-domain separation
- async API path + sync worker path
- robust extraction orchestration model
- operational admin endpoints for health/recovery

### 9.2 Risk Areas
- extraction orchestration complexity concentration
- status coordination across document + metadata states
- prompt/schema consistency burden as scenarios increase

## 10. Capability Expansion Roadmap
## 10.1 Expansion Goals
- Increase capability: better reasoning and fewer extraction errors
- Increase capacity: higher throughput with less manual effort
- Increase intelligence: agent-like orchestration with evidence
- Preserve trust: keep auditable supervision and controlled automation

## 10.2 Phase A: Deterministic Extraction Uplift
- Tighten prompts for standard company templates
- Add strict label precedence maps per document type
- Add field-level confidence/risk calibration
- Expand deterministic validators for known failure patterns

Expected outcome:
- Better first-pass accuracy
- Reduced noisy review workload

## 10.3 Phase B: Agent-Assisted Review Layer
- Introduce review agent logic:
  - compare extraction vs source text spans
  - compare document vs chain counterparts
  - generate evidence-backed mismatch explanations
- Keep final verify/reject as supervised action

Expected outcome:
- Faster review and better consistency
- Human effort focused on true exceptions

## 10.4 Phase C: Cross-Document Intelligence
- Add stronger chain reasoning:
  - reference continuity
  - amount continuity
  - date/sequence sanity
  - line-item consistency checks
- Add PO-level confidence-of-completeness score

Expected outcome:
- Better PO-level decision quality
- Earlier detection of hidden business mismatches

## 10.5 Phase D: Controlled Straight-Through Processing
- Auto-verify low-risk docs only when strict criteria pass:
  - high confidence
  - no chain mismatches
  - known template
  - no policy-rule violations
- Maintain full audit and rollback paths

Expected outcome:
- Higher throughput
- Significant manual dependency reduction

## 10.6 Phase E: Insight and Decision Support
- Build ranked action suggestions per PO
- Show root-cause oriented discrepancy explanations
- Add queue prioritization by business impact and risk

Expected outcome:
- Better manager decision speed
- Easier operational triage

## 11. Target Future State
A practical high-intelligence target state for DPP is:
- AI for extraction + agentic validation + supervised approval
- exception-driven human workload
- chain-aware business reasoning
- end-to-end auditability

This achieves both scale and trust without unsafe full autonomy.

## 12. Final Assessment
The current architecture is strong enough to support capability and capacity expansion. The best next step is not a full rebuild; it is layered intelligence upgrades on top of your existing PO-centric workflow and trust boundary.
