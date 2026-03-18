# DPP Project Task Sheet

---

## 2026-03-11

- Explored full codebase — models, services, API, extraction pipeline
- Identified cross-document validation gap (SO number never validated across documents)
- Designed SO Number Cross-Document Validation feature plan
- Designed Filter System Expansion plan (PO List + new Documents page)
- Designed Admin Console page plan

---

## 2026-03-16

- Implemented `PENDING_MODEL` document status
- Added pre-flight model/endpoint check to Celery extraction task
- New `POST /admin/requeue-pending-models` endpoint to re-queue held documents
- DB migration: added `PENDING_MODEL` to `documentstatus` enum

---

## 2026-03-17

### CI/CD Pipeline Setup
- Created multi-stage `backend/Dockerfile` (api + worker targets)
- Created `frontend/Dockerfile` (build + nginx runtime)
- Created `docker-compose.prod.yml` (6 services: postgres, redis, backend, worker×2, frontend, nginx)
- Created `nginx/nginx.conf` (reverse proxy: `/api/` → backend, `/` → frontend)
- Created `.github/workflows/deploy.yml` (push to DPP-2.3.0 → rsync + SSH deploy to Azure)
- Created `.github/workflows/test.yml` (pytest + vitest on PR to main)

### Azure VM Provisioned
- VM: Standard_D2as_v5 (2 vCPU, 8GB RAM, South India, ~$40/month)
- OS: Ubuntu 22.04 LTS
- Docker 29.3.0 + Compose v2 installed
- GitHub Actions SSH key configured

### Bugs Fixed
| Bug | Fix |
|---|---|
| `npm ci` failed — lockfile mismatch | Changed to `npm install` in frontend Dockerfile |
| Alembic initial migration crashed on fresh DB (tried to ALTER non-existent tables) | Rewrote `upgrade()` to CREATE all tables from scratch |
| `sa.Enum(create_type=False)` not respected by asyncpg — duplicate enum error | Switched to `postgresql.ENUM(create_type=False)` |
| Celery worker couldn't find `app.celery_app` module | Fixed path to `celery_app` |
| nginx 502 after container restarts (stale upstream) | `docker restart app-nginx-1` after each backend restart |
| `window.confirm` for document delete silently blocked by browser over HTTP | Replaced with custom confirmation modal |
| `OCR_BASE_URL` + `OCR_EXTRACTOR_BASE_URL` pointing to old RunPod endpoint | Updated both in `.env` on VM |

### Verified Working (Staging: http://20.198.16.146)
- All 6 Alembic migrations applied on fresh DB
- All containers healthy (postgres, redis, backend, worker×2, frontend, nginx)
- All pages load: Dashboard, Customers, Purchase Orders, PO Detail, Documents, Search, Admin
- All API endpoints: GET/POST customers, POs, documents, admin health/stats/queue
- Celery workers: both running, extraction pipeline live
- Health check: DB ✅ Redis ✅ Storage ✅ Ollama ✅ Models ✅
- CI/CD report saved at `docs/cicd-deployment-report.md`

---

## Pending / Next

- Update `STAGING_ENV` GitHub secret with correct RunPod URLs (currently fixed manually on VM)
- Full end-to-end extraction test with a real document
- Tier 1 UX fixes (pending review queue, chain status tooltip, re-extract confirmation, JPEG handling)
- SO Number cross-document validation implementation
- Admin Console page implementation
