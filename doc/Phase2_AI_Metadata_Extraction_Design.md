# Document Platform V2.0 — Phase 2: AI Metadata Extraction

## Technical Design Document

**Version:** 2.0  
**Date:** February 2026  
**Status:** Implementation Blueprint  
**Depends On:** Phase 1 (Document Management Platform V1.1)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [AI/OCR Model Setup — GLM-OCR](#3-aiocr-model-setup--glm-ocr)
4. [Database Schema & Migration](#4-database-schema--migration)
5. [Extraction Prompts Per Document Type](#5-extraction-prompts-per-document-type)
6. [Backend API — Endpoints & Services](#6-backend-api--endpoints--services)
7. [Extraction Service — Core Pipeline](#7-extraction-service--core-pipeline)
8. [Frontend — Review & Verification UI](#8-frontend--review--verification-ui)
9. [Docker Compose Updates](#9-docker-compose-updates)
10. [Configuration & Environment Variables](#10-configuration--environment-variables)
11. [Error Handling & Retry Strategy](#11-error-handling--retry-strategy)
12. [Testing Strategy](#12-testing-strategy)
13. [Deployment Guide](#13-deployment-guide)
14. [Future Enhancements](#14-future-enhancements)

---

## 1. Executive Summary

Phase 2 adds AI-powered metadata extraction to the Document Platform. When a user uploads a document (Invoice, PO, DC, etc.) in Phase 1, they can now click an **"Extract Metadata"** button. The system sends the PDF to a locally hosted **GLM-OCR** model, which extracts structured fields (invoice numbers, dates, PO references, etc.) into JSON. The user reviews and verifies the extracted data before it is saved to the database.

### Key Decisions

- **AI Model**: GLM-OCR (0.9B params) — MIT licensed, native JSON extraction, runs on 8GB VRAM
- **Metadata Storage**: Hybrid approach (Option C) — indexed common fields + JSONB for full extraction
- **Workflow**: Manual trigger → Extract → Human review → Verify/Edit → Save
- **Deployment**: Ollama (development), vLLM (production)

---

## 2. Architecture Overview

### System Flow

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐     ┌────────────┐
│   Frontend   │────▶│  FastAPI      │────▶│  GLM-OCR Service │────▶│ PostgreSQL │
│  (React UI)  │◀────│  Backend      │◀────│  (Ollama/vLLM)   │     │  Database   │
└─────────────┘     └──────────────┘     └──────────────────┘     └────────────┘
                           │                       │
                           │                       │
                    ┌──────▼───────┐        ┌──────▼───────┐
                    │  NAS Storage │        │  PDF → Image  │
                    │  /nas/cases/ │        │  Conversion   │
                    └──────────────┘        └──────────────┘
```

### Component Responsibilities

| Component | Role |
|-----------|------|
| **Frontend** | Extract button, review modal, edit fields, verify/reject |
| **FastAPI Backend** | API endpoints, orchestration, validation, DB writes |
| **Extraction Service** | PDF-to-image conversion, GLM-OCR API calls, JSON parsing |
| **GLM-OCR (Ollama/vLLM)** | Actual OCR + structured extraction |
| **PostgreSQL** | `document_metadata` table (hybrid JSONB schema) |
| **NAS Storage** | Existing document storage from Phase 1 |

### Request Flow — Full Extraction Cycle

```
1. User clicks "Extract Metadata" on a document in the UI
2. Frontend → POST /api/v1/documents/{doc_id}/extract
3. Backend reads document record → gets file path from `documents` table
4. Backend calls Extraction Service:
   a. Reads PDF from NAS path
   b. Converts PDF pages to images (pdf2image)
   c. Sends image + doc-type-specific JSON prompt to GLM-OCR
   d. Receives structured JSON response
   e. Parses and validates response against Pydantic schema
5. Backend creates `document_metadata` record with status=EXTRACTED
6. Response returned to Frontend with extracted fields
7. User reviews, optionally edits fields
8. User clicks "Verify" → PUT /api/v1/metadata/{meta_id}/verify
9. Backend updates status=VERIFIED, sets verified_by
10. Done — metadata is now trusted and queryable
```

---

## 3. AI/OCR Model Setup — GLM-OCR

### 3.1 Development Setup (Ollama — RTX 3050 8GB)

#### Install Ollama

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull GLM-OCR model
ollama pull glm-ocr

# Verify it's running
ollama list
```

#### Test the Model

```bash
# Test with a sample image
ollama run glm-ocr "/path/to/test_invoice.png
请按下列JSON格式输出图中信息:
{
  \"invoice_no\": \"\",
  \"date\": \"\"
}"
```

#### Ollama API Endpoint

Once running, Ollama exposes an OpenAI-compatible API:

```
Base URL: http://localhost:11434
Chat endpoint: POST http://localhost:11434/api/chat
Model name: glm-ocr
```

**Example API Call:**

```python
import requests
import base64

def extract_with_ollama(image_path: str, prompt: str) -> dict:
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "glm-ocr",
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_b64]
                }
            ],
            "stream": False,
            "options": {
                "temperature": 0.01,
                "num_predict": 4096
            }
        }
    )

    return response.json()["message"]["content"]
```

### 3.2 Production Setup (vLLM — RTX 4000/5000)

#### Install vLLM

```bash
pip install -U vllm --extra-index-url https://wheels.vllm.ai/nightly
pip install git+https://github.com/huggingface/transformers.git
```

#### Start vLLM Server

```bash
vllm serve zai-org/GLM-OCR \
    --allowed-local-media-path / \
    --port 8080 \
    --gpu-memory-utilization 0.8 \
    --max-model-len 8192
```

#### vLLM API Endpoint

vLLM exposes an OpenAI-compatible API:

```
Base URL: http://localhost:8080
Chat endpoint: POST http://localhost:8080/v1/chat/completions
Model name: zai-org/GLM-OCR
```

**Example API Call:**

```python
import requests
import base64

def extract_with_vllm(image_path: str, prompt: str) -> dict:
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    response = requests.post(
        "http://localhost:8080/v1/chat/completions",
        json={
            "model": "zai-org/GLM-OCR",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_b64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ],
            "max_tokens": 4096,
            "temperature": 0.01
        }
    )

    return response.json()["choices"][0]["message"]["content"]
```

### 3.3 Model Configuration Summary

| Setting | Development | Production |
|---------|-------------|------------|
| **Runtime** | Ollama | vLLM |
| **GPU** | RTX 3050 (8GB) | RTX 4000/5000 |
| **Port** | 11434 | 8080 |
| **Temperature** | 0.01 | 0.01 |
| **Max tokens** | 4096 | 4096 |
| **VRAM usage** | ~2-3GB | ~2-3GB + batching overhead |

> **Important**: Temperature must be very low (0.01) for deterministic extraction. Higher temperatures cause hallucinated field values.

---

## 4. Database Schema & Migration

### 4.1 New Table: `document_metadata`

```sql
-- Alembic migration: add_document_metadata_table

CREATE TYPE extraction_status AS ENUM ('PENDING', 'EXTRACTED', 'VERIFIED', 'FAILED');

CREATE TYPE document_type AS ENUM (
    'CUSTOMER_PO',
    'VENDOR_INVOICE',
    'VENDOR_DC',
    'COMPANY_INVOICE',
    'COMPANY_DC',
    'POD',
    'PURCHASE_BILL'
);

CREATE TABLE document_metadata (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    document_path   VARCHAR(1024) NOT NULL,

    -- Document classification
    doc_type        document_type NOT NULL,

    -- Promoted indexed fields (for fast queries)
    primary_ref_no  VARCHAR(255),
    doc_date        DATE,

    -- Full extraction result
    extracted_data  JSONB NOT NULL DEFAULT '{}',

    -- Extraction metadata
    confidence_score FLOAT,
    status          extraction_status NOT NULL DEFAULT 'PENDING',
    raw_ocr_text    TEXT,

    -- Audit fields
    extracted_at    TIMESTAMP WITH TIME ZONE,
    verified_by     VARCHAR(255),
    verified_at     TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT uq_document_metadata UNIQUE (document_id)
);

-- Indexes for common queries
CREATE INDEX idx_metadata_doc_type ON document_metadata(doc_type);
CREATE INDEX idx_metadata_status ON document_metadata(status);
CREATE INDEX idx_metadata_primary_ref ON document_metadata(primary_ref_no);
CREATE INDEX idx_metadata_doc_date ON document_metadata(doc_date);
CREATE INDEX idx_metadata_extracted_data ON document_metadata USING GIN(extracted_data);
```

### 4.2 SQLAlchemy Model

**File: `backend/app/models/document_metadata.py`**

```python
import uuid
import enum
from datetime import datetime, date
from sqlalchemy import (
    Column, String, Float, Text, Date, DateTime, Enum, ForeignKey,
    UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class ExtractionStatus(str, enum.Enum):
    PENDING = "PENDING"
    EXTRACTED = "EXTRACTED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


class DocumentType(str, enum.Enum):
    CUSTOMER_PO = "CUSTOMER_PO"
    VENDOR_INVOICE = "VENDOR_INVOICE"
    VENDOR_DC = "VENDOR_DC"
    COMPANY_INVOICE = "COMPANY_INVOICE"
    COMPANY_DC = "COMPANY_DC"
    POD = "POD"
    PURCHASE_BILL = "PURCHASE_BILL"


class DocumentMetadata(Base):
    __tablename__ = "document_metadata"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    document_path = Column(String(1024), nullable=False)

    # Document classification
    doc_type = Column(Enum(DocumentType), nullable=False)

    # Promoted indexed fields
    primary_ref_no = Column(String(255), nullable=True)
    doc_date = Column(Date, nullable=True)

    # Full extraction result
    extracted_data = Column(JSONB, nullable=False, default=dict)

    # Extraction metadata
    confidence_score = Column(Float, nullable=True)
    status = Column(
        Enum(ExtractionStatus),
        nullable=False,
        default=ExtractionStatus.PENDING
    )
    raw_ocr_text = Column(Text, nullable=True)

    # Audit fields
    extracted_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(String(255), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False,
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    document = relationship("Document", back_populates="metadata")

    __table_args__ = (
        Index("idx_metadata_doc_type", "doc_type"),
        Index("idx_metadata_status", "status"),
        Index("idx_metadata_primary_ref", "primary_ref_no"),
        Index("idx_metadata_doc_date", "doc_date"),
        Index("idx_metadata_extracted_data", "extracted_data", postgresql_using="gin"),
    )
```

### 4.3 Alembic Migration

**File: `backend/alembic/versions/xxxx_add_document_metadata.py`**

```bash
# Generate the migration
cd backend
alembic revision --autogenerate -m "add_document_metadata_table"

# Apply the migration
alembic upgrade head
```

### 4.4 Update Existing Document Model

Add the back-reference to the existing `Document` model:

```python
# In backend/app/models/document.py — add this relationship
metadata = relationship(
    "DocumentMetadata",
    back_populates="document",
    uselist=False,  # One-to-one
    cascade="all, delete-orphan"
)
```

---

## 5. Extraction Prompts Per Document Type

### 5.1 Prompt Engineering Strategy

GLM-OCR's Information Extraction mode requires a **strict JSON schema** in the prompt. The model reads the document image and fills in the values.

**Critical Rules:**
1. Temperature must be `0.01` (near-deterministic)
2. Prompt must include the exact JSON schema with empty string values
3. Add explicit instruction text before the JSON
4. Date format instruction should be included (DD-MM-YYYY or as found)
5. Include "If a field is not found, return empty string" instruction

### 5.2 Base Prompt Template

Every document type uses this wrapper:

```python
BASE_PROMPT_TEMPLATE = """Analyze this document image carefully and extract the following information.
Return ONLY a valid JSON object with the exact structure shown below.
If a field cannot be found in the document, return an empty string for that field.
Do not add any explanation or text outside the JSON.
Dates should be extracted exactly as they appear in the document.

{json_schema}"""
```

### 5.3 Document-Specific Prompts & JSON Schemas

#### A. Delivery Challan (`VENDOR_DC` / `COMPANY_DC`)

```python
DC_SCHEMA = {
    "dc_no": "",
    "customer_order_no": "",
    "dc_date": "",
    "so_no": ""
}

DC_PROMPT = """Analyze this Delivery Challan document image carefully and extract the following information.
Return ONLY a valid JSON object with the exact structure shown below.
If a field cannot be found in the document, return an empty string for that field.
Do not add any explanation or text outside the JSON.
Dates should be extracted exactly as they appear in the document.

Look for these specific fields:
- dc_no: The Delivery Challan Number (may appear as "DC No", "DC No.", "Challan No", "D.C. No")
- customer_order_no: Customer Order Number (may appear as "Customer Order No", "Cust Order", "Customer PO")
- dc_date: Date of Delivery Challan (may appear as "DC Date", "Date", "Challan Date")
- so_no: Sales Order Number (may appear as "SO No", "Sales Order", "SO Number", "S.O. No")

{
    "dc_no": "",
    "customer_order_no": "",
    "dc_date": "",
    "so_no": ""
}"""

# Primary reference field mapping
DC_PRIMARY_REF = "dc_no"
DC_DATE_FIELD = "dc_date"
```

#### B. Company Tax Invoice (`COMPANY_INVOICE`)

```python
COMPANY_INVOICE_SCHEMA = {
    "invoice_no": "",
    "customer_order_no": "",
    "so_no": "",
    "invoice_date": "",
    "customer_order_date": "",
    "acct_manager": ""
}

COMPANY_INVOICE_PROMPT = """Analyze this Company Tax Invoice document image carefully and extract the following information.
Return ONLY a valid JSON object with the exact structure shown below.
If a field cannot be found in the document, return an empty string for that field.
Do not add any explanation or text outside the JSON.
Dates should be extracted exactly as they appear in the document.

Look for these specific fields:
- invoice_no: Invoice Number (may appear as "Invoice No", "Invoice #", "Inv No", "Tax Invoice No")
- customer_order_no: Customer Order Number (may appear as "Customer Order No", "Cust PO", "Buyer's Order No")
- so_no: Sales Order Number (may appear as "SO No", "Sales Order", "SO Number")
- invoice_date: Date of Invoice (may appear as "Invoice Date", "Date", "Inv Date", "Dated")
- customer_order_date: Customer Order Date (may appear as "Customer Order Date", "PO Date", "Buyer's Order Date", "Order Date")
- acct_manager: Account Manager name (may appear as "Acct Manager", "Account Manager", "Sales Person", "Sales Rep")

{
    "invoice_no": "",
    "customer_order_no": "",
    "so_no": "",
    "invoice_date": "",
    "customer_order_date": "",
    "acct_manager": ""
}"""

COMPANY_INVOICE_PRIMARY_REF = "invoice_no"
COMPANY_INVOICE_DATE_FIELD = "invoice_date"
```

#### C. Vendor Invoice (`VENDOR_INVOICE`)

```python
VENDOR_INVOICE_SCHEMA = {
    "invoice_no": "",
    "our_order": "",
    "invoice_date": "",
    "customer": "",
    "def_pmnt": "",
    "ack_no": "",
    "ack_date": "",
    "customer_po_no": ""
}

VENDOR_INVOICE_PROMPT = """Analyze this Vendor Invoice document image carefully and extract the following information.
Return ONLY a valid JSON object with the exact structure shown below.
If a field cannot be found in the document, return an empty string for that field.
Do not add any explanation or text outside the JSON.
Dates should be extracted exactly as they appear in the document.

Look for these specific fields:
- invoice_no: Invoice Number (may appear as "Invoice No", "Invoice #", "Inv No", "Tax Invoice No", "Bill No")
- our_order: Our Order reference (may appear as "Our Order", "Your Order", "Order Ref", "PO Ref")
- invoice_date: Date of Invoice (may appear as "Invoice Date", "Date", "Inv Date", "Dated")
- customer: Customer name (may appear as "Customer", "Bill To", "Buyer", "Customer Name", "M/s")
- def_pmnt: Deferred Payment terms (may appear as "Def Pmnt", "Payment Terms", "Credit Period", "Net Days", "Payment")
- ack_no: Acknowledgement Number (may appear as "Ack. No", "Ack No", "Acknowledgement No", "IRN Ack No")
- ack_date: Acknowledgement Date (may appear as "Ack. Date", "Ack Date", "Acknowledgement Date", "IRN Date")
- customer_po_no: Customer PO Number (may appear as "Customer PO No", "PO No", "Purchase Order", "Buyer's Order No")

{
    "invoice_no": "",
    "our_order": "",
    "invoice_date": "",
    "customer": "",
    "def_pmnt": "",
    "ack_no": "",
    "ack_date": "",
    "customer_po_no": ""
}"""

VENDOR_INVOICE_PRIMARY_REF = "invoice_no"
VENDOR_INVOICE_DATE_FIELD = "invoice_date"
```

#### D. Customer Purchase Order (`CUSTOMER_PO`)

```python
CUSTOMER_PO_SCHEMA = {
    "ref_no": "",
    "po_no": "",
    "reference_no": "",
    "po_date": ""
}

CUSTOMER_PO_PROMPT = """Analyze this Purchase Order (PO) document image carefully and extract the following information.
Return ONLY a valid JSON object with the exact structure shown below.
If a field cannot be found in the document, return an empty string for that field.
Do not add any explanation or text outside the JSON.
Dates should be extracted exactly as they appear in the document.

Look for these specific fields:
- ref_no: Reference Number (may appear as "Ref No", "Ref.", "Ref No/", "Our Ref")
- po_no: Purchase Order Number (may appear as "PO No", "PO #", "Purchase Order No", "Order No", "P.O. No")
- reference_no: Additional Reference Number (may appear as "Reference No", "Your Ref", "Quotation Ref", "Quote No")
- po_date: PO Date (may appear as "PO Date", "Date", "Order Date", "Dated")

{
    "ref_no": "",
    "po_no": "",
    "reference_no": "",
    "po_date": ""
}"""

CUSTOMER_PO_PRIMARY_REF = "po_no"
CUSTOMER_PO_DATE_FIELD = "po_date"
```

#### E. Purchase Bill (`PURCHASE_BILL`)

```python
PURCHASE_BILL_SCHEMA = {
    "purchase_bill_no": "",
    "po_no": "",
    "bill_no": "",
    "date": "",
    "due_date": "",
    "bill_date": ""
}

PURCHASE_BILL_PROMPT = """Analyze this Purchase Bill document image carefully and extract the following information.
Return ONLY a valid JSON object with the exact structure shown below.
If a field cannot be found in the document, return an empty string for that field.
Do not add any explanation or text outside the JSON.
Dates should be extracted exactly as they appear in the document.

Look for these specific fields:
- purchase_bill_no: Purchase Bill Number (may appear as "Purchase Bill No", "Bill Number", "PB No")
- po_no: Purchase Order Number (may appear as "PO No", "PO #", "Purchase Order", "Order No")
- bill_no: Bill Number (may appear as "Bill No", "Bill #", "Invoice No", "Vendor Bill No")
- date: General date on the document (may appear as "Date", "Dated")
- due_date: Payment Due Date (may appear as "Due Date", "Payment Due", "Due On", "Pay By")
- bill_date: Bill Date (may appear as "Bill Date", "Invoice Date", "Billing Date")

{
    "purchase_bill_no": "",
    "po_no": "",
    "bill_no": "",
    "date": "",
    "due_date": "",
    "bill_date": ""
}"""

PURCHASE_BILL_PRIMARY_REF = "bill_no"
PURCHASE_BILL_DATE_FIELD = "bill_date"
```

#### F. Proof of Delivery (`POD`)

```python
POD_SCHEMA = {
    "pod_no": "",
    "delivery_date": "",
    "receiver_name": "",
    "dc_ref_no": "",
    "so_no": ""
}

POD_PROMPT = """Analyze this Proof of Delivery (POD) document image carefully and extract the following information.
Return ONLY a valid JSON object with the exact structure shown below.
If a field cannot be found in the document, return an empty string for that field.
Do not add any explanation or text outside the JSON.
Dates should be extracted exactly as they appear in the document.

Look for these specific fields:
- pod_no: POD Number or Receipt Number (may appear as "POD No", "Receipt No", "Delivery Receipt", "LR No", "Docket No")
- delivery_date: Date of Delivery (may appear as "Delivery Date", "Date", "Received Date", "Date of Receipt")
- receiver_name: Name of person who received (may appear as "Received By", "Receiver", "Accepted By", "Signed By")
- dc_ref_no: Delivery Challan Reference (may appear as "DC No", "DC Ref", "Challan Ref", "Reference")
- so_no: Sales Order Number (may appear as "SO No", "Sales Order", "SO Number", "Order No")

{
    "pod_no": "",
    "delivery_date": "",
    "receiver_name": "",
    "dc_ref_no": "",
    "so_no": ""
}"""

POD_PRIMARY_REF = "pod_no"
POD_DATE_FIELD = "delivery_date"
```

### 5.4 Prompt Registry

**File: `backend/app/services/extraction/prompts.py`**

```python
from app.models.document_metadata import DocumentType

PROMPT_REGISTRY = {
    DocumentType.CUSTOMER_PO: {
        "prompt": CUSTOMER_PO_PROMPT,
        "schema": CUSTOMER_PO_SCHEMA,
        "primary_ref_field": "po_no",
        "date_field": "po_date",
    },
    DocumentType.VENDOR_INVOICE: {
        "prompt": VENDOR_INVOICE_PROMPT,
        "schema": VENDOR_INVOICE_SCHEMA,
        "primary_ref_field": "invoice_no",
        "date_field": "invoice_date",
    },
    DocumentType.VENDOR_DC: {
        "prompt": DC_PROMPT,
        "schema": DC_SCHEMA,
        "primary_ref_field": "dc_no",
        "date_field": "dc_date",
    },
    DocumentType.COMPANY_INVOICE: {
        "prompt": COMPANY_INVOICE_PROMPT,
        "schema": COMPANY_INVOICE_SCHEMA,
        "primary_ref_field": "invoice_no",
        "date_field": "invoice_date",
    },
    DocumentType.COMPANY_DC: {
        "prompt": DC_PROMPT,           # Same prompt as VENDOR_DC
        "schema": DC_SCHEMA,
        "primary_ref_field": "dc_no",
        "date_field": "dc_date",
    },
    DocumentType.POD: {
        "prompt": POD_PROMPT,
        "schema": POD_SCHEMA,
        "primary_ref_field": "pod_no",
        "date_field": "delivery_date",
    },
    DocumentType.PURCHASE_BILL: {
        "prompt": PURCHASE_BILL_PROMPT,
        "schema": PURCHASE_BILL_SCHEMA,
        "primary_ref_field": "bill_no",
        "date_field": "bill_date",
    },
}


def get_prompt_config(doc_type: DocumentType) -> dict:
    """Get the prompt configuration for a document type."""
    config = PROMPT_REGISTRY.get(doc_type)
    if not config:
        raise ValueError(f"No prompt configured for document type: {doc_type}")
    return config
```

---

## 6. Backend API — Endpoints & Services

### 6.1 Pydantic Schemas

**File: `backend/app/schemas/document_metadata.py`**

```python
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import date, datetime
from uuid import UUID
from app.models.document_metadata import ExtractionStatus, DocumentType


# --- Response Schemas ---

class MetadataResponse(BaseModel):
    id: UUID
    document_id: UUID
    document_path: str
    doc_type: DocumentType
    primary_ref_no: Optional[str] = None
    doc_date: Optional[date] = None
    extracted_data: Dict[str, Any] = {}
    confidence_score: Optional[float] = None
    status: ExtractionStatus
    raw_ocr_text: Optional[str] = None
    extracted_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExtractionResponse(BaseModel):
    metadata_id: UUID
    status: ExtractionStatus
    extracted_data: Dict[str, Any]
    confidence_score: Optional[float]
    primary_ref_no: Optional[str]
    doc_date: Optional[str]
    message: str


# --- Request Schemas ---

class ExtractionRequest(BaseModel):
    """Trigger extraction for a document."""
    force_re_extract: bool = Field(
        default=False,
        description="Force re-extraction even if metadata already exists"
    )


class MetadataVerifyRequest(BaseModel):
    """Verify/edit extracted metadata."""
    extracted_data: Dict[str, Any] = Field(
        ..., description="The verified/edited extraction data"
    )
    primary_ref_no: Optional[str] = Field(
        None, description="Corrected primary reference number"
    )
    doc_date: Optional[date] = Field(
        None, description="Corrected document date"
    )
    verified_by: str = Field(
        ..., description="Name/ID of the person verifying"
    )


class MetadataListResponse(BaseModel):
    items: list[MetadataResponse]
    total: int
```

### 6.2 API Router

**File: `backend/app/routers/extraction.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import get_db
from app.schemas.document_metadata import (
    ExtractionRequest,
    ExtractionResponse,
    MetadataResponse,
    MetadataVerifyRequest,
    MetadataListResponse,
)
from app.services.extraction.extraction_service import ExtractionService

router = APIRouter(prefix="/api/v1", tags=["extraction"])


@router.post(
    "/documents/{document_id}/extract",
    response_model=ExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger metadata extraction for a document"
)
async def extract_metadata(
    document_id: UUID,
    request: ExtractionRequest = ExtractionRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers AI-powered metadata extraction for the specified document.
    Converts the document PDF to images, sends to GLM-OCR with the
    appropriate prompt for the document type, and stores results.
    """
    service = ExtractionService(db)
    try:
        result = await service.extract(document_id, request.force_re_extract)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.get(
    "/documents/{document_id}/metadata",
    response_model=MetadataResponse,
    summary="Get metadata for a document"
)
async def get_metadata(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the extracted metadata for a specific document."""
    service = ExtractionService(db)
    metadata = await service.get_metadata(document_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="No metadata found for this document")
    return metadata


@router.put(
    "/metadata/{metadata_id}/verify",
    response_model=MetadataResponse,
    summary="Verify or edit extracted metadata"
)
async def verify_metadata(
    metadata_id: UUID,
    request: MetadataVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Human-in-the-loop verification. Accepts edited fields and marks
    the metadata as VERIFIED.
    """
    service = ExtractionService(db)
    try:
        result = await service.verify(metadata_id, request)
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Metadata record not found")


@router.put(
    "/metadata/{metadata_id}/reject",
    response_model=MetadataResponse,
    summary="Reject extraction and reset to PENDING"
)
async def reject_metadata(
    metadata_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Reject the extraction result and allow re-extraction."""
    service = ExtractionService(db)
    result = await service.reject(metadata_id)
    return result


@router.get(
    "/metadata",
    response_model=MetadataListResponse,
    summary="List all metadata records with filters"
)
async def list_metadata(
    doc_type: DocumentType = None,
    status: ExtractionStatus = None,
    primary_ref_no: str = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List metadata records with optional filters."""
    service = ExtractionService(db)
    items, total = await service.list_metadata(
        doc_type=doc_type,
        status=status,
        primary_ref_no=primary_ref_no,
        limit=limit,
        offset=offset,
    )
    return MetadataListResponse(items=items, total=total)
```

### 6.3 Register Router

**In `backend/app/main.py`:**

```python
from app.routers.extraction import router as extraction_router
app.include_router(extraction_router)
```

---

## 7. Extraction Service — Core Pipeline

### 7.1 OCR Client (Abstraction Layer)

**File: `backend/app/services/extraction/ocr_client.py`**

```python
import base64
import json
import logging
import httpx
from pathlib import Path
from app.config import settings

logger = logging.getLogger(__name__)


class OCRClient:
    """
    Abstraction layer for GLM-OCR API calls.
    Supports both Ollama (dev) and vLLM (prod) backends.
    """

    def __init__(self):
        self.backend = settings.OCR_BACKEND  # "ollama" or "vllm"
        self.base_url = settings.OCR_BASE_URL
        self.model_name = settings.OCR_MODEL_NAME
        self.timeout = settings.OCR_TIMEOUT  # seconds

    def _encode_image(self, image_path: str) -> str:
        """Read and base64-encode an image file."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    async def extract(self, image_path: str, prompt: str) -> str:
        """
        Send an image + prompt to GLM-OCR and return the raw text response.

        Args:
            image_path: Path to the image file (JPEG/PNG)
            prompt: The extraction prompt with JSON schema

        Returns:
            Raw text response from the model
        """
        image_b64 = self._encode_image(image_path)

        if self.backend == "ollama":
            return await self._call_ollama(image_b64, prompt)
        elif self.backend == "vllm":
            return await self._call_vllm(image_b64, prompt)
        else:
            raise ValueError(f"Unknown OCR backend: {self.backend}")

    async def _call_ollama(self, image_b64: str, prompt: str) -> str:
        """Call Ollama's chat API."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model_name,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                            "images": [image_b64]
                        }
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.01,
                        "num_predict": 4096
                    }
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]

    async def _call_vllm(self, image_b64: str, prompt: str) -> str:
        """Call vLLM's OpenAI-compatible API."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_b64}"
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": prompt
                                }
                            ]
                        }
                    ],
                    "max_tokens": 4096,
                    "temperature": 0.01
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def health_check(self) -> bool:
        """Check if the OCR service is available."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                if self.backend == "ollama":
                    resp = await client.get(f"{self.base_url}/api/tags")
                else:
                    resp = await client.get(f"{self.base_url}/v1/models")
                return resp.status_code == 200
        except Exception:
            return False
```

### 7.2 PDF-to-Image Converter

**File: `backend/app/services/extraction/pdf_converter.py`**

```python
import os
import logging
import tempfile
from pathlib import Path
from pdf2image import convert_from_path

logger = logging.getLogger(__name__)

# DPI for conversion — 200 balances quality vs size for OCR
DEFAULT_DPI = 200


def pdf_to_images(pdf_path: str, dpi: int = DEFAULT_DPI) -> list[str]:
    """
    Convert a PDF file to a list of JPEG image file paths.

    For single-page PDFs (most documents), returns a single image.
    For multi-page PDFs, returns one image per page.

    Args:
        pdf_path: Path to the PDF file
        dpi: Resolution for conversion (default 200)

    Returns:
        List of temporary image file paths (JPEG)
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # Create temp directory for images
    temp_dir = tempfile.mkdtemp(prefix="ocr_")

    try:
        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            fmt="jpeg",
            output_folder=temp_dir,
            thread_count=2
        )

        image_paths = []
        for i, image in enumerate(images):
            image_path = os.path.join(temp_dir, f"page_{i + 1}.jpg")
            image.save(image_path, "JPEG", quality=95)
            image_paths.append(image_path)
            logger.info(f"Converted page {i + 1} → {image_path}")

        return image_paths

    except Exception as e:
        logger.error(f"PDF conversion failed for {pdf_path}: {e}")
        raise


def cleanup_temp_images(image_paths: list[str]):
    """Remove temporary image files after extraction."""
    for path in image_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            logger.warning(f"Failed to cleanup {path}: {e}")

    # Also remove the temp directory
    if image_paths:
        temp_dir = os.path.dirname(image_paths[0])
        try:
            os.rmdir(temp_dir)
        except Exception:
            pass
```

### 7.3 Response Parser

**File: `backend/app/services/extraction/response_parser.py`**

```python
import json
import re
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import date

logger = logging.getLogger(__name__)


def parse_ocr_response(
    raw_response: str,
    expected_schema: dict,
    primary_ref_field: str,
    date_field: str
) -> Tuple[Dict[str, Any], Optional[str], Optional[date], float]:
    """
    Parse the raw GLM-OCR response into structured data.

    Args:
        raw_response: Raw text from GLM-OCR
        expected_schema: Expected JSON schema (for validation)
        primary_ref_field: Key name for the primary reference
        date_field: Key name for the date field

    Returns:
        Tuple of (extracted_data, primary_ref_no, doc_date, confidence_score)
    """
    # Step 1: Extract JSON from response
    extracted_json = _extract_json(raw_response)

    if not extracted_json:
        logger.warning("Failed to extract JSON from OCR response")
        return {}, None, None, 0.0

    # Step 2: Validate against expected schema
    validated_data = _validate_against_schema(extracted_json, expected_schema)

    # Step 3: Extract promoted fields
    primary_ref = validated_data.get(primary_ref_field, "").strip() or None
    doc_date = _parse_date(validated_data.get(date_field, ""))

    # Step 4: Calculate confidence score
    confidence = _calculate_confidence(validated_data, expected_schema)

    logger.info(
        f"Parsed extraction: ref={primary_ref}, date={doc_date}, "
        f"confidence={confidence:.2f}, fields_found={sum(1 for v in validated_data.values() if v)}"
    )

    return validated_data, primary_ref, doc_date, confidence


def _extract_json(raw_text: str) -> Optional[dict]:
    """
    Extract a JSON object from raw model output.
    Handles common issues like markdown code blocks, extra text, etc.
    """
    text = raw_text.strip()

    # Try 1: Direct JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try 2: Extract from markdown code block
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try 3: Find first { ... } block
    brace_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    # Try 4: Fix common JSON issues (trailing commas, single quotes)
    cleaned = text
    cleaned = re.sub(r',\s*}', '}', cleaned)   # trailing commas
    cleaned = re.sub(r',\s*]', ']', cleaned)
    cleaned = cleaned.replace("'", '"')          # single → double quotes
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    logger.error(f"Could not extract JSON from response: {text[:200]}...")
    return None


def _validate_against_schema(data: dict, schema: dict) -> dict:
    """
    Validate extracted data against the expected schema.
    Only keeps keys that are in the schema. Ensures all values are strings.
    """
    validated = {}
    for key in schema:
        value = data.get(key, "")
        # Ensure string type
        if value is None:
            value = ""
        elif not isinstance(value, str):
            value = str(value)
        validated[key] = value.strip()

    return validated


def _parse_date(date_str: str) -> Optional[date]:
    """
    Try to parse a date string in various formats.
    Returns None if parsing fails.
    """
    if not date_str or not date_str.strip():
        return None

    date_str = date_str.strip()

    # Common date formats found in Indian business documents
    formats = [
        "%d-%m-%Y",      # 15-01-2026
        "%d/%m/%Y",      # 15/01/2026
        "%d.%m.%Y",      # 15.01.2026
        "%Y-%m-%d",      # 2026-01-15
        "%d-%b-%Y",      # 15-Jan-2026
        "%d %b %Y",      # 15 Jan 2026
        "%d %B %Y",      # 15 January 2026
        "%d-%m-%y",      # 15-01-26
        "%d/%m/%y",      # 15/01/26
        "%m/%d/%Y",      # 01/15/2026
        "%b %d, %Y",     # Jan 15, 2026
        "%B %d, %Y",     # January 15, 2026
    ]

    from datetime import datetime as dt

    for fmt in formats:
        try:
            return dt.strptime(date_str, fmt).date()
        except ValueError:
            continue

    logger.warning(f"Could not parse date: {date_str}")
    return None


def _calculate_confidence(data: dict, schema: dict) -> float:
    """
    Calculate a confidence score based on how many fields were extracted.

    Score = (non-empty fields / total expected fields) * 100

    This is a basic heuristic. In future, GLM-OCR's internal confidence
    scores could be used if available.
    """
    total_fields = len(schema)
    if total_fields == 0:
        return 0.0

    filled_fields = sum(1 for key in schema if data.get(key, "").strip())
    return round((filled_fields / total_fields) * 100, 2)
```

### 7.4 Main Extraction Service

**File: `backend/app/services/extraction/extraction_service.py`**

```python
import logging
from datetime import datetime
from uuid import UUID
from typing import Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_metadata import (
    DocumentMetadata, ExtractionStatus, DocumentType
)
from app.models.audit_log import AuditLog
from app.schemas.document_metadata import (
    ExtractionResponse, MetadataResponse, MetadataVerifyRequest
)
from app.services.extraction.ocr_client import OCRClient
from app.services.extraction.pdf_converter import pdf_to_images, cleanup_temp_images
from app.services.extraction.response_parser import parse_ocr_response
from app.services.extraction.prompts import get_prompt_config

logger = logging.getLogger(__name__)


class ExtractionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.ocr_client = OCRClient()

    async def extract(
        self, document_id: UUID, force: bool = False
    ) -> ExtractionResponse:
        """
        Full extraction pipeline for a document.

        Steps:
        1. Load document record
        2. Check for existing metadata
        3. Convert PDF → images
        4. Call GLM-OCR with doc-type-specific prompt
        5. Parse response
        6. Save metadata to DB
        7. Create audit log entry
        """

        # Step 1: Load document
        doc = await self._get_document(document_id)
        if not doc:
            raise FileNotFoundError(f"Document not found: {document_id}")

        # Step 2: Check existing metadata
        existing = await self._get_existing_metadata(document_id)
        if existing and not force:
            if existing.status == ExtractionStatus.VERIFIED:
                raise ValueError(
                    "Document already has verified metadata. "
                    "Use force_re_extract=true to override."
                )
            if existing.status == ExtractionStatus.EXTRACTED:
                # Return existing extraction for review
                return ExtractionResponse(
                    metadata_id=existing.id,
                    status=existing.status,
                    extracted_data=existing.extracted_data,
                    confidence_score=existing.confidence_score,
                    primary_ref_no=existing.primary_ref_no,
                    doc_date=str(existing.doc_date) if existing.doc_date else None,
                    message="Extraction already exists. Showing existing results."
                )

        # Step 3: Get prompt config for this doc type
        doc_type = DocumentType(doc.doc_type)
        prompt_config = get_prompt_config(doc_type)

        # Step 4: Convert PDF to images
        image_paths = []
        try:
            image_paths = pdf_to_images(doc.file_path)
            if not image_paths:
                raise ValueError("PDF conversion produced no images")

            # Step 5: Call GLM-OCR (use first page — most business docs are single-page)
            # For multi-page documents, you could process all pages and merge
            raw_response = await self.ocr_client.extract(
                image_path=image_paths[0],
                prompt=prompt_config["prompt"]
            )

            logger.info(f"OCR raw response for {document_id}: {raw_response[:200]}...")

            # Step 6: Parse response
            extracted_data, primary_ref, doc_date, confidence = parse_ocr_response(
                raw_response=raw_response,
                expected_schema=prompt_config["schema"],
                primary_ref_field=prompt_config["primary_ref_field"],
                date_field=prompt_config["date_field"]
            )

            # Step 7: Save to DB
            metadata = await self._save_metadata(
                document_id=document_id,
                document_path=doc.file_path,
                doc_type=doc_type,
                extracted_data=extracted_data,
                primary_ref_no=primary_ref,
                doc_date=doc_date,
                confidence_score=confidence,
                raw_ocr_text=raw_response,
                status=ExtractionStatus.EXTRACTED,
                existing=existing
            )

            # Step 8: Audit log
            await self._create_audit_log(
                action="METADATA_EXTRACTED",
                document_id=document_id,
                details={
                    "metadata_id": str(metadata.id),
                    "confidence": confidence,
                    "fields_extracted": sum(
                        1 for v in extracted_data.values() if v
                    )
                }
            )

            return ExtractionResponse(
                metadata_id=metadata.id,
                status=metadata.status,
                extracted_data=metadata.extracted_data,
                confidence_score=metadata.confidence_score,
                primary_ref_no=metadata.primary_ref_no,
                doc_date=str(metadata.doc_date) if metadata.doc_date else None,
                message="Extraction successful. Please review and verify."
            )

        except Exception as e:
            # Save failed status
            if existing or True:
                await self._save_metadata(
                    document_id=document_id,
                    document_path=doc.file_path,
                    doc_type=doc_type,
                    extracted_data={},
                    primary_ref_no=None,
                    doc_date=None,
                    confidence_score=0.0,
                    raw_ocr_text=str(e),
                    status=ExtractionStatus.FAILED,
                    existing=existing
                )
            logger.error(f"Extraction failed for {document_id}: {e}")
            raise

        finally:
            # Cleanup temp images
            cleanup_temp_images(image_paths)

    async def get_metadata(self, document_id: UUID) -> Optional[DocumentMetadata]:
        """Get metadata for a document."""
        result = await self.db.execute(
            select(DocumentMetadata).where(
                DocumentMetadata.document_id == document_id
            )
        )
        return result.scalar_one_or_none()

    async def verify(
        self, metadata_id: UUID, request: MetadataVerifyRequest
    ) -> DocumentMetadata:
        """Verify/edit extracted metadata."""
        result = await self.db.execute(
            select(DocumentMetadata).where(DocumentMetadata.id == metadata_id)
        )
        metadata = result.scalar_one_or_none()
        if not metadata:
            raise FileNotFoundError(f"Metadata not found: {metadata_id}")

        # Update with verified data
        metadata.extracted_data = request.extracted_data
        metadata.primary_ref_no = request.primary_ref_no or metadata.primary_ref_no
        metadata.doc_date = request.doc_date or metadata.doc_date
        metadata.status = ExtractionStatus.VERIFIED
        metadata.verified_by = request.verified_by
        metadata.verified_at = datetime.utcnow()
        metadata.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(metadata)

        # Audit log
        await self._create_audit_log(
            action="METADATA_VERIFIED",
            document_id=metadata.document_id,
            details={
                "metadata_id": str(metadata_id),
                "verified_by": request.verified_by
            }
        )

        return metadata

    async def reject(self, metadata_id: UUID) -> DocumentMetadata:
        """Reject extraction and reset to PENDING."""
        result = await self.db.execute(
            select(DocumentMetadata).where(DocumentMetadata.id == metadata_id)
        )
        metadata = result.scalar_one_or_none()
        if not metadata:
            raise FileNotFoundError(f"Metadata not found: {metadata_id}")

        metadata.status = ExtractionStatus.PENDING
        metadata.extracted_data = {}
        metadata.primary_ref_no = None
        metadata.doc_date = None
        metadata.confidence_score = None
        metadata.verified_by = None
        metadata.verified_at = None
        metadata.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(metadata)
        return metadata

    async def list_metadata(
        self,
        doc_type=None,
        status=None,
        primary_ref_no=None,
        limit=50,
        offset=0
    ) -> Tuple[list, int]:
        """List metadata records with optional filters."""
        query = select(DocumentMetadata)
        count_query = select(func.count(DocumentMetadata.id))

        if doc_type:
            query = query.where(DocumentMetadata.doc_type == doc_type)
            count_query = count_query.where(DocumentMetadata.doc_type == doc_type)
        if status:
            query = query.where(DocumentMetadata.status == status)
            count_query = count_query.where(DocumentMetadata.status == status)
        if primary_ref_no:
            query = query.where(
                DocumentMetadata.primary_ref_no.ilike(f"%{primary_ref_no}%")
            )
            count_query = count_query.where(
                DocumentMetadata.primary_ref_no.ilike(f"%{primary_ref_no}%")
            )

        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        query = query.order_by(DocumentMetadata.created_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        items = result.scalars().all()

        return list(items), total

    # --- Private Helpers ---

    async def _get_document(self, document_id: UUID) -> Optional[Document]:
        result = await self.db.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def _get_existing_metadata(
        self, document_id: UUID
    ) -> Optional[DocumentMetadata]:
        result = await self.db.execute(
            select(DocumentMetadata).where(
                DocumentMetadata.document_id == document_id
            )
        )
        return result.scalar_one_or_none()

    async def _save_metadata(
        self,
        document_id,
        document_path,
        doc_type,
        extracted_data,
        primary_ref_no,
        doc_date,
        confidence_score,
        raw_ocr_text,
        status,
        existing=None
    ) -> DocumentMetadata:
        """Create or update metadata record."""
        if existing:
            existing.document_path = document_path
            existing.doc_type = doc_type
            existing.extracted_data = extracted_data
            existing.primary_ref_no = primary_ref_no
            existing.doc_date = doc_date
            existing.confidence_score = confidence_score
            existing.raw_ocr_text = raw_ocr_text
            existing.status = status
            existing.extracted_at = datetime.utcnow()
            existing.updated_at = datetime.utcnow()
            # Clear verification on re-extract
            existing.verified_by = None
            existing.verified_at = None

            await self.db.commit()
            await self.db.refresh(existing)
            return existing
        else:
            metadata = DocumentMetadata(
                document_id=document_id,
                document_path=document_path,
                doc_type=doc_type,
                extracted_data=extracted_data,
                primary_ref_no=primary_ref_no,
                doc_date=doc_date,
                confidence_score=confidence_score,
                raw_ocr_text=raw_ocr_text,
                status=status,
                extracted_at=datetime.utcnow()
            )
            self.db.add(metadata)
            await self.db.commit()
            await self.db.refresh(metadata)
            return metadata

    async def _create_audit_log(self, action, document_id, details):
        """Create an audit log entry."""
        log = AuditLog(
            action=action,
            entity_type="document_metadata",
            entity_id=str(document_id),
            details=details,
            actor="system"
        )
        self.db.add(log)
        await self.db.commit()
```

---

## 8. Frontend — Review & Verification UI

### 8.1 API Client Layer

**File: `frontend/src/api/extraction.ts`**

```typescript
import axios from './client';  // Your existing Axios instance

export interface ExtractionResponse {
  metadata_id: string;
  status: 'PENDING' | 'EXTRACTED' | 'VERIFIED' | 'FAILED';
  extracted_data: Record<string, string>;
  confidence_score: number | null;
  primary_ref_no: string | null;
  doc_date: string | null;
  message: string;
}

export interface MetadataResponse {
  id: string;
  document_id: string;
  document_path: string;
  doc_type: string;
  primary_ref_no: string | null;
  doc_date: string | null;
  extracted_data: Record<string, string>;
  confidence_score: number | null;
  status: string;
  extracted_at: string | null;
  verified_by: string | null;
  verified_at: string | null;
}

export interface VerifyRequest {
  extracted_data: Record<string, string>;
  primary_ref_no?: string;
  doc_date?: string;
  verified_by: string;
}

// Trigger extraction
export const triggerExtraction = async (
  documentId: string,
  forceReExtract: boolean = false
): Promise<ExtractionResponse> => {
  const { data } = await axios.post(
    `/api/v1/documents/${documentId}/extract`,
    { force_re_extract: forceReExtract }
  );
  return data;
};

// Get existing metadata
export const getMetadata = async (
  documentId: string
): Promise<MetadataResponse> => {
  const { data } = await axios.get(
    `/api/v1/documents/${documentId}/metadata`
  );
  return data;
};

// Verify metadata
export const verifyMetadata = async (
  metadataId: string,
  request: VerifyRequest
): Promise<MetadataResponse> => {
  const { data } = await axios.put(
    `/api/v1/metadata/${metadataId}/verify`,
    request
  );
  return data;
};

// Reject metadata
export const rejectMetadata = async (
  metadataId: string
): Promise<MetadataResponse> => {
  const { data } = await axios.put(
    `/api/v1/metadata/${metadataId}/reject`
  );
  return data;
};
```

### 8.2 Field Label Mapping

**File: `frontend/src/config/fieldLabels.ts`**

```typescript
/**
 * Human-readable labels for each field, per document type.
 * Used in the Review Modal to display friendly names.
 */
export const FIELD_LABELS: Record<string, Record<string, string>> = {
  CUSTOMER_PO: {
    ref_no: "Reference No",
    po_no: "PO Number",
    reference_no: "Quotation / Additional Ref No",
    po_date: "PO Date",
  },
  VENDOR_INVOICE: {
    invoice_no: "Invoice Number",
    our_order: "Our Order Ref",
    invoice_date: "Invoice Date",
    customer: "Customer Name",
    def_pmnt: "Payment Terms",
    ack_no: "Acknowledgement No (IRN)",
    ack_date: "Acknowledgement Date",
    customer_po_no: "Customer PO Number",
  },
  VENDOR_DC: {
    dc_no: "DC Number",
    customer_order_no: "Customer Order No",
    dc_date: "DC Date",
    so_no: "Sales Order No",
  },
  COMPANY_INVOICE: {
    invoice_no: "Invoice Number",
    customer_order_no: "Customer Order No",
    so_no: "Sales Order No",
    invoice_date: "Invoice Date",
    customer_order_date: "Customer Order Date",
    acct_manager: "Account Manager",
  },
  COMPANY_DC: {
    dc_no: "DC Number",
    customer_order_no: "Customer Order No",
    dc_date: "DC Date",
    so_no: "Sales Order No",
  },
  POD: {
    pod_no: "POD / Receipt Number",
    delivery_date: "Delivery Date",
    receiver_name: "Received By",
    dc_ref_no: "DC Reference No",
    so_no: "Sales Order No",
  },
  PURCHASE_BILL: {
    purchase_bill_no: "Purchase Bill No",
    po_no: "PO Number",
    bill_no: "Bill Number",
    date: "Date",
    due_date: "Due Date",
    bill_date: "Bill Date",
  },
};
```

### 8.3 Extract Button Component

**File: `frontend/src/components/extraction/ExtractButton.tsx`**

```tsx
import React, { useState } from 'react';
import { triggerExtraction, ExtractionResponse } from '../../api/extraction';

interface ExtractButtonProps {
  documentId: string;
  currentStatus?: string;  // existing metadata status if any
  onExtractionComplete: (result: ExtractionResponse) => void;
}

export const ExtractButton: React.FC<ExtractButtonProps> = ({
  documentId,
  currentStatus,
  onExtractionComplete,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleExtract = async () => {
    setLoading(true);
    setError(null);

    try {
      const forceReExtract = currentStatus === 'EXTRACTED' || currentStatus === 'FAILED';
      const result = await triggerExtraction(documentId, forceReExtract);
      onExtractionComplete(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Extraction failed');
    } finally {
      setLoading(false);
    }
  };

  const getButtonLabel = () => {
    if (loading) return 'Extracting...';
    if (currentStatus === 'VERIFIED') return 'Re-Extract';
    if (currentStatus === 'EXTRACTED') return 'Re-Extract';
    if (currentStatus === 'FAILED') return 'Retry Extract';
    return 'Extract Metadata';
  };

  const getButtonColor = () => {
    if (currentStatus === 'VERIFIED') return 'bg-green-600 hover:bg-green-700';
    if (currentStatus === 'FAILED') return 'bg-red-600 hover:bg-red-700';
    return 'bg-blue-600 hover:bg-blue-700';
  };

  return (
    <div>
      <button
        onClick={handleExtract}
        disabled={loading}
        className={`${getButtonColor()} text-white px-4 py-2 rounded-lg
          flex items-center gap-2 disabled:opacity-50 transition-colors`}
      >
        {loading && (
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10"
              stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        )}
        {getButtonLabel()}
      </button>

      {error && (
        <p className="text-red-500 text-sm mt-2">{error}</p>
      )}
    </div>
  );
};
```

### 8.4 Review & Verification Modal

**File: `frontend/src/components/extraction/ReviewModal.tsx`**

```tsx
import React, { useState, useEffect } from 'react';
import { verifyMetadata, rejectMetadata, ExtractionResponse } from '../../api/extraction';
import { FIELD_LABELS } from '../../config/fieldLabels';

interface ReviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  extraction: ExtractionResponse;
  docType: string;
  documentPath: string;
  onVerified: () => void;
}

export const ReviewModal: React.FC<ReviewModalProps> = ({
  isOpen,
  onClose,
  extraction,
  docType,
  documentPath,
  onVerified,
}) => {
  const [editedData, setEditedData] = useState<Record<string, string>>({});
  const [verifying, setVerifying] = useState(false);
  const [rejecting, setRejecting] = useState(false);

  useEffect(() => {
    if (extraction?.extracted_data) {
      setEditedData({ ...extraction.extracted_data });
    }
  }, [extraction]);

  if (!isOpen) return null;

  const labels = FIELD_LABELS[docType] || {};

  const handleFieldChange = (key: string, value: string) => {
    setEditedData(prev => ({ ...prev, [key]: value }));
  };

  const handleVerify = async () => {
    setVerifying(true);
    try {
      await verifyMetadata(extraction.metadata_id, {
        extracted_data: editedData,
        primary_ref_no: extraction.primary_ref_no || undefined,
        doc_date: extraction.doc_date || undefined,
        verified_by: "current_user",  // Replace with actual user context
      });
      onVerified();
      onClose();
    } catch (err) {
      console.error('Verification failed:', err);
    } finally {
      setVerifying(false);
    }
  };

  const handleReject = async () => {
    setRejecting(true);
    try {
      await rejectMetadata(extraction.metadata_id);
      onClose();
    } catch (err) {
      console.error('Rejection failed:', err);
    } finally {
      setRejecting(false);
    }
  };

  const confidenceColor = (score: number | null) => {
    if (!score) return 'text-gray-500';
    if (score >= 80) return 'text-green-600';
    if (score >= 50) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center
      justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full
        max-h-[90vh] overflow-hidden flex flex-col">

        {/* Header */}
        <div className="px-6 py-4 border-b bg-gray-50 flex justify-between
          items-center">
          <div>
            <h2 className="text-lg font-semibold text-gray-800">
              Review Extracted Metadata
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              Document Type: <span className="font-medium">{docType}</span>
              {' '} | Confidence:{' '}
              <span className={`font-medium ${confidenceColor(extraction.confidence_score)}`}>
                {extraction.confidence_score?.toFixed(1)}%
              </span>
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400
            hover:text-gray-600 text-xl">✕</button>
        </div>

        {/* Body — split view */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

            {/* Left: Document Preview (PDF) */}
            <div className="border rounded-lg overflow-hidden bg-gray-100">
              <div className="p-2 bg-gray-200 text-sm font-medium
                text-gray-600">
                Document Preview
              </div>
              <iframe
                src={`/api/v1/documents/preview?path=${encodeURIComponent(documentPath)}`}
                className="w-full h-96 lg:h-full"
                title="Document Preview"
              />
            </div>

            {/* Right: Extracted Fields (Editable) */}
            <div>
              <h3 className="text-sm font-semibold text-gray-600 mb-4
                uppercase tracking-wide">
                Extracted Fields
              </h3>

              <div className="space-y-4">
                {Object.entries(editedData).map(([key, value]) => (
                  <div key={key}>
                    <label className="block text-sm font-medium
                      text-gray-700 mb-1">
                      {labels[key] || key}
                    </label>
                    <input
                      type="text"
                      value={value}
                      onChange={(e) => handleFieldChange(key, e.target.value)}
                      className={`w-full px-3 py-2 border rounded-lg
                        text-sm focus:ring-2 focus:ring-blue-500
                        focus:border-blue-500 ${
                          !value ? 'border-red-300 bg-red-50' : 'border-gray-300'
                        }`}
                      placeholder={`Enter ${labels[key] || key}`}
                    />
                    {!value && (
                      <p className="text-xs text-red-500 mt-1">
                        Not found — please fill manually
                      </p>
                    )}
                  </div>
                ))}
              </div>

              {/* Document Path (read-only) */}
              <div className="mt-6 p-3 bg-gray-50 rounded-lg">
                <label className="block text-xs font-medium text-gray-500
                  mb-1">
                  Document Path
                </label>
                <p className="text-sm text-gray-700 font-mono break-all">
                  {documentPath}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Footer — Actions */}
        <div className="px-6 py-4 border-t bg-gray-50 flex justify-between">
          <button
            onClick={handleReject}
            disabled={rejecting}
            className="px-4 py-2 border border-red-300 text-red-600
              rounded-lg hover:bg-red-50 transition-colors disabled:opacity-50"
          >
            {rejecting ? 'Rejecting...' : 'Reject & Re-extract'}
          </button>

          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 text-gray-600
                rounded-lg hover:bg-gray-100 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleVerify}
              disabled={verifying}
              className="px-6 py-2 bg-green-600 text-white rounded-lg
                hover:bg-green-700 transition-colors disabled:opacity-50
                flex items-center gap-2"
            >
              {verifying ? 'Saving...' : '✓ Verify & Save'}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
};
```

### 8.5 Status Badge Component

**File: `frontend/src/components/extraction/StatusBadge.tsx`**

```tsx
import React from 'react';

interface StatusBadgeProps {
  status: 'PENDING' | 'EXTRACTED' | 'VERIFIED' | 'FAILED' | null;
}

const STATUS_CONFIG = {
  PENDING: { label: 'Pending', bg: 'bg-gray-100', text: 'text-gray-600', dot: 'bg-gray-400' },
  EXTRACTED: { label: 'Needs Review', bg: 'bg-yellow-100', text: 'text-yellow-700', dot: 'bg-yellow-500' },
  VERIFIED: { label: 'Verified', bg: 'bg-green-100', text: 'text-green-700', dot: 'bg-green-500' },
  FAILED: { label: 'Failed', bg: 'bg-red-100', text: 'text-red-700', dot: 'bg-red-500' },
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  if (!status) return null;

  const config = STATUS_CONFIG[status];

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5
      rounded-full text-xs font-medium ${config.bg} ${config.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
      {config.label}
    </span>
  );
};
```

---

## 9. Docker Compose Updates

### 9.1 Updated `docker-compose.yml`

Add the OCR service container alongside your existing services:

```yaml
version: '3.8'

services:
  # --- Existing Phase 1 services ---

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: docplatform
      POSTGRES_USER: docuser
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://docuser:${DB_PASSWORD}@db:5432/docplatform
      - OCR_BACKEND=${OCR_BACKEND:-ollama}
      - OCR_BASE_URL=${OCR_BASE_URL:-http://ocr-service:11434}
      - OCR_MODEL_NAME=${OCR_MODEL_NAME:-glm-ocr}
      - OCR_TIMEOUT=${OCR_TIMEOUT:-120}
    volumes:
      - nas_storage:/nas
    depends_on:
      - db
      - ocr-service

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend

  # --- NEW: Phase 2 OCR Service ---

  ocr-service:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_models:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    # Auto-pull the model on startup
    entrypoint: ["/bin/bash", "-c"]
    command:
      - |
        ollama serve &
        sleep 5
        ollama pull glm-ocr
        wait

volumes:
  pgdata:
  nas_storage:
  ollama_models:    # Persist downloaded models
```

### 9.2 Production Docker Compose Override

**File: `docker-compose.prod.yml`**

```yaml
version: '3.8'

services:
  # Override OCR service for production (vLLM)
  ocr-service:
    image: vllm/vllm-openai:latest
    ports:
      - "8080:8080"
    command:
      - "--model"
      - "zai-org/GLM-OCR"
      - "--allowed-local-media-path"
      - "/"
      - "--port"
      - "8080"
      - "--gpu-memory-utilization"
      - "0.85"
      - "--max-model-len"
      - "8192"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - huggingface_cache:/root/.cache/huggingface

  backend:
    environment:
      - OCR_BACKEND=vllm
      - OCR_BASE_URL=http://ocr-service:8080
      - OCR_MODEL_NAME=zai-org/GLM-OCR

volumes:
  huggingface_cache:
```

**Usage:**
```bash
# Development
docker compose up

# Production
docker compose -f docker-compose.yml -f docker-compose.prod.yml up
```

---

## 10. Configuration & Environment Variables

### 10.1 Backend Config Update

**File: `backend/app/config.py`** — Add these fields:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # ... existing Phase 1 settings ...

    # --- Phase 2: OCR Configuration ---
    OCR_BACKEND: str = "ollama"              # "ollama" or "vllm"
    OCR_BASE_URL: str = "http://localhost:11434"
    OCR_MODEL_NAME: str = "glm-ocr"
    OCR_TIMEOUT: int = 120                   # seconds
    OCR_MAX_RETRIES: int = 3
    OCR_PDF_DPI: int = 200                   # DPI for PDF → image conversion
    OCR_MAX_PAGES: int = 3                   # Max pages to process per document

    class Config:
        env_file = ".env"

settings = Settings()
```

### 10.2 Environment File

**File: `.env`** — Add:

```bash
# --- Phase 2: OCR Settings ---
OCR_BACKEND=ollama
OCR_BASE_URL=http://localhost:11434
OCR_MODEL_NAME=glm-ocr
OCR_TIMEOUT=120
OCR_MAX_RETRIES=3
OCR_PDF_DPI=200
OCR_MAX_PAGES=3
```

### 10.3 Backend Dependencies

**Add to `backend/requirements.txt`:**

```
# Phase 2 — Extraction
httpx>=0.25.0          # Async HTTP client for OCR API calls
pdf2image>=1.17.0      # PDF to image conversion
Pillow>=10.0.0         # Image processing (dependency of pdf2image)
```

**System dependency (Dockerfile):**
```dockerfile
# Add poppler-utils for pdf2image
RUN apt-get update && apt-get install -y poppler-utils && rm -rf /var/lib/apt/lists/*
```

---

## 11. Error Handling & Retry Strategy

### 11.1 Error Types and Handling

| Error | Cause | Action |
|-------|-------|--------|
| **OCR service unavailable** | Ollama/vLLM not running | Return 503, log, show "OCR service offline" in UI |
| **PDF conversion fails** | Corrupted PDF, no poppler | Return 400, set status=FAILED |
| **JSON parse fails** | Model returned non-JSON | Retry up to 3 times, then set status=FAILED |
| **Empty extraction** | Model couldn't read doc | Set confidence=0, status=EXTRACTED, flag in UI |
| **Timeout** | Large/complex document | Increase timeout, retry once, then FAILED |

### 11.2 Retry Logic

```python
# In extraction_service.py — wrap the OCR call

import asyncio

async def _call_ocr_with_retry(
    self, image_path: str, prompt: str, max_retries: int = 3
) -> str:
    """Call OCR with retry logic."""
    last_error = None

    for attempt in range(max_retries):
        try:
            response = await self.ocr_client.extract(image_path, prompt)

            # Validate we got a parseable response
            if response and response.strip():
                return response

            raise ValueError("Empty OCR response")

        except Exception as e:
            last_error = e
            logger.warning(
                f"OCR attempt {attempt + 1}/{max_retries} failed: {e}"
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

    raise last_error or Exception("OCR extraction failed after all retries")
```

---

## 12. Testing Strategy

### 12.1 Unit Tests

**File: `backend/tests/test_response_parser.py`**

```python
import pytest
from app.services.extraction.response_parser import (
    parse_ocr_response, _extract_json, _parse_date
)

class TestExtractJson:
    def test_direct_json(self):
        result = _extract_json('{"invoice_no": "INV-001", "date": "15-01-2026"}')
        assert result == {"invoice_no": "INV-001", "date": "15-01-2026"}

    def test_json_in_code_block(self):
        raw = '```json\n{"po_no": "PO-123"}\n```'
        result = _extract_json(raw)
        assert result == {"po_no": "PO-123"}

    def test_json_with_extra_text(self):
        raw = 'Here is the result:\n{"dc_no": "DC-456"}\nDone.'
        result = _extract_json(raw)
        assert result == {"dc_no": "DC-456"}

    def test_trailing_comma(self):
        raw = '{"invoice_no": "INV-001", "date": "01-01-2026",}'
        result = _extract_json(raw)
        assert result is not None

    def test_invalid_json(self):
        result = _extract_json("This is not JSON at all")
        assert result is None


class TestParseDate:
    def test_dd_mm_yyyy(self):
        assert _parse_date("15-01-2026") is not None

    def test_dd_slash_mm_slash_yyyy(self):
        assert _parse_date("15/01/2026") is not None

    def test_iso_format(self):
        assert _parse_date("2026-01-15") is not None

    def test_named_month(self):
        assert _parse_date("15-Jan-2026") is not None

    def test_empty_string(self):
        assert _parse_date("") is None

    def test_invalid_date(self):
        assert _parse_date("not-a-date") is None


class TestParseOcrResponse:
    def test_full_vendor_invoice(self):
        raw = '{"invoice_no":"INV-2026-001","our_order":"ORD-123","invoice_date":"15-01-2026","customer":"ABC Corp","def_pmnt":"Net 30","ack_no":"ACK-001","ack_date":"16-01-2026","customer_po_no":"PO-456"}'
        schema = {
            "invoice_no": "", "our_order": "", "invoice_date": "",
            "customer": "", "def_pmnt": "", "ack_no": "",
            "ack_date": "", "customer_po_no": ""
        }
        data, ref, dt, conf = parse_ocr_response(raw, schema, "invoice_no", "invoice_date")

        assert ref == "INV-2026-001"
        assert dt is not None
        assert conf == 100.0
        assert data["customer"] == "ABC Corp"

    def test_partial_extraction(self):
        raw = '{"dc_no":"DC-001","customer_order_no":"","dc_date":"","so_no":"SO-999"}'
        schema = {"dc_no": "", "customer_order_no": "", "dc_date": "", "so_no": ""}
        data, ref, dt, conf = parse_ocr_response(raw, schema, "dc_no", "dc_date")

        assert ref == "DC-001"
        assert dt is None
        assert conf == 50.0  # 2 out of 4 fields
```

### 12.2 Integration Test (with mock OCR)

```python
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from app.main import app

@pytest.fixture
def mock_ocr_response():
    return '{"invoice_no": "INV-TEST-001", "invoice_date": "01-02-2026"}'

@pytest.mark.asyncio
async def test_extraction_endpoint(mock_ocr_response):
    with patch(
        'app.services.extraction.ocr_client.OCRClient.extract',
        new_callable=AsyncMock,
        return_value=mock_ocr_response
    ):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/documents/{test_doc_id}/extract"
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "EXTRACTED"
            assert data["extracted_data"]["invoice_no"] == "INV-TEST-001"
```

### 12.3 Manual Testing Checklist

```
□ Upload a digital PDF invoice → Extract → Review → Verify
□ Upload a scanned/photo PDF → Extract → Check accuracy
□ Extract with missing fields → Verify UI shows red highlights
□ Edit a field in review modal → Save → Confirm DB updated
□ Reject extraction → Re-extract → Verify new results
□ Force re-extract on verified document → Verify clears verification
□ Test with each document type (6 types)
□ Test with multi-page PDF → Verify first page extracted
□ Disconnect OCR service → Verify proper error message
□ Test concurrent extractions → Verify no race conditions
```

---

## 13. Deployment Guide

### 13.1 Development — Step by Step

```bash
# 1. Start the platform (Phase 1 services + new OCR service)
docker compose up -d

# 2. Wait for Ollama to download GLM-OCR model (~1.5GB)
docker compose logs -f ocr-service
# Look for: "pulling manifest... pulling layer... success"

# 3. Verify OCR service is running
curl http://localhost:11434/api/tags
# Should show glm-ocr in the list

# 4. Run the database migration
docker compose exec backend alembic upgrade head

# 5. Verify the new table exists
docker compose exec db psql -U docuser -d docplatform \
  -c "SELECT * FROM document_metadata LIMIT 1;"

# 6. Install new Python dependencies
docker compose exec backend pip install httpx pdf2image Pillow

# 7. Restart backend to pick up new code
docker compose restart backend

# 8. Test extraction via API
curl -X POST http://localhost:8000/api/v1/documents/{DOC_ID}/extract
```

### 13.2 Production — Step by Step

```bash
# 1. Deploy with production override
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 2. vLLM will auto-download the model from HuggingFace
docker compose logs -f ocr-service

# 3. Run migration
docker compose exec backend alembic upgrade head

# 4. Verify health
curl http://localhost:8080/v1/models
# Should return: {"data": [{"id": "zai-org/GLM-OCR"}]}

# 5. Monitor GPU usage
nvidia-smi
```

---

## 14. Future Enhancements

### Phase 2.1 — Short Term
- **Batch extraction**: "Extract All" button for all documents in a Sales Order
- **Auto-extract on upload**: Option to trigger extraction immediately after upload
- **Confidence thresholds**: Auto-verify if confidence ≥ 95%, auto-flag if ≤ 50%

### Phase 2.2 — Medium Term
- **Multi-page support**: Merge extractions from all pages of a PDF
- **DeepSeek OCR 2 fallback**: Route failed extractions to DeepSeek OCR 2 for a second attempt
- **Template learning**: Learn from verified corrections to improve prompts over time
- **Search by metadata**: Search across all documents by invoice number, PO number, date range, etc.

### Phase 2.3 — Long Term
- **Cross-document validation**: Auto-check that PO numbers on vendor invoices match uploaded Customer POs
- **Dashboard analytics**: Extraction success rates, average confidence by doc type, verification turnaround time
- **Webhook notifications**: Alert when extraction fails or needs review

---

## File Structure Summary (New/Modified Files)

```
backend/
├── alembic/versions/
│   └── xxxx_add_document_metadata.py          # NEW — Migration
├── app/
│   ├── models/
│   │   ├── document.py                        # MODIFIED — add relationship
│   │   └── document_metadata.py               # NEW — SQLAlchemy model
│   ├── schemas/
│   │   └── document_metadata.py               # NEW — Pydantic schemas
│   ├── routers/
│   │   └── extraction.py                      # NEW — API endpoints
│   ├── services/
│   │   └── extraction/
│   │       ├── __init__.py                    # NEW
│   │       ├── extraction_service.py          # NEW — Main service
│   │       ├── ocr_client.py                  # NEW — GLM-OCR client
│   │       ├── pdf_converter.py               # NEW — PDF → images
│   │       ├── response_parser.py             # NEW — JSON parsing
│   │       └── prompts.py                     # NEW — Prompt registry
│   └── config.py                              # MODIFIED — OCR settings
├── requirements.txt                           # MODIFIED — new deps
└── tests/
    └── test_response_parser.py                # NEW — Unit tests

frontend/
├── src/
│   ├── api/
│   │   └── extraction.ts                      # NEW — API client
│   ├── components/
│   │   └── extraction/
│   │       ├── ExtractButton.tsx              # NEW
│   │       ├── ReviewModal.tsx                # NEW
│   │       └── StatusBadge.tsx                # NEW
│   └── config/
│       └── fieldLabels.ts                     # NEW

docker-compose.yml                             # MODIFIED — add ocr-service
docker-compose.prod.yml                        # NEW — production override
.env                                           # MODIFIED — OCR settings
```
