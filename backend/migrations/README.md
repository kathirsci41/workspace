# Order Assurance Migrations

Lightweight SQL migrations for the independent Order Assurance backend.

Run from `order-assurance/backend`:

```powershell
python -m app.migrations.runner up
python -m app.migrations.runner down
```

The runner uses `ORDER_ASSURANCE_DATABASE_URL`, defaulting to `sqlite:///./order_assurance.db`.
