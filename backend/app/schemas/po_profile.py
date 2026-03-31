from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class POProfileDocument(BaseModel):
    """Per-document data within a slot. A slot may contain multiple documents."""
    model_config = ConfigDict(from_attributes=True)

    document_id: uuid.UUID
    status: str
    filename: str | None = None
    original_filename: str | None = None
    primary_ref_no: str | None = None
    po_ref_no: str | None = None
    doc_date: date | None = None
    total_amount: float | None = None
    confidence_score: float | None = None
    field_confidences: dict[str, Any] | None = None
    extraction_route: str | None = None
    extracted_data: dict[str, Any] | None = None
    verified_at: datetime | None = None
    uploaded_at: datetime | None = None


class POProfileDocumentSlot(BaseModel):
    """One slot per document type in the 6-step chain.

    `documents` holds all non-rejected uploads for this type, sorted most-recent
    first. The slot `status` reflects the most-advanced status across all documents.
    """
    model_config = ConfigDict(from_attributes=True)

    document_type: str
    status: str  # "empty" | most-advanced DocumentStatus value across all docs
    documents: list[POProfileDocument] = []


class POProfileDiscrepancy(BaseModel):
    type: str        # "SO_MISMATCH" | "MISSING_PO_REF" | "PO_REF_MISMATCH"
    doc_type: str
    message: str
    severity: str    # "error" | "warning"


class POProfileTimelineEvent(BaseModel):
    event_type: str  # "uploaded" | "extracted" | "verified" | "rejected"
    doc_type: str
    timestamp: datetime
    detail: str | None = None


class POProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    po_id: uuid.UUID
    po_number: str
    customer_name: str
    customer_sky_id: str
    so_number: str | None
    po_date: date | None
    total_amount: float | None
    status: str
    chain_completeness: float
    fulfillment_type: str = "procurement"
    created_at: datetime
    slots: list[POProfileDocumentSlot]
    timeline: list[POProfileTimelineEvent]
    discrepancies: list[POProfileDiscrepancy]
    cross_references: dict[str, list[str]]
