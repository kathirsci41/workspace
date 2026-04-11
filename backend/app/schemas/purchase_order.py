from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import date, datetime
from typing import Literal, Optional


class POCreate(BaseModel):
    customer_id: UUID
    po_number: str = Field(..., min_length=1, max_length=100)
    po_date: Optional[date] = None
    total_amount: Optional[float] = None
    notes: Optional[str] = None


class POUpdate(BaseModel):
    po_number: Optional[str] = None
    po_date: Optional[date] = None
    total_amount: Optional[float] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    so_number: Optional[str] = None
    fulfillment_type: Optional[Literal['procurement', 'stock']] = None
    items_verified: Optional[bool] = None
    order_scenario: Optional[Literal['unknown', 'procurement', 'stock', 'drop_ship', 'service_amc']] = None
    gst_type: Optional[Literal['unknown', 'igst', 'cgst_sgst']] = None
    invoice_split: Optional[bool] = None
    completion_note: Optional[str] = None
    billing_type: Optional[Literal['full', 'staged', 'recurring']] = None
    billing_milestones: Optional[list[dict]] = None
    requires_install_report: Optional[bool] = None
    chain_status: Optional[Literal['incomplete', 'complete', 'verified', 'mismatch']] = None


class POResponse(BaseModel):
    id: UUID
    customer_id: UUID
    po_number: str
    po_date: Optional[date] = None
    total_amount: Optional[float] = None
    currency: str = "INR"
    status: str
    chain_completeness: float
    notes: Optional[str] = None
    so_number: Optional[str] = None
    fulfillment_type: Optional[str] = "procurement"
    items_verified: bool = False
    order_scenario: str = "unknown"
    gst_type: str = "unknown"
    invoice_split: bool = False
    manually_completed: bool = False
    completed_at: Optional[datetime] = None
    completion_note: Optional[str] = None
    billing_type: str = "full"
    billing_milestones: Optional[list[dict]] = None
    requires_install_report: bool = False
    chain_status: str = "incomplete"
    created_at: datetime
    updated_at: datetime
    customer_name: str = ""
    customer_sky_id: str = ""

    model_config = ConfigDict(from_attributes=True)


class POListResponse(BaseModel):
    items: list[POResponse]
    total: int
    page: int
    per_page: int


class ChainSlot(BaseModel):
    status: str
    document_id: Optional[UUID] = None
    ref_no: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    confidence: Optional[float] = None
    extraction_route: Optional[str] = None         # Phase 1
    has_validation_errors: Optional[bool] = None   # Phase 6
    slot_message: Optional[str] = None             # Why this slot is pending/failed


class ChainStatusResponse(BaseModel):
    po_id: UUID
    po_number: str
    completeness_pct: float
    chain: dict[str, list[ChainSlot]]


class SONumberUpdate(BaseModel):
    so_number: str = Field(..., max_length=100)  # empty string clears the SO number
