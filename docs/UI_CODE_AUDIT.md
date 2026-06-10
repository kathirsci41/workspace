# UI Code Audit

Date: 2026-05-25  
Scope: current `order-assurance` frontend and the backend contracts/services that supply it.  
Purpose: establish the contract baseline before any UI redesign. No redesign or application behavior change is included in this audit.

## Sources Reviewed

Required frontend sources were read in full:

- `frontend/package.json`, `package-lock.json`, `vite.config.ts`, `tsconfig.json`, `playwright.config.ts`, `Dockerfile`, and `index.html`.
- `frontend/src/App.tsx`, `main.tsx`, `index.css`, `vite-env.d.ts`, `types/*`, `api/*`, `components/*`, `pages/*`, and `test/setup.ts`.
- `frontend/e2e/*` to identify covered UI workflows and test prerequisites.

There is no `frontend/src/styles/` directory. Current global styles are in `frontend/src/index.css`, with additional inline styles in components.

Required backend sources were read in full:

- `backend/app/api/routes/documents.py` and `backend/app/api/serializers.py`.
- `backend/app/services/extraction_service.py`, `manual_metadata_service.py`, `reference_index_service.py`, `order_bundle_verifier.py`, and `export_service.py`.
- `backend/app/models/reference_index.py`, `backend/app/repositories/reference_index.py`, and `backend/migrations/001_initial_schema.sql`.

Supporting contract sources were also read because the current UI calls or depends on them:

- `backend/app/api/routes/bundles.py`, `dev.py`, `health.py`; schemas, domain enums, document/bundle/audit models and repositories.
- `verification_summary_service.py`, `document_normalizer.py`, `demo_seed_service.py`, `storage_service.py`, and `audit_service.py`.
- Integration/unit tests covering bundle workflow, extraction, export, status safety, reference integrity, dev gating, migrations, and verification.
- `README.md`, `docs/architecture.md`, `docs/status-model.md`, `docs/extraction-runtime.md`, `docs/migration-notes.md`, `docs/production-readiness-checklist.md`, `docs/risk-register.md`, `docs/demo-handoff.md`, `docs/client-demo-pack.md`, and `docs/docker-demo-validation.md`.

## Key Findings

1. `VerificationSummary` is the authoritative verification state, while bundle list/detail payload statuses are persisted snapshots. `BundleDetailPage` accounts for this in its header; `BundleListPage` displays snapshot status without indicating possible staleness.
2. The frontend contract types are intentionally loose at the most important redesign surfaces: `extracted_data`, `diagnostics`, `checks`, and `issues` are `Record<string, unknown>`, and extraction/manual-patch API calls return `unknown`.
3. The current detail page is a single orchestration component handling four initial reads and every mutation. A failure in any initial detail request blocks the whole refresh path.
4. The verification card's manual-entry action opens `documents[0]`, not a document associated with the reported issue. The backend issues/checks currently do not provide a complete correction-target contract for all cases.
5. Manual validation, normalization, reference rebuilding, and verification are correctly backend-owned and must remain backend-owned after redesign.
6. The code defaults `APP_ENV` to `development` and `ENABLE_DEV_TOOLS` to `true`, while the README/environment example and production notes describe production-safe defaults. Deployment configuration can override this, but local code defaults do not match the stated safety posture.
7. Baseline verification is mostly healthy: backend tests, frontend unit tests, and frontend build pass. Frontend lint cannot run because no ESLint configuration exists; Playwright cannot start because its Chromium executable is absent.

## 1. Current Frontend Stack

| Area | Current implementation | Audit note |
| --- | --- | --- |
| Framework | React `18.3.1`, React DOM `18.3.1`, TypeScript, Vite `5.4.21` | SPA built from `src/main.tsx` and `App.tsx`. |
| Routing | No router dependency; `App.tsx` stores `bundleId` in `useState` | List/detail navigation is not URL-addressable and is lost on reload. |
| State management | Component-local `useState` and `useEffect`; `Promise.all` refresh in `BundleDetailPage` | No shared server-state/query cache, request cancellation, or per-resource error boundaries. |
| API client | Native `fetch`; common JSON helper in `src/api/client.ts`; domain modules in `src/api/*` | Upload/export bypass `requestJson` for multipart/blob handling. Error bodies are surfaced as raw text. |
| Styling | Global plain CSS in `src/index.css` and substantial component inline style objects | No `src/styles` directory, component library, tokens, or CSS module layer. |
| Unit/component tests | Vitest `1.6.1`, jsdom, Testing Library, `@testing-library/jest-dom` | Configured in `vite.config.ts`; 9 files / 15 tests currently pass. |
| End-to-end tests | Playwright with backend/frontend `webServer` configuration | Covers seeded bundle/export and document field highlighting; currently blocked by missing browser binary locally. |
| Typecheck/build | `npm run build` runs `tsc && vite build` | Passes at audit time. |
| Lint | Script declared as `eslint . --ext ts,tsx --max-warnings 0` | No ESLint config is present, so the command fails before linting. |

