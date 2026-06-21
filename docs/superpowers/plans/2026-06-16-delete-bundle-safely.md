# Safe Bundle Delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe bundle deletion feature that removes a bundle and its dependent documents/files without affecting unrelated modules.

**Architecture:** The backend owns deletion through `DELETE /api/bundles/{bundle_id}` and performs child cleanup in one transaction. The frontend adds a danger-styled table action guarded by a browser confirmation and refreshes the bundle queue after successful deletion.

**Tech Stack:** FastAPI, SQLAlchemy, React, Vite, Vitest.

---

### Task 1: Backend Delete API

**Files:**
- Modify: `backend/app/repositories/bundles.py`
- Modify: `backend/app/api/routes/bundles.py`
- Test: `backend/tests/integration/test_bundle_workflow.py`

- [ ] Add integration tests for deleting a bundle with documents and for deleting a missing bundle.
- [ ] Verify the new tests fail before implementation.
- [ ] Add repository and route support for deleting a bundle.
- [ ] Verify the focused backend tests pass.

### Task 2: Frontend Delete Action

**Files:**
- Modify: `frontend/src/api/bundles.ts`
- Modify: `frontend/src/components/bundles/BundleTable.tsx`
- Modify: `frontend/src/pages/BundlesPage.tsx`
- Test: `frontend/src/App.test.tsx`

- [ ] Add frontend tests for confirm-delete success and cancel behavior.
- [ ] Verify the new tests fail before implementation.
- [ ] Add `deleteBundle`, wire a danger action in the bundle table, and refresh the queue after deletion.
- [ ] Verify the focused frontend tests pass.

### Task 3: Verification

**Files:**
- No additional files.

- [ ] Run focused backend tests.
- [ ] Run focused frontend tests.
- [ ] Run frontend build.
- [ ] Run backend test suite.
- [ ] Confirm no OCR, parser, extraction, export, schema, or unrelated page behavior changed.
