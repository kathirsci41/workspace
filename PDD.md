# Document Processing Platform — v2.2.0

Product & Project Definition Document (PDD)

**Document type:** Combined Product Design + Project Definition Document
**Project:** DPP — Document Processing Platform
**Domain:** Indian IT / Logistics Distribution
**Version:** 2.2.0
**Date:** March 2026
**Status:** Active Development → Staging

---

## 1. Project Overview

The Document Processing Platform (DPP) is an internal web application built for Indian IT and logistics distribution companies to manage the complete document chain associated with each Purchase Order. It replaces fragmented manual workflows (Tally entries + physical files + WhatsApp) with a single, AI-powered platform that extracts, validates, and tracks all logistics documents from receipt to completion.

---

## 2. Stakeholders and Users

| Role | Who | What they need |
| ---- | --- | -------------- |
| Operations Staff | Data entry / admin team | Upload documents, verify extracted data, track status |
| Logistics Manager | Team lead / supervisor | Real-time visibility across all POs and document chains |
| Management | Director / owner | High-level summary — what is pending, what is complete |
| Developer | Internal / contracted | Maintain, extend, and deploy the platform |

---

## 3. Problem Statement — As-Is (Current State)

### How the team works today

The company currently uses **Tally / ERP** as the primary accounting and procurement system. Documents flow through the business but the system has significant gaps in visibility and traceability.

### Current document flow

```text
Customer sends PO
      |
      v
Staff receives via email / WhatsApp / physical copy
      |
      v
Data manually entered into Tally (PO number, amounts)
      |
      v
Physical or scanned document saved to a local folder
(naming convention varies by staff member)
      |
      v
Vendor documents (DC, Invoice) arrive separately
      |
      v
Staff matches them manually to the original PO
      |
      v
Company issues its own DC and Invoice
      |
      v
All documents exist in separate places —
Tally has the financial data, folders have the files,
no single place ties them together
```

### Pain points identified

| Pain Point | Impact |
| ---------- | ------ |
| **No real-time visibility** | Management cannot see which POs are fully documented without asking staff |
| **Document chain is fragmented** | Tally has financial data but actual document files are in folders with no structured link to the PO |
| **No chain completeness tracking** | No system checks whether all 6 document types exist for a PO — gaps discovered only during audits or disputes |
| **Manual data extraction** | Staff re-types reference numbers, dates, and amounts from scanned documents into Tally — error-prone and slow |
| **Search is difficult** | Finding a specific invoice or DC requires navigating folder structures or scrolling Tally entries |
| **No cross-document validation** | Nobody checks whether the SO number on the Company DC matches the one generated for that Customer PO — mismatches go unnoticed |

---

## 4. Proposed Solution — To-Be (Future State)

### How the team works with DPP

```text
Customer sends PO (PDF or scan)
      |
      v
Staff uploads to DPP — takes 10 seconds
      |
      v
AI extracts all fields automatically (two-layer OCR)
glm-ocr reads the document → qwen2.5:7b structures the data
      |
      v
Staff reviews extracted data on screen — corrects if needed
One click to verify
      |
      v
System prompts: "Enter SO number for this PO"
SO stored — all future documents validated against it
      |
      v
Vendor documents uploaded as they arrive
Auto-extracted, auto-validated against PO reference
      |
      v
Company DC and Invoice uploaded
SO number auto-checked — mismatch flagged immediately
      |
      v
Chain completeness updates in real time (0% → 100%)
Management sees live dashboard — no need to ask staff
      |
      v
Any document findable in seconds via search or filter
```

### What changes

| Before (As-Is) | After (To-Be) |
| -------------- | ------------- |
| Documents in scattered folders | All files linked to a PO in one place |
| Data re-typed into Tally manually | AI extracts fields automatically |
| Chain status unknown until asked | Live chain completeness bar per PO (0–100%) |
| No cross-document validation | SO number auto-validated across COMPANY_DC and COMPANY_INVOICE |
| Management asks staff for status | Dashboard shows all pending, extracting, verified counts live |
| Finding old documents is slow | Full-text search + filter by type, date, customer |
| Extraction failures silent | Admin console shows exact error and where to fix it |

