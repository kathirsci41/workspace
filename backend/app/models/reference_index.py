import uuid
from sqlalchemy import String, Enum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TimestampMixin
from app.models.document import DocumentType


class ReferenceIndex(TimestampMixin, Base):
    __tablename__ = "reference_index"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    po_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False,
        comment="Denormalized for speed"
    )
    ref_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="e.g. invoice_number, dc_number, po_number"
    )
    ref_value: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
        comment="The actual reference value"
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType), nullable=False
    )

    __table_args__ = (
        Index("ix_ref_value", "ref_value"),
        Index("ix_ref_type_value", "ref_type", "ref_value"),
        Index("ix_ref_document_id", "document_id"),
        Index("ix_ref_po_id", "po_id"),
    )
