# Document Platform V1.1

A document management platform for tracking business documents organized by Opportunity ID and Sales Order numbers.

## Project Structure

```
Phase 1.1/
├── .devcontainer/        # Dev container configuration
│   ├── devcontainer.json
│   └── docker-compose.yml
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── api/          # API routers
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Business logic
│   │   └── utils/        # Utility functions
│   ├── alembic/          # Database migrations
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/             # React frontend
│   ├── src/
│   │   ├── api/          # API client
│   │   ├── components/   # React components
│   │   ├── hooks/        # React Query hooks
│   │   ├── pages/        # Page components
│   │   └── types/        # TypeScript types
│   ├── Dockerfile
│   └── package.json
└── docker-compose.yml    # Production compose
```

## Quick Start

### Option 1: Using Docker Compose (Recommended)

```bash
docker-compose up -d --build
```

This starts all services:

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5433

To stop:

```bash
docker-compose down
```

### Option 2: Run Without Docker

#### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 15 (or use Docker for database only)

#### 1. Start Database (using Docker)

```bash
docker run -d --name docplatform-db \
  -e POSTGRES_USER=docplatform \
  -e POSTGRES_PASSWORD=docplatform \
  -e POSTGRES_DB=docplatform \
  -p 5432:5432 \
  postgres:15-alpine
```

#### 2. Start Backend

```bash
cd backend
pip install -r requirements.txt
mkdir -p storage/cases

DATABASE_URL="postgresql://docplatform:docplatform@localhost:5432/docplatform" \
NAS_BASE_PATH="$(pwd)/storage/cases" \
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 3. Start Frontend

```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

#### Access Points

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### Option 3: Dev Container

1. Open this folder in VS Code
2. When prompted, click "Reopen in Container"
3. Wait for the container to build and start
4. The database will be ready on port 5432
5. Run the backend and frontend commands from Option 2

## Business Rules

### Cases

- Each case has a unique `CASE_ID` (e.g., `CS-2025-00001`)
- Identified by `opportunity_id` (e.g., `OPP-443`)
- Types: `HARDWARE` or `SERVICES`

### Sales Orders (SO)

- SO number is **globally unique** across all cases
- **Month is fixed at SO creation** and cannot be changed
- Format: `10TM2526001365` (12 digits)

### Documents

- **Customer PO**: Attached to Case directly (no SO required)
- **SO Documents**: VENDOR_INVOICE, VENDOR_DC, COMPANY_INVOICE, COMPANY_DC, POD
- Each SO has a checklist showing which document types are uploaded

### Storage Hierarchy

```
/nas/cases/
└── {CASE_ID}/
    ├── CUSTOMER_PO/
    │   └── {filename}.pdf
    └── {SO_MONTH}/
        └── SO-{SO_NUMBER}/
            ├── VENDOR_INVOICE/
            ├── VENDOR_DC/
            ├── COMPANY_INVOICE/
            ├── COMPANY_DC/
            └── POD/
```

## 9-Stage Business Process

1. Customer sends inquiry
2. Create opportunity in CRM
3. Get vendor quote → Customer sends PO
4. Vendor Invoice → Payment
5. Vendor DC (Delivery Challan)
6. Company raises Invoice to customer
7. Company DC to customer
8. POD (Proof of Delivery) from transporter
9. Payment collection

## API Endpoints

### Cases

- `GET /api/cases?opportunity_id={id}` - Search cases
- `POST /api/cases` - Create case
- `GET /api/cases/{case_id}` - Get case with details
- `PATCH /api/cases/{case_id}` - Update case

### Sales Orders

- `GET /api/sales-orders?so_number={number}` - Search globally
- `POST /api/cases/{case_id}/sales-orders` - Create SO
- `GET /api/cases/{case_id}/sales-orders` - List SOs

### Documents

- `POST /api/cases/{case_id}/documents` - Upload document
- `GET /api/documents/{id}/preview` - Preview PDF
- `GET /api/documents/{id}/download` - Download file
- `POST /api/documents/{id}/rotate` - Rotate PDF
- `DELETE /api/documents/{id}` - Delete document

### Admin

- `GET /api/admin/health` - Health check
- `GET /api/admin/stats` - Platform statistics
- `GET /api/admin/audit-logs` - Audit logs

## Environment Variables

### Backend

- `DATABASE_URL` - PostgreSQL connection string
- `NAS_BASE_PATH` - Base path for document storage
- `DEBUG` - Enable debug mode

### Frontend

- `VITE_API_BASE_URL` - Backend API URL

## Tech Stack

### Backend

- Python 3.11+
- FastAPI 0.109
- SQLAlchemy 2.0
- Alembic 1.13
- PostgreSQL 15

### Frontend

- React 18.2
- TypeScript 5.3
- Vite 5.0
- TailwindCSS 3.4
- React Query 5.17
