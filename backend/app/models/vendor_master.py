from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VendorMasterRecord(Base):
    __tablename__ = "vendor_master"

    gstin: Mapped[str] = mapped_column(String(15), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default", index=True)
    vendor_name: Mapped[str] = mapped_column(String(256), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