## 2. Current Screens And Components

The current application has two page states, both mounted from `App.tsx`; it does not have browser routes.

| Component | Route/page where used | Backend API used | Current purpose | Problems/gaps |
| --- | --- | --- | --- | --- |
| `App` | Root mount, toggles list/detail | None directly | Holds selected bundle ID and page switch | No URL route/history/deep-link support; wraps pages that themselves render `<main>`. |
| `BundleListPage` | Initial/root state | `GET /bundles`, `POST /bundles` | Create bundle; list/open bundles | Displays snapshot status as if current; create failure is not caught in `submit`; no loading/empty workflow state beyond table. |
| `BundleDetailPage` | Selected bundle state | `GET /bundles/{id}`, `/documents`, `/verification-summary`, `/audit-events`; document mutations; export | Full bundle workbench and refresh orchestration | Monolithic state/orchestration; all four reads fail as one refresh; manual-entry shortcut chooses first document rather than issue target. |
| `DocumentUploadPanel` | Detail page | Via parent: `POST /bundles/{id}/documents` | Select canonical document type and upload PDF | No upload busy/reset state; shows only five canonical types although backend enum permits aliases/additional types. |
| `DocumentList` | Detail page | Via callbacks | Collection renderer for document cards | No ordering/grouping/empty expected-document guidance; delegates all state to parent. |
| `DocumentCard` | Detail page document list | Via parent: extract/re-extract | Display status, references, diagnostics, and actions | Renders low-level diagnostic keys directly; derives action from `status !== UPLOADED`; no structured review requirement or reference provenance display. |
| `VerificationSummaryCard` | Detail page | Via parent: `GET /verification-summary` | Overall/section status, references, passing checks, issues, recommendation | `checks`/`issues` are untyped; does not render `connections`; vendor status is not rendered through `StatusBadge`; issue action lacks document targeting. |
| `IssueList` | Verification summary | None | Render issue code/message | Drops structured issue details such as affected document IDs, amounts, and difference. |
| `StatusBadge` | List/detail/cards/summary | None | Status display | Assumes a closed palette while API types allow arbitrary strings; unknown values become visually generic. |
| `DocumentPreviewPanel` | Detail document review | `GET /documents/{id}/preview`, `GET /documents/{id}/preview/pages/{page}.png` | Original PDF preview and field bounding-box overlay | Exact highlight is available only for field locations with page dimensions/bbox; OCR/manual evidence necessarily falls back to text. |
| `ExtractedFieldsPanel` | Detail document review | None | Display extracted fields, confidence, evidence-location action | Generic rendering of arbitrary fields; does not distinguish manual/rules/model source clearly except source text; does not expose alternate values. |
| `ManualMetadataForm` | Detail document review | Via parent: `PATCH /documents/{id}/extracted-data` | Edit document-type-specific fields with reason | UI field sets are narrower than backend allowlists; same selected document keeps initial form state after refreshed backend values; server validation rules are not represented before submit. |

### UI-Owned API Modules

| Module | Operations currently used |
| --- | --- |
| `api/client.ts` | API base URL selection, JSON requests, unused `getHealth()` helper |
| `api/bundles.ts` | list/get/create bundles |
| `api/documents.ts` | list/get/upload/extract/re-extract/manual patch and preview URLs |
| `api/verification.ts` | computed verification summary |
| `api/audit.ts` | bundle audit events |
| `api/export.ts` | download XLSX blob |
| `api/debugLog.ts` | optional console event logging behind `VITE_DEBUG_LOGS=true` |

## 3. Current Backend API Contracts Used By The UI

All paths below are relative to `/api`. Timestamps returned from model-backed reads serialize as JSON datetime strings.

### Shared Response Shapes

