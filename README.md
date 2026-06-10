# Order Assurance

Order Assurance is a new independent application extracted from the proven ODMP Order Bundle Verification MVP.

The app runs independently from the existing ODMP backend/frontend. It does not import old ODMP frontend pages, PO detail chain widgets, billing widgets, or validation-agent placeholders.

## Local Ports

- Backend: `8100`
- Docker backend: `8100`
- Frontend: `5180`

## Frontend Routes

- `/` redirects to `/bundles`
- `/bundles`
- `/bundles/:bundleId/overview`
- `/bundles/:bundleId/documents`
- `/bundles/:bundleId/extraction`
- `/bundles/:bundleId/extraction/:documentId`
- `/bundles/:bundleId/verification`
- `/bundles/:bundleId/issues`
- `/bundles/:bundleId/audit`
- `/bundles/:bundleId/exports`

`/bundles/:bundleId` is a compatibility redirect to the canonical overview route.

## Environment

Copy `.env.example` values into your local environment as needed:

```powershell
APP_ENV=production
ENABLE_DEV_TOOLS=false
LOG_LEVEL=INFO
LOG_FORMAT=text
DATABASE_URL=sqlite:///./order_assurance.db
DB_STARTUP_MAX_ATTEMPTS=30
DB_STARTUP_RETRY_SECONDS=2
STORAGE_DIR=storage/documents
MAX_UPLOAD_MB=20
FILE_RETENTION_DAYS=30
TEMP_FILE_RETENTION_HOURS=24
VITE_API_BASE_URL=http://127.0.0.1:8100/api
DIGITAL_TEXT_ENABLED=true
DIGITAL_TEXT_MAX_PAGES=10
OCR_ENABLED=true
OCR_PROVIDER=glm_ocr
OCR_MODEL=glm-ocr:latest
OCR_BASE_URL=http://localhost:11434
OCR_DPI=200
OCR_MAX_PAGES=5
OCR_TIMEOUT_SECONDS=90
OCR_RETRY_ATTEMPTS=1
OCR_MIN_TEXT_LENGTH=30
OCR_CONTEXT_LENGTH=8192
STRUCTURED_RULES_ENABLED=true
MODEL_LAYER2_ENABLED=false
MODEL_LAYER2_PROVIDER=ollama
MODEL_LAYER2_MODEL=gemma4:31b-cloud
MODEL_LAYER2_BASE_URL=http://localhost:11434
MODEL_LAYER2_TIMEOUT_SECONDS=120
MODEL_LAYER2_CONTEXT_LENGTH=8192
MODEL_LAYER2_RETRY_ATTEMPTS=1
VITE_DEBUG_LOGS=false
```

The development seed endpoint is available only when `APP_ENV=development` or `ENABLE_DEV_TOOLS=true`. The base Docker Compose file is production-safe by default; use `docker-compose.dev.yml` only for local demo/dev seeding.

## Implemented Scope

The current review/demo scope is locked in [`docs/current-scope-lock.md`](docs/current-scope-lock.md). Use that document as the boundary for what is in scope, out of scope, and allowed before review.

- Core domain object: `OrderBundle`
- Clean document/status enums
- Bundle/document APIs
- PDF upload and local file storage
- Synchronous extraction and re-extraction APIs
- Release-candidate extraction mode: digital text + glm-ocr text acquisition + structured rules + manual fallback
- Document normalization service
- Order bundle verifier service
- Structured text parser service
- Digital PDF text extractor service
- Reference index rebuild helper
- Audit event model/schema/service
- Manual extracted-data patch helper with audit event creation
- Excel verification report export
- Panimalar demo seed and E2E flow
- Cleanup runner for orphaned local files
- Docker Compose for local/demo deployment
- Panimalar expected fixture
- Minimal independent frontend workflow

## Run Backend

```powershell
cd order-assurance/backend
python -m app.migrations.runner up
python -m uvicorn app.main:app --host 127.0.0.1 --port 8100
```

## Run Frontend

