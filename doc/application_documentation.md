# Document Platform V1.1 Documentation

## 1. Feature Perspectives (Functional Overview)

### Core Purpose

A comprehensive document management platform designed to track and organize business documents for sales operations. It links Cases (defined by Opportunities) with Sales Orders (SOs) and their respective supply chain documents.

### Key Capabilities

#### 1. Case Management

- **Search & Tracking**: Cases can be searched by "Opportunity ID" (using the `SKY-XXX` format) or "Sales Order Number".
- **Identification**: Each case is unique and linked to a CRM Opportunity.
- **Categorization**: Cases are classified as `HARDWARE` or `SERVICES`.

#### 2. Sales Order (SO) Tracking

- **Global Uniqueness**: Sales Order numbers are globally unique across the system.
- **Monthly Buckets**: SOs are organized by their creation month (immutable once set).
- **Multiple SOs per Case**: A single case can handle multiple Sales Orders.

#### 3. Document Management

The system enforces a strict hierarchy and checklist for documents. All documents are attached at the **Sales Order (SO) level**:

- **SO Level documents**:
  - `CUSTOMER_PO` (Customer Purchase Order)
  - `VENDOR_INVOICE`
  - `VENDOR_DC` (Delivery Challan)
  - `COMPANY_INVOICE`
  - `COMPANY_DC`
  - `POD` (Proof of Delivery)
- **Features**:
  - PDF Previewing
  - Checksum validation (SHA-256) to prevent duplicates
  - PDF Rotation tools
  - Metadata tracking (upload time, uploader, file size)

#### 4. Audit & Compliance

- **Audit Logs**: Tracks all critical actions (`CASE_CREATED`, `DOCUMENT_UPLOADED`, etc.) with actor and timestamp.
- **Consistency**: Enforces naming conventions and storage paths.

### Business Workflow (9-Stage Process)

The application supports the complete lifecycle of a sales transaction:

1.  **Inquiry**: Customer initiates interest.
2.  **Opportunity**: Created in CRM (Synced/Input as `SKY-XXX`).
3.  **PO**: Customer sends Purchase Order → Uploaded as `CUSTOMER_PO` to the relevant SO.
4.  **Vendor Invoice**: Procurement pays vendor → Uploaded to SO.
5.  **Vendor DC**: Goods delivered from vendor → Uploaded to SO.
6.  **Company Invoice**: Bill raised to customer → Uploaded to SO.
7.  **Company DC**: Delivery Challan to customer → Uploaded to SO.
8.  **POD**: Transporter provides Proof of Delivery → Uploaded to SO.
9.  **Collection**: Payment collection (Closing the loop).

---

## 2. Technical Perspectives (Architecture & Implementation)

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
    └── {SO_MONTH}/             # e.g., 2026-01
        └── SO-{SO_NUMBER}/     # e.g., SO-10TM2526001365
            ├── CUSTOMER_PO/
            ├── VENDOR_INVOICE/
            ├── VENDOR_DC/
            ├── COMPANY_INVOICE/
            ├── COMPANY_DC/
            └── POD/
```

#### 3. Database Schema

- **`cases`**: The root entity. `opportunity_id` is a unique index.
- **`sales_orders`**: Linked to `cases` (1:N). `so_number` is a unique index.
- **`documents`**: Linked to both `Case` and `SalesOrder`. All documents require a Sales Order association. Stores file metadata and physical path.
- **`audit_logs`**: Immutable record of events.

#### 4. Environment & Configuration

- **Configuration**: `backend/app/config.py` uses `pydantic-settings`.
- **Environment**: `.env` files manage credentials and behavior (Debug mode, CORS, DB URL).
- **DevContainer**: Fully containerized development environment ensuring consistency across developers (Node, Python, Postgres tools pre-installed).
