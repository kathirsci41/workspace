from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.reference_index import ReferenceIndexRecord
from app.services.reference_index_service import build_reference_index


class ReferenceIndexRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def replace_for_document(
        self,
        document_id: str,
        extracted_data: dict,
        order_bundle_id: str | None,
        *,
        document_type: str | None = None,
        diagnostics: dict | None = None,
    ) -> list[ReferenceIndexRecord]:
        self.db.execute(delete(ReferenceIndexRecord).where(ReferenceIndexRecord.document_id == document_id))
        records = build_reference_index(
            document_id,
            extracted_data,
            order_bundle_id,
            document_type=document_type,
            diagnostics=diagnostics,
        )
        for record in records:
            self.db.add(record)
        self.db.flush()
        return records

    def list_for_document(self, document_id: str) -> list[ReferenceIndexRecord]:
        return list(self.db.scalars(select(ReferenceIndexRecord).where(ReferenceIndexRecord.document_id == document_id)))

    def list_for_bundle(self, bundle_id: str) -> list[ReferenceIndexRecord]:
        return list(
            self.db.scalars(
                select(ReferenceIndexRecord)
                .where(ReferenceIndexRecord.order_bundle_id == bundle_id)
                .order_by(ReferenceIndexRecord.created_at.asc())
            )
        )