```powershell
cd order-assurance/frontend
$env:VITE_API_BASE_URL="http://127.0.0.1:8100/api"
npm ci
npm run dev
```

## Run Without Docker

```powershell
cd order-assurance
.\scripts\run-local.ps1
```

The script runs migrations, starts the backend on `127.0.0.1:8100`, starts the frontend on
`127.0.0.1:5180`, and configures the frontend to call the backend through the local `/api` proxy.
Logs are written under `runtime/logs`. Press `Ctrl+C` in the script terminal to stop processes that
the script started.

Options:

```powershell
.\scripts\run-local.ps1 -InstallFrontendDeps
.\scripts\run-local.ps1 -SkipMigrations
.\scripts\run-local.ps1 -OpenBrowser
.\scripts\run-local.ps1 -Detach
```

Local development uses the absolute backend base URL above. The Docker frontend is built with
`VITE_API_BASE_URL=/api`; Nginx proxies `/api` to `backend:8100` and serves `index.html` for direct
SPA route requests.

If Windows cannot use the default npm cache or temp directory, point both at a writable drive before
running `npm ci`:

```powershell
$env:TEMP="E:\tmp"
$env:TMP="E:\tmp"
$env:NPM_CONFIG_CACHE="E:\tmp\npm-cache"
npm ci
```

## Migrations

```powershell
cd order-assurance/backend
python -m app.migrations.runner up
python -m app.migrations.runner down
```

`init_db()` remains available for tests and local development.

## Seed Demo Data

Script-based seed remains available even when HTTP dev tools are disabled:

```powershell
cd order-assurance/backend
python -m app.scripts.seed_panimalar_demo
```

Local development API seed:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8100/api/dev/seed-panimalar
```

## Test

```powershell
cd order-assurance/frontend
npm ci
npm run lint
npm test
npm run build
npm run test:e2e

cd ../backend
python -m pytest -q -p no:cacheprovider --basetemp=E:\tmp\pytest-order-assurance
```

## Docker Compose

```powershell
cd order-assurance
docker compose up --build
```

The PowerShell helper runs the same stack and verifies backend health:

```powershell
cd order-assurance
.\odmp.ps1 up -Build
```

Local demo/dev mode with the HTTP seed endpoint enabled:

```powershell
cd order-assurance
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Services:

- backend: `http://127.0.0.1:8100`
- frontend: `http://127.0.0.1:5180`
- database: local Postgres exposed on `15432`

The Compose backend uses `DATABASE_URL=postgresql+psycopg://order_assurance:order_assurance@database:5432/order_assurance`. Keep the host as the Compose service name `database`; do not use `localhost` from inside the backend container.
The backend container runs `python -m app.migrations.runner up` before starting Uvicorn. Running the
migration command again through `odmp.ps1` or `docker compose exec` remains safe because the current
initial migration uses `IF NOT EXISTS`.

Troubleshooting backend startup:

- Postgres has a healthcheck and the backend waits for `service_healthy`.
- Backend also retries the DB connection on startup using `DB_STARTUP_MAX_ATTEMPTS` and `DB_STARTUP_RETRY_SECONDS`.
- If the backend is unhealthy or restarting, inspect logs with:

```powershell
cd order-assurance
docker compose logs database backend
```

Health check:

```powershell
curl http://127.0.0.1:8100/api/health
```

## Manual Testing Logs

Backend logs include a lightweight structured event stream for manual testing. Every API response includes an `X-Request-ID` header; use that value to match a browser action to backend logs.

Defaults:

```env
LOG_LEVEL=INFO
LOG_FORMAT=text
```

Use JSON logs when machine parsing is useful:

```env
LOG_FORMAT=json
```

Follow backend and frontend logs in Docker:

```powershell
cd order-assurance
docker compose logs backend -f
docker compose logs frontend -f
```

Enable frontend debug console logs only during manual testing:

```powershell
$env:VITE_DEBUG_LOGS="true"
npm --prefix order-assurance/frontend run dev -- --host 127.0.0.1 --port 5180
```

Manual testing checklist:

