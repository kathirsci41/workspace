from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.audit_event import AuditEventRecord
from app.logging_config import log_event
from app.repositories.audit import AuditRepository
from app.schemas.audit import AuditEventCreate


class AuditService:
    """Persist Build 1 manual-correction audit events."""

    def __init__(self, db: Session | None = None) -> None:
        self.db = db
        self.events: list[AuditEventRecord] = []

    def record_event(self, event: AuditEventCreate) -> AuditEventRecord:
        if self.db is not None:
            record = AuditRepository(self.db).create(event)
            log_event(
                "audit_event_created",
                bundle_id=record.order_bundle_id,
                document_id=record.document_id,
                audit_event_id=record.id,
                audit_event_type=record.event_type,
                actor=record.actor,
            )
            return record
        record = AuditEventRecord(**event.model_dump())
        self.events.append(record)
        log_event(
            "audit_event_created",
            bundle_id=record.order_bundle_id,
            document_id=record.document_id,
            audit_event_id=record.id,
            audit_event_type=record.event_type,
            actor=record.actor,
        )
        return record
