import uuid
import enum
from datetime import date, datetime
from sqlalchemy import String, Text, Numeric, Float, Enum, ForeignKey, Index, Date, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
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


class FulfillmentType(str, enum.Enum):
    PROCUREMENT = "procurement"
    STOCK = "stock"


class OrderScenario(str, enum.Enum):
    UNKNOWN = "unknown"
    PROCUREMENT = "procurement"
    STOCK = "stock"
    DROP_SHIP = "drop_ship"
    SERVICE_AMC = "service_amc"


class GstType(str, enum.Enum):
    UNKNOWN = "unknown"
    IGST = "igst"
    CGST_SGST = "cgst_sgst"


class BillingType(str, enum.Enum):
    FULL = "full"
    STAGED = "staged"
    RECURRING = "recurring"


class ChainStatus(str, enum.Enum):
    INCOMPLETE = "incomplete"
    COMPLETE = "complete"
    VERIFIED = "verified"
    MISMATCH = "mismatch"


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
    so_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fulfillment_type: Mapped[FulfillmentType] = mapped_column(
        Enum(FulfillmentType, name="fulfillmenttype",
             values_callable=lambda obj: [e.value for e in obj]),
        default=FulfillmentType.PROCUREMENT,
        nullable=False,
        server_default="procurement",
    )
    items_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    order_scenario: Mapped[OrderScenario] = mapped_column(
        Enum(OrderScenario, name="orderscenario",
             values_callable=lambda obj: [e.value for e in obj]),
        default=OrderScenario.UNKNOWN,
        nullable=False,
        server_default="unknown",
    )
    gst_type: Mapped[GstType] = mapped_column(
        Enum(GstType, name="gsttype",
             values_callable=lambda obj: [e.value for e in obj]),
        default=GstType.UNKNOWN,
        nullable=False,
        server_default="unknown",
    )
    invoice_split: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    manually_completed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completion_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    billing_type: Mapped[BillingType] = mapped_column(
        Enum(BillingType, name="billingtype",
             values_callable=lambda obj: [e.value for e in obj]),
        default=BillingType.FULL,
        nullable=False,
        server_default="full",
    )
    billing_milestones: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    requires_install_report: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    chain_status: Mapped[ChainStatus] = mapped_column(
        Enum(ChainStatus, name="chainstatus",
             values_callable=lambda obj: [e.value for e in obj]),
        default=ChainStatus.INCOMPLETE,
        nullable=False,
        server_default="incomplete",
    )

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
        Index("ix_po_so_number", "so_number"),
    )
