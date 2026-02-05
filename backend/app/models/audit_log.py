from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(50), nullable=False)
    actor = Column(String(100), nullable=False)
    details = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    case = relationship("Case", back_populates="audit_logs")
    document = relationship("Document", back_populates="audit_logs")
    sales_order = relationship("SalesOrder", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog {self.action} by {self.actor}>"
