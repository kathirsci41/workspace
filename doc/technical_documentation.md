# Document Platform V1.1 - Technical Documentation

## Architecture & Implementation

### Tech Stack

- **Frontend**: React 18, TypeScript, Vite, TailwindCSS (Modern SPA).
- **Backend**: FastAPI (Python 3.11), Pydantic (Validation).
- **Database**: PostgreSQL 15, SQLAlchemy (ORM), Alembic (Migrations).
- **Infrastructure**: Docker, Docker Compose, DevContainer.

### Project Structure (Monorepo)

- `/backend`: Python API service.
  - `app/models`: SQLAlchemy definitions (`Case`, `SalesOrder`, `Document`, `AuditLog`).
  - `app/schemas`: Pydantic models for request/response validation.
  - `app/services`: Business logic layer (separation of concerns).
  - `storage/`: Local NAS-like storage simulation.
- `/frontend`: React application.
  - `src/api`: Axios client layers.
  - `src/components`: Reusable UI blocks.
- `docker-compose.yml`: Orchestration for DB, Backend, and Frontend.

### Key Technical Implementations

#### 1. Identifier Normalization (`SKY-` Prefix)

- **Logic**: All Opportunity IDs are normalized to `SKY-XXX` format.
- **Implementation**:
  - `backend/app/utils/normalizer.py`: Central logic to strip whitespace, uppercase, and append prefix.
  - `backend/app/schemas/case.py`: Pydantic validator to enforce format at the API entry point.
  - **Frontend**: Search inputs provide visual hints (`e.g., SKY-443`).

#### 2. Storage Architecture

Files are stored physically on disk (simulating NAS) with a deterministic structure to ensure organization outside the DB:

```text
/nas/cases/
└── {CASE_ID}/                  # e.g., CASE-2026-0001
    ├── CUSTOMER_PO/
    │   └── {filename}.pdf
    └── {SO_MONTH}/             # e.g., 2026-01
        └── SO-{SO_NUMBER}/     # e.g., SO-10TM2526001365
            ├── VENDOR_INVOICE/
            └── ... (other types)
```

#### 3. Database Schema

- **`cases`**: The root entity. `opportunity_id` is a unique index.
- **`sales_orders`**: Linked to `cases` (1:N). `so_number` is a unique index.
- **`documents`**: Polymorphic-like association. Can link to `Case` (for POs) or `SalesOrder` (for others). Stores file metadata and physical path.
- **`audit_logs`**: Immutable record of events.

#### 4. Environment & Configuration

- **Configuration**: `backend/app/config.py` uses `pydantic-settings`.
- **Environment**: `.env` files manage credentials and behavior (Debug mode, CORS, DB URL).
- **DevContainer**: Fully containerized development environment ensuring consistency across developers (Node, Python, Postgres tools pre-installed).
