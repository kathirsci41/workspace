# Build 1 Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the existing Order Assurance frontend with a Build 1 workflow UI that uses the current FastAPI contracts for bundles, documents, extraction review, verification, audit, health, and Excel export.

**Architecture:** Keep the backend unchanged and make the frontend API layer the source of truth for request/response normalization. Use React Router routes for the Build 1 pages, a shared `AppShell`, and small reusable components for status, KPI cards, tables, document slots, extraction fields, verification checks, issues, audit, and export readiness. Derive issues and counts from `GET /api/bundles/{bundle_id}/verification-summary` and `GET /api/bundles/{bundle_id}/documents` when no dedicated endpoint exists.

**Tech Stack:** React 18, React Router 7, TypeScript, Vite, Vitest, Testing Library, existing Fetch-based API clients.

---

### Task 1: Contract-Focused Tests

**Files:**
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/api/documents.test.ts`
- Create: `frontend/src/lib/build1.test.ts`

- [ ] Write tests for Build 1 route rendering against mocked backend payloads.
- [ ] Write tests for document mutation envelope normalization and multipart upload fields.
- [ ] Write tests for status labels, required document slots, KPI counts, verification check categories, and issue derivation.
- [ ] Run `npm run test -- --runInBand` or `npm test` and confirm the new tests fail because Build 1 UI/lib modules are not implemented yet.

### Task 2: Frontend Contract and Normalization Layer

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/bundles.ts`
- Modify: `frontend/src/api/documents.ts`
- Modify: `frontend/src/api/verification.ts`
- Modify: `frontend/src/api/audit.ts`
- Modify: `frontend/src/api/export.ts`
- Create: `frontend/src/api/health.ts`
- Create: `frontend/src/lib/build1.ts`

- [ ] Keep `POST /api/bundles` body as `{ bundle_number, customer_name?, customer_po_no?, so_no? }`; expose only bundle name plus optional backend-supported fields in UI.
- [ ] Keep upload multipart fields as `document_type` and `file`.
- [ ] Keep manual correction body as `{ fields, actor: "frontend", reason }`.
- [ ] Add centralized status label/tone mapping for `OK`, `PASS`, `PARTIAL_PASS`, `REVIEW_REQUIRED`, `MISMATCH`, `MISSING_DOCUMENTS`, `BLOCKED`, `UPLOADED`, `EXTRACTING`, `PENDING_REVIEW`, `EXTRACTION_FAILED`, `VERIFIED`, `REJECTED`, `PENDING`, `EXTRACTED`, `FAILED`, and `MANUAL_ENTRY`.
- [ ] Add Build 1 helpers for required document slots, bundle/document KPIs, extraction progress, verification summaries, check categories, and derived issues.
- [ ] Run the focused lib/API tests and confirm they pass.

### Task 3: Shared Build 1 UI Components

**Files:**
- Create: `frontend/src/components/layout/AppShell.tsx`
- Create: `frontend/src/components/layout/Sidebar.tsx`
- Create: `frontend/src/components/layout/TopBar.tsx`
- Create: `frontend/src/components/common/StatusBadge.tsx`
- Create: `frontend/src/components/common/KpiCard.tsx`
- Create: `frontend/src/components/common/DataTable.tsx`
- Create: `frontend/src/components/common/EmptyState.tsx`
- Create: `frontend/src/components/common/ErrorState.tsx`
- Create: `frontend/src/components/common/LoadingState.tsx`
- Modify: `frontend/src/index.css`

- [ ] Build a fixed sidebar and top header/search shell.
- [ ] Build compact status badges, KPI cards, reusable table wrapper, and loading/empty/error states.
- [ ] Replace the old CSS with the Build 1 enterprise SaaS styling.

### Task 4: Bundles and Bundle Workspace Pages

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/pages/BundlesPage.tsx`
- Create: `frontend/src/pages/BundleOverviewPage.tsx`
- Create: `frontend/src/components/bundles/BundleTable.tsx`
- Create: `frontend/src/components/bundles/CreateBundleModal.tsx`

- [ ] Route `/` and `/bundles` to the new bundles work queue.
- [ ] Add create bundle modal using `POST /api/bundles`; map the UI bundle name to backend `bundle_number`.
- [ ] Route `/bundles/:bundleId` to the overview tab and expose Build 1 workflow tabs.
- [ ] Use real bundle, document, verification, and audit data on overview.

### Task 5: Document, Extraction, Verification, Issues, Audit, Export, Health Pages

**Files:**
- Create: `frontend/src/pages/DocumentsPage.tsx`
- Create: `frontend/src/pages/ExtractionReviewPage.tsx`
- Create: `frontend/src/pages/VerificationPage.tsx`
- Create: `frontend/src/pages/IssuesPage.tsx`
- Create: `frontend/src/pages/AuditTrailPage.tsx`
- Create: `frontend/src/pages/ExportsPage.tsx`
- Create: `frontend/src/pages/HealthPage.tsx`
- Create supporting components under `frontend/src/components/documents`, `frontend/src/components/extraction`, `frontend/src/components/verification`, `frontend/src/components/issues`, `frontend/src/components/audit`, and `frontend/src/components/exports`.

- [ ] Implement five required document slot cards with upload, preview, extract, re-extract, delete, and replace-by-upload semantics.
- [ ] Implement split-pane extraction review using `GET /api/documents/{document_id}`, page PNG preview, field metadata, manual correction modal, and refresh after save/re-extract.
- [ ] Implement verification checks from normalized summary checks with filters and detail panel.
- [ ] Implement issues by deriving missing documents, failed/mismatched/review checks, and summary issues.
- [ ] Implement audit event timeline/table with before/after values when payload changes exist.
- [ ] Implement export readiness and Excel binary download.
- [ ] Implement internal health view using `GET /api/health`.

### Task 6: Remove Old UI and Verify

**Files:**
- Delete old pages/components/tests no longer referenced by Build 1.
- Keep useful low-level API utilities and format/document type helpers if still used.

- [ ] Remove old `/orders` routes and old UI pages/components.
- [ ] Run `npm ci`, `npm run build`, `npm test`, `npm run lint` if configured, Playwright/E2E if available, and backend pytest/API smoke checks.
- [ ] If a command fails from pre-existing setup, capture command, exit reason, and whether the frontend change caused it.
