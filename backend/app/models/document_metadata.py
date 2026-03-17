import uuid
import enum
from datetime import date, datetime
from sqlalchemy import (
    String, Text, Integer, Float, Numeric, Date, DateTime,
    Enum, ForeignKey, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from typing import TYPE_CHECKING

from app.models.base import Base, TimestampMixin
from app.models.document import DocumentType

if TYPE_CHECKING:
    from app.models.document import Document


class MetadataStatus(str, enum.Enum):
    PENDING = "PENDING"
    EXTRACTED = "EXTRACTED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


class DocumentMetadata(TimestampMixin, Base):
    __tablename__ = "document_metadata"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), unique=True, nullable=False
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType), nullable=False
    )
    extracted_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_ref_no: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    po_ref_no: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    doc_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_amount: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[MetadataStatus] = mapped_column(
        Enum(MetadataStatus), default=MetadataStatus.PENDING
    )
    extraction_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Version-safe persistence
    extraction_version: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    field_confidences: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    extraction_route: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document", back_populates="doc_metadata", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_meta_document_id", "document_id", unique=True),
        Index("ix_meta_primary_ref", "primary_ref_no"),
        Index("ix_meta_po_ref", "po_ref_no"),
        Index("ix_meta_doc_date", "doc_date"),
        Index("ix_meta_status", "status"),
        Index("ix_meta_extracted_data", "extracted_data", postgresql_using="gin"),
    )
