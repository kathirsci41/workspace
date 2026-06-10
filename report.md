# Order Assurance Application Smoke Check

Final verdict: **NO, not fully green**. The application is up, frontend-to-backend traffic is live, and the main order review, manual correction, export, recovery, and 404 flows work. The seeded Panimalar document preview fails with `404 Document preview not found`, so the full end-to-end smoke check is not completely passing.

## Commands And Runtime Notes

- Backend expected direct command from config:
  `cd order-assurance/backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8100`
- Backend was already running on `127.0.0.1:8100` via Docker Compose, so I did not start a second uvicorn process on the same port.
- Backend runtime command used for this check:
  `docker compose -f order-assurance/docker-compose.yml -f order-assurance/docker-compose.dev.yml ps`
- Backend restart command used for failure-mode recovery:
  `docker compose -f order-assurance/docker-compose.yml -f order-assurance/docker-compose.dev.yml up -d backend`
- Frontend expected command:
  `npm --prefix order-assurance/frontend run dev -- --host 127.0.0.1 --port 5180`
- Frontend was already serving on `127.0.0.1:5180`; I did not start a second Vite process.
- Build command:
  `npm --prefix order-assurance/frontend run build`
- Build result: PASS, `tsc && vite build` completed successfully.
- Browser used: Playwright with installed Microsoft Edge at `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`. Bundled Playwright Chromium was not installed, so no browser download was attempted.

## Part 1 - Backend Reachability

PASS - Backend and DB were running.

- Docker Compose showed `order-assurance-backend-1` up on `0.0.0.0:8100->8100` and `order-assurance-database-1` healthy on `15432->5432`.
- Backend restart after failure-mode test completed cleanly; logs showed `Application startup complete` and `Uvicorn running on http://0.0.0.0:8100`.

PASS - `GET /api/health`.

Status: `200 OK`

Response:

```json
{"status":"ok","service":"order-assurance","ocr":{"enabled":true,"provider":"glm_ocr","model":"glm-ocr:latest","reachable":true}}
```

PASS - `GET /api/bundles`.

- Before seeding: `200 OK`, JSON array with 6 bundles.
- After seeding: JSON array with 7 bundles.
- Seeded bundle used for the UI journey:
  `OA-PANIMALAR-DEMO-958a1dc6`, id `9884b491-8b8b-4fcb-9ecd-c548c2b86c59`, `computed_status=REVIEW_REQUIRED`.

PASS - API docs mounted.

- `GET /openapi.json` returned `200 OK`.
- OpenAPI included `/api/health`, `/api/bundles`, document, verification, audit, export, and dev seed routes.

## Part 2 - Demo Seed

PASS - Dev seed route was available.

- Compose dev override enables `APP_ENV=development` and `ENABLE_DEV_TOOLS=true`.
- `POST /api/dev/seed-panimalar` returned `201 Created`.

PASS - Seed result.

- Created bundle: `OA-PANIMALAR-DEMO-958a1dc6`.
- Seed response included 4 documents and a verification summary.
- Summary status: `REVIEW_REQUIRED`.
- Checks: 7.
- Issues: 2.

## Part 3 - Frontend Reachability

PASS - Frontend build.

- `npm --prefix order-assurance/frontend run build` completed successfully.

PASS - Frontend served.

- `GET http://127.0.0.1:5180/` returned `200 OK` and served the Vite app shell.

PASS - Orders queue rendered live data.

- Browser loaded `http://127.0.0.1:5180/`.
- Orders queue rendered row `OA-PANIMALAR-DEMO-958a1dc6`.
- Network captured live `GET http://127.0.0.1:8100/api/bundles` with `200`.
- This was real frontend-to-backend traffic, not mocked data.

Screenshot:

- `order-assurance/output/playwright/smoke-orders-queue.png`

## Part 4 - End-To-End UI Journey

PASS - Open order and Summary tab.

- Clicked `Open order` for `OA-PANIMALAR-DEMO-958a1dc6`.
- Network:
  - `GET /api/bundles/9884b491-8b8b-4fcb-9ecd-c548c2b86c59` -> `200`
  - `GET /api/bundles/9884b491-8b8b-4fcb-9ecd-c548c2b86c59/verification-summary` -> `200`
- Rendered verdict `REVIEW_REQUIRED`.
- Summary checks table rendered.
- Missing-document issue `CUSTOMER_PO_MISSING` had no dead document link.
- Existing-document issue `VENDOR_PARTIAL_BILLING_REVIEW_REQUIRED` linked to:
  `/orders/9884b491-8b8b-4fcb-9ecd-c548c2b86c59/documents/c9bc3e75-6e51-4157-adbc-87af05abbf87`

Screenshot:

- `order-assurance/output/playwright/smoke-summary.png`

PASS - Verification detail tab.

- Tab rendered expanded checks.
- Verified visible left/right values, reasons, severity, and rule ids.
- `INVOICE_DC_SO_MATCH` was visible.

Screenshot:

- `order-assurance/output/playwright/smoke-verification-detail.png`

PASS - Comparison tab.

- Matrix rendered.
- Banner rendered: `Quantity is not compared.`
- Reference checks and amount checks tables rendered.

Screenshot:

- `order-assurance/output/playwright/smoke-comparison.png`

PASS - Documents tab.

- Document list rendered 4 seeded documents.
- Network had `GET /api/bundles/{id}/documents` with `200` during the order page load.

Screenshot:

