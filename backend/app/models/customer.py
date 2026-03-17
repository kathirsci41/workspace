import uuid
from sqlalchemy import String, Text, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from typing import List, TYPE_CHECKING

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.purchase_order import PurchaseOrder


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False,
        comment="Business ID like SKY-AB1234, used as NAS folder name"
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Display name like Acme Corp"
    )
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    gst_number: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    purchase_orders: Mapped[List["PurchaseOrder"]] = relationship(
        "PurchaseOrder", back_populates="customer", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_customers_customer_id", "customer_id", unique=True),
        Index("ix_customers_name", "name"),
        Index("ix_customers_gst", "gst_number"),
    )
