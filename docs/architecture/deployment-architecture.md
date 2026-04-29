# DPP On-Prem Deployment Architecture
**Last Updated:** 2026-04-20

---

## 1. Purpose

This document defines the deployment architecture for rolling out DPP as an on-prem application.

It complements the application architecture docs by answering a different question:

- application architecture: how the product is designed in code
- deployment architecture: how the product should be installed, hosted, secured, operated, and upgraded in a customer environment

This document should be used as the rollout reference for customer-hosted deployments.

---

## 2. Deployment Goal

The on-prem deployment must provide a stable internal business application for document operations with the following characteristics:

- customer-hosted infrastructure
- internal network access
- predictable service dependencies
- durable document storage
- restartable background processing
- monitored extraction pipeline
- clear operational recovery paths

The deployment model must support both:

- fully local model hosting
- hybrid deployments where extraction models run on a reachable external endpoint

---

## 3. Supported Deployment Model

The recommended deployment model is a single customer-controlled environment with separated runtime services.

### Core services

- reverse proxy
- frontend application
- backend API
- Celery worker
- PostgreSQL
- Redis
- document storage mount
- model endpoint, local or remote

### Logical topology

```text
User Browser
  -> Reverse Proxy
     -> Frontend
     -> Backend API
        -> PostgreSQL
        -> Redis
        -> Storage
        -> Celery worker
           -> Model endpoint
```

### Recommended deployment principle

Even if several services run on the same host, they should still be treated as separate operational units for restart, monitoring, and troubleshooting.

---

## 4. Deployment Profiles

### Profile A: Single-Server On-Prem

Recommended for smaller teams or first rollout.

All of the following run on one customer-managed server:

- reverse proxy
- frontend
- backend
- worker
- PostgreSQL
- Redis
- local storage

Model endpoint can be:

- local on the same host if GPU is available
- local on a second host
- remote but customer-approved

### Profile B: Split Application And Data

Recommended when the customer already has managed database or storage infrastructure.

Typical split:

- app host: reverse proxy, frontend, backend, worker
- data host: PostgreSQL
- cache host: Redis
- NAS or shared storage: document files
- model host: GPU box or remote provider

### Profile C: On-Prem Application With External Model Endpoint

Recommended when the customer wants the app hosted on-prem but cannot or does not want to host local models.

Application services remain on-prem, while extraction providers point to:

- RunPod-hosted endpoint
- Datalab
- another OpenAI-compatible service approved by the customer

This profile requires explicit network and security approval because extraction traffic leaves the local environment.

---

## 5. Service Inventory

### Reverse Proxy

Responsibilities:

- terminate TLS
- route frontend and API traffic
- expose a single internal URL
- support large file upload paths
- support SSE for chat streaming

Current repo support:

- `nginx/nginx.conf`
- docker compose files

### Frontend

Responsibilities:

- serve the React application
- provide operator, admin, and assistant UI

Typical runtime:

- built static assets served behind reverse proxy

### Backend API

Responsibilities:

- core business APIs
- document upload
- search
- admin
- export
- chat streaming

### Celery Worker

Responsibilities:

- background extraction
- model health dependent processing
- held-document reprocessing after recovery

### PostgreSQL

Responsibilities:

- persistent business data
- extracted metadata
- reference index
- audit history

### Redis

Responsibilities:

- Celery broker
- Celery backend
- transient caches

### Storage

Responsibilities:

- hold source PDF files
- remain readable by backend and worker
- remain writable during uploads and document rotation/replacement flows

### Model Endpoint

Responsibilities:

- Layer 1 OCR or equivalent extraction
- Layer 2 structured extraction
- assistant chat if configured to share the same model endpoint family

---

## 6. Infrastructure Requirements

### Minimum platform requirements

The customer environment must provide:

- Linux or Windows host environment capable of running the required services
- persistent disk for database and document storage
- reliable internal networking between app, DB, Redis, storage, and model endpoint
- backup capability for both database and document storage

### GPU requirement

GPU is required only when the customer chooses local model hosting.

If local OCR/extraction is enabled:

- GPU sizing must match the selected models
- VRAM limits matter because Layer 1 and Layer 2 models may not coexist comfortably
- model warmup and readiness affect throughput

If external model hosting is used:

- the application tier does not require GPU
- network reliability becomes a rollout dependency

### Disk requirement

The deployment must reserve storage for:

- PostgreSQL data
- uploaded PDFs
- rotated or replacement files if applicable
- logs
- optional debug markdown and extraction artifacts if enabled

Document storage growth should be treated as long-term operational capacity, not temporary scratch space.

---

## 7. Network Architecture

### Internal traffic

Normal internal traffic flows:

- browser to reverse proxy
- reverse proxy to frontend and backend
- backend to PostgreSQL
- backend to Redis
- backend and worker to storage
- worker to model endpoint

### External traffic

External outbound traffic is only required when using:

