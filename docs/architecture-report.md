# Architecture Report and Capability Expansion (Detailed)

## 1. Executive Summary
DPP is a PO-centric logistics document operations platform designed to convert unstructured business documents into trusted operational decisions.

It combines four layers of intelligence:
- machine extraction from documents
- deterministic validation and normalization
- cross-document business checks
- supervised human/agent decisioning

The current architecture is strong enough to scale. It already has the right foundation for higher capability and capacity: modular service boundaries, asynchronous workers, scenario-aware order logic, and review as a trust boundary. The next growth phase should focus on precision, automation gates, and explainable cross-document reasoning.

## 2. Report Scope
This report covers:
- system design and runtime topology
- domain model and workflow model
- user-flow architecture
- data-flow architecture
- backend and frontend component architecture
- OCR/extraction subsystem architecture
- trust model and human/agent supervision
- capability expansion roadmap
- scale, risk, and implementation guidance

## 3. Business Context and Product Intent
The platform is not just OCR tooling. It is an operational workflow engine for logistics document chains.

Core business intent:
- keep each PO as a complete, validated business packet
- detect missing chain evidence early
- reduce manual data-entry time
- maintain auditable trust before closure

Primary business outcomes:
- faster document-to-decision cycle time
- fewer shipment/invoice mismatches
- better closure confidence
- searchable evidence trail by reference and order context

## 4. System Architecture (High-Level)
### 4.1 Runtime Topology
- Frontend: React + Vite + TypeScript workflow console
- API: FastAPI application for synchronous workflow operations
- Data: PostgreSQL for domain entities and extraction metadata
- Queue/Broker: Redis
- Worker: Celery for long-running extraction tasks
- File storage: filesystem or NAS mounted path
- AI endpoints: pluggable OCR/extraction providers

### 4.2 Architectural Style
- Modular monolith with worker tier
- Domain services own business logic
- API routes act as orchestration boundaries
- Worker pipeline isolates high-latency inference

### 4.3 Why This Style Fits
This style matches your current maturity and complexity because:
- workflow rules evolve quickly and benefit from one deployable codebase
- extraction workload is asynchronous and failure-prone
- business state needs relational consistency and auditability

## 5. Domain Architecture
### 5.1 Core Aggregate
Purchase Order is the aggregate root. It carries business truth and drives lifecycle state.

PO-owned concerns:
- required document chain by scenario
- chain completeness and chain status
- SO-level and billing-level validation context
- closure readiness and completion overrides

### 5.2 Supporting Entities
- Customer: commercial parent and identity context
- Document: uploaded source artifact plus processing status
- DocumentMetadata: structured extraction payload plus confidence, errors, and timing
- ReferenceIndex: search-optimized references across entities
- ExtractionCorrection: audit record of human-reviewed changes

### 5.3 Domain Integrity Principle
A document alone is evidence, not truth. Truth is established after review and chain-level consistency checks inside the PO context.

## 6. Workflow Architecture
### 6.1 End-to-End Workflow
1. Customer setup
2. PO creation
3. Document upload under PO
4. Asynchronous extraction
5. Human/agent review against source file
6. Cross-document validation at PO level
7. Discrepancy resolution or re-extraction
8. Manager closure decision

### 6.2 Status and Transition Model
Document states encode both operational progress and failure class:
- Uploaded
- Extracting
- Pending review
- Verified
- Rejected
- Extraction failed
- Pending model

PO states encode business readiness, not just extraction completion.

### 6.3 Scenario-Aware Chain Logic
Chain requirements vary by scenario (stock, procurement, drop-ship, service/AMC, unknown). Completeness and missing-slot reporting are scenario-dependent, not static document counts.

## 7. User-Flow Architecture (Detailed)
### 7.1 Operator Journey
- open dashboard and review pending workload
- create or select PO
- upload document by document type
- inspect extraction result beside source PDF
- verify/edit/reject as needed
- resolve flagged chain mismatches

### 7.2 Manager Journey
- inspect PO profile and discrepancy context
- verify billing and chain readiness
- accept closure with note when operationally justified

### 7.3 Admin Journey
- monitor API, queue, model, and storage health
- inspect backlog/failure categories
- requeue pending-model artifacts

### 7.4 Assistant Journey
- optionally provide PO-scoped context responses
- support quick triage and explanation, not final authority

## 8. Data-Flow Architecture (Detailed)
### 8.1 Ingestion Flow
UI upload -> API validation -> file storage write -> document row creation -> extraction task enqueue.

### 8.2 Extraction Flow
Worker fetches document -> route decision (digital/scanned) -> text acquisition -> structured extraction -> validator/normalizer pass -> metadata/reference persistence -> status transition.

### 8.3 Review Flow
UI loads source + metadata -> reviewer compares fields to source -> review action (verify/reject/edit) -> correction/audit write -> chain recompute.

### 8.4 Validation Flow
Field-level checks + document-level checks + cross-document checks + scenario completeness checks -> final PO readiness signal.

### 8.5 Search Flow
Reference and metadata persistence feed indexed retrieval paths for fast operational lookup.

