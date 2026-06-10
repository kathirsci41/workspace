"""EvidenceService: facade over EvidenceRepository with deterministic hash helpers.

Phase 1d: provides safe cache-checked text source recording and hash utilities.
Not wired into the extraction runtime — that happens in a later phase.
"""
from __future__ import annotations

import hashlib
import json

from sqlalchemy.orm import Session

from app.models.document_page import DocumentPageRecord
from app.models.field_candidate import FieldCandidateRecord
from app.models.text_source import TextSourceRecord
from app.repositories.evidence import EvidenceRepository


# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------

def build_settings_hash(provider: str, settings: dict | None) -> str:
    """Deterministic SHA-256 of provider + settings dict.

    Key order in the dict is irrelevant — JSON sort_keys=True normalises it.
    None and {} are treated identically.
    """
    payload = {"provider": provider, "settings": settings or {}}
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def build_image_hash(image_data: bytes) -> str:
    """SHA-256 of raw image bytes."""
    return f"sha256:{hashlib.sha256(image_data).hexdigest()}"


def build_synthetic_source_hash(source_type: str, document_id: str, page_number: int) -> str:
    """Deterministic hash for sources that have no page image (e.g. digital text).

    Used so that image_hash is never NULL in the database, preserving the
    UNIQUE(document_id, page_number, provider, settings_hash, image_hash)
    cache-key constraint.
    """
    key = f"synthetic|{source_type}|{document_id}|{page_number}"
    return f"sha256:{hashlib.sha256(key.encode('utf-8')).hexdigest()}"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class EvidenceService:
    def __init__(self, db: Session) -> None:
        self._repo = EvidenceRepository(db)

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
        return self._repo.upsert_document_page(
            document_id,
            page_number,
            image_path=image_path,
            image_hash=image_hash,
            has_digital_text=has_digital_text,
            rotation_detected=rotation_detected,
            page_classification=page_classification,
        )

    def get_document_page(
        self, document_id: str, page_number: int
    ) -> DocumentPageRecord | None:
        return self._repo.get_document_page(document_id, page_number)

    # ------------------------------------------------------------------
    # text_sources
    # ------------------------------------------------------------------

    def record_text_source(
        self,
        *,
        document_id: str,
        page_number: int,
        source_type: str,
        provider: str,
        settings: dict | None = None,
        image_data: bytes | None = None,
        success: bool,
        provider_version: str | None = None,
        raw_text: str | None = None,
        normalized_text: str | None = None,
        error: str | None = None,
        duration_ms: int | None = None,
    ) -> TextSourceRecord:
        """Return a cached or newly inserted TextSourceRecord.

        Computes cache key hashes from raw inputs so callers never supply
        NULL values — the service owns hash derivation.
        """
        settings_hash = build_settings_hash(provider, settings)
        if image_data is not None:
            image_hash = build_image_hash(image_data)
        else:
            image_hash = build_synthetic_source_hash(source_type, document_id, page_number)

        existing = self._repo.get_text_source_by_cache_key(
            document_id, page_number, provider, settings_hash, image_hash
        )
        if existing is not None:
            return existing

        settings_json = json.dumps(settings, sort_keys=True) if settings else None

        return self._repo.insert_text_source(
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
        )

    def get_text_source(
        self,
        document_id: str,
        page_number: int,
        provider: str,
        settings_hash: str,
        image_hash: str,
    ) -> TextSourceRecord | None:
        return self._repo.get_text_source_by_cache_key(
            document_id, page_number, provider, settings_hash, image_hash
        )

    def list_text_sources(
        self,
        document_id: str,
        *,
        page_number: int | None = None,
    ) -> list[TextSourceRecord]:
        return self._repo.list_text_sources(document_id, page_number=page_number)

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
        return self._repo.insert_field_candidate(
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
        )

    def list_field_candidates(
        self,
        document_id: str,
        *,
        field_key: str | None = None,
    ) -> list[FieldCandidateRecord]:
        return self._repo.list_field_candidates(document_id, field_key=field_key)

    def select_field_candidate(
        self, candidate_id: str
    ) -> FieldCandidateRecord | None:
        return self._repo.select_field_candidate(candidate_id)