### What does NOT change

- Tally / ERP continues as the accounting system — DPP complements it, not replaces it
- Staff still reviews extracted data — human verification step is kept intentionally
- Physical document storage at the company — DPP stores digital copies alongside

---

## 5. Document Types and Business Flow

DPP manages 6 document types per Purchase Order, representing the complete logistics chain:

| # | Document Type | Direction | Primary Key | When it appears |
| - | ------------- | --------- | ----------- | --------------- |
| 1 | CUSTOMER_PO | Customer → Company | `po_number` | Start of chain — customer sends purchase order |
| 2 | COMPANY_PO | Company → Vendor | `purchase_bill_no` | Company orders from vendor to fulfil |
| 3 | VENDOR_DC | Vendor → Company | `dc_number` | Vendor dispatches goods |
| 4 | VENDOR_INVOICE | Vendor → Company | `invoice_number` | Vendor bills the company |
| 5 | COMPANY_DC | Company → Customer | `dc_number` | Company dispatches to customer — contains SO number |
| 6 | COMPANY_INVOICE | Company → Customer | `invoice_number` | Company bills the customer — contains SO number |

### Chain completeness score

Each PO has a `chain_completeness` score from 0.0 to 1.0:

- Each verified document contributes ~0.167 (1/6)
- Failed or rejected documents do not count
- Score shown as a progress bar on every PO card

### SO Number flow

```text
CUSTOMER_PO verified
      |
      v
Operator enters SO number (generated internally by company)
Stored on PurchaseOrder record
      |
      v
COMPANY_DC uploaded → SO number extracted → compared → flagged if wrong
COMPANY_INVOICE uploaded → same check applied
```

---

## 6. Feature Scope

### In scope — v2.2.0

- Customer and PO management (CRUD)
- Document upload — PDF, PNG, TIFF
- Two-layer AI extraction (glm-ocr + qwen2.5:7b)
- Human review and verification workflow
- SO number cross-document validation
- Chain completeness tracking per PO
- Filter system on PO list (date range, SO number, chain completeness, missing doc type, sort)
- Documents page — cross-PO search by type, status, customer, date
- Dashboard — pipeline overview + top 10 pending queue
- Admin console — system health, pipeline counters, failure diagnostics, Celery queue status
- Full-text search and reference number lookup
- PDF in-browser preview and download
- Re-extraction and manual data entry fallback

### Out of scope — v2.2.0 (planned for future versions)

- Tally / ERP two-way sync
- User accounts and role-based access control
- Audit trail (who verified what, when)
- Bulk document upload
- Email / WhatsApp automatic ingestion
- Mobile app
- Single vision model pipeline (qwen2-vl:7b — planned for v3.0)
- Multi-company / multi-branch support

---

## 7. Technical Architecture

### Stack

| Layer | Technology |
| ----- | ---------- |
| Backend API | FastAPI (Python 3.12), async |
| Task Queue | Celery + Redis broker |
| Database | PostgreSQL 16, SQLAlchemy async ORM |
| Frontend | React 18 + TypeScript + Vite + TanStack Query |
| OCR Layer 1 | `glm-ocr:latest` via Ollama — image to Markdown |
| OCR Layer 2 | `qwen2.5:7b` via Ollama — Markdown to structured JSON |
| OCR Hosting | RunPod remote endpoint (current) / local Ollama (dev) |
| File Storage | Local filesystem (NAS-mountable path) |

### Development hardware

| Resource | Spec |
| -------- | ---- |
| CPU | Intel Core i5-13450HX |
| RAM | 16 GB |
| GPU | NVIDIA RTX 3050 6GB VRAM (laptop) |
| OCR | RunPod remote — offloads GPU from dev machine |

### Extraction pipeline

