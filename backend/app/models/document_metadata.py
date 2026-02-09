import enum
from datetime import date, datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    Column, Integer, String, Float, Text, Date, DateTime, Enum, ForeignKey,
    Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class ExtractionStatus(str, enum.Enum):
    PENDING = "PENDING"
    EXTRACTED = "EXTRACTED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


class DocumentType(str, enum.Enum):
    CUSTOMER_PO = "CUSTOMER_PO"
    VENDOR_INVOICE = "VENDOR_INVOICE"
    VENDOR_DC = "VENDOR_DC"
    COMPANY_INVOICE = "COMPANY_INVOICE"
    COMPANY_DC = "COMPANY_DC"
    POD = "POD"
    PURCHASE_BILL = "PURCHASE_BILL"


class DocumentMetadata(Base):
    __tablename__ = "document_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True
    )
    document_path: Mapped[str] = mapped_column(String(1024))

    # Document classification
    doc_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="metadata_doc_type", native_enum=True)
    )

    # Promoted indexed fields (for fast queries)
    primary_ref_no: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    doc_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Full extraction result
    extracted_data: Mapped[Dict[str, Any]] = mapped_column(JSONB, server_default='{}')

    # Extraction metadata
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(ExtractionStatus, name="extraction_status", native_enum=True),
        server_default="PENDING"
    )
    raw_ocr_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit fields
    extracted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    document = relationship("Document", back_populates="extraction_metadata")

    __table_args__ = (
        Index("idx_metadata_doc_type", "doc_type"),
        Index("idx_metadata_status", "status"),
        Index("idx_metadata_primary_ref", "primary_ref_no"),
        Index("idx_metadata_doc_date", "doc_date"),
        Index("idx_metadata_extracted_data", "extracted_data", postgresql_using="gin"),
    )

    def __repr__(self):
        return f"<DocumentMetadata doc_type={self.doc_type} status={self.status}>"
