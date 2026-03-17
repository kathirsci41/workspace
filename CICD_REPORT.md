# CI/CD Deployment Report — DPP v2.3.0
**Date:** 2026-03-17
**Target:** Azure VM (dpp-staging-vm) — `20.198.16.146`
**Branch:** `DPP-2.3.0` → `kathirsci41/workspace`

---

## Summary

Successfully deployed DPP v2.3.0 to Azure staging environment.
All 6 services running: `postgres`, `redis`, `backend`, `worker`, `frontend`, `nginx`.
Application accessible at `http://20.198.16.146`.

---

## Infrastructure Setup

| Component | Choice | Reason |
|-----------|--------|--------|
| Cloud | Microsoft Azure | Existing account |
| VM Size | Standard_D2as_v5 (2 vCPU, 8GB RAM) | B2ms unavailable in South India |
| OS | Ubuntu 22.04 LTS | Stable, Docker-compatible |
| Region | South India | Lowest latency for India-based users |
| Cost | ~$40.59/month | Pay-as-you-go |
| Model Endpoint | RunPod (remote) | GPU too expensive on Azure (~$350+/month) |
| Database | PostgreSQL in Docker (staging) | Managed Azure DB reserved for production |

---

## Difficulties Encountered

---

### Issue 1 — Azure VM Size Not Available

**Error:**
```
Size not available: Standard_B2ms in South India region
```

**Cause:**
Azure B-series (burstable) VMs have limited availability in the South India region.
B2ms was the initially planned size.

**Fix:**
Switched to `Standard_D2as_v5` — same specs (2 vCPU, 8GB RAM), general purpose series,
available in South India at a lower cost ($40.59/month vs $65/month estimated for B2ms).

---

### Issue 2 — GitHub Actions SSH Heredoc Failed Silently

**Error:**
Deploy workflow showed "Success" in 6 seconds but no containers were running on the VM.

**Cause:**
The `.env` file was being written inside a nested heredoc over SSH:
```yaml
ssh ... << 'ENDSSH'
  cat > .env << 'ENDENV'
  ${{ secrets.STAGING_ENV }}
  ENDENV
  docker compose up -d --build
ENDSSH
```
GitHub Actions does not expand `${{ secrets.* }}` variables inside single-quoted heredocs
passed over SSH. The inner heredoc wrote an empty `.env`, and the SSH session exited
silently before `docker compose up` completed.

**Fix:**
Split into two separate steps:
1. Write `.env` locally on the GitHub Actions runner using `echo "${{ secrets.STAGING_ENV }}" > .env`
2. Let `rsync` copy it to the VM along with the rest of the files
3. Run `docker compose up` in a clean separate SSH step

---

### Issue 3 — .env File Written to Wrong Location

**Error:**
```
docker compose -f docker-compose.prod.yml ps
NAME    IMAGE    COMMAND    SERVICE    CREATED    STATUS    PORTS
(empty — no containers)
```

**Cause:**
The `STAGING_ENV` GitHub Secret was created before the deploy workflow fix.
During the first manual test, `cat /home/azureuser/app/.env` showed the file existed,
but an earlier `cd ..` caused confusion — the file was actually in the correct location
`/home/azureuser/app/.env` all along.

**Fix:**
No fix needed — `.env` was already in the correct location.
The real problem was the SSH heredoc issue (Issue 2) preventing `docker compose up`
from running at all.

---

### Issue 4 — Frontend Docker Build Failed: `npm ci` Lock File Mismatch

**Error:**
```
npm error code EUSAGE
npm error `npm ci` can only install packages when your package.json and
package-lock.json are in sync.
npm error Missing: esbuild@0.27.4 from lock file
```

**Cause:**
`npm ci` requires `package-lock.json` to be exactly in sync with `package.json`.
The lock file was generated with a different version of npm locally (newer) than
what ships in the `node:20-slim` Docker image. The `esbuild@0.27.4` package was
present in `package.json` but missing from the lock file as seen by the Docker npm version.

**Fix:**
Changed `npm ci` to `npm install` in `frontend/Dockerfile`:
```dockerfile
# Before
RUN npm ci

# After
RUN npm install
```
`npm install` is more forgiving of lock file version differences.

