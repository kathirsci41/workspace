from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OrderBundleRecord(Base):
    __tablename__ = "order_bundles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    bundle_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_po_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    so_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="REVIEW_REQUIRED")
    customer_delivery_status: Mapped[str] = mapped_column(String(50), default="REVIEW_REQUIRED")
    vendor_procurement_status: Mapped[str] = mapped_column(String(50), default="REVIEW_REQUIRED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    documents = relationship("DocumentRecord", back_populates="bundle", cascade="all, delete-orphan")
