from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, List, Any
import re


class CaseBase(BaseModel):
    """Base case schema with common fields."""
    customer_name: str = Field(..., min_length=1, max_length=255)
    case_type: str = Field(..., pattern="^(HARDWARE|SERVICES)$")
    notes: Optional[str] = None


class CaseCreate(CaseBase):
    """Schema for creating a new case."""
    opportunity_id: str = Field(..., min_length=1, max_length=20)
    
    @field_validator('opportunity_id')
    @classmethod
    def normalize_opportunity_id(cls, v: str) -> str:
        """Normalize opportunity ID format."""
        v = v.strip().upper()
        # If it's just a number, prefix with SKY-
        if v.isdigit():
            return f"SKY-{v}"
        # If it doesn't have SKY- prefix, add it
        if not v.startswith("SKY-"):
            # Check if it matches SKY123 format (no dash)
            match = re.match(r'^SKY(\d+)$', v)
            if match:
                return f"SKY-{match.group(1)}"
        return v


class CaseUpdate(BaseModel):
    """Schema for updating a case."""
    customer_name: Optional[str] = Field(None, min_length=1, max_length=255)
    case_type: Optional[str] = Field(None, pattern="^(HARDWARE|SERVICES)$")
    status: Optional[str] = Field(None, pattern="^(OPEN|IN_PROGRESS|CLOSED)$")
    notes: Optional[str] = None


class CaseResponse(BaseModel):
    """Schema for case response."""
    id: int
    case_id: str
    opportunity_id: str
    customer_name: str
    case_type: str
    status: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SalesOrderSummary(BaseModel):
    """Summary of sales order for case details."""
    id: int
    so_number: str
    so_month: str
    document_count: int = 0
    checklist: dict = {}

    class Config:
        from_attributes = True


class DocumentSummary(BaseModel):
    """Summary of document for case details."""
    id: int
    document_type: str
    original_filename: str
    reference_number: Optional[str]
    uploaded_at: datetime

    class Config:
        from_attributes = True


class CaseWithDetails(CaseResponse):
    """Case response with sales orders and documents."""
    customer_po: Optional[Any] = None
    sales_orders: List[Any] = []

    class Config:
        from_attributes = True
