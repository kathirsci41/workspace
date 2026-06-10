# Order Assurance Demo Handoff

## Start Locally

Backend:

```powershell
cd order-assurance/backend
$env:LOG_LEVEL="INFO"
$env:LOG_FORMAT="text"
python -m app.migrations.runner up
python -m uvicorn app.main:app --host 127.0.0.1 --port 8100
```

Frontend:

```powershell
npm --prefix order-assurance/frontend install
$env:VITE_API_BASE_URL="http://127.0.0.1:8100/api"
$env:VITE_DEBUG_LOGS="true"
npm --prefix order-assurance/frontend run dev -- --host 127.0.0.1 --port 5180
```

Docker:

```powershell
cd order-assurance
docker compose up --build
```

Docker local demo/dev mode with the HTTP seed endpoint enabled:

```powershell
cd order-assurance
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Follow logs during manual testing:

```powershell
docker compose logs backend -f
docker compose logs frontend -f
```

Every backend API response has an `X-Request-ID` header. When a manual test action behaves unexpectedly, copy that header from the browser Network tab and find the matching `request_id` in backend logs. With `VITE_DEBUG_LOGS=true`, frontend actions such as upload, extraction, manual patch, export, and verification refresh are also printed in the browser console.

## Seed Panimalar Demo

Script:

```powershell
cd order-assurance/backend
python -m app.scripts.seed_panimalar_demo
```

Development API:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8100/api/dev/seed-panimalar
```

The HTTP seed endpoint is disabled in the base Compose file because it runs with `APP_ENV=production` and `ENABLE_DEV_TOOLS=false`. Use the dev override above or the script-based seed for local demos.

## Expected Statuses

- Bundle: `REVIEW_REQUIRED`
- Customer delivery: `PARTIAL_PASS`
- Vendor procurement: `REVIEW_REQUIRED`
- Vendor PO total: `696200`
- Vendor invoice total: `554600`
- Difference: `141600`
- Recommendation: `Review vendor-side partial billing before closure.`

## Talking Points

- Official extraction strategy for the release candidate is digital text extraction, `glm-ocr:latest` OCR text acquisition for scanned/low-text PDFs, and deterministic structured rules.
- Scanned or low-text documents still have manual fallback when OCR fails or misses required fields.
- Model Layer 2 is configurable but disabled by default and is not used for business validation.
- Invoice and DC references match.
- Customer PO is missing in the seeded demo, so customer delivery is partial rather than final pass.
- Vendor bill is linked to the Vendor PO but only partially covers it.
- Manual extracted data is supported and audited.
- Verification summary is read-only; manual edits live in document review.

## Screenshots

Screenshots are written under:

```text
tests/artifacts/order-assurance-e2e/screenshots/
```

Expected files:

- `bundle-list.png`
- `bundle-detail.png`
- `verification-summary.png`
- `document-card.png`
- `manual-metadata-form.png`
- `export-success.png`

## Export Report

Click `Export Verification Report` from the bundle detail page.

Expected workbook sheets:

- `Verification Summary`
- `Documents`
- `Checks`
- `Extracted Fields`
- `References`
- `Audit Trail`

The `Extracted Fields` sheet includes extraction source, confidence, and evidence columns. The `References` sheet identifies which references were extracted or entered manually. `Audit Trail` includes correction reason and request ID.

## Known Limitations

- Auth/RBAC is intentionally deferred.
- Line-item description matching is intentionally deferred.
- ERP integration is intentionally deferred.
- OCR uses host Ollama with `glm-ocr:latest`; scanned/low-text documents use manual entry if OCR is unavailable or incomplete.