## 9. Backend Architecture (Detailed)
### 9.1 Layering
- API routers for endpoint contracts
- service layer for business orchestration
- model/schema layers for persistence and payload contracts
- extraction service cluster for OCR and parsing

### 9.2 Persistence and Session Model
- async DB sessions for API request path
- sync DB sessions for Celery worker path

This separation reduces async complexity inside Celery and keeps request-path performance predictable.

### 9.3 Operational Interfaces
- admin health and queue introspection
- requeue and recovery actions
- search and advanced retrieval endpoints

### 9.4 Backend Strengths
- clear PO-centric domain ownership
- practical async/sync split
- provider-agnostic extraction pipeline
- operationally visible failure states

### 9.5 Backend Risks
- extraction orchestration function has high complexity concentration
- status synchronization across document and metadata can drift if not guarded
- prompt + validator consistency is a long-term maintenance burden

## 10. Frontend Architecture (Detailed)
### 10.1 UI Structure
- shared app shell and route-driven pages
- workflow-specific pages for PO operations, profile, documents, search, admin, chat

### 10.2 State and Data Strategy
- server-state first pattern via query/mutation
- local state only for transient interaction concerns
- shared HTTP client behavior for error-to-toast mapping

### 10.3 UX Architecture for Trust
- side-by-side source and extracted data review
- explicit review actions and status feedback
- mismatch visibility and drilldown through PO profile

### 10.4 Frontend Strengths
- mirrors backend workflow semantics well
- optimized for operator throughput
- supports exception-focused review patterns

### 10.5 Frontend Risks
- review surfaces are state-heavy and high-regression zones
- cache key discipline must stay strict as features expand
- UI consistency depends heavily on stable API contracts

## 11. OCR/Extraction Subsystem Architecture
### 11.1 Two-Layer Pattern
- Layer 1: text capture from digital PDFs or OCR on scanned pages
- Layer 2: schema-bound field extraction from captured text

### 11.2 Route Strategy
- digital route for machine-readable documents
- scanned route for image-first documents

### 11.3 Quality Controls
- provider health checks before extraction
- retries and circuit-style failure handling
- pending-model hold path when dependency unavailable
- deterministic post-extraction normalization

### 11.4 Business Validation Integration
Extraction does not finalize trust. It feeds:
- field-level checks
- SO and reference checks
- invoice math checks
- chain-level consistency checks

### 11.5 Design Implication
This subsystem is mature and flexible, but precision depends on prompt quality and validator coverage. That is the main leverage point for improvement.

## 12. Trust Boundary and Supervision Model
Trust is established through supervised validation, not through model confidence alone.

### 12.1 Required Validation Layers
- source-grounded field verification
- cross-document consistency checks
- PO-level business-rule checks

### 12.2 Human/Agent Supervision
The supervision model should remain:
- AI/agent proposes
- system validates
- human approves high-impact decisions

This design allows automation growth without losing governance.

## 13. Capability and Capacity Expansion Strategy
### 13.1 Strategic Objectives
- capability: better semantic extraction and reasoning quality
- capacity: higher throughput with less manual touch
- intelligence: evidence-driven, policy-constrained agentic orchestration
- trust: preserve auditability and decision traceability

### 13.2 Phase A - Deterministic Uplift
- harden standard-template prompts (company-side docs first)
- define label-precedence maps by document type
- add field risk calibration and stricter validator logic

Outcome:
- measurable first-pass precision gain
- reduced review noise

### 13.3 Phase B - Agent-Assisted Review
- add review agent to compare extracted fields with source evidence spans
- add explanation generation for mismatch cases
- preserve supervised verify/reject authority

Outcome:
- faster review cycles
- improved consistency across operators

### 13.4 Phase C - Cross-Document Intelligence
- strengthen chain reasoning: reference continuity, amount continuity, temporal coherence, line-item consistency
- introduce PO-level confidence-of-completeness metric

Outcome:
- earlier detection of hidden integrity issues
- better closure confidence

### 13.5 Phase D - Controlled Straight-Through Processing
- auto-verify only low-risk classes with strict policy gates
- keep rollback and audit for every auto action

Outcome:
- major capacity increase
- reduced routine human dependency

### 13.6 Phase E - Insight and Decision Support
- ranked next-best action suggestions
- root-cause discrepancy summaries
- risk-prioritized queues for manager focus

Outcome:
- better decision velocity
- improved operational predictability

## 14. Agentic Architecture Blueprint
This target architecture is agent-driven, not just rule automation.

### 14.1 Agent Roles
- Extraction Agent: executes document parsing/extraction and produces field-level confidence and evidence candidates.
- Validation Agent: verifies extracted fields against source text and structured business rules.
- Reconciliation Agent: performs cross-document checks across the PO chain and prepares mismatch summaries.
- Orchestration Agent: decides next best action per PO (re-extract, route to review, request missing doc, or advance stage).
- Supervisor Agent: enforces policy gates and decides what can be auto-processed versus escalated.

