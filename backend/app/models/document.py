from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DocumentRecord(Base):
    __tablename__ = "bundle_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    order_bundle_id: Mapped[str] = mapped_column(ForeignKey("order_bundles.id"), index=True)
    document_type: Mapped[str] = mapped_column(String(50), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="UPLOADED")
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default", index=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    bundle = relationship("OrderBundleRecord", back_populates="documents")
    metadata_record = relationship("DocumentMetadataRecord", back_populates="document", cascade="all, delete-orphan", uselist=False)
