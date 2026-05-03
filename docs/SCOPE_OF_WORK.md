# Scope of Work (SOW)

## Project
Document Processing Platform (DPP) for PO-Centric Logistics Operations

## Version
Draft v1.0  
Date: 2026-04-11

## 1. Purpose
This Scope of Work defines the implementation and rollout scope for the Document Processing Platform (DPP), a web-based system to manage, extract, validate, and track logistics documents under each Purchase Order (PO) using a human-in-the-loop AI workflow.

## 2. Project Objectives
1. Centralize end-to-end PO document lifecycle management in one platform.
2. Automate extraction of structured data from logistics documents using two-layer OCR + LLM extraction.
3. Improve operational visibility with PO chain completeness tracking, search, and dashboards.
4. Reduce manual reconciliation effort through cross-document validation and review workflows.
5. Deploy a stable, supportable environment for daily operations.

## 3. Current Baseline
The current DPP baseline includes:
1. FastAPI backend, React frontend, PostgreSQL, Redis, Celery.
2. Two-layer extraction pipeline (`glm-ocr` + `qwen2.5:7b`) with re-extraction and review workflow.
3. PO-centric data model with chain completeness and status tracking.
4. Support for six core document types:
- Customer PO
- Company PO
- Vendor DC
- Vendor Invoice
- Company DC
- Company Invoice
5. Admin tools for health monitoring and model requeue.
6. Existing dev/prod Docker setup and migration framework.

## 4. In-Scope Work
### 4.1 Discovery and Configuration
1. Confirm business scenarios (stock, procurement, drop-ship, service/AMC, partial fulfillment, special cases).
2. Finalize required vs optional extraction fields per document type.
3. Define document chain rules and completeness logic per scenario.

### 4.2 AI Extraction and Validation Tuning
1. Tune extraction prompts and parsing behavior against client sample PDFs.
2. Improve field-level accuracy for high-priority business fields.
3. Validate SO/reference consistency checks and exception handling.
4. Configure fallback handling for model unavailability (`PENDING_MODEL` / requeue flow).

### 4.3 Workflow and UI Finalization
1. Finalize operator review/correction workflow.
2. Finalize PO list filters, document search, and operational dashboard behavior.
3. Complete required UX gaps for validation-driven actions (e.g., SO-entry-related flow where applicable).

### 4.4 QA and UAT
1. Execute functional testing for document upload, extraction, review, verification, search, and chain completion.
2. Execute regression test pass on backend and frontend critical paths.
3. Run UAT with client team using agreed sample sets and scenarios.
4. Resolve UAT defects in agreed priority order.

### 4.5 Deployment and Handover
1. Prepare production environment configuration.
2. Deploy application stack and validate health checks.
3. Provide admin and operator handover walkthrough.
4. Deliver release notes and known limitations register.

## 5. Deliverables
1. Configured DPP application build for client workflow.
2. Scenario and extraction field configuration sheet (approved).
3. UAT test log and defect resolution tracker.
4. Production deployment package/configuration.
5. User guidance:
- Operator runbook (upload, review, verify, re-extract, search)
- Admin runbook (service health, queue, requeue, troubleshooting)
6. Go-live sign-off report.

## 6. Out of Scope
1. ERP customization or direct ERP integration (unless separately approved).
2. New document classes beyond agreed six core types in this SOW cycle.
3. Mobile application development.
4. Advanced analytics/BI data warehouse implementation.
5. Custom model training/fine-tuning pipeline beyond prompt/pipeline tuning.
6. Long-term managed hosting/SRE operations (unless separately contracted).

## 7. Client Responsibilities
1. Provide sample documents per agreed scenarios and formats.
2. Provide business rule clarifications and sign-off on extraction fields.
3. Nominate UAT users and provide timely defect feedback.
4. Provide required infrastructure access (on-prem/cloud), VPN/network access, and credentials.
5. Ensure legal/internal approval for using document data in testing.

## 8. Assumptions
1. Sample documents provided are representative of actual operational variety.
2. OCR/model endpoint availability will be maintained during UAT windows.
3. Required stakeholders will review and approve outputs within agreed turnaround times.
4. Scope changes after sign-off follow formal change request and impact review.

## 9. Acceptance Criteria
1. Agreed critical scenarios can be processed end-to-end without blocker defects.
2. All six core document workflows are operational in UAT.
3. Review and verification workflow functions with audit trail persistence.
4. Search, filters, and PO chain completeness are operational and validated by users.
5. No open Severity-1 defects and no unapproved Severity-2 defects at go-live sign-off.

## 10. Indicative Timeline (6-8 Weeks)
1. Week 1: Discovery, scenario lock, field-finalization workshop.
2. Week 2-3: Extraction tuning and workflow alignment.
3. Week 4: Integration hardening and internal QA.
4. Week 5-6: UAT cycle, fixes, and regression.
5. Week 7-8: Production deployment, handover, and sign-off.

## 11. Change Control
1. Any requirement outside this scope must be raised as a Change Request (CR).
2. Each CR will include impact on timeline, effort, and cost.
3. CR work starts only after written approval.

## 12. Support and Warranty (Post Go-Live)
1. Hypercare support period: 2-4 weeks from go-live (to be finalized in contract).
2. Includes bug fixes for in-scope functionality.
3. Excludes new features and change requests.

## 13. Commercial Notes
Commercials, payment milestones, and legal terms (NDA, IP, liability, SLA) are to be documented in the commercial proposal/MSA and are not defined in this technical SOW draft.

