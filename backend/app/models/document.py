from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base

# Single source of truth for DocumentType enum
from app.models.document_metadata import DocumentType  # noqa: F401


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=True, index=True)
    document_type = Column(String(30), nullable=False, index=True)
    filename = Column(String(255), nullable=False)  # UUID-based unique filename
    original_filename = Column(String(255), nullable=False)
    reference_number = Column(String(100), nullable=True)
    storage_path = Column(Text, nullable=False)
    checksum = Column(String(64), nullable=False)  # SHA256
    file_size = Column(Integer, nullable=False)
    rotation = Column(Integer, default=0)  # 0, 90, 180, 270
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    uploaded_by = Column(String(100), default="Anonymous")

    # Relationships
    case = relationship("Case", back_populates="documents")
    sales_order = relationship("SalesOrder", back_populates="documents")
    audit_logs = relationship("AuditLog", back_populates="document")
    extraction_metadata = relationship(
        "DocumentMetadata",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Document {self.original_filename} ({self.document_type})>"
