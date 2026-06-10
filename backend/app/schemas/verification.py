from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class VerificationSummary:
    bundle_status: str
    customer_delivery_status: str
    vendor_procurement_status: str
    extracted_summary: dict[str, Any] = field(default_factory=dict)
    connections: list[dict[str, Any]] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)
    recommendation: str = ""