```ts
type BundleRead = {
  id: string;
  bundle_number: string;
  customer_name: string | null;
  customer_po_no: string | null;
  so_no: string | null;
  status: string;                    // persisted snapshot
  customer_delivery_status: string;  // persisted snapshot
  vendor_procurement_status: string; // persisted snapshot
  created_at: string;
  updated_at: string;
};

type DocumentRead = {
  id: string;
  order_bundle_id: string;
  document_type: string;
  filename: string;
  content_type: string | null;
  status: string;
  last_error: string | null;
  created_at: string;
  updated_at: string;
  metadata: null | {
    id: string;
    document_id: string;
    status: string;
    extracted_data: Record<string, unknown>;
    diagnostics: Record<string, unknown>;
    field_confidences: Record<string, number | null>;
    field_evidence: Record<string, string | null>;
    field_locations: Record<string, FieldLocation>;
    primary_ref_no: string | null;
    po_ref_no: string | null;
    last_error: string | null;
  };
};

type DocumentMutationResult = {
  document: DocumentRead;
  metadata: DocumentRead["metadata"];
  references: Array<{
    id: string;
    document_id: string;
    order_bundle_id: string | null;
    reference_type: string;
    reference_value: string;
    source_type: string | null;
    document_type: string | null;
    field_name: string | null;
    confidence: number | null;
    evidence_text: string | null;
    created_at: string;
  }>;
  audit_event?: AuditEvent; // present for manual patch only
};

type VerificationSummary = {
  bundle_status: string;             // computed authoritative result
  customer_delivery_status: string;
  vendor_procurement_status: string;
  extracted_summary: Record<string, unknown>;
  connections: Array<Record<string, unknown>>;
  checks: Array<Record<string, unknown>>;
  issues: Array<Record<string, unknown>>;
  recommendation: string;
};
```

The public document serializer removes `raw_text` and `raw_ocr_text` from `extracted_data` and never exposes `storage_path`. Diagnostics remain public and loosely shaped.

### Runtime UI Endpoints

| Endpoint | Request shape | Response shape | Status/error cases observed from code/tests | Contract gaps for a redesigned UI |
| --- | --- | --- | --- | --- |
| `GET /bundles` | None | `200 BundleRead[]` | No explicit route errors | Status fields are snapshots, with no `computed_at`, staleness indicator, counts, pagination, or review workload summary. |
| `POST /bundles` | JSON `{ bundle_number: string, customer_name?: string, customer_po_no?: string, so_no?: string }` | `201 BundleRead` | `422` for schema errors; duplicate-number database failure is not translated into a user contract | Needs structured conflict/error response if bundle creation remains exposed. |
| `GET /bundles/{bundle_id}` | Path ID | `200 BundleRead` | `404 {detail:"Bundle not found"}` | Same snapshot-status ambiguity as list. |
| `POST /bundles/{bundle_id}/documents` | Multipart `document_type` enum plus `file` PDF | `201 DocumentRead` | `404` missing bundle; `400` non-PDF/invalid PDF; `413` too large; `422` invalid enum/form | No explicit supported-type/display-label/maximum-size capability contract returned to UI. |
| `GET /bundles/{bundle_id}/documents` | Path ID | `200 DocumentRead[]` | `404` missing bundle | No server-provided expected/missing document slots or review/action flags. |
| `GET /documents/{document_id}` | Path ID | `200 DocumentRead` | `404` missing document | Defined in frontend API but not currently called by pages. Useful for isolated review refresh only after redesign. |
| `POST /documents/{document_id}/extract` | Path ID; empty POST | `200 DocumentMutationResult` | `404` missing document; an extraction business failure still returns `200` with `document.status="EXTRACTION_FAILED"` and diagnostic failure codes | Frontend currently types response as `unknown`; no async/progress contract because extraction is synchronous. |
| `POST /documents/{document_id}/re-extract` | Path ID; empty POST | `200 DocumentMutationResult` | Same as extract | Same missing typed mutation/result model; diagnostics contain runs but are unstructured at API boundary. |
| `PATCH /documents/{document_id}/extracted-data` | JSON `{ fields: Record<string, unknown>, actor?: string="system", reason?: string|null }` | `200 DocumentMutationResult` plus `audit_event` | `400` unsupported fields, invalid numeric value, missing reason for high-impact fields, blank critical refs; `404` no document/metadata; `422` malformed body; `500` transactional patch/audit failure | UI cannot discover allowed/required/high-impact fields from API; actor is client supplied and not authenticated. |
| `GET /documents/{document_id}/preview` | Path ID | Inline `application/pdf` | `404` absent path/file; `403` storage path outside configured root | Appropriate for PDF display; no preview availability/page-count field beyond diagnostics. |
| `GET /documents/{document_id}/preview/pages/{page}.png` | Positive page number | `image/png` | `404` absent/out-of-range; `403` unsafe path; `422` render error | Bounding-box support is conditional and should be treated as optional capability. |
| `GET /bundles/{bundle_id}/verification-summary` | Path ID | `200 VerificationSummary` | `404` missing bundle | `checks`, `issues`, `connections`, and `extracted_summary` need stable schemas/document targeting to support richer UI safely. |
| `GET /bundles/{bundle_id}/audit-events` | Path ID | `200 AuditEvent[]` | `404` missing bundle | Events/payload are generic; no pagination; identity is an actor string rather than authenticated user. |
| `GET /bundles/{bundle_id}/export.xlsx` | Path ID | XLSX binary attachment | `404` missing bundle; `500 {detail:"Export failed"}` | Export is synchronous with no persisted export job/state; frontend discards server filename and downloads with its own ID-based filename. |

