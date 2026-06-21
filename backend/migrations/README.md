# Order Assurance Migrations

Lightweight SQL migrations for the independent Order Assurance backend.

## Location

- SQL files live in `order-assurance/backend/migrations`.
- Runtime code lives in `order-assurance/backend/app/migrations/runner.py`.
- The runner reads `DATABASE_URL`; `ORDER_ASSURANCE_DATABASE_URL` remains a backward-compatible fallback through the app configuration.
- The default local database is `sqlite:///./order_assurance.db` when commands are run from `order-assurance/backend`.

## Run

Run from `order-assurance/backend`:

```powershell
python -m app.migrations.runner up
python -m app.migrations.runner down
```

`up` creates `_migrations`, applies pending `*.sql` files in filename order, and skips files already recorded in `_migrations`.

`down` executes `001_initial_schema_down.sql` and drops `_migrations` so a later `up` can rebuild the schema from scratch.

Docker Compose runs `python -m app.migrations.runner up` before starting Uvicorn.

## Adding A Migration

1. Add a new numbered SQL file, for example `003_add_new_table.sql`.
2. Keep statements idempotent where practical, especially for demo and Docker reruns.
3. Add or update migration tests under `backend/tests/integration/test_migrations.py`.
4. Run:

```powershell
cd order-assurance/backend
python -m pytest tests/integration/test_migrations.py -q
```