### 14.2 Agent Decision Loop
1. Observe state: document status, extraction payload, chain context, and policy profile.
2. Plan action: choose minimal safe next step based on risk and confidence.
3. Execute with tools: extraction calls, validation routines, and retrieval queries.
4. Evaluate outcome: compare result quality and policy compliance.
5. Escalate or continue: send to human/agent review when risk exceeds threshold.

### 14.3 Guardrails and Governance
- No high-impact business transition without policy check.
- No silent overwrite of reviewed values.
- All agent actions must be auditable and attributable.
- Human override remains available for all closure-critical decisions.

### 14.4 Human-in-the-Loop Policy
- Low-risk, high-confidence, policy-compliant cases can be auto-routed.
- Medium-risk cases require agent-assisted review.
- High-risk cases require explicit human approval.

### 14.5 Why Agentic Over Plain Automation
- Plain automation follows fixed scripts and breaks on variability.
- Agentic orchestration adapts sequence and strategy to document context.
- It reduces repetitive human effort while preserving governance.

## 15. Non-Functional Architecture Considerations
### 15.1 Performance
- keep API operations lean and async
- offload heavy inference to worker tier
- prioritize exception handling paths for operator latency

### 15.2 Reliability
- classify failures by cause (document quality vs model availability)
- make requeue and recovery first-class operations
- expose health and queue metrics in admin surfaces

### 15.3 Security and Governance
- enforce strict access boundaries for document actions
- maintain immutable correction/audit traces
- treat model outputs as untrusted until verified

### 15.4 Maintainability
- keep prompt and validator logic versioned and synchronized
- avoid hidden state transitions
- isolate high-complexity orchestration for targeted testing

## 16. Delivery and Execution Plan
### 16.1 Recommended First 90 Days
- complete Phase A for COMPANY_PO, COMPANY_DC, COMPANY_INVOICE
- define benchmark set and quality KPIs
- implement evidence-ready mismatch reporting

### 16.2 Next 90 Days
- pilot agent-assisted review with bounded policy
- expand cross-document checks and confidence scoring
- add queue risk prioritization

### 16.3 KPI Framework
- first-pass extraction accuracy
- review time per document
- mismatch escape rate
- auto-pass ratio (policy-safe)
- closure delay by chain discrepancy type

## 17. Agentic Implementation Matrix

This matrix translates the agentic blueprint into execution-ready responsibilities.

| Agent | Core purpose | Key tools/capabilities | Primary inputs | Primary outputs | Policy gate | Human escalation condition |
| --- | --- | --- | --- | --- | --- | --- |
| Extraction Agent | Convert source documents into structured candidate fields | OCR providers, digital extractor, prompt templates, schema parser | PDF/image file, document type, provider config | extracted fields, field confidences, extraction diagnostics | schema validity, minimum confidence, no parser failure | unreadable source, confidence below threshold, repeated extraction failure |
| Validation Agent | Validate extracted fields against source evidence and field rules | field validators, type/format checks, SO checks, invoice math checks | extracted fields, raw OCR text, PO context | normalized fields, validation errors/warnings, pass/fail status | no critical validation errors | conflicting field evidence, high-impact field mismatch |
| Reconciliation Agent | Check consistency across PO chain documents | cross-document validators, reference checks, amount/date checks, item comparison | verified/preview metadata across PO docs, scenario profile | discrepancy set, chain consistency score, mismatch severity | mismatch severity below auto-pass threshold | chain mismatch on financial/reference-critical fields |
| Orchestration Agent | Decide next best action for each document/PO | workflow policy engine, queue prioritization, retry/re-extract routing | document state, validation state, queue state, business priority | action plan: verify route, review route, re-extract, request missing doc | action allowed by policy state machine | unresolved ambiguity after bounded retries |
| Supervisor Agent | Enforce governance and approval boundaries | policy rules, risk model, approval matrix, audit controls | outputs from all agents, risk score, role permissions | final disposition: auto-advance or supervised hold | policy compliance + risk within allowed envelope | high-risk class, closure-impacting decisions, policy conflict |

### 17.1 Suggested baseline policy thresholds
- Auto-advance allowed only when all of the following are true:
	- extraction confidence above configured threshold
	- zero critical validation errors
	- no high-severity chain mismatch
	- document type in approved low-risk set
- Mandatory supervised review when any of the following are true:
	- financial totals mismatch across chain
	- SO/PO reference mismatch on company-side docs
	- low confidence on identity-critical fields (invoice no, DC no, PO ref)
	- model/provider instability indicators exceed retry policy

### 17.2 Event and audit logging requirements
- Log every agent decision with:
	- input snapshot hash
	- policy version
	- selected action
	- confidence/risk values
	- escalation reason if any
- Persist immutable correction history and approval actor identity.
- Retain reversible state transitions for auto-advanced documents.

## 18. Final Assessment
The architecture is fundamentally sound and already aligned with your long-term direction.

You do not need a platform rewrite to reach a high-intelligence system. You need controlled evolution along three tracks:
- deterministic extraction quality
- supervised agentic validation
- exception-driven operational workflows

If executed in phases, DPP can significantly increase agentic capability, throughput, and insight quality while preserving the trust model required for enterprise logistics operations.
