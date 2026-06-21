# Build 1 Workflow Audit — Missing Pieces

**Date:** 2026-06-18
**Scope:** `order-assurance/` Build 1 frontend + backing FastAPI endpoints that the Build 1 plan and Phase 1xJ design promised.
**Method:** Static read of every file touched by the workflow against the two governing documents:
- [docs/superpowers/plans/2026-06-06-build-1-frontend.md](superpowers/plans/2026-06-06-build-1-frontend.md)
- [docs/superpowers/specs/2026-06-15-phase1xj-multidocument-visibility-design.md](superpowers/specs/2026-06-15-phase1xj-multidocument-visibility-design.md)

Plus the live build:
- `npm test` → 81 / 81 passed across 11 files (vitest output).
- `py -m pytest backend/tests -q` → 821 passed, 5 skipped (live OCR / model fixtures).

Every finding below is grounded in a specific file and line number. No guessed gaps.

---

## 1. Workflow as Currently Wired

End-to-end happy path traced from code:

```
[BundlesPage] ─POST /bundles────────────────────► create_bundle (bundles.py:34)
       │
       │ navigate /bundles/:id/overview
       ▼
[BundleOverviewPage] ─GET /bundles/{id}, /documents, /verification-summary, /audit-events
       │  (4 parallel useAsyncResource calls in BundleOverviewPage.tsx:27-30)
       │
       ▼
[DocumentsPage] ─buildDocumentGroups (build1.ts:169) ──► five required slots
       │ ─POST /bundles/{id}/documents (upload_document, bundles.py:119)
       │ ─POST /documents/{id}/extract  (extract_document_route, documents.py:159)
       │ ─POST /documents/{id}/re-extract (documents.py:168)
       │ ─DELETE /documents/{id} (documents.py:73)
       │
       ▼
[ExtractionReviewPage]
       │ ─GET /documents/{id} (ExtractionReviewPage.tsx:31)
       │ ─GET /documents/{id}/preview/pages/{n}.png (PdfPreviewPane.tsx:344)
       │ ─PATCH /documents/{id}/extracted-data (ExtractionReviewPage.tsx:67)
       │ ─POST /documents/{id}/re-extract (with ocr_rotation_degrees)
       │
       ▼
[VerificationPage] ─GET /bundles/{id}/verification-summary (VerificationPage.tsx:29)
[IssuesPage]       ─deriveIssues over summary + documents (build1.ts:271)
[AuditTrailPage]   ─GET /bundles/{id}/audit-events (AuditTrailPage.tsx:23)
[ExportsPage]      ─GET /bundles/{id}/export.xlsx (export.ts:6)
[HealthPage]       ─GET /health (health.ts:15)

ExtractionActivityProvider polls /extractions/activity every 3s
(ExtractionActivityContext.tsx:73) and renders a banner.

Bundle status sync points (verification_summary_service.sync_bundle_status_from_verification):
 • POST /documents/{id}/extract           (documents.py:112)
 • POST /documents/{id}/re-extract        (documents.py:112)
 • PATCH /documents/{id}/extracted-data   (documents.py:216)
 • DELETE /documents/{id}                 (documents.py:90)
 • GET   /bundles/{id}/export.xlsx        (via build_bundle_export → not in current export_service; verified below)
```

API client surface (`frontend/src/api/*`) — every backend route is wired except `/dev/seed-panimalar`. No frontend file references that path (grep result: zero matches).

---

## 2. Missing Pieces — Evidence Only

### 2.1 `Sidebar.tsx` promised by Build 1 plan, never created

- Plan, [2026-06-06-build-1-frontend.md:50](superpowers/plans/2026-06-06-build-1-frontend.md), Task 3 file list says: **Create: `frontend/src/components/layout/Sidebar.tsx`** with the action item "Build a fixed sidebar and top header/search shell."
- Actual layout folder ([frontend/src/components/layout/](../frontend/src/components/layout/)) contains only `AppShell.tsx`, `TopBar.tsx`, `WorkflowTabs.tsx`.
- [AppShell.tsx:28-52](../frontend/src/components/layout/AppShell.tsx) renders `<TopBar/>` + `<main>` only. No sidebar slot.
- Grep `"Sidebar"` across `frontend/src` → only `ExportReadinessPanel` matched (substring of "ReadinessPanel"); no `Sidebar.tsx` exists.

