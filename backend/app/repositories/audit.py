from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.audit_event import AuditEventRecord
from app.schemas.audit import AuditEventCreate


class AuditRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: AuditEventCreate) -> AuditEventRecord:
        record = AuditEventRecord(**payload.model_dump())
        self.db.add(record)
        self.db.flush()
        return record

    def list_for_bundle(self, bundle_id: str) -> list[AuditEventRecord]:
        return list(
            self.db.scalars(
                select(AuditEventRecord)
                .where(AuditEventRecord.order_bundle_id == bundle_id)
                .order_by(AuditEventRecord.created_at.desc())
            )
        )
