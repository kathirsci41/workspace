from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional

from app.schemas.extraction import ExtractionResponse


class DocumentUploadResponse(BaseModel):
    id: UUID
    po_id: UUID
    document_type: str
    filename: str
    original_filename: str
    file_size: int
    page_count: Optional[int] = None
    checksum: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    id: UUID
    po_id: UUID
    document_type: str
    filename: str
    original_filename: str
    file_path: str
    file_size: int
    mime_type: str
    page_count: Optional[int] = None
    checksum: str
    status: str
    rotation: int = 0
    created_at: datetime
    updated_at: datetime
    po_number: str = ""
    customer_name: str = ""
    po_so_number: Optional[str] = None
    metadata: Optional[ExtractionResponse] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