### Supporting/Non-Screen Endpoints

| Endpoint | Current consumer | Contract |
| --- | --- | --- |
| `GET /health` | Helper exists in `api/client.ts`, not rendered by screens | `200 {status, service, ocr}` where OCR provider health is nested and not represented in frontend helper type. |
| `POST /dev/seed-panimalar` | Playwright/test/demo operations, not normal UI | `201` seeded bundle/documents/summary when dev tools enabled; `403` when disabled. |
| `DELETE /documents/{document_id}` | Backend-supported but not called by current UI | `204` and recomputed persisted bundle snapshot; `404` missing document. Current functionality is intentionally not exposed in screens. |

## 4. Current Document/Order-Assurance Workflow

### Upload And Seed

1. A user creates a bundle with `POST /bundles`; it begins with persisted review-oriented status defaults.
2. A user uploads a PDF through `POST /bundles/{id}/documents`. The server validates extension/content type/header and maximum bytes, stores the file, creates document metadata, and records `page_count` where readable.
3. Upload returns `DocumentRead` with document status `UPLOADED` and metadata status `PENDING`.
4. The deterministic demo path uses `POST /dev/seed-panimalar` or the seed script. It creates documents with seeded/manual metadata and immediately synchronizes the persisted bundle snapshot.

### Extraction

1. `POST /documents/{id}/extract` or `/re-extract` runs synchronously.
2. The service sets in-transaction document status `EXTRACTING` and metadata status `PENDING`.
3. Digital text is attempted first. Text below the configured threshold routes to OCR (`glm-ocr`) when enabled, otherwise to manual-entry-required failure.
4. Deterministic structured rules parse acquired text. Optional Model Layer 2 may fill unresolved fields only when enabled; it is disabled by default, cannot set verification state, and cannot override deterministic values.
5. Field metadata and optional field locations are stored in diagnostics. Digital extraction can produce page/bounding-box highlighting; OCR/manual extraction generally provides text evidence without exact coordinates.
6. On usable extraction, the response carries document `PENDING_REVIEW` and metadata `EXTRACTED`. A handled extraction failure still returns HTTP `200`, with document `EXTRACTION_FAILED` and metadata `FAILED` or `MANUAL_ENTRY`.

### Manual Metadata

1. The review form patches fields through `PATCH /documents/{id}/extracted-data`.
2. The backend allowlists fields per document type, requires a reason for high-impact fields, rejects blank critical references, and normalizes numeric input.
3. Manual fields receive `source="manual_entry"`, confidence `1.0`, and text evidence `"Manual entry"`.
4. If required manual fields remain missing for supported required-field cases, status remains `MANUAL_ENTRY`/`EXTRACTION_FAILED`. Otherwise metadata becomes `EXTRACTED` and document becomes `PENDING_REVIEW`.
5. Each patch creates an audit event containing field-level changes and the supplied reason.

### Reference Index

1. Extraction and manual correction both replace reference-index records for the affected document.
2. Reference records include value, field/document type, source provenance, confidence, and bounded evidence text.
3. The index is available in mutation responses and Excel export. There is no current UI read endpoint that lists reference index entries independently.

### Bundle Verification

