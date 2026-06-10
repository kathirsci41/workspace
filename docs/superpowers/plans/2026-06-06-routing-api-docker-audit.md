# Routing, API, and Docker Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing Build 1 frontend routes, API URL construction, and Docker startup/proxy behavior match the backend contracts without adding product features.

**Architecture:** Keep FastAPI's `/api` prefix and existing request/response contracts unchanged. Canonicalize React workspace routes under `/bundles/:bundleId`, normalize API base URL joining in one client helper, and serve the Docker frontend through Nginx with same-origin `/api` proxying and SPA fallback.

**Tech Stack:** React Router, TypeScript, Vitest, Playwright, FastAPI, Nginx, Docker Compose.

---

### Task 1: Canonical frontend workspace routes

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/ExtractionReviewPage.tsx`
- Modify: `frontend/src/pages/BundlesPage.tsx`
- Modify: `frontend/src/components/bundles/BundleTable.tsx`
- Modify: `frontend/src/components/layout/WorkflowTabs.tsx`
- Modify: bundle-scoped links in pages/components/helpers
- Test: `frontend/src/App.test.tsx`
- Test: `frontend/e2e/*.spec.ts`

- [ ] Add failing assertions for `/bundles/:bundleId/overview` and `/bundles/:bundleId/extraction/:documentId`.
- [ ] Verify current tests fail because overview and document extraction use legacy URLs.
- [ ] Render overview at `/overview`, redirect `/bundles/:bundleId` to it, and add the document extraction route.
- [ ] Replace query-string document links with the path parameter and keep the base extraction route.
- [ ] Run `npm test` and the focused E2E suite.

### Task 2: Centralized API URL normalization

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/documents.ts`
- Modify: `frontend/src/api/export.ts`
- Create: `frontend/src/api/client.test.ts`

- [ ] Add failing tests proving host-only, trailing-slash, `/api`, and accidental `/api/...` paths produce one `/api` segment.
- [ ] Add `normalizeApiBaseUrl` and `apiUrl` helpers.
- [ ] Route JSON, upload, delete, preview, and export URLs through `apiUrl`.
- [ ] Keep local default `http://127.0.0.1:8100/api`.
- [ ] Run API unit tests.

### Task 3: Docker Nginx and backend startup

**Files:**
- Create: `frontend/nginx.conf`
- Modify: `frontend/Dockerfile`
- Modify: `backend/Dockerfile`
- Modify: `docker-compose.yml`

- [ ] Add Nginx `/api/` proxy to `backend:8100` and `try_files $uri $uri/ /index.html`.
- [ ] Build Docker frontend with `VITE_API_BASE_URL=/api`.
- [ ] Run the idempotent migration runner before Uvicorn in the backend container.
- [ ] Validate with `docker compose config` and Docker build/up when available.

### Task 4: Start and handoff documentation

**Files:**
- Modify: `README.md`
- Modify: `.env.example` only if the local default is incorrect.

- [ ] Document canonical frontend routes and local/Docker API base behavior.
- [ ] Keep local backend command `python -m uvicorn app.main:app --host 127.0.0.1 --port 8100`.
- [ ] Keep migration command `python -m app.migrations.runner up`.
- [ ] Document that Docker runs migrations before Uvicorn.

### Task 5: Full verification

**Files:**
- No production changes.

- [ ] Run `npm ci`.
- [ ] Run `npm run lint`.
- [ ] Run `npm test`.
- [ ] Run `npm run build`.
- [ ] Run `npm run test:e2e`.
- [ ] Run backend `python -m pytest`.
- [ ] Run API smoke checks for health, bundles, documents, preview page, verification, audit, and XLSX.
- [ ] Report exact route/endpoint tables, changed files, base URL behavior, results, and remaining risks.
