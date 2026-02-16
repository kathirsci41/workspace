from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import date, datetime
from typing import Optional


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


class POResponse(BaseModel):
    id: UUID
    customer_id: UUID
    po_number: str
    po_date: Optional[date] = None
    total_amount: Optional[float] = None
    status: str
    chain_completeness: float
    notes: Optional[str] = None
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


class ChainStatusResponse(BaseModel):
    po_id: UUID
    po_number: str
    completeness_pct: float
    chain: dict[str, list[ChainSlot]]