1. `build_verification_summary` normalizes current document metadata into canonical customer invoice, delivery challan, vendor PO, vendor invoice, and customer PO forms.
2. `verify_order_bundle` performs matching, coverage, amount, and missing-document decisions.
3. Vendor invoice totals count against a vendor PO only when a proven `po_reference`, `customer_ref_no`, or `external_doc_no` matches that PO.
4. The freshly computed verification summary is authoritative. Persisted bundle statuses are updated only after extraction, re-extraction, manual patch, deletion, or seed.
5. The UI detail header uses summary status when present; the list uses the persisted status snapshot.

### Export

1. `GET /bundles/{id}/export.xlsx` computes a fresh summary and generates an XLSX response synchronously.
2. The workbook contains `Verification Summary`, `Documents`, `Checks`, `Extracted Fields`, `References`, and `Audit Trail`.
3. Export reads current state but does not update persisted status.
4. The frontend represents export only as local in-progress/success/error download state.

## 5. Current Data States

### Document And Extraction States

| Entity | Defined states | Observed transitions/meaning |
| --- | --- | --- |
| `DocumentRecord.status` | `UPLOADED`, `EXTRACTING`, `PENDING_REVIEW`, `EXTRACTION_FAILED`, `VERIFIED`, `REJECTED` | Upload creates `UPLOADED`; extraction sets transient `EXTRACTING`, then `PENDING_REVIEW` or `EXTRACTION_FAILED`; successful manual correction sets `PENDING_REVIEW`. No reviewed service sets `VERIFIED` or `REJECTED`. |
| `DocumentMetadataRecord.status` | `PENDING`, `EXTRACTED`, `FAILED`, `MANUAL_ENTRY` | Upload creates `PENDING`; extraction/manual patch resolves to `EXTRACTED`, `FAILED`, or `MANUAL_ENTRY`. |
| Diagnostic extraction outcome | `failure_code` may be null or include `TEXT_EXTRACTION_FAILED`, `OCR_EMPTY`, `OCR_FAILED`, `STRUCTURED_PARSE_FAILED`, `REQUIRED_FIELDS_MISSING`, `LOW_CONFIDENCE_EXTRACTION`, `MANUAL_ENTRY_REQUIRED` | Not a typed response model; drives document-card messaging and recovery guidance. |

`EXTRACTING` is set during a synchronous transaction and is not a dependable UI polling/progress state in the current request model.

### Verification States

| Scope | States | Source of truth |
| --- | --- | --- |
| Bundle | `OK`, `REVIEW_REQUIRED`, `MISMATCH`, `MISSING_DOCUMENTS`, `BLOCKED` | Computed `VerificationSummary.bundle_status`; persisted `OrderBundle.status` is a snapshot. |
| Customer delivery / vendor procurement sections | `PASS`, `PARTIAL_PASS`, `REVIEW_REQUIRED`, `MISMATCH`, `MISSING_DOCUMENTS`, `BLOCKED` | Computed summary fields; persisted bundle fields are snapshots. |
| Individual checks | Same result-style strings plus severity `INFO`, `WARNING`, `BLOCKER` in verifier output | Generated per summary; currently typed only as generic records in UI. |

### Manual Review States

There is no dedicated manual-review entity or completion status. The UI infers manual review from:

- `metadata.status === "MANUAL_ENTRY"`;
- `diagnostics.failure_code === "MANUAL_ENTRY_REQUIRED"` or another recoverable failure;
- the presence of a manual patch audit event; and
- post-patch `PENDING_REVIEW`/`EXTRACTED`, which still does not mean verified.

### Export States

There is no backend export state model. Export is synchronous:

| Layer | States |
| --- | --- |
| Backend | Response succeeds with XLSX; fails with `404` or `500`. |
| Frontend local UI | Idle, `isExporting=true`, download-started message, or error message. |

## 6. UI Redesign Constraints

### Reliable Backend Fields And Behaviors

- `VerificationSummary.bundle_status`, section statuses, checks, issues, and recommendation are the correct source for current verification decisions.
- Public `DocumentRead` deliberately excludes storage paths and raw extracted/OCR text.
- Document and metadata top-level statuses, filename/type/IDs, errors, timestamps, field location envelope, and manual audit-event creation are established contracts covered by tests.
- Manual corrections are server validated and normalized; reference provenance and amount/reference matching are tested server behaviors.
- Digital-field `field_locations` can support evidence highlighting when `page`, `bbox`, `page_width`, and `page_height` are present.