**Impact:** The Build 1 navigation collapses into a single top bar. Cross-bundle navigation (jumping to Health, Bundles, Admin) is squeezed into `<details>` `More` menus in [TopBar.tsx:34-40](../frontend/src/components/layout/TopBar.tsx).

### 2.2 Top-bar global search input is a dead control

- [TopBar.tsx:22-25](../frontend/src/components/layout/TopBar.tsx):
  ```tsx
  <div className="topbar__search" role="search">
    <label className="visually-hidden" htmlFor="global-search">Search</label>
    <input id="global-search" type="search" placeholder="Search bundles, documents, references" />
  </div>
  ```
- No `onChange`, no `onSubmit`, no `form` wrapper, no consumer.
- Grep `"global-search"` across `frontend/src` → matches only this file's `<label htmlFor>` and the `<input id>`. Nothing reads or routes this query.

**Impact:** A visible search box that does nothing. The same plan called for the "top header/search shell"; the input was created, the wire was never connected.

### 2.3 `ExportReadinessPanel` is an orphan component

- [ExportReadinessPanel.tsx](../frontend/src/components/exports/ExportReadinessPanel.tsx) exists (54 lines).
- Grep `"ExportReadinessPanel"` across `frontend/src` → only its own file is returned. Zero importers.
- [ExportsPage.tsx](../frontend/src/pages/ExportsPage.tsx) re-implements an inline "Export Readiness" header, KPI grid, financial summary, and coverage table; never imports `ExportReadinessPanel`.

**Impact:** Plan Task 3 promised "small reusable components for ... export readiness." The reusable component was built and then bypassed. Dead code path, dual sources of truth for "is the bundle ready to export?".

### 2.4 `/dev/seed-panimalar` reachable from backend, not from frontend

- Backend route: [dev.py:15-33](../backend/app/api/routes/dev.py), `POST /dev/seed-panimalar`.
- Grep `"seed-panimalar"` across `frontend/src` → zero matches.
- [BundlesPage.tsx](../frontend/src/pages/BundlesPage.tsx) only exposes "Create Bundle" via `createBundle({ bundle_number: ... })` ([line 68](../frontend/src/pages/BundlesPage.tsx)).

**Impact:** A demo seeding endpoint with no UI affordance. To bootstrap a demo bundle, an operator must `curl POST /api/dev/seed-panimalar`. This isn't strictly a Build 1 requirement, but the demo handoff workflow depends on it and there's no surfaced trigger.

### 2.5 `GET /bundles/{id}` returns no `computed_status`; list endpoint does

- [bundles.py:85-89](../backend/app/api/routes/bundles.py):
  ```python
  def get_bundle(bundle_id: str, db: Session = Depends(get_db)):
      bundle = BundleRepository(db).get(bundle_id)
      if not bundle: raise HTTPException(...)
      return bundle
  ```
  Returns the raw `OrderBundleRecord`. `computed_status`, `computed_customer_status`, `computed_vendor_status`, `status_computed_at` are all `null` in the response (allowed by [schemas/bundle.py:28-31](../backend/app/schemas/bundle.py)).
- [bundles.py:56-81](../backend/app/api/routes/bundles.py) (`list_bundles`) **does** populate all four computed fields.
- Frontend `bundleStatus(bundle)` in [build1.ts:126-128](../frontend/src/lib/build1.ts) reads `bundle.computed_status ?? bundle.status`. On the overview page the fallback uses the persisted snapshot, which is only refreshed by mutation handlers (see 2.6) — so the overview header can lag.

