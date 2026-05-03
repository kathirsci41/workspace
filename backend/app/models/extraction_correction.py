"""
ExtractionCorrection Model - Phase 8

Records every human correction made during document review.
Captures original vs corrected values for LayoutLMv3 fine-tuning.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Boolean, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from typing import TYPE_CHECKING

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.document import Document


class ExtractionCorrection(TimestampMixin, Base):
    """Records every human correction made during document review.

    When a human verifies and corrects extraction results, we capture:
    - The field name being corrected
    - The original (model-extracted) value
    - The corrected (human-entered) value
    - Who made the correction and when
    - Which extraction version this was for

    This data is used for:
    1. Audit trail of all corrections
    2. Incremental LayoutLMv3 fine-tuning (active learning)
    """
    __tablename__ = "extraction_corrections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    original_value: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # what the model extracted
    corrected_value: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # what the human entered
    operator_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # user who made the correction
    corrected_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    extraction_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )
    used_for_training: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # flagged after LayoutLMv3 fine-tune

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document", back_populates="corrections"
    )