### Unstable Or Insufficiently Shaped Fields

- Persisted bundle status fields can be stale until a mutation synchronizes them.
- `diagnostics` is a runtime/debug-oriented dictionary whose keys vary by extraction route, flags, optional model behavior, and failures.
- `extracted_data` varies by document type and extraction path and currently lacks a discriminated frontend contract.
- `checks`, `issues`, `connections`, and `extracted_summary` are returned as generic records rather than stable UI contracts.
- OCR/manual field locations cannot be assumed to include a bounding box.
- Audit `actor` is supplied from the request and is not an authenticated user identity.
- OCR/model availability and accuracy depend on runtime settings/provider availability.

### Logic That Must Not Be Duplicated In The Frontend

- Required-field validation, allowed-field validation, numeric normalization, high-impact-reason enforcement, and critical-reference rejection.
- Canonical document/field alias normalization.
- Reference-index creation, replacement, provenance, and vendor-reference proof rules.
- Amount comparison, vendor billing coverage, match tolerance, name/ref matching, issue construction, recommendations, and all verification statuses.
- Extraction/OCR/model routing and any interpretation of confidence as business acceptance.
- Export composition and audit integrity.

### Current Frontend Assumptions That Are Wrong Or Unsafe For Redesign

| Current assumption/behavior | Why it is unsafe |
| --- | --- |
| Bundle list displays `bundle.status` as current outcome | Backend documents and tests state it is a persisted snapshot; only the computed summary is authoritative. |
| Any summary issue can be addressed by opening `documents[0]` | An issue may relate to a different document, several documents, or missing documents; the action is not issue-targeted. |
| Mutation responses can be ignored as `unknown` and followed only by full refresh | This discards reference/audit/diagnostic contracts and makes precise optimistic or targeted refresh behavior impossible. |
| Manual form fields represent all supported correction paths | Backend supports fields not shown by the form, including alternate vendor reference fields and additional normalized aliases. |
| A selected document's form remains valid after refresh | `ManualMetadataForm` initializes state once per document ID; refreshed metadata for the same selected document does not reset its input state. |
| Diagnostics are appropriate primary product UI state | They are implementation/runtime information, loosely shaped, and can change with extraction/provider configuration. |
| `actor: "frontend"` is meaningful audit identity | Auth/RBAC is deferred; this string identifies a caller label, not an accountable user. |
| Server-provided export filename is used | Current client forces `order-assurance-{bundleId}-verification-report.xlsx` instead of honoring response disposition. |

## 7. Recommended Redesign Architecture

These are architecture recommendations only. They should not be implemented until redesign requirements are approved.

### Proposed Routes

| Route | Responsibility |
| --- | --- |
| `/bundles` | Bundle queue/list with clearly labeled snapshot or server-supplied current status. |
| `/bundles/new` | Bundle creation flow if manual creation remains required. |
| `/bundles/:bundleId` | Bundle summary workspace driven by authoritative verification-summary data. |
| `/bundles/:bundleId/documents/:documentId` | Addressable document review, evidence, and manual correction surface. |

If separate URL routes are too large a first step, the minimum requirement is preserving selected bundle/document in URL state rather than only component memory.

### Proposed Component Boundaries

| Boundary | Responsibility |
| --- | --- |
| `BundleQueuePage` and `BundleCreateForm` | Listing/creation, separated from detail orchestration. |
| `BundleWorkspacePage` | Layout and resource composition only. |
| `BundleHeader` and `VerificationOverview` | Clearly display authoritative computed status and recommendation. |
| `VerificationChecksTable` and `IssuePanel` | Typed check/issue presentation; issue-to-document actions only where contract supports targeting. |
| `DocumentInventory` and `DocumentUploadForm` | Document collection, expected/received/review states, upload action. |
| `DocumentReviewPage` | Single-document load/mutation owner. |
| `DocumentEvidenceViewer` and `ExtractedFieldTable` | Optional bounding-box evidence and provenance without interpreting business validity. |
| `ManualCorrectionForm` | Schema-aligned edit form that renders server validation feedback and records a reason. |
| `AuditTimeline` and `ExportAction` | Audit history and download state separated from document editing. |

### Proposed API Client Modules And Types

Preserve the domain separation in `src/api`, but strengthen the contracts:

