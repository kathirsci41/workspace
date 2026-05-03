# Deployment Checklist
**Date:** 2026-04-21  
**Purpose:** Final pre-deployment and go-live checklist for DPP on-prem rollout

---

## 1. Use Of This Checklist

Use this checklist in order:

1. pre-deployment readiness
2. environment and configuration validation
3. service startup validation
4. application smoke tests
5. operational validation
6. go/no-go decision

This checklist assumes the current deployment gate audit in:

- [DEPLOYMENT_GATE_ISSUE_AUDIT_2026-04-21.md](/E:/PROJECTS/Experiments/Logistic/DPP%202.2.0/docs/DEPLOYMENT_GATE_ISSUE_AUDIT_2026-04-21.md:1)

and the deployment design in:

- [deployment-architecture.md](/E:/PROJECTS/Experiments/Logistic/DPP%202.2.0/docs/architecture/deployment-architecture.md:1)

---

## 2. Pre-Deploy Checks

Mark each item `Pass`, `Fail`, or `Accepted Limitation`.

### 2.1 Code and issue state

- [ ] Deployment branch or working tree is the intended release state
- [ ] No known `high` severity unresolved application bugs remain in scope
- [ ] Address search cleanup fix is included in deployed backend build
- [ ] Billing full-mode fallback fix is included in deployed frontend build
- [ ] PO detail `/chain` endpoint confirmed stable on current build
- [ ] PO profile endpoint confirmed stable on current build

### 2.2 Scope decisions

- [ ] Chat is confirmed either `in scope` or `out of scope`
- [ ] If chat is out of scope, it is clearly disabled or documented as unavailable
- [ ] Date parsing limitation for formats like `20 March 2026` is explicitly accepted if not fixed

### 2.3 Data readiness

- [ ] Seed/demo/customer data has been reviewed for obvious invalid placeholders
- [ ] Test-only customers or bad emails are removed or clearly marked
- [ ] Any showcase/demo POs have realistic document chains and totals

---

## 3. Environment And Config Checks

### 3.1 Core services

- [ ] Frontend runtime configured
- [ ] Backend runtime configured
- [ ] PostgreSQL reachable
- [ ] Redis reachable
- [ ] Worker runtime configured
- [ ] Document storage path mounted and writable

### 3.2 Required configuration

- [ ] `DATABASE_URL` points to the deployment database
- [ ] `SYNC_DATABASE_URL` points to the deployment database
- [ ] `REDIS_URL` points to the deployment Redis instance
- [ ] `NAS_BASE_PATH` points to the real document storage location
- [ ] `CORS_ORIGINS` matches the deployment frontend origin
- [ ] `COMPANY_STATE` is set correctly for GST logic

### 3.3 OCR / extraction configuration

- [ ] Layer 1 provider is configured correctly
- [ ] Layer 2 provider is configured correctly if enabled
- [ ] Model endpoint is reachable from the worker host
- [ ] Required API keys are present if using remote/external providers
- [ ] TLS/CA bundle configuration is correct if private certs are used

### 3.4 Chat configuration

Only complete this section if chat is in scope.

- [ ] `chat_base_url` or equivalent runtime config points to a reachable chat-capable endpoint
- [ ] `chat_model` is available on that endpoint
- [ ] SSE traffic is allowed through reverse proxy

---

## 4. Service Startup Checks

### 4.1 Startup order

- [ ] PostgreSQL started successfully
- [ ] Redis started successfully
- [ ] Backend started successfully
- [ ] Worker started successfully
- [ ] Frontend started successfully
- [ ] Reverse proxy started successfully

### 4.2 Health validation

- [ ] Backend health endpoint responds
- [ ] Frontend loads from the deployment URL
- [ ] Admin/System page shows green or expected health state for:
  - [ ] database
  - [ ] redis
  - [ ] storage
  - [ ] model endpoint
  - [ ] worker presence / queue visibility

### 4.3 Logs

- [ ] Backend logs show no startup exceptions
- [ ] Worker logs show no immediate task boot failures
- [ ] Reverse proxy logs show no routing/TLS errors on first load

---

## 5. Application Smoke Tests

These are the minimum smoke tests before go-live.

### 5.1 Navigation

- [ ] Dashboard loads
- [ ] Customers page loads
- [ ] Purchase Orders page loads
- [ ] Documents page loads
- [ ] Search page loads
- [ ] System/Admin page loads
- [ ] Assistant page loads if chat is in scope

### 5.2 PO workflow

- [ ] Open a real PO detail page successfully
- [ ] Open a real PO profile page successfully
- [ ] Chain status renders without server errors
- [ ] Reference validation panel renders
- [ ] Billing section renders with non-broken values
- [ ] Selecting a document opens preview/review correctly

### 5.3 Search workflow

- [ ] Global/reference search returns results
- [ ] Address search returns clean `ref_number` values
- [ ] Advanced document type filter returns only expected result types
- [ ] Header search dropdown closes cleanly when leaving focus

### 5.4 Document/review workflow

- [ ] Documents queue loads
- [ ] Open one review flow from documents or PO detail
- [ ] Review modal renders extracted fields
- [ ] No raw `{'value': ..., 'confidence': ...}` payloads visibly leak in reviewed fields for the tested record
- [ ] Verify / reject controls are present for expected statuses

### 5.5 Billing workflow

- [ ] Full-billing PO with invoices shows non-zero `Billed So Far`
- [ ] Empty full-billing PO shows the true empty state
- [ ] If stage breakdown is unavailable, UI does not falsely show `No invoices uploaded yet`

### 5.6 Chat workflow

Only required if chat is in scope.

- [ ] Sending a simple message returns streamed content
- [ ] PO context selector works
- [ ] No `403` or model-unavailable errors occur on a normal request

---

## 6. Operational Checks

### 6.1 Storage and backup

- [ ] Database backup procedure is defined
- [ ] Document storage backup procedure is defined
- [ ] Restore owner and restore steps are known

### 6.2 Recovery

- [ ] Team knows how to restart backend
- [ ] Team knows how to restart worker
- [ ] Team knows how to inspect failed extraction state
- [ ] Team knows how to requeue pending/failed work

### 6.3 Access and security

- [ ] Deployment is inside the intended trusted network boundary
- [ ] Reverse proxy/TLS behavior is validated
- [ ] Lack of in-app RBAC is explicitly accepted for this rollout

---

## 7. Go / No-Go Criteria

## Go

Proceed if all of the following are true:

- all core services are healthy
- PO detail and PO profile work on the deployed build
- search and address search are working correctly
- billing values render correctly for a real PO
- no critical runtime errors appear in smoke tests
- any remaining limitations are explicitly accepted

## Go With Conditions

Proceed only with explicit signoff if:

- the only open issue is the accepted date parsing limitation
- chat is out of scope or optional
- all other core workflows pass

## No-Go

Do not deploy if any of the following are true:

- PO detail or PO profile is failing
- address search still leaks raw confidence-dict values
- billing still shows incorrect zero totals for real invoices
- backend health, storage, DB, Redis, or worker are unstable
- chat is in scope but not operational

---

## 8. Final Signoff

### Release owner

- Name:
- Date:
- Decision: `Go` / `Go with conditions` / `No-Go`

### Conditions accepted

- [ ] Date parsing limitation accepted
- [ ] Chat out of scope
- [ ] No in-app RBAC accepted for this rollout

### Notes

- 