1. Open browser DevTools Network tab and perform the action.
2. Copy the response `X-Request-ID`.
3. Search backend logs for that `request_id`.
4. For frontend action traces, enable `VITE_DEBUG_LOGS=true` and watch the browser console.

Logged backend events include bundle creation, document upload, extraction start/completion/failure, OCR and Model Layer 2 attempts, manual metadata patch, reference index rebuild, verification summary calculation, export start/completion/failure, and audit event creation. Logs include IDs, statuses, route names, failure codes, text lengths, counts, and durations. They intentionally do not include raw OCR text, full PDF text, file bytes, or full extracted document payloads.

## Extraction Strategy

Release-candidate defaults:

- `DIGITAL_TEXT_ENABLED=true`
- `STRUCTURED_RULES_ENABLED=true`
- `OCR_ENABLED=true`
- `OCR_PROVIDER=glm_ocr`
- `OCR_MODEL=glm-ocr:latest`
- `MODEL_LAYER2_ENABLED=false`

Digital PDFs are parsed through PyMuPDF text acquisition and deterministic structured rules. Scanned or low-text PDFs render pages to images and send those images to `glm-ocr:latest` for OCR text acquisition only. The OCR result is plain text; structured field extraction still happens in the parser layer, and verification still happens in the verifier.

For a local non-Docker backend:

```env
OCR_BASE_URL=http://localhost:11434
```

For a Docker backend calling host Ollama on Docker Desktop:

```env
OCR_BASE_URL=http://host.docker.internal:11434
```

If OCR is unavailable or returns no usable text, the UI labels this state as `Manual entry required` and the manual fallback remains the safe recovery path.

`OCR_CONTEXT_LENGTH=8192` is applied to each `glm-ocr` Ollama request. This avoids relying on an oversized server default that can fail during GPU model loading on constrained local systems. Provider errors remain recoverable through manual entry.

Model Layer 2 is configurable for later experiments with `gemma4:31b-cloud`, but it is disabled by default. If enabled, it receives document text and an allowed field schema only; deterministic fields take priority over model alternatives, and it must never decide verification status.

Layer 2 responses are accepted only as one validated JSON object. A single JSON code fence is tolerated with an explicit diagnostic warning because local gemma testing returned that format; prose, multiple objects, and unevidenced Vendor PO reference values are rejected. This hardening does not enable Layer 2 by default.

## Status Source Of Truth

The computed Verification Summary is authoritative. Persisted bundle statuses are snapshots refreshed only after mutations such as extraction, manual correction, document deletion, or demo seed. Read and export endpoints calculate current results without rewriting bundle rows. See [docs/status-model.md](docs/status-model.md).

## Cleanup

Dry run:

```powershell
cd order-assurance/backend
python -m app.scripts.cleanup_files --dry-run
```

Execute requires an explicit empty-DB safety override only if the database returns no referenced document paths:

```powershell
cd order-assurance/backend
python -m app.scripts.cleanup_files --execute
```

The cleanup runner never deletes files currently referenced by `bundle_documents.storage_path`. It refuses `--execute` when the known path set is empty unless `--allow-empty-known-paths` is passed intentionally.

## Playwright

Install browser:

```powershell
npm --prefix order-assurance/frontend run install:browsers
```

Run E2E:

```powershell
npm --prefix order-assurance/frontend run test:e2e
```

Troubleshooting: if the headless browser package fails to download but full Chromium is present, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE` to the local `chrome.exe` path before running E2E.

## Dependency Review

- Backend runtime dependencies are listed in [backend/Dockerfile](backend/Dockerfile) and [backend/pyproject.toml](backend/pyproject.toml).
- `npm audit` currently reports moderate vulnerabilities.
- Do not run force upgrades during demo prep; schedule dependency hardening separately.

## Known Limitations

- Auth/RBAC is intentionally deferred.
- Line-item description matching is intentionally deferred.
- ERP integration is intentionally deferred.
- OCR uses host Ollama with `glm-ocr:latest`; scanned/low-text documents still require manual entry if OCR is unavailable or low confidence.
