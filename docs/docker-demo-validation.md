# Docker Demo Validation

Date: 2026-05-22

## Scope

Clean Docker validation for the independent Order Assurance app only. Existing ODMP backend/frontend were not touched.

## Commands Run

```powershell
docker compose -f order-assurance/docker-compose.yml down -v
docker compose -f order-assurance/docker-compose.yml up --build -d
docker compose -f order-assurance/docker-compose.yml exec -T backend python -m app.migrations.runner up
docker compose -f order-assurance/docker-compose.yml exec -T backend python -m app.scripts.seed_panimalar_demo
curl.exe http://127.0.0.1:8100/api/health
python -m pytest order-assurance/backend/tests -q
```

Browser validation was run against `http://127.0.0.1:5180` with Playwright using the local Chromium executable workaround documented in the project notes.

## Validation Result

Passed after fixing two Docker-demo blockers:

1. Docker seed fixture lookup failed because the backend image stores copied shared fixtures at `/app/shared`, while the seed service only searched the local source-tree parent path.
2. Excel export failed in Docker/Postgres because timezone-aware audit timestamps were written directly to openpyxl cells.

## Health

`curl.exe http://127.0.0.1:8100/api/health` returned:

```json
{"status":"ok","service":"order-assurance"}
```

## Seeded Bundle

Bundle ID: `bd631e21-02cf-49ed-bd75-7f68f345a64a`

The seeded bundle appeared in the frontend bundle list and opened successfully.

## Verification Summary

Expected values confirmed:

- bundle_status: `REVIEW_REQUIRED`
- customer_delivery_status: `PARTIAL_PASS`
- vendor_procurement_status: `REVIEW_REQUIRED`
- difference: `141600`

## UI Checks

Confirmed in Docker-run frontend:

- Bundle list loads.
- Seeded Panimalar bundle appears.
- Bundle detail opens.
- Verification summary appears.
- Diagnostics panel appears on document cards.
- Audit section appears.
- Document review/manual metadata area opens.
- Export button downloads workbook.

## Excel Export

Downloaded workbook: `tests/artifacts/order-assurance-docker-demo/api/verification-report.xlsx`

Required sheets confirmed:

- Verification Summary
- Documents
- Checks
- Extracted Fields
- Audit Trail

Export inspection artifact: `tests/artifacts/order-assurance-docker-demo/api/export-inspection.json`

## Screenshots

Screenshots saved under:

`tests/artifacts/order-assurance-docker-demo/screenshots/`

Files:

- `01-bundle-list.png`
- `02-bundle-detail.png`
- `03-verification-summary.png`
- `04-diagnostics-panel.png`
- `05-audit-section.png`
- `06-document-review.png`
- `07-export-success.png`

## API Artifacts

Saved under:

`tests/artifacts/order-assurance-docker-demo/api/`

Files:

- `bundles.json`
- `bundle.json`
- `documents.json`
- `verification-summary.json`
- `audit-events.json`
- `verification-report.xlsx`
- `export-inspection.json`

## Test Result

Backend tests:

`25 passed, 1 skipped`

The skipped test is the real/redacted PDF regression test, which skips when local real PDFs are not present.

## Notes

The clean Docker validation started from `docker compose down -v`, rebuilt containers, ran migrations, seeded Panimalar, validated UI behavior, and inspected the downloaded workbook.
