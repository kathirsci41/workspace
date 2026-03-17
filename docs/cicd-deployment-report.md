# CI/CD Deployment Report — DPP v2.3.0 Staging

**Date:** 2026-03-17
**Branch:** `DPP-2.3.0`
**Target:** Azure VM — `20.198.16.146` (Standard_D2as_v5, South India)
**Final Status:** ✅ Deployed and verified

---

## Infrastructure Summary

| Component | Details |
|---|---|
| Cloud | Microsoft Azure |
| VM Size | Standard_D2as_v5 (2 vCPU, 8 GB RAM) |
| Region | South India |
| OS | Ubuntu 22.04 LTS |
| Docker | 29.3.0 |
| Docker Compose | v2.x (plugin) |
| Estimated Cost | ~$40.59/month ($0.0556/hr) |

---

## Architecture Deployed

```
Internet → nginx (port 80)
              ├── /api/*  → backend (FastAPI, port 8000)
              └── /*      → frontend (React + nginx, port 80)

backend → PostgreSQL 16 (container)
backend → Redis 7 (container)
worker  → PostgreSQL + Redis (2 Celery replicas)
```

---

## CI/CD Pipeline

### Trigger
- **Deploy:** Push to `DPP-2.3.0` branch → `.github/workflows/deploy.yml`
- **Tests:** PR/push to `main` → `.github/workflows/test.yml`

### Deploy Steps
1. Checkout code
2. Set up SSH key from GitHub Secret
3. `rsync` files to `/home/azureuser/app/` on VM (excludes `.git`, `node_modules`, `venv`, `.env`)
4. SSH into VM → write `.env` from GitHub Secret → `docker compose -f docker-compose.prod.yml up -d --build`

### GitHub Secrets Required
| Secret | Purpose |
|---|---|
| `STAGING_SSH_KEY` | SSH private key for VM access |
| `STAGING_HOST` | VM public IP (`20.198.16.146`) |
| `STAGING_USER` | VM username (`azureuser`) |
| `STAGING_ENV` | Full `.env` file contents |

---

## Errors Encountered & Fixes

### 1. VM Size Not Available
| | |
|---|---|
| **Error** | `B2ms` size not available in South India region |
| **Cause** | Microsoft capacity constraints in that region for B-series VMs |
| **Fix** | Used `Standard_D2as_v5` (2 vCPU, 8 GB) — same cost range, general purpose |

---

### 2. `npm ci` Failed — Lockfile Mismatch
| | |
|---|---|
| **Error** | `npm ci` failed: `package-lock.json` missing `esbuild@0.27.4` |
| **Cause** | `package-lock.json` was generated with a different npm version; `node:20-slim` npm disagreed on the lockfile |
| **Fix** | Changed `npm ci` → `npm install` in `frontend/Dockerfile` |

---

### 3. Container Name Conflict on Restart
| | |
|---|---|
| **Error** | `container name /app-redis-1 is already in use` |
| **Cause** | Previous failed `docker compose up` left containers in a stopped state |
| **Fix** | `docker compose down` before `docker compose up` on subsequent deploys |

---

### 4. Alembic Migration Crash — Legacy Table Drops (Attempt 1)
| | |
|---|---|
| **Error** | `ProgrammingError: index "ix_users_email" does not exist` |
| **Cause** | The initial migration (`6e44882e6975`) was auto-generated as a diff against an old v1 database. Its `upgrade()` began by dropping `users` and `audit_logs` tables that don't exist on a fresh install |
| **Fix** | Wrapped the legacy DROP operations in `sa.inspect()` existence checks |

---

### 5. Alembic Migration Crash — Duplicate Enum Types (Attempt 2)
| | |
|---|---|
| **Error** | `ProgrammingError: type "postatus" already exists` |
| **Cause** | The first fix partially ran and created enum types before crashing on table creation. On the second run, `sa.Enum(create_type=False)` was not respected by the asyncpg driver — SQLAlchemy still tried to emit `CREATE TYPE` |
| **Fix** | Replaced `sa.Enum(create_type=False)` with `postgresql.ENUM(create_type=False)` (PostgreSQL dialect-specific type). Completely rewrote `upgrade()` to `CREATE TABLE` from scratch with idempotent `DO $$ BEGIN ... EXCEPTION WHEN duplicate_object THEN NULL; END $$;` guards for enum types. Wiped the partial DB state with `docker compose down -v` before re-running |

---

## Final Verification

```
GET http://20.198.16.146/api/v1/admin/health
```

```json
{
  "database": "ok",
  "redis": "ok",
  "ollama": "error: HTTP 404 from https://4exl6si9w8v02w-11434.proxy.runpod.net",
  "models": "missing: ['glm-ocr:latest', 'qwen2.5:7b']",
  "storage": "ok"
}
```

| Service | Status | Note |
|---|---|---|
| Database | ✅ ok | All 6 migrations applied successfully |
| Redis | ✅ ok | |
| Storage | ✅ ok | |
| Ollama / Models | ⚠️ expected | RunPod endpoint is stopped — start pod to enable extraction |

**Application accessible at:** `http://20.198.16.146`

---

## Migration Chain Applied (Fresh DB)

```
6e44882e6975  initial schema — CREATE all tables
a1b2c3d4e5f6  add COMPANY_PO, remove POD from documenttype enum
phase7_versioning  add extraction_version, field_confidences; create extraction_corrections
ff989461aa4f  add extraction_route to document_metadata
a3f1c9b2e7d4  add so_number to purchase_orders
b4c2d8e1f0a9  add PENDING_MODEL to documentstatus enum
```
