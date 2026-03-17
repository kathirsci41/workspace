from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import date, datetime
from typing import Optional


class ExtractionResponse(BaseModel):
    id: UUID
    document_id: UUID
    document_type: str
    extracted_data: Optional[dict] = None
    primary_ref_no: Optional[str] = None
    po_ref_no: Optional[str] = None
    doc_date: Optional[date] = None
    total_amount: Optional[float] = None
    confidence_score: Optional[float] = None
    status: str
    extraction_attempts: int = 0
    last_error: Optional[str] = None
    extracted_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    model_version: Optional[str] = None
    processing_time_ms: Optional[int] = None
    extraction_version: Optional[int] = None       # Phase 7
    field_confidences: Optional[dict] = None       # Phase 7
    extraction_route: Optional[str] = None         # Phase 1
    requires_so_entry: bool = False                 # True if PO has no SO number set yet
    verification_pending: bool = False              # True if verify was blocked (awaiting SO)
    so_mismatch_message: Optional[str] = None       # Set when SO in doc doesn't match PO SO
    po_id: Optional[UUID] = None                    # PO id for SO number PATCH call
    po_so_number: Optional[str] = None             # PO's stored SO number (context)

    model_config = ConfigDict(from_attributes=True)


class VerifyRequest(BaseModel):
    extracted_data: dict


class SearchResult(BaseModel):
    result_type: str  # "customer" | "purchase_order" | "document"
    id: UUID
    ref_number: str
    display_name: str
    document_type: Optional[str] = None
    po_number: Optional[str] = None
    po_id: Optional[str] = None
    customer_name: Optional[str] = None
    confidence: Optional[float] = None


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    query: str