- `order-assurance/output/playwright/smoke-documents.png`

FAIL - Document review preview.

- Document review page itself rendered.
- Network:
  - `GET /api/documents/4ae630a0-8525-406c-b320-d4b4ec2e4ea0` -> `200`
- Extracted fields rendered with 8 confidence badges.
- Manual-source badges rendered after correction.
- Preview failed for the seeded Panimalar document:
  - `GET /api/documents/4ae630a0-8525-406c-b320-d4b4ec2e4ea0/preview` -> `404`
  - Response body: `{"detail":"Document preview not found"}`
  - `GET /api/documents/4ae630a0-8525-406c-b320-d4b4ec2e4ea0/preview/pages/1.png` -> `404`
- Additional probe showed every freshly seeded Panimalar document preview returned `404`.
- Existing stored-file documents under bundle `SF001` did return preview `200`, so the preview service is reachable; the failure appears to be missing stored preview/source files for the Panimalar seed records.

Screenshot:

- `order-assurance/output/playwright/smoke-document-review.png`

PASS - Manual correction with reason.

- Edited `invoice_date` through the UI.
- Sent reason: `smoke check manual correction`.
- Network:
  - `PATCH /api/documents/4ae630a0-8525-406c-b320-d4b4ec2e4ea0/extracted-data` -> `200`
  - `GET /api/bundles/9884b491-8b8b-4fcb-9ecd-c548c2b86c59/verification-summary` -> `200`
- Response updated `invoice_date` to `13/02/2026 SMOKE 653134`.
- UI showed `Corrections saved`.
- Correction reason field reset to empty.
- Field data showed `extraction_source: manual_entry`.
- Manual badge became visible.

PASS - Export.

- Clicked `Export XLSX`.
- Network:
  - `GET /api/bundles/9884b491-8b8b-4fcb-9ecd-c548c2b86c59/export.xlsx` -> `200`
- Browser download suggested filename:
  `OA-PANIMALAR-DEMO-958a1dc6-verification-report.xlsx`
- Response header:
  `Content-Disposition: attachment; filename="OA-PANIMALAR-DEMO-958a1dc6-verification-report.xlsx"`

## Part 5 - Reachability And Failure Modes

PASS - Backend stopped, frontend showed error.

Command:

`docker compose -f order-assurance/docker-compose.yml -f order-assurance/docker-compose.dev.yml stop backend`

Evidence:

- `curl http://127.0.0.1:8100/api/health` failed with connection refused.
- Browser reload of `http://127.0.0.1:5180/orders` showed alert text: `Failed to fetch`.
- Loading indicator was not stuck.
- Failed browser requests:
  - `GET http://127.0.0.1:8100/api/bundles net::ERR_CONNECTION_REFUSED`

Screenshot:

- `order-assurance/output/playwright/smoke-backend-down.png`

PASS - Backend restarted and frontend recovered.

Command:

`docker compose -f order-assurance/docker-compose.yml -f order-assurance/docker-compose.dev.yml up -d backend`

Evidence:

- `GET /api/health` returned `200 OK`.
- Browser reload of `/orders` captured `GET /api/bundles` -> `200`.
- Orders queue table rendered again.
- No alert was visible.

Screenshot:

- `order-assurance/output/playwright/smoke-recovery.png`

PASS - Bad bundle URL.

- Loaded `http://127.0.0.1:5180/orders/00000000-0000-0000-0000-000000000000`.
- Network:
  - `GET /api/bundles/00000000-0000-0000-0000-000000000000` -> `404`
- UI header rendered `Order not found`.
- `Loading order...` was not visible.

Screenshot:

- `order-assurance/output/playwright/smoke-bad-bundle.png`

PASS - CORS and export filename exposure.

Cross-origin export probe with `Origin: http://127.0.0.1:5180` returned:

- `HTTP/1.1 200 OK`
- `access-control-allow-origin: http://127.0.0.1:5180`
- `access-control-expose-headers: Content-Disposition`
- `content-disposition: attachment; filename="OA-PANIMALAR-DEMO-958a1dc6-verification-report.xlsx"`

The browser download filename matched the server-provided filename, confirming the frontend can read `Content-Disposition`.

## Issues Found

1. Seeded Panimalar document previews are missing.
   - Observed: `GET /api/documents/{panimalar_doc_id}/preview` -> `404 Document preview not found`.
   - Impact: Document review fields and correction work, but the PDF preview portion of the review screen cannot display for the seeded Panimalar order.
   - Scope: Existing stored-file documents such as bundle `SF001` return preview `200`, so this appears tied to seed/storage data rather than frontend routing or CORS.
   - No code change was made.

## Artifacts

- Browser result JSON:
  `order-assurance/output/playwright/smoke-main-results.json`
- Screenshots:
  - `order-assurance/output/playwright/smoke-orders-queue.png`
  - `order-assurance/output/playwright/smoke-summary.png`
  - `order-assurance/output/playwright/smoke-verification-detail.png`
  - `order-assurance/output/playwright/smoke-comparison.png`
  - `order-assurance/output/playwright/smoke-documents.png`
  - `order-assurance/output/playwright/smoke-document-review.png`
  - `order-assurance/output/playwright/smoke-backend-down.png`
  - `order-assurance/output/playwright/smoke-recovery.png`
  - `order-assurance/output/playwright/smoke-bad-bundle.png`

## App-Code Changes

None. This check only created the requested smoke report and Playwright evidence artifacts.