| Module | Recommendation |
| --- | --- |
| `api/client.ts` | Keep base URL/request/error handling; add structured API error parsing and request-ID retention. |
| `api/bundles.ts` | Keep list/get/create; represent persisted snapshot status explicitly in types. |
| `api/documents.ts` | Type `DocumentMutationResult`, preview capability, manual-patch errors, and document detail independently. |
| `api/verification.ts` | Define typed `VerificationCheck`, `VerificationIssue`, summary values, and any document linkage before richer issue UI. |
| `api/audit.ts` | Define manual-change event payload shape while allowing other event variants. |
| `api/export.ts` | Preserve binary download behavior; honor server filename where appropriate. |
| `types/contracts.ts` or generated schema layer | Eliminate duplicate/partial status/type definitions and distinguish stable fields from diagnostics. |

Backend contract additions should be considered before building a richer UI:

- A stable typed issue/check schema with affected document identifiers and applicable actions.
- A deliberate status freshness/snapshot contract for list screens, or a server endpoint that returns computed queue statuses.
- A manual-entry form/capability schema if UI fields must track backend allowlists and required/reason rules.
- Typed reference/provenance retrieval if references are to become an interactive UI surface.
- Authenticated actor identity before treating audit display as production accountability.

### Proposed State Boundaries

| State type | Owner |
| --- | --- |
| Bundle list/detail, documents, summary, and audit events | Server-state layer keyed by bundle/document ID, with invalidation after mutation. |
| Selected bundle/document and review location | URL/router state. |
| Selected field/highlight and expanded diagnostic panel | Local presentation state. |
| Manual form values, dirty state, validation messages, submission | Document-review form state; reset explicitly from accepted server response. |
| Export button in-flight state | Local action state; no backend export status exists today. |

### Preserve

- Existing backend ownership of extraction, normalization, verification, references, audit events, and XLSX generation.
- Summary-as-authority status model.
- Public serializer exclusion of raw text/storage paths.
- Manual fallback with auditable reasons and evidence/provenance display.
- Field highlighting only when supported by backend evidence location data.
- Existing endpoint behavior until an explicit contract migration is designed and tested.

### Replace Or Correct During Redesign

- In-memory page switch navigation with addressable routing.
- The monolithic detail-page resource/mutation orchestration with bounded screen components and typed state.
- Generic `Record<string, unknown>` consumption for verification/product-facing structures.
- First-document manual-entry navigation with issue-aware navigation or neutral document selection.
- Presentation of persisted snapshot status as authoritative current status.
- Diagnostic-detail-first presentation as the primary user workflow.
- Missing lint configuration and missing automated coverage for error/loading/navigation cases.

## 8. Test Baseline

Commands were executed from the repository workspace on 2026-05-25.

| Check | Command | Result |
| --- | --- | --- |
| Backend tests | `python -m pytest order-assurance/backend/tests -q` | Passed: `108 passed, 4 skipped in 15.75s`. |
| Frontend unit/component tests | `npm --prefix order-assurance/frontend test` | Passed: `9` test files, `15` tests. |
| Frontend typecheck/production build | `npm --prefix order-assurance/frontend run build` | Passed: `tsc && vite build`; Vite produced production assets. |
| Frontend lint | `npm --prefix order-assurance/frontend run lint` | Failed before linting: ESLint `8.57.1` could not find a configuration file. |
| Frontend E2E | `npm --prefix order-assurance/frontend run test:e2e` | Failed before UI assertions: both Playwright tests could not launch because the expected managed Chromium headless-shell executable is not installed. |

### Remaining Baseline Test Gaps

- Lint is declared but currently not operational.
- E2E behavior could not be revalidated in this environment without an installed Playwright browser or configured local Chromium path.
- Current component coverage does not protect bundle-create error handling, multi-request detail refresh failure behavior, issue-to-document navigation, manual form reset after refresh, or list-page snapshot/current-status semantics.

## Audit Conclusion

The current application already has a defensible backend separation: extraction, manual correction validation, reference provenance, verification, and export are backend responsibilities, and verification summary is explicitly authoritative. The redesign should build around those contracts rather than reconstruct business decisions in React.

The primary work to authorize before visual redesign is contract hardening: distinguish persisted versus computed status in list experiences, type the summary/mutation/issue contracts, establish issue-to-document navigation behavior, and decide whether manual-form capability metadata is a backend contract. The present UI should remain functionally unchanged until those decisions are made.
