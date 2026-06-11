"""Read-only evidence observability service for Phase 1f dev endpoints.

Provides get_document_evidence and get_bundle_evidence which assemble
evidence table rows into a structured response without any DB mutations.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import DocumentRecord
from app.models.document_page import DocumentPageRecord
from app.models.field_candidate import FieldCandidateRecord
from app.models.order_bundle import OrderBundleRecord
from app.models.text_source import TextSourceRecord

_PREVIEW_LEN = 300


def _text_source_to_dict(ts: TextSourceRecord) -> dict:
    raw = ts.raw_text or ""
    norm = ts.normalized_text or ""
    return {
        "id": ts.id,
        "page_number": ts.page_number,
        "source_type": ts.source_type,
        "provider": ts.provider,
        "provider_version": ts.provider_version,
        "success": ts.success,
        "error": ts.error,
        "duration_ms": ts.duration_ms,
        "settings_hash": ts.settings_hash,
        "image_hash": ts.image_hash,
        "raw_text_length": len(raw),
        "raw_text_preview": raw[:_PREVIEW_LEN] if raw else None,
        "normalized_text_length": len(norm) if norm else None,
        "normalized_text_preview": norm[:_PREVIEW_LEN] if norm else None,
        "created_at": ts.created_at.isoformat() if ts.created_at else None,
    }


def _document_page_to_dict(dp: DocumentPageRecord) -> dict:
    return {
        "id": dp.id,
        "page_number": dp.page_number,
        "image_path": dp.image_path,
        "image_hash": dp.image_hash,
        "has_digital_text": dp.has_digital_text,
        "rotation_detected": dp.rotation_detected,
        "page_classification": dp.page_classification,
        "created_at": dp.created_at.isoformat() if dp.created_at else None,
    }


def _field_candidate_to_dict(fc: FieldCandidateRecord) -> dict:
    return {
        "id": fc.id,
        "field_key": fc.field_key,
        "candidate_value": fc.candidate_value,
        "normalized_value": fc.normalized_value,
        "source_type": fc.source_type,
        "provider": fc.provider,
        "text_source_id": fc.text_source_id,
        "page_number": fc.page_number,
        "evidence_text": fc.evidence_text,
        "confidence": fc.confidence,
        "selection_status": fc.selection_status,
        "rejection_reason": fc.rejection_reason,
        "created_at": fc.created_at.isoformat() if fc.created_at else None,
    }


def _build_document_evidence(db: Session, doc: DocumentRecord) -> dict:
    pages = list(db.scalars(
        select(DocumentPageRecord)
        .where(DocumentPageRecord.document_id == doc.id)
        .order_by(DocumentPageRecord.page_number)
    ))
    sources = list(db.scalars(
        select(TextSourceRecord)
        .where(TextSourceRecord.document_id == doc.id)
        .order_by(TextSourceRecord.page_number, TextSourceRecord.created_at)
    ))
    candidates = list(db.scalars(
        select(FieldCandidateRecord)
        .where(FieldCandidateRecord.document_id == doc.id)
        .order_by(FieldCandidateRecord.field_key, FieldCandidateRecord.created_at)
    ))

    page_dicts = [_document_page_to_dict(p) for p in pages]
    source_dicts = [_text_source_to_dict(s) for s in sources]
    candidate_dicts = [_field_candidate_to_dict(c) for c in candidates]

    return {
        "document_id": doc.id,
        "document_type": doc.document_type,
        "filename": doc.filename,
        "summary": {
            "document_pages_count": len(page_dicts),
            "text_sources_count": len(source_dicts),
            "field_candidates_count": len(candidate_dicts),
        },
        "document_pages": page_dicts,
        "text_sources": source_dicts,
        "field_candidates": candidate_dicts,
    }


class EvidenceQueryService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_document_evidence(self, document_id: str) -> dict | None:
        doc = self._db.scalars(
            select(DocumentRecord).where(DocumentRecord.id == document_id)
        ).first()
        if doc is None:
            return None
        return _build_document_evidence(self._db, doc)

    def get_bundle_evidence(self, bundle_id: str) -> dict:
        bundle = self._db.scalars(
            select(OrderBundleRecord).where(OrderBundleRecord.id == bundle_id)
        ).first()
        docs = list(self._db.scalars(
            select(DocumentRecord)
            .where(DocumentRecord.order_bundle_id == bundle_id)
            .order_by(DocumentRecord.created_at)
        ))
        return {
            "bundle_id": bundle_id,
            "bundle_number": bundle.bundle_number if bundle else None,
            "documents": [_build_document_evidence(self._db, d) for d in docs],
        }
