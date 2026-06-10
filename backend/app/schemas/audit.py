from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditEventCreate(BaseModel):
    event_type: str
    actor: str
    document_id: str | None = None
    order_bundle_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    actor: str
    created_at: datetime
    document_id: str | None = None
    order_bundle_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
