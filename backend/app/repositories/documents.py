from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models.document import DocumentRecord
from app.models.document_metadata import DocumentMetadataRecord
from app.models.reference_index import ReferenceIndexRecord


class DocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        bundle_id: str,
        document_type: str,
        filename: str,
        content_type: str | None,
        storage_path: str | None,
    ) -> DocumentRecord:
        document = DocumentRecord(
            order_bundle_id=bundle_id,
            document_type=document_type,
            filename=filename,
            content_type=content_type,
            storage_path=storage_path,
            status="UPLOADED",
        )
        self.db.add(document)
        self.db.flush()
        metadata = DocumentMetadataRecord(document_id=document.id, status="PENDING", extracted_data={}, diagnostics={})
        self.db.add(metadata)
        self.db.flush()
        self.db.refresh(document)
        return document

    def list_for_bundle(self, bundle_id: str) -> list[DocumentRecord]:
        stmt = (
            select(DocumentRecord)
            .where(DocumentRecord.order_bundle_id == bundle_id)
            .options(selectinload(DocumentRecord.metadata_record))
            .order_by(DocumentRecord.created_at.asc())
        )
        return list(self.db.scalars(stmt))

    def get(self, document_id: str) -> DocumentRecord | None:
        stmt = select(DocumentRecord).where(DocumentRecord.id == document_id).options(selectinload(DocumentRecord.metadata_record))
        return self.db.scalars(stmt).first()

    def delete(self, document: DocumentRecord) -> None:
        self.db.execute(delete(ReferenceIndexRecord).where(ReferenceIndexRecord.document_id == document.id))
        self.db.delete(document)
