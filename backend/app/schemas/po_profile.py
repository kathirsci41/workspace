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
    `required` = counts toward chain completeness.
    `optional`  = can be uploaded but doesn't affect completeness.
    `status` = "not_applicable" when slot is irrelevant for this scenario.
    """
    model_config = ConfigDict(from_attributes=True)

    document_type: str
    status: str  # "empty" | "not_applicable" | DocumentStatus value
    documents: list[POProfileDocument] = []
    required: bool = True
    optional: bool = False


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


class FieldComparison(BaseModel):
    """One cross-document field comparison result."""
    field_label: str             # Human-readable: "Delivery Address", "Grand Total", etc.
    source_doc: str              # Document type that holds the canonical value
    source_value: str | None     # Value from source_doc
    compared_doc: str            # Document type being compared against
    compared_value: str | None   # Value from compared_doc
    match: bool | None           # None = cannot compare (one side missing)
    note: str | None = None      # Extra context, e.g. "tolerance ±1%"


class VendorGroup(BaseModel):
    """Completeness view for one vendor within a procurement PO."""
    vendor_po_ref: str                   # primary_ref_no of the COMPANY_PO doc
    vendor_name: str | None = None       # extracted_data['vendor_name'] from COMPANY_PO
    completeness_pct: float              # filled vendor slots / 3 × 100
    slots: list[POProfileDocumentSlot]   # COMPANY_PO, VENDOR_DC, VENDOR_INVOICE


class ItemComparison(BaseModel):
    """One row-level comparison between order_items across two documents."""
    sr_no: str | None = None
    description: str | None = None
    part_no: str | None = None
    source_doc: str
    source_qty: float | None = None
    compared_doc: str
    compared_qty: float | None = None
    qty_match: bool | None = None
    source_price: float | None = None
    compared_price: float | None = None
    price_match: bool | None = None


class ItemMatch(BaseModel):
    """AI-assisted description → part_no link result."""
    sr_no: str | None = None
    description: str | None = None
    matched_part_no: str | None = None
    confidence: float
    match_type: str   # 'exact' | 'ai' | 'unmatched'


class ParsedAddress(BaseModel):
    pin_code: str | None
    city: str | None
    state: str | None
    full_address: str | None


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
    order_scenario: str = "unknown"
    gst_type: str = "unknown"
    invoice_split: bool = False
    manually_completed: bool = False
    completed_at: datetime | None = None
    completion_note: str | None = None
    chain_completeness_display: str | None = None  # "72.5%" | "—" when unknown
    created_at: datetime
    slots: list[POProfileDocumentSlot]
    timeline: list[POProfileTimelineEvent]
    discrepancies: list[POProfileDiscrepancy]
    cross_references: dict[str, list[str]]
    vendor_groups: list[VendorGroup] = []
    field_comparisons: list[FieldComparison] = []
    items_verified: bool = False
    item_comparisons: list[ItemComparison] = []
    item_matches: list[ItemMatch] = []
    delivery_address_parsed: ParsedAddress | None = None
