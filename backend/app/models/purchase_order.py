import uuid
import enum
from datetime import date
from sqlalchemy import String, Text, Numeric, Float, Enum, ForeignKey, Index, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from typing import List, TYPE_CHECKING

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.document import Document


class POStatus(str, enum.Enum):
    INITIATED = "INITIATED"
    IN_PROGRESS = "IN_PROGRESS"
    NEAR_COMPLETE = "NEAR_COMPLETE"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"


class PurchaseOrder(TimestampMixin, Base):
    __tablename__ = "purchase_orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )
    po_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    po_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_amount: Mapped[float | None] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    status: Mapped[POStatus] = mapped_column(
        Enum(POStatus), default=POStatus.INITIATED
    )
    chain_completeness: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    customer: Mapped["Customer"] = relationship(
        "Customer", back_populates="purchase_orders", lazy="selectin"
    )
    documents: Mapped[List["Document"]] = relationship(
        "Document", back_populates="purchase_order", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_po_number", "po_number", unique=True),
        Index("ix_po_customer_id", "customer_id"),
        Index("ix_po_status", "status"),
        Index("ix_po_date", "po_date"),
    )
