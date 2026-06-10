# Order Assurance Phase 1 Architecture

The new app is isolated under `order-assurance/` and uses app-local imports only.

## Backend

- `app.domain`: enums and core `OrderBundle` type.
- `app.models`: persistence skeletons for order bundles, documents, metadata, reference index, and audit events.
- `app.services`: pure business services for normalization, verification, reference indexing, manual metadata patching, and audit creation.
- `app.services.extraction`: text acquisition and structured parsing modules.
- `app.api`: independent FastAPI skeleton.
- `app.migrations`: lightweight SQL migration runner for the independent schema.
- `app.services.file_cleanup_service`: local storage cleanup and retention helpers.

## Frontend

The frontend is a minimal Vite/React shell. Full workflow screens are intentionally deferred to Phase 2.

## Shared

Shared TypeScript enums and sample fixtures live in `shared/`.

## Deployment

`docker-compose.yml` runs only the new Order Assurance services:

- backend on port `8100`
- frontend on port `5180`
- Postgres on port `55432`
- local document storage volume

## Environment-Gated Dev Tools

`POST /api/dev/seed-panimalar` is available only when `APP_ENV=development` or `ENABLE_DEV_TOOLS=true`.
The script seed path remains available for local operations:

```powershell
cd order-assurance/backend
python -m app.scripts.seed_panimalar_demo
```

## Deferred Production Concerns

- Auth/RBAC is intentionally held for a later phase.
- Line-item description matching is not part of this application.
- ERP integration is not implemented.
