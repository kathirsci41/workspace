from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ManualExtractedDataPatch(BaseModel):
    fields: dict[str, Any]
    actor: str = "system"
    reason: str | None = None


class ExtractionRequest(BaseModel):
    ocr_rotation_degrees: int | str | None = None


class MetadataRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    status: str
    extracted_data: dict[str, Any]
    diagnostics: dict[str, Any]
    field_confidences: dict[str, float | None] = Field(default_factory=dict)
    field_evidence: dict[str, str | None] = Field(default_factory=dict)
    field_locations: dict[str, dict[str, Any]] = Field(default_factory=dict)
    primary_ref_no: str | None
    po_ref_no: str | None
    last_error: str | None


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_bundle_id: str
    document_type: str
    filename: str
    content_type: str | None
    status: str
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    metadata: MetadataRead | None = None