---

### Issue 5 — Frontend Dockerfile Not Updated on VM After Push

**Error:**
Even after pushing the `npm install` fix to GitHub and the Actions workflow syncing files,
the VM still ran `npm ci` and failed.

**Cause:**
The GitHub Actions `rsync` step was completing in 4 seconds — too fast to have actually
transferred files. The SSH heredoc issue (Issue 2) meant the workflow "succeeded" without
properly running `docker compose`. Docker was using its cached layer from the previous
build where `npm ci` was still in the Dockerfile.

**Fix:**
Manually patched the Dockerfile directly on the VM:
```bash
sed -i 's/npm ci/npm install/' /home/azureuser/app/frontend/Dockerfile
```
Then triggered `docker compose up --build` manually.

---

### Issue 6 — TypeScript Build Errors

**Errors:**
```
src/api/documents.ts(2,25): error TS6196: 'DocumentStatus' is declared but never used.
src/pages/DocumentsPage.tsx(206,118): error TS2339: Property 'filename' does not exist on type 'Document'.
src/pages/DocumentsPage.tsx(207,51): error TS2339: Property 'filename' does not exist on type 'Document'.
```

**Cause:**
1. `DocumentStatus` was imported in `documents.ts` but never actually used in that file.
2. `DocumentsPage.tsx` referenced `doc.filename` as a fallback, but the `Document` TypeScript
   interface only defines `original_filename` — `filename` is a backend-only internal field
   not exposed in the frontend type definition.

These errors do not surface locally because `vite dev` does not enforce strict TypeScript
checking during development. The production build (`tsc && vite build`) runs full type
checking and fails on these.

**Fix:**
```typescript
// documents.ts — removed unused import
import type { Document } from '@/types';  // removed DocumentStatus

// DocumentsPage.tsx — replaced missing property with fallback
// Before: doc.original_filename ?? doc.filename
// After:  doc.original_filename ?? '—'
```

---

### Issue 7 — Docker Container Name Conflict on Restart

**Error:**
```
Error response from daemon: Conflict. The container name "/app-redis-1" is already in
use by container "2d58e6a462bf...". You have to remove (or rename) that container to
be able to reuse that name.
```

**Cause:**
A previous partially failed `docker compose up` run had created and started the `redis`
container before the overall compose command failed. Running `docker compose up` again
tried to create a new container with the same name while the old one was still registered
(even though it wasn't fully running as part of a compose stack).

**Fix:**
```bash
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```
`down` removes all containers and the network cleanly. Subsequent `up` had no conflicts.

---

## Final State

```
docker compose -f docker-compose.prod.yml ps

NAME              STATUS          PORTS
app-postgres-1    Up (healthy)    5432/tcp
app-redis-1       Up (healthy)    6379/tcp
app-backend-1     Up              8000/tcp
app-worker-1      Up
app-worker-2      Up
app-frontend-1    Up              80/tcp
app-nginx-1       Up              0.0.0.0:80->80/tcp
```

**Application URL:** `http://20.198.16.146`
**Deploy trigger:** Push to branch `DPP-2.3.0`
**Deploy time:** ~2 minutes (after images cached)

---

## GitHub Secrets Configured

| Secret | Purpose |
|--------|---------|
| `STAGING_SSH_KEY` | SSH private key to access the Azure VM |
| `STAGING_HOST` | VM public IP address |
| `STAGING_USER` | SSH username (`azureuser`) |
| `STAGING_ENV` | Full `.env` file contents for staging |

---

## Lessons Learned

1. **Always test TypeScript strict build locally before deploying** — run `npx tsc --noEmit` to catch type errors before the Docker build fails.
2. **GitHub Actions heredoc + SSH + secrets don't mix** — write secrets to files locally on the runner, then transfer via rsync.
3. **`npm install` over `npm ci` for Docker builds** unless the lock file is guaranteed to be in sync with the exact npm version in the base image.
4. **`docker compose down` before `up` on re-deploys** to avoid container name conflicts from partial previous runs.
5. **Azure B-series VM availability varies by region** — always check available sizes for your target region before planning infrastructure.
