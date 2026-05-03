from pydantic import BaseModel, ConfigDict, field_validator
from uuid import UUID
from datetime import date, datetime
from typing import Optional
import ast
import re


_CONF_PATTERN = re.compile(r"'?\{'value'\s*:\s*([^,}]+?)\s*,\s*'confidence'\s*:[^}]*\}'?")


def _clean_ref_string(v: object) -> object:
    """Unwrap legacy confidence-wrapped values.

    Handles both dict form {"value": x, "confidence": y} and
    string-repr form "{'value': x, 'confidence': y}" produced by old
    extractions that stringified Python dicts instead of storing JSON.
    Also cleans embedded confidence patterns inside warning strings.
    """
    if isinstance(v, dict) and "value" in v and "confidence" in v:
        return v.get("value")
    if isinstance(v, str) and v.startswith("{") and "'value'" in v:
        try:
            parsed = ast.literal_eval(v)
            if isinstance(parsed, dict) and "value" in parsed and "confidence" in parsed:
                return parsed.get("value")
        except (ValueError, SyntaxError):
            pass
    if isinstance(v, str) and "'value'" in v:
        return _CONF_PATTERN.sub(lambda m: m.group(1).strip().strip("'\""), v)
    return v


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

    @field_validator("primary_ref_no", "po_ref_no", mode="before")
    @classmethod
    def unwrap_ref_fields(cls, v):
        return _clean_ref_string(v)

    @field_validator("extracted_data", mode="before")
    @classmethod
    def unwrap_extracted_data_fields(cls, v):
        if not isinstance(v, dict):
            return v
        result = {}
        for k, val in v.items():
            if isinstance(val, list):
                result[k] = [_clean_ref_string(item) if isinstance(item, str) else item for item in val]
            else:
                result[k] = _clean_ref_string(val)
        return result


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
