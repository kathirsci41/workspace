from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class OrderBundle:
    """Core aggregate for a set of documents belonging to one order context."""

    id: str
    customer_name: str | None = None
    order_reference: str | None = None
    documents: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