- RunPod
- Datalab
- OpenAI-compatible remote providers

### Recommended policy

For strict on-prem environments:

- prefer local or customer-managed model endpoints
- keep PostgreSQL and Redis off public exposure
- expose only the reverse proxy URL to users

---

## 8. Storage Architecture

Document storage is a first-class deployment dependency.

### Requirements

- mounted path must exist before application startup
- backend and worker must share consistent access to the same document root
- write permission must be verified
- backup policy must include the storage root, not just the database

### Failure model

If storage is unavailable:

- uploads fail
- preview and download may fail
- worker processing may fail when reading source files

This means storage must be treated as production infrastructure, not an incidental local folder.

---

## 9. Security Posture

### Current state

The application architecture currently has a major rollout constraint:

- authentication and RBAC are not yet implemented as an enforced platform security layer

That means role separation in the product is operational and procedural, not technically enforced.

### On-prem implication

For this version, the deployment should be treated as:

- internal trusted-network application
- access restricted by network perimeter, reverse proxy rules, VPN, or customer directory controls outside the app

### Minimum deployment safeguards

- do not expose PostgreSQL or Redis publicly
- restrict app access to internal users
- terminate TLS at the reverse proxy
- lock down storage paths at the OS and network level
- control admin endpoint access at the network layer where possible

### Release blocker note

If the customer expects per-user access control inside the app, that is a product gap for this rollout and must be called out before deployment.

---

## 10. Operational Monitoring

The deployment must support ongoing operations, not just installation.

### Operational checks

- backend health
- database availability
- Redis availability
- storage accessibility
- model endpoint health
- worker presence
- queue backlog
- failed extraction volume
- `PENDING_MODEL` document count

### In-product support

The Admin page already surfaces part of this operational view, but customer rollout should not rely on UI alone. Logs and service-level monitoring should also be available.

---

## 11. Logging And Diagnostics

### Required log surfaces

- backend logs
- worker logs
- reverse proxy logs
- database logs where available
- host/service logs for model endpoint if locally hosted

### Diagnostic value

The most important rollout-time diagnostic categories are:

- storage access failure
- model unreachability
- extraction timeout or malformed output
- database connectivity issues
- Redis or worker outage

These categories should be easy for the deployment team to identify from logs and admin screens.

---

## 12. Backup And Restore Model

On-prem rollout is incomplete without backup design.

### Back up both

- PostgreSQL database
- document storage root

Backing up only the database is insufficient because source PDFs are stored outside it.

### Restore principle

A valid restore must recover:

- PO and document rows
- document metadata and corrections
- reference index data
- source document files

If files and database snapshots are taken from unrelated points in time, restore consistency risk must be understood and accepted.

---

## 13. Startup And Recovery Order

### Recommended startup order

1. storage mount available
2. PostgreSQL healthy
3. Redis healthy
4. model endpoint available if locally hosted
5. backend API
6. Celery worker
7. frontend and reverse proxy

### Recovery principle

If the model endpoint is unavailable:

- application remains usable for non-extraction workflows
- new extraction tasks may accumulate
- documents can move into `PENDING_MODEL`
- admin requeue flow is used after recovery

This is a degraded mode, not necessarily a full outage.

---

## 14. Upgrade Architecture

Each rollout or upgrade should be treated as a controlled change across:

- application code
- frontend build
- backend dependencies
- database schema
- configuration

### Minimum safe sequence

1. back up database and document storage
2. stop write-heavy application use where possible
3. deploy updated backend and frontend artifacts
4. run database migrations
5. restart backend and worker
6. verify admin health
7. verify upload, extraction, review, and search paths

### Rollback constraint

Rollback is only safe when:

- schema changes are backward compatible
- or a tested restore path exists for both DB and storage

This needs to be treated explicitly in rollout planning.

---

## 15. Rollout Readiness Checklist

Before deploying this version on-prem, confirm:

- customer deployment profile selected
- model hosting approach selected
- storage mount path confirmed
- DB backup plan approved
- document storage backup plan approved
- internal TLS/proxy plan approved
- admin and operational ownership assigned
- access restriction approach approved
- auth limitation acknowledged if customer expects in-app permissions
- health verification procedure documented
- requeue and degraded-mode procedure documented

---

## 16. Current Rollout Constraints

This version is suitable for on-prem rollout only under the correct expectations.

### Important constraints

- app-level auth and RBAC are not yet enforced
- deployment security therefore depends on infrastructure controls
- model availability can materially affect throughput and user experience
- storage reliability is critical to correctness
- backup and restore must cover both database and files

These are not minor details. They are part of the deployment architecture.

---

## 17. Deployment Principle

For this release, the correct on-prem interpretation of DPP is:

- an internal operational application
- hosted inside customer infrastructure
- backed by managed database, queue, storage, and model dependencies
- safe to deploy when network boundaries, storage, monitoring, and backup practices are defined

That is the intended deployment architecture for this version.
