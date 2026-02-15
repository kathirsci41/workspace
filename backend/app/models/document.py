import uuid
import enum
from sqlalchemy import String, Integer, Enum, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from typing import TYPE_CHECKING

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.purchase_order import PurchaseOrder
    from app.models.document_metadata import DocumentMetadata


class DocumentType(str, enum.Enum):
    CUSTOMER_PO = "CUSTOMER_PO"
    VENDOR_DC = "VENDOR_DC"
    VENDOR_INVOICE = "VENDOR_INVOICE"
    COMPANY_DC = "COMPANY_DC"
    COMPANY_INVOICE = "COMPANY_INVOICE"
    POD = "POD"


class DocumentStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    PENDING_REVIEW = "PENDING_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    po_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType), nullable=False
    )
    filename: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="UUID-prefixed stored name"
    )
    original_filename: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="User's original filename"
    )
    file_path: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Relative NAS path"
    )
    file_size: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="File size in bytes"
    )
    mime_type: Mapped[str] = mapped_column(
        String(100), default="application/pdf"
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="SHA-256 hex"
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.UPLOADED
    )
    rotation: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    purchase_order: Mapped["PurchaseOrder"] = relationship(
        "PurchaseOrder", back_populates="documents", lazy="selectin"
    )
    doc_metadata: Mapped["DocumentMetadata | None"] = relationship(
        "DocumentMetadata", back_populates="document", uselist=False, lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("po_id", "document_type", "checksum", name="uq_doc_per_po_type"),
        Index("ix_doc_po_id", "po_id"),
        Index("ix_doc_type", "document_type"),
        Index("ix_doc_checksum", "checksum"),
        Index("ix_doc_status", "status"),
    )
