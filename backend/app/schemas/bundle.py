from __future__ import annotations

import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class BundleCreate(BaseModel):
    bundle_number: str
    customer_name: str | None = None
    customer_po_no: str | None = None
    so_no: str | None = None


class BundleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    bundle_number: str
    customer_name: str | None
    customer_po_no: str | None
    so_no: str | None
    # Persisted snapshot - updated after mutations only.
    status: str
    customer_delivery_status: str
    vendor_procurement_status: str
    # Computed live status - authoritative and populated for list responses.
    computed_status: str | None = None
    computed_customer_status: str | None = None
    computed_vendor_status: str | None = None
    status_computed_at: datetime | None = None
    dismissed_check_ids: list[str] = []
    created_at: datetime
    updated_at: datetime

    @field_validator("dismissed_check_ids", mode="before")
    @classmethod
    def parse_dismissed_check_ids(cls, v: object) -> list[str]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        if isinstance(v, list):
            return v
        return []
