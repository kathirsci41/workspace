# Auth + RBAC Design — Deferred

**Date:** 2026-04-07
**Status:** Brainstorm captured — not yet planned or implemented

## Context

Codex adversarial review flagged:
- `[critical]` Document read/delete/preview/download endpoints have no auth (`documents.py:148-177`)
- `[high]` Admin requeue endpoint is unauthenticated (`admin.py:202-227`)
- All API routes currently use only `Depends(get_db)` — no authentication at all

## Decisions So Far

| Question | Answer |
|----------|--------|
| Role model | Two roles: **Staff** (upload + view) and **Admin** (full access + user management) |
| Session approach | TBD — options: JWT bearer token, HTTP session cookie, or shared API key per role |

## Proposed Approach (To Be Finalized)

**Option A — JWT Bearer Tokens (Recommended)**
- Username + password → JWT access token (15–30 min) + refresh token (7 days)
- Stateless; works with existing React frontend
- `get_current_user` FastAPI dependency injected per route or globally via middleware
- `require_admin` dependency for admin-only routes

**Option B — HTTP Session Cookie**
- Server-side sessions in Redis
- Force-logout capability
- Slightly more complex but better for high-security environments

**Option C — Shared API Key per Role**
- One key per role in `.env`
- Minimal friction for small internal team
- No user audit trail

## Files That Need Changes

```
backend/app/
  models/user.py              — User model (username, hashed_password, role, is_active)
  api/v1/auth.py              — POST /auth/login, POST /auth/refresh
  core/auth.py                — JWT creation, verification, get_current_user dependency
  api/v1/documents.py         — Add Depends(get_current_user) to read/delete/preview/download
  api/v1/admin.py             — Add Depends(require_admin) to all admin routes
  api/v1/purchase_orders.py   — Add Depends(get_current_user) to all routes
  api/v1/extraction.py        — Add Depends(get_current_user) to all routes
  api/v1/customers.py         — Add Depends(get_current_user) to all routes
  api/v1/search.py            — Add Depends(get_current_user) to all routes
  main.py                     — Optional: global auth middleware
  config.py                   — Add JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES

frontend/src/
  api/auth.ts                 — Login, refresh, logout API calls
  context/AuthContext.tsx     — Token storage + refresh logic
  components/ProtectedRoute   — Redirect to /login if unauthenticated
  pages/LoginPage.tsx         — Login form
```

## DB Migration Needed

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY,
  username VARCHAR(64) UNIQUE NOT NULL,
  hashed_password VARCHAR(256) NOT NULL,
  role VARCHAR(16) NOT NULL,  -- 'staff' | 'admin'
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ,
  last_login_at TIMESTAMPTZ
);
```

## Next Step

Resume brainstorming when ready → finalize session approach → invoke writing-plans skill.
