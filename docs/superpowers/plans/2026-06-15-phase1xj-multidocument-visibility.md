# Phase 1xJ Multi-Document Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show and manage every uploaded document while preserving the five required Build 1 document groups.

**Architecture:** Add alias-aware grouping helpers in `build1.ts`, render each group as a list of independent document records, and keep uploads canonical. Filter verification input by metadata readiness without changing storage, extraction, parsing, OCR, or vendor-matching algorithms.

**Tech Stack:** React 18, TypeScript, React Router, Vitest, Testing Library, FastAPI, SQLAlchemy, pytest.

---

### Task 1: Frontend Regression Tests

**Files:**
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/lib/build1.test.ts`

- [ ] Add documents containing two `VENDOR_INVOICE` records plus `COMPANY_INVOICE` and `CUSTOMER_INVOICE` aliases.
- [ ] Assert both vendor filenames render, the pending record exposes `Extract`, the extracted record exposes `Re-extract`, populated groups expose `Add another`, empty groups expose `Upload`, and alias records are labeled.
- [ ] Run `npm test -- App.test.tsx build1.test.ts` and confirm the new assertions fail because only the first exact type currently renders.

### Task 2: Alias-Aware Document Groups

**Files:**
- Modify: `frontend/src/lib/build1.ts`

- [ ] Add a canonical alias map and `buildDocumentGroups(documents)` that filters all matching records.
- [ ] Reuse the canonical matcher in `buildDocumentSlots()` so alias records satisfy required-slot presence checks.
- [ ] Add display helpers for raw alias labels and extraction route text.
- [ ] Run the focused helper tests and confirm they pass.

### Task 3: Render Per-Document Actions

**Files:**
- Modify: `frontend/src/pages/DocumentsPage.tsx`
- Modify: `frontend/src/components/documents/DocumentSlotCard.tsx`
- Modify: `frontend/src/index.css`

- [ ] Change the page to render document groups instead of one retained document per slot.
- [ ] Pass document IDs into Extract, Re-extract, and Delete handlers so each action targets exactly one record.
- [ ] Render filename, type, status, extraction status, route, upload date, Review, Preview, and Delete for each record.
- [ ] Render `Upload` for empty groups and `Add another` for populated groups.
- [ ] Run the focused frontend tests and confirm they pass.

### Task 4: Verification Readiness Filter

**Files:**
- Create: `backend/tests/unit/test_verification_summary_service.py`
- Modify: `backend/app/services/verification_summary_service.py`

- [ ] Write a failing test that supplies extracted, manual-entry, pending, and failed metadata records and captures the documents passed to the verifier.
- [ ] Implement a minimal readiness predicate accepting only `EXTRACTED` and `MANUAL_ENTRY`.
- [ ] Run `python -m pytest tests/unit/test_verification_summary_service.py -q` and confirm it passes.

### Task 5: Full Verification and Live Validation

**Files:**
- Create: `backend/output/ocr-evaluations/phase1xJ_multidocument_visibility_hotfix_report.md`

- [ ] Run `python -m pytest tests -q` from `backend`.
- [ ] Run `npm test` and `npm run build` from `frontend`.
- [ ] Start or reuse the local stack, validate the Trade bundle, extract the second vendor bill, inspect verification, and save the required screenshots.
- [ ] Record exact results, unchanged scope, document counts, extraction behavior, and Build 1 lock impact in the report.

