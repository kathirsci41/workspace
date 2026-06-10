from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReferenceIndexRecord(Base):
    __tablename__ = "reference_index"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("bundle_documents.id"), index=True)
    order_bundle_id: Mapped[str | None] = mapped_column(ForeignKey("order_bundles.id"), nullable=True, index=True)
    reference_type: Mapped[str] = mapped_column(String(80), index=True)
    reference_value: Mapped[str] = mapped_column(String(255), index=True)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    field_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
