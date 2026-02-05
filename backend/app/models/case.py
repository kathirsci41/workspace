from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class CaseType(str, enum.Enum):
    HARDWARE = "HARDWARE"
    SERVICES = "SERVICES"


class CaseStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    CLOSED = "CLOSED"


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String(20), unique=True, nullable=False, index=True)
    opportunity_id = Column(String(20), unique=True, nullable=False, index=True)
    customer_name = Column(String(255), nullable=False)
    case_type = Column(String(20), nullable=False)
    status = Column(String(20), default="OPEN")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    sales_orders = relationship("SalesOrder", back_populates="case", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="case", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="case")

    def __repr__(self):
        return f"<Case {self.case_id} - {self.opportunity_id}>"
