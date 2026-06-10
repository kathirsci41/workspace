"""Evidence repository: persistence layer for Phase 1b/1c evidence tables.

All functions are intentionally unused by the extraction runtime in Phase 1c.
They will be wired into the extraction pipeline in later phases.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.document_page import DocumentPageRecord
from app.models.field_candidate import FieldCandidateRecord
from app.models.text_source import TextSourceRecord


def _now() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # document_pages
    # ------------------------------------------------------------------

    def upsert_document_page(
        self,
        document_id: str,
        page_number: int,
        *,
        image_path: str | None = None,
        image_hash: str | None = None,
        has_digital_text: bool | None = None,
        rotation_detected: int | None = None,
        page_classification: str | None = None,
    ) -> DocumentPageRecord:
        existing = self.get_document_page(document_id, page_number)
        if existing is not None:
            existing.image_path = image_path
            existing.image_hash = image_hash
            existing.has_digital_text = has_digital_text
            existing.rotation_detected = rotation_detected
            existing.page_classification = page_classification
            self.db.flush()
            return existing

        record = DocumentPageRecord(
            id=str(uuid4()),
            document_id=document_id,
            page_number=page_number,
            image_path=image_path,
            image_hash=image_hash,
            has_digital_text=has_digital_text,
            rotation_detected=rotation_detected,
            page_classification=page_classification,
            created_at=_now(),
        )
        self.db.add(record)
        self.db.flush()
        return record

    def get_document_page(
        self, document_id: str, page_number: int
    ) -> DocumentPageRecord | None:
        stmt = select(DocumentPageRecord).where(
            DocumentPageRecord.document_id == document_id,
            DocumentPageRecord.page_number == page_number,
        )
        return self.db.scalars(stmt).first()

    # ------------------------------------------------------------------
    # text_sources
    # ------------------------------------------------------------------

    def insert_text_source(
        self,
        *,
        document_id: str,
        page_number: int,
        source_type: str,
        provider: str,
        settings_hash: str,
        image_hash: str,
        success: bool,
        provider_version: str | None = None,
        settings_json: str | None = None,
        raw_text: str | None = None,
        normalized_text: str | None = None,
        error: str | None = None,
        duration_ms: int | None = None,
    ) -> TextSourceRecord:
        record = TextSourceRecord(
            id=str(uuid4()),
            document_id=document_id,
            page_number=page_number,
            source_type=source_type,
            provider=provider,
            settings_hash=settings_hash,
            image_hash=image_hash,
            success=success,
            provider_version=provider_version,
            settings_json=settings_json,
            raw_text=raw_text,
            normalized_text=normalized_text,
            error=error,
            duration_ms=duration_ms,
            created_at=_now(),
        )
        self.db.add(record)
        self.db.flush()
        return record

    def get_text_source_by_cache_key(
        self,
        document_id: str,
        page_number: int,
        provider: str,
        settings_hash: str,
        image_hash: str,
    ) -> TextSourceRecord | None:
        stmt = select(TextSourceRecord).where(
            TextSourceRecord.document_id == document_id,
            TextSourceRecord.page_number == page_number,
            TextSourceRecord.provider == provider,
            TextSourceRecord.settings_hash == settings_hash,
            TextSourceRecord.image_hash == image_hash,
        )
        return self.db.scalars(stmt).first()

    def list_text_sources(
        self,
        document_id: str,
        *,
        page_number: int | None = None,
    ) -> list[TextSourceRecord]:
        stmt = select(TextSourceRecord).where(
            TextSourceRecord.document_id == document_id
        )
        if page_number is not None:
            stmt = stmt.where(TextSourceRecord.page_number == page_number)
        return list(self.db.scalars(stmt))

    # ------------------------------------------------------------------
    # field_candidates
    # ------------------------------------------------------------------

    def insert_field_candidate(
        self,
        *,
        document_id: str,
        field_key: str,
        source_type: str,
        selection_status: str,
        candidate_value: str | None = None,
        normalized_value: str | None = None,
        provider: str | None = None,
        text_source_id: str | None = None,
        page_number: int | None = None,
        evidence_text: str | None = None,
        confidence: float | None = None,
        rejection_reason: str | None = None,
    ) -> FieldCandidateRecord:
        record = FieldCandidateRecord(
            id=str(uuid4()),
            document_id=document_id,
            field_key=field_key,
            source_type=source_type,
            selection_status=selection_status,
            candidate_value=candidate_value,
            normalized_value=normalized_value,
            provider=provider,
            text_source_id=text_source_id,
            page_number=page_number,
            evidence_text=evidence_text,
            confidence=confidence,
            rejection_reason=rejection_reason,
            created_at=_now(),
        )
        self.db.add(record)
        self.db.flush()
        return record

    def list_field_candidates(
        self,
        document_id: str,
        *,
        field_key: str | None = None,
    ) -> list[FieldCandidateRecord]:
        stmt = select(FieldCandidateRecord).where(
            FieldCandidateRecord.document_id == document_id
        )
        if field_key is not None:
            stmt = stmt.where(FieldCandidateRecord.field_key == field_key)
        return list(self.db.scalars(stmt))

    def select_field_candidate(
        self, candidate_id: str
    ) -> FieldCandidateRecord | None:
        target = self.db.get(FieldCandidateRecord, candidate_id)
        if target is None:
            return None

        # Flip all "candidate" status siblings (same doc + field, different id)
        self.db.execute(
            update(FieldCandidateRecord)
            .where(
                FieldCandidateRecord.document_id == target.document_id,
                FieldCandidateRecord.field_key == target.field_key,
                FieldCandidateRecord.id != candidate_id,
                FieldCandidateRecord.selection_status == "candidate",
            )
            .values(
                selection_status="rejected",
                rejection_reason="superseded_by_selection",
            )
        )

        target.selection_status = "selected"
        self.db.flush()
        return target
