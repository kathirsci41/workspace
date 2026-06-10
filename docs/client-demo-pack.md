# Client Demo Pack

## Official Extraction Strategy

The release-candidate demo uses deterministic extraction:

- digital PDF text extraction enabled
- structured rules enabled
- `glm-ocr:latest` for scanned or low-text OCR acquisition
- manual fallback when OCR fails or returns low-confidence text
- `gemma4:31b-cloud` structured Layer 2 available but disabled by default

This keeps demo behavior explainable: OCR acquires text only, structured rules extract fields, and the verifier alone decides bundle status. If OCR fails or fields remain incomplete, the workflow shows `Manual entry required`.

Optional Layer 2 is not part of the default demo decision path. When explicitly enabled during controlled tests, it proposes schema-limited fields with evidence only; deterministic fields win conflicts and Python verification remains the sole status authority.

Controlled Layer 2 validation accepts raw JSON or a single fenced JSON object with a recorded warning. It rejects prose/multiple objects and cannot use a model-proposed Vendor PO reference without field evidence.

## Docker Start

```powershell
cd order-assurance
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec backend python -m app.migrations.runner up
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec backend python -m app.scripts.seed_panimalar_demo
```

The base `docker-compose.yml` runs with `APP_ENV=production` and `ENABLE_DEV_TOOLS=false`. Use the dev override only for local demo seeding.

Open:

```text
http://127.0.0.1:5180
```

For Docker Desktop, the backend reaches local Ollama using:

```env
OCR_BASE_URL=http://host.docker.internal:11434
OCR_CONTEXT_LENGTH=8192
```

Use the application OCR path for demo validation. An unbounded standalone `ollama run glm-ocr:latest` request can select an oversized context on the tested workstation, while Order Assurance supplies the bounded OCR context explicitly.

## Panimalar Demo Flow

1. Start backend and frontend.
2. Seed Panimalar demo data.
3. Open the Panimalar bundle.
4. Confirm the verification summary:
   - bundle status: `REVIEW_REQUIRED`
   - customer delivery status: `PARTIAL_PASS`
   - vendor procurement status: `REVIEW_REQUIRED`
   - vendor PO total: `696200`
   - vendor invoice total: `554600`
   - difference: `141600`
5. Open document review to show manual metadata correction.
6. Export the verification report.

## What To Say

- Customer invoice and delivery challan references match.
- Customer PO is absent in the seeded demo, so customer delivery remains partial.
- Vendor invoice is linked to Vendor PO `1PTR2526000467`.
- Vendor invoice total `554600` does not fully cover Vendor PO total `696200`.
- The system recommends reviewing vendor-side partial billing before closure.
- Digital documents use embedded PDF text; scanned/low-text documents use `glm-ocr` only to acquire text.
- Manual correction is the recovery path when OCR is unavailable, returns no text, or structured fields remain missing.

## What Not To Claim

- Do not claim line-item description matching is solved.
- Do not claim OCR guarantees complete extraction of scanned documents.
- Do not claim model extraction is used in the release-candidate path.
- Do not claim any model determines `OK`, `REVIEW_REQUIRED`, `MISMATCH`, or `BLOCKED`.
- Do not claim Auth/RBAC is implemented.

## Export Expectations

The workbook contains:

- `Verification Summary`
- `Documents`
- `Checks`
- `Extracted Fields`
- `References`
- `Audit Trail`

The `Extracted Fields` sheet includes source, confidence, evidence, and failure reason columns. `References` shows reference provenance, and `Audit Trail` includes correction reasons and request IDs.

## Artifacts

- E2E screenshots: `tests/artifacts/order-assurance-e2e/screenshots/`
- E2E API captures: `tests/artifacts/order-assurance-e2e/api/`
- Docker validation notes: `order-assurance/docs/docker-demo-validation.md`

## Known Limitations

- Auth/RBAC is deferred.
- Representative real scanned-PDF regression coverage is incomplete until approved redacted fixtures are supplied.
- `glm-ocr` depends on a reachable Ollama runtime and may require manual recovery.
- Line-item description matching and ERP integration are intentionally excluded.
