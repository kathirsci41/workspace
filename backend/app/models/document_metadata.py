from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DocumentMetadataRecord(Base):
    __tablename__ = "document_metadata"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("bundle_documents.id"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    extracted_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    diagnostics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    primary_ref_no: Mapped[str | None] = mapped_column(String(150), nullable=True)
    po_ref_no: Mapped[str | None] = mapped_column(String(150), nullable=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default", index=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    document = relationship("DocumentRecord", back_populates="metadata_record")
