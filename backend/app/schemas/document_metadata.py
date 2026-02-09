from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import date, datetime

from app.models.document_metadata import ExtractionStatus, DocumentType


# --- Response Schemas ---

class MetadataResponse(BaseModel):
    id: int
    document_id: int
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
    metadata_id: int
    status: str
    extracted_data: Dict[str, Any]
    confidence_score: Optional[float] = None
    primary_ref_no: Optional[str] = None
    doc_date: Optional[str] = None
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
    doc_date: Optional[str] = Field(
        None, description="Corrected document date (ISO-8601 or common formats)"
    )
    verified_by: str = Field(
        ..., description="Name/ID of the person verifying"
    )


class MetadataListResponse(BaseModel):
    items: list[MetadataResponse]
    total: int
