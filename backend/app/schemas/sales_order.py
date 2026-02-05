from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, List, Any
import re


class SalesOrderBase(BaseModel):
    """Base sales order schema."""
    so_number: str = Field(..., min_length=1, max_length=50)
    so_month: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    
    @field_validator('so_month')
    @classmethod
    def validate_month_format(cls, v: str) -> str:
        """Validate YYYY-MM format."""
        if not re.match(r'^\d{4}-\d{2}$', v):
            raise ValueError("Invalid month format. Use YYYY-MM")
        year, month = map(int, v.split('-'))
        if month < 1 or month > 12:
            raise ValueError("Invalid month value")
        return v


class SalesOrderCreate(SalesOrderBase):
    """Schema for creating a new sales order."""
    pass


class SalesOrderResponse(BaseModel):
    """Schema for sales order response."""
    id: int
    case_id: int
    so_number: str
    so_month: str
    created_at: datetime
    updated_at: datetime
    document_count: int = 0
    checklist: dict = {
        "VENDOR_INVOICE": False,
        "VENDOR_DC": False,
        "COMPANY_INVOICE": False,
        "COMPANY_DC": False,
        "POD": False
    }

    class Config:
        from_attributes = True


class SalesOrderWithDocuments(SalesOrderResponse):
    """Sales order with full document list."""
    documents: List[Any] = []

    class Config:
        from_attributes = True


class SOSearchResult(BaseModel):
    """Schema for SO search result with case info."""
    so_number: str
    so_month: str
    case_id: str
    opportunity_id: str
    customer_name: str
    document_count: int
    checklist: dict
    folder_path: str
    documents: List[Any] = []

    class Config:
        from_attributes = True
