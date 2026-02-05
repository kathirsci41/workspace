from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional
from enum import Enum


class DocumentType(str, Enum):
    CUSTOMER_PO = "CUSTOMER_PO"
    VENDOR_INVOICE = "VENDOR_INVOICE"
    VENDOR_DC = "VENDOR_DC"
    COMPANY_INVOICE = "COMPANY_INVOICE"
    COMPANY_DC = "COMPANY_DC"
    POD = "POD"


class DocumentCreate(BaseModel):
    """Schema for document upload metadata."""
    document_type: DocumentType
    sales_order_id: Optional[int] = None
    reference_number: Optional[str] = Field(None, max_length=100)
    
    @field_validator('sales_order_id')
    @classmethod
    def validate_so_requirement(cls, v, info):
        """Validate SO requirement based on document type."""
        doc_type = info.data.get('document_type')
        if doc_type == DocumentType.CUSTOMER_PO:
            if v is not None:
                raise ValueError("Customer PO cannot be linked to a Sales Order")
        else:
            if v is None:
                raise ValueError(f"{doc_type} requires a Sales Order")
        return v


class DocumentResponse(BaseModel):
    """Schema for document response."""
    id: int
    case_id: int
    sales_order_id: Optional[int]
    document_type: str
    filename: str
    original_filename: str
    reference_number: Optional[str]
    storage_path: str
    file_size: int
    rotation: int
    uploaded_at: datetime
    uploaded_by: str

    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    """Response after successful document upload."""
    id: int
    message: str
    filename: str
    storage_path: str
    checksum: str


class RotateRequest(BaseModel):
    """Request to rotate a document."""
    degrees: int = Field(..., description="Rotation degrees: 90, 180, or 270")
    
    @field_validator('degrees')
    @classmethod
    def validate_rotation(cls, v: int) -> int:
        if v not in [0, 90, 180, 270]:
            raise ValueError("Rotation must be 0, 90, 180, or 270 degrees")
        return v
