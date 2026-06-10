from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TextSourceRecord(Base):
    __tablename__ = "text_sources"

    __table_args__ = (
        UniqueConstraint(
            "document_id", "page_number", "provider", "settings_hash", "image_hash",
            name="uq_text_sources_cache_key",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    provider_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # NOT NULL: cache identity must be deterministic (use synthetic hash for digital text)
    settings_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    settings_json: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(String, nullable=True)
    normalized_text: Mapped[str | None] = mapped_column(String, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # NOT NULL: hash of page image, or synthetic hash for digital-text pages
    image_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