```text
PDF / image upload
      |
      v
Celery async task (non-blocking)
      |
      v
Layer 1 — glm-ocr:latest
  Convert pages to images (PyMuPDF, 200 DPI, max 768px)
  Each page sent to Ollama vision model
  Output: raw Markdown preserving tables and layout
      |
      v
Layer 2 — qwen2.5:7b
  Markdown + document-type-specific JSON schema prompt
  Output: structured JSON with all extracted fields
      |
      v
Validation
  Invoice math check (line items × qty vs total)
  SO number cross-check (COMPANY_DC, COMPANY_INVOICE)
  Errors stored in extracted_data._validation_errors
      |
      v
Status → PENDING_REVIEW
Operator reviews, corrects, and verifies
```

**On failure:** full exception string stored in `DocumentMetadata.last_error`, status set to `EXTRACTION_FAILED`, partial data preserved for review.

---

## 8. Deployment Plan

### Phase 1 — Local Development (current)

- Dev machine: FastAPI on port 8000, React on port 5173
- PostgreSQL + Redis via Docker Compose
- OCR on RunPod remote endpoint
- Manual restarts, no CI/CD

### Phase 2 — Azure Staging (next)

- Azure VM: Ubuntu 22.04, B2ms (2 vCPU, 8GB RAM)
- FastAPI + Celery managed by systemd (auto-restart on crash)
- Nginx serving React build + proxying `/api` to FastAPI
- GitHub Actions auto-deploys on push to `staging` branch
- OCR continues on RunPod — no GPU required on VM
- **Purpose:** stable demo environment, recovery checkpoint if dev codebase is lost or broken

### Phase 3 — Production (planned)

- Azure NC4as T4 v3 (NVIDIA T4, 16GB VRAM) with Reserved Instance pricing
- Local Ollama on VM — no RunPod dependency, both models loaded simultaneously
- Option: single vision model (qwen2-vl:7b) to simplify pipeline
- Auto-shutdown scheduling during off-hours to reduce cost

### Branch strategy

```text
dev      → local development (unstable, experimental)
staging  → auto-deploys to Azure VM (always demo-ready)
main     → production releases (tagged snapshots)
```

---

## 9. Known Limitations and Risks

| Item | Detail | Mitigation |
| ---- | ------ | ---------- |
| OCR quality on bad scans | glm-ocr can struggle with blurry, rotated, or very low-res phone photos | Re-upload with better scan; rotation tool built in |
| RunPod dependency | If RunPod endpoint goes down, all extraction stops | Admin console flags Ollama health in real time; local Ollama fallback available |
| No user authentication | Any user on the network can access and modify data | Acceptable for internal single-team use; auth planned for v3.0 |
| VRAM constraint (dev) | RTX 3050 6GB requires sequential model unloading between layers | RunPod handles OCR in dev; not a constraint on staging or production |
| No audit trail | No record of who verified or corrected a document | Planned for v3.0 with user login system |
| Celery solo pool (Windows dev) | Single-threaded task execution | Linux staging and production use standard Celery pool |
| Tally not connected | Verified extracted data stays in DPP, not synced to Tally | Manual cross-reference required until integration is built in future version |

---

## 10. Glossary

| Term | Meaning |
| ---- | ------- |
| PO | Purchase Order |
| DC | Delivery Challan |
| SO | Sales Order number — generated internally, links outgoing company documents |
| Chain completeness | 0.0–1.0 score showing how many of the 6 document types are verified for a PO |
| PENDING_REVIEW | Document extracted, waiting for operator to verify |
| EXTRACTION_FAILED | AI extraction crashed — error stored, needs re-upload or manual entry |
| Layer 1 | glm-ocr — converts document image to Markdown text |
| Layer 2 | qwen2.5:7b — converts Markdown to structured JSON |
| RunPod | Remote GPU cloud hosting the Ollama models |
| ERP | Enterprise Resource Planning software (e.g. Tally) used for accounting |

---

*This document reflects DPP v2.2.0 as of March 2026.*
*Next major version (v3.0) targets: single-model pipeline, user authentication, Tally integration.*
