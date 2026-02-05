from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    so_number = Column(String(50), unique=True, nullable=False, index=True)
    so_month = Column(String(7), nullable=False, index=True)  # Format: "2026-01"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    case = relationship("Case", back_populates="sales_orders")
    documents = relationship("Document", back_populates="sales_order", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="sales_order")

    def __repr__(self):
        return f"<SalesOrder {self.so_number} ({self.so_month})>"