**Impact:** Inconsistent API contract. The list and detail responses differ on the same model. `ExportsPage` ([ExportsPage.tsx:49-51](../frontend/src/pages/ExportsPage.tsx)) explicitly falls back: `bund?.computed_status ?? bund?.status ?? null`.

### 2.6 Document upload does not refresh the persisted bundle status snapshot

- [bundles.py:119-157](../backend/app/api/routes/bundles.py) (`upload_document`) commits the new document and metadata page-count but never calls `sync_bundle_status_from_verification`.
- All other mutation paths do call it: extract ([documents.py:112](../backend/app/api/routes/documents.py)), re-extract (same), PATCH extracted-data ([documents.py:216](../backend/app/api/routes/documents.py)), delete-document ([documents.py:90](../backend/app/api/routes/documents.py)).
- Result: after an upload, `OrderBundleRecord.status` / `customer_delivery_status` / `vendor_procurement_status` remain at whatever they were before. The next `GET /bundles` call would refresh `computed_status` live, but `GET /bundles/{id}` would not (see 2.5), and the workspace tab badges built off raw `bundle.status` will be stale until any other mutation happens or a list refresh runs.

**Impact:** Until the first extract runs, the persisted snapshot is stale. The verifier filter ([verification_summary_service.py:13-23](../backend/app/services/verification_summary_service.py)) only counts `EXTRACTED`/`MANUAL_ENTRY` metadata anyway, so the live status would still be `MISSING_DOCUMENTS` — but the bundle table on the queue page already uses `computed_status`, so the user sees the same number. The gap is real only in the overview header (where computed isn't returned).

### 2.7 Audit page misrepresents its own contents

- [AuditTrailPage.tsx:47-49](../frontend/src/pages/AuditTrailPage.tsx) renders the note: "This section records manual corrections. Upload, extraction, review, and export events are available in system logs."
- The backend writes audit-event rows for: `bundle_created` ([bundles.py:42](../backend/app/api/routes/bundles.py)), `document_uploaded` ([bundles.py:140](../backend/app/api/routes/bundles.py)), `document_deleted` ([documents.py:83](../backend/app/api/routes/documents.py)), `extraction_completed` / `extraction_failed` ([documents.py:117](../backend/app/api/routes/documents.py)), `export_generated` ([bundles.py:205](../backend/app/api/routes/bundles.py)), `manual_extracted_data_patched` ([manual_metadata_service.py via patch_extracted_data]).
- The page's filter dropdown ([AuditTrailPage.tsx:27](../frontend/src/pages/AuditTrailPage.tsx)) builds `eventTypes` from `(audit.data ?? []).map((event) => event.event_type)` — so all of the above are shown by default.

**Impact:** The page title says "Manual Correction History"; the data feed actually delivers the full audit log. Either the page note is wrong, or the page should filter to `event_type === 'manual_extracted_data_patched'` (and the note then becomes true). Today it's neither.

### 2.8 Manual Correction Modal is single-field-at-a-time

- [ExtractionReviewPage.tsx:67](../frontend/src/pages/ExtractionReviewPage.tsx): `patchExtractedData(activeDocument.id, { [field]: value }, reason)`.
- [ManualCorrectionModal.tsx:17](../frontend/src/components/extraction/ManualCorrectionModal.tsx) opens for a single field.
- Backend [schemas/document.py:9-12](../backend/app/schemas/document.py) accepts `fields: dict[str, Any]` — multi-field PATCH is supported, but the UI never sends more than one key per request.

**Impact:** A user correcting five fields makes five round trips, five audit events, five reference-index rebuilds, five verification-summary syncs. Plan Task 5 said "manual correction modal" — fulfilled minimally but not at the granularity the backend supports.

### 2.9 No "Extract all" / "Re-extract all" action on Documents page

- [DocumentsPage.tsx:88-90](../frontend/src/pages/DocumentsPage.tsx) wires `onExtract` and `onReextract` per document via `DocumentSlotCard`.
- No code path triggers extraction for every uploaded doc at once. After uploading 5 PDFs the operator must click `Extract` five times sequentially.
- No backend route accepts a bulk extract either ([api/routes/documents.py](../backend/app/api/routes/documents.py) only has per-document endpoints).

**Impact:** Plan Task 5 didn't explicitly require bulk extract, but the workflow it described ("upload, preview, extract, re-extract, delete, and replace-by-upload semantics") repeated five times is friction. The extraction queue ([extraction_queue.py:39-152](../backend/app/services/extraction_queue.py)) already supports concurrent jobs — the cap is settings-driven, not UI-driven.

### 2.10 Frontend ignores backend `extraction_activity_status: "running_ocr"` token

- [extraction_service.py:513](../backend/app/services/extraction_service.py) writes `diagnostics["extraction_activity_status"] = "running_ocr"` while OCR is mid-flight.
- [build1.ts:137](../frontend/src/lib/build1.ts) `documentExtractionStatus` only matches:
  ```ts
  if (diagnostics.extraction_activity_status === 'queued' || diagnostics.queued === true) {
    return 'Waiting in extraction queue';
  }
  ```
- The string `"running_ocr"` never reaches the user via per-document diagnostics. The polled `ExtractionActivityProvider` ([ExtractionActivityContext.tsx:122-134](../frontend/src/components/extraction/ExtractionActivityContext.tsx)) covers it for the active job because that path uses the backend `/extractions/activity` snapshot — but a stale per-document diagnostic showing `running_ocr` after a hard refresh between polls falls through to the default `'Pending'` branch.

**Impact:** Minor display gap. The polled queue activity covers the active doc; the stale persisted diagnostic does not.

### 2.11 `getBundle` is fetched in every workspace page despite caching opportunity

- Five workspace pages (Overview, Documents, ExtractionReview, Verification, Issues, AuditTrail, Exports) each call `useAsyncResource(() => getBundle(bundleId), [bundleId])` independently.
- No shared bundle context. Navigating tabs re-fetches the same row N times per session.
- Same for `listBundleDocuments` and `getVerificationSummary` — fetched per tab.

**Impact:** Not a missing piece, but a missing pattern. The plan ([line 7](superpowers/plans/2026-06-06-build-1-frontend.md)) called the API layer "the source of truth for request/response normalization." There's no caching layer (no SWR, no React Query, no manual cache). Real users will see flicker on every tab change.

### 2.12 `BundleOverviewPage.refresh` semantics missing — only initial load

- [BundleOverviewPage.tsx:26-30](../frontend/src/pages/BundleOverviewPage.tsx) uses four `useAsyncResource` calls, each with `[bundleId]` as the dependency. After the operator clicks `Export Excel` ([line 41](../frontend/src/pages/BundleOverviewPage.tsx)), no resource is reloaded.
- Contrast with [DocumentsPage.tsx:37-39](../frontend/src/pages/DocumentsPage.tsx) which defines a `refresh()` helper that calls `documents.reload()` + `summary.reload()` + `bundle.reload()` after each mutation.
- BundleOverviewPage does not re-fetch the verification summary after the export call (which audits `export_generated` server-side). The audit trail card on the overview is stale until the operator navigates away and back.

**Impact:** Operator exports; the audit log section ([BundleOverviewPage.tsx:159-168](../frontend/src/pages/BundleOverviewPage.tsx)) doesn't show the new event without a hard refresh.

### 2.13 `Health` link only reachable via TopBar `More` menu

- [App.tsx:29](../frontend/src/App.tsx) defines `/health`. [TopBar.tsx:38](../frontend/src/components/layout/TopBar.tsx) is the only navigational link to it.
- [WorkflowTabs.tsx](../frontend/src/components/layout/WorkflowTabs.tsx) does not include Health.
- No bundle page or bundles list surfaces an OCR-down banner. If OCR provider is unreachable, the operator finds out only by clicking through to `/health` or by triggering an extraction that fails.

**Impact:** Operational dead-end. The `health.ocr.reachable` boolean from [health.py:13](../backend/app/api/routes/health.py) is never polled by the rest of the UI.

### 2.14 No re-extract retry / cooldown logic when extraction returns 503 from queue

- Backend [documents.py:135-137](../backend/app/api/routes/documents.py) re-raises `OcrExtractionQueueFullError` / `OcrExtractionQueueTimeoutError` as HTTP 503.
- Frontend `extractDocument` / `reextractDocument` ([documents.ts:61-75](../frontend/src/api/documents.ts)) returns the raised error to the caller (`DocumentsPage.run` or `ExtractionReviewContent.handleReextract`).
- The caller displays it via `mutationError` text. There is no auto-retry, no exponential back-off, no "queue is full — try again later" hint.

**Impact:** When the queue saturates (`OCR_QUEUE_MAX_SIZE`, settings-driven), the operator sees the raw error message. The 3-second poll banner won't help because the doc is not in the queue.

### 2.15 `MANUAL_ENTRY_REQUIRED` failure path uses a generic message

- Frontend treats `metadata.status === 'MANUAL_ENTRY'` as `'Needs Review'` in [build1.ts:68](../frontend/src/lib/build1.ts).
- There is no dedicated "Manual entry required" badge or workflow card. Operators have to open Extraction Review to figure out why.
- The extraction-failed reason (`metadata.last_error`) is shown in `DocumentSlotCard.tsx:131-133` — only when truthy. For some failure codes the backend sets it; for `MANUAL_ENTRY_REQUIRED` after manual save it's cleared (intentionally). The transition path is correct but the affordance is buried.

**Impact:** Not a missing endpoint; a missing UI affordance. Plan Task 5 said "manual correction modal" but the entry-point for "this doc needs manual entry from scratch" is the same `Edit` icon next to each field, which only makes sense when fields already exist.

### 2.16 No deep-link to a specific issue

- [IssuesPage.tsx:32](../frontend/src/pages/IssuesPage.tsx) uses `useState<DerivedIssue | null>(null)` for the selected issue. There is no `useSearchParams` / route param to deep-link a specific issue.
- `deriveIssues` in [build1.ts:271-357](../frontend/src/lib/build1.ts) constructs the `actionPath` for each issue — most go to `/bundles/{id}/extraction/{documentId}` or `/bundles/{id}/documents`. The user clicks an action, navigates away, then `Back` returns to a fresh `IssuesPage` with the first issue selected. No memory of which issue they were on.

**Impact:** Contrast with [VerificationPage.tsx:27,40,44](../frontend/src/pages/VerificationPage.tsx) which DOES read `searchParams.get('check')` and pre-selects a check. The same pattern is missing on the Issues page.

### 2.17 `WorkflowTabs` hides "Manual Correction History" inside a native `<details>`

- [WorkflowTabs.tsx:20-25](../frontend/src/components/layout/WorkflowTabs.tsx) puts the audit tab inside a `<details><summary>More</summary>...</details>`. Native HTML disclosure widget, not styled as a tab.
- Plan Task 4 said: "Route `/bundles/:bundleId` to the overview tab and expose Build 1 workflow tabs." The plan doesn't mandate audit as a top-level tab, but the experience drifts from the visible workflow.

**Impact:** Discovery gap. Audit is functionally implemented; just not surfaced.

### 2.18 `documents.test.ts` covers the upload + extract + patch contracts; no test covers `re-extract` body shape with `ocr_rotation_degrees`

- [frontend/src/api/documents.ts:50-67](../frontend/src/api/documents.ts) builds the body `{ ocr_rotation_degrees: rotation === undefined || rotation === 'auto' ? null : rotation }`.
- [frontend/src/api/documents.test.ts](../frontend/src/api/documents.test.ts) (3 tests) covers upload-multipart-form-fields, extract-mutation-normalization, and patch-mutation-shape. None asserts that `re-extract` sends `ocr_rotation_degrees: 90` when the user picks `90deg` from the rotation menu in [PdfPreviewPane.tsx:261-272](../frontend/src/components/documents/PdfPreviewPane.tsx).

**Impact:** A regression that flips the rotation payload could ship without failing tests.

### 2.19 No `Pending Extraction` state for orphan documents on the Documents page

- [DocumentSlotCard.tsx:92-97](../frontend/src/components/documents/DocumentSlotCard.tsx) flips between `Extract` / `Re-extract` button labels based on `documentExtractionStatus`:
  - `'Extracted'` or `'Failed'` → Re-extract.
  - Anything else → Extract.
- After upload, `metadata.status === 'PENDING'`, so the button reads `Extract`. Click it once → status becomes `EXTRACTING` → returns to `EXTRACTED` or `EXTRACTION_FAILED`. No issue here.
- But: an `UPLOADED` doc with `metadata.status === 'PENDING'` shows extraction status `'Pending'` ([build1.ts:142](../frontend/src/lib/build1.ts)) instead of distinguishing "never extracted" from "extraction queued". The Phase 1xJ spec wanted "Waiting in extraction queue" surfaced — that only fires when the activity poll matches.

**Impact:** Minor. Not a missing endpoint, just a status label that conflates two situations.

### 2.20 No frontend test for the bundle-status sync gap on upload (2.6)

- The upload-without-sync gap above has no regression test in either `frontend/src/api/documents.test.ts` or `backend/tests/integration/test_bundle_workflow.py` (the latter exists but exercises extraction → patch → list, not upload-only).

---

## 3. What Is Wired Correctly

For the record, none of the following are gaps:

- All API client functions in [frontend/src/api/](../frontend/src/api/) target a real backend route. Verified by grep:
  - `listBundles` → `GET /bundles` ([bundles.py:56](../backend/app/api/routes/bundles.py))
  - `getBundle` → `GET /bundles/{id}` ([bundles.py:84](../backend/app/api/routes/bundles.py))
  - `createBundle` → `POST /bundles` ([bundles.py:34](../backend/app/api/routes/bundles.py))
  - `deleteBundle` → `DELETE /bundles/{id}` ([bundles.py:92](../backend/app/api/routes/bundles.py))
  - `listBundleDocuments` → `GET /bundles/{id}/documents` ([bundles.py:160](../backend/app/api/routes/bundles.py))
  - `uploadDocument` → `POST /bundles/{id}/documents` ([bundles.py:119](../backend/app/api/routes/bundles.py))
  - `getDocument` → `GET /documents/{id}` ([documents.py:28](../backend/app/api/routes/documents.py))
  - `extractDocument` → `POST /documents/{id}/extract` ([documents.py:159](../backend/app/api/routes/documents.py))
  - `reextractDocument` → `POST /documents/{id}/re-extract` ([documents.py:168](../backend/app/api/routes/documents.py))
  - `patchExtractedData` → `PATCH /documents/{id}/extracted-data` ([documents.py:177](../backend/app/api/routes/documents.py))
  - `deleteDocument` → `DELETE /documents/{id}` ([documents.py:73](../backend/app/api/routes/documents.py))
  - `documentPreviewUrl` / `documentPreviewPageUrl` → `GET /documents/{id}/preview[/pages/{n}.png]` ([documents.py:36,52](../backend/app/api/routes/documents.py))
  - `getExtractionActivity` → `GET /extractions/activity` ([extractions.py:11](../backend/app/api/routes/extractions.py))
  - `getVerificationSummary` → `GET /bundles/{id}/verification-summary` ([bundles.py:167](../backend/app/api/routes/bundles.py))
  - `listAuditEvents` → `GET /bundles/{id}/audit-events` ([bundles.py:184](../backend/app/api/routes/bundles.py))
  - `exportVerificationReport` → `GET /bundles/{id}/export.xlsx` ([bundles.py:191](../backend/app/api/routes/bundles.py))
  - `getHealth` → `GET /health` ([health.py:11](../backend/app/api/routes/health.py))
- Phase 1xJ readiness filter in place at [verification_summary_service.py:13-23](../backend/app/services/verification_summary_service.py).
- Phase 1xJ alias-aware document grouping in [build1.ts:82-92, 169-185](../frontend/src/lib/build1.ts).
- Per-document Extract/Re-extract/Review/Preview/Delete actions live in [DocumentSlotCard.tsx:135-170](../frontend/src/components/documents/DocumentSlotCard.tsx).
- Extraction activity banner polls every 3 s ([ExtractionActivityContext.tsx:62-80](../frontend/src/components/extraction/ExtractionActivityContext.tsx)).
- Backend cascading delete for bundles cleans `ReferenceIndexRecord`, `AuditEventRecord`, `DocumentPageRecord`, `TextSourceRecord`, `FieldCandidateRecord` ([bundles.py:104-111](../backend/app/api/routes/bundles.py)).
- Export `Content-Disposition` honored by frontend filename parser ([export.ts:22, 31-48](../frontend/src/api/export.ts)).

---

## 4. Fix Priority

Top of the list = closest to a real user-visible defect.

1. **Wire or remove the global search input** ([TopBar.tsx:24](../frontend/src/components/layout/TopBar.tsx)). Either submit to BundlesPage with a query param, or delete the control.
2. **Make `get_bundle` return computed status fields** so overview header doesn't depend on the stale snapshot. Add the same fields the list endpoint returns ([bundles.py:62-80](../backend/app/api/routes/bundles.py)).
3. **Call `sync_bundle_status_from_verification` from `upload_document`** ([bundles.py:147](../backend/app/api/routes/bundles.py)) for symmetry.
4. **Either filter `AuditTrailPage` to manual corrections only, or rewrite the note** ([AuditTrailPage.tsx:47-49](../frontend/src/pages/AuditTrailPage.tsx)).
5. **Decide on `ExportReadinessPanel`**: import it into [ExportsPage.tsx](../frontend/src/pages/ExportsPage.tsx) and delete the inline rewrite, or delete the panel.
6. **Delete or build `Sidebar.tsx`**. If it's deliberately dropped, update the plan; if it's deferred, raise a follow-up issue.
7. **Add `Refresh` after export on `BundleOverviewPage`** so the audit card updates.
8. **Add deep-link `?issue=` support to `IssuesPage`** to match `VerificationPage`.
9. **Add multi-field manual save** in [ManualCorrectionModal.tsx](../frontend/src/components/extraction/ManualCorrectionModal.tsx) (backend already supports it).
10. **Add OCR-down banner**: poll `/health` from the AppShell when `health.ocr.reachable === false` and show a warning strip.
11. **Add a regression test** asserting `re-extract` body contains `ocr_rotation_degrees` when the user picks a fixed rotation (gap 2.18).
12. **Bulk Extract Action** on the Documents page that fans out per-doc extractions through the existing queue.
13. **Recognize `extraction_activity_status === 'running_ocr'`** in `documentExtractionStatus` ([build1.ts:134-144](../frontend/src/lib/build1.ts)).
14. **Surface the dev seed endpoint** behind an `ENABLE_DEV_TOOLS` UI affordance on BundlesPage so demos don't need curl.
15. **Introduce shared bundle-context caching** (React Query, SWR, or a single `useBundleContext` hook) to stop the per-tab re-fetch storm.

---

## 5. Closing

The Build 1 workflow runs end-to-end. The plumbing is in place: every API client function reaches a working backend route; the alias-aware document grouping from Phase 1xJ is implemented; the verifier readiness filter is correct.

The missing pieces fall into three buckets:

- **Promised in the plan, never built:** `Sidebar.tsx`, wired global search.
- **Built but not connected:** `ExportReadinessPanel`, the dev seed endpoint, the `extraction_activity_status: "running_ocr"` token.
- **Working but inconsistent:** `get_bundle` vs `list_bundles`, upload skipping the status-sync hook, the audit page note that doesn't match its data, single-field manual correction against a multi-field API, no shared resource cache.

None of these block the demo flow as written in [docs/demo-script-panimalar.md](demo-script-panimalar.md). All of them widen the gap between what Build 1 promised and what an outside reviewer will see when they walk through the UI without a tour guide.
