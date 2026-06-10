"""TDD tests for EvidenceService facade and hash helpers.

Phase 1d: deterministic hash helpers and a safe service facade over EvidenceRepository.

These tests run against the real migration schema (run("up")) — no mocks.
"""
from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.config import Settings, replace_settings
from app.migrations.runner import run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(tmp_path: Path, name: str = "test.db") -> Session:
    """Return a Session backed by a freshly migrated SQLite DB."""
    db_url = f"sqlite:///{tmp_path / name}"
    replace_settings(Settings(database_url=db_url))
    run("up")
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _doc_id() -> str:
    return str(uuid4())


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


# ---------------------------------------------------------------------------
# Imports under test — these will fail (ImportError) until the modules exist
# ---------------------------------------------------------------------------
from app.services.evidence_service import (  # noqa: E402
    EvidenceService,
    build_settings_hash,
    build_image_hash,
    build_synthetic_source_hash,
)


# ---------------------------------------------------------------------------
# build_settings_hash
# ---------------------------------------------------------------------------

class TestBuildSettingsHash:
    def test_is_deterministic(self):
        h1 = build_settings_hash("pdfminer", {"dpi": 150, "lang": "eng"})
        h2 = build_settings_hash("pdfminer", {"dpi": 150, "lang": "eng"})
        assert h1 == h2

    def test_independent_of_dict_key_order(self):
        h1 = build_settings_hash("pdfminer", {"a": 1, "b": 2})
        h2 = build_settings_hash("pdfminer", {"b": 2, "a": 1})
        assert h1 == h2

    def test_different_settings_produce_different_hashes(self):
        h1 = build_settings_hash("pdfminer", {"dpi": 150})
        h2 = build_settings_hash("pdfminer", {"dpi": 300})
        assert h1 != h2

    def test_different_providers_produce_different_hashes(self):
        settings = {"dpi": 150}
        h1 = build_settings_hash("pdfminer", settings)
        h2 = build_settings_hash("tesseract", settings)
        assert h1 != h2

    def test_none_settings_is_deterministic(self):
        h1 = build_settings_hash("pdfminer", None)
        h2 = build_settings_hash("pdfminer", None)
        assert h1 == h2

    def test_none_and_empty_dict_hash_identically(self):
        h1 = build_settings_hash("pdfminer", None)
        h2 = build_settings_hash("pdfminer", {})
        assert h1 == h2

    def test_format_is_sha256_prefixed(self):
        h = build_settings_hash("pdfminer", {"dpi": 150})
        assert _SHA256_RE.match(h), f"unexpected format: {h!r}"


# ---------------------------------------------------------------------------
# build_image_hash
# ---------------------------------------------------------------------------

class TestBuildImageHash:
    def test_is_deterministic(self):
        data = b"fake-image-bytes-1234"
        assert build_image_hash(data) == build_image_hash(data)

    def test_different_bytes_produce_different_hashes(self):
        assert build_image_hash(b"aaa") != build_image_hash(b"bbb")

    def test_format_is_sha256_prefixed(self):
        h = build_image_hash(b"some bytes")
        assert _SHA256_RE.match(h), f"unexpected format: {h!r}"


# ---------------------------------------------------------------------------
# build_synthetic_source_hash
# ---------------------------------------------------------------------------

class TestBuildSyntheticSourceHash:
    def test_is_deterministic(self):
        h1 = build_synthetic_source_hash("digital_text", "doc-abc", 1)
        h2 = build_synthetic_source_hash("digital_text", "doc-abc", 1)
        assert h1 == h2

    def test_differs_for_different_pages(self):
        h1 = build_synthetic_source_hash("digital_text", "doc-abc", 1)
        h2 = build_synthetic_source_hash("digital_text", "doc-abc", 2)
        assert h1 != h2

    def test_differs_for_different_documents(self):
        h1 = build_synthetic_source_hash("digital_text", "doc-aaa", 1)
        h2 = build_synthetic_source_hash("digital_text", "doc-bbb", 1)
        assert h1 != h2

    def test_format_is_sha256_prefixed(self):
        h = build_synthetic_source_hash("digital_text", "doc-abc", 1)
        assert _SHA256_RE.match(h), f"unexpected format: {h!r}"


# ---------------------------------------------------------------------------
# EvidenceService.record_text_source
# ---------------------------------------------------------------------------

class TestRecordTextSource:
    def _svc(self, tmp_path: Path) -> tuple[EvidenceService, Session]:
        session = _make_session(tmp_path)
        return EvidenceService(session), session

    def test_creates_row_on_first_call(self, tmp_path: Path):
        svc, session = self._svc(tmp_path)
        doc_id = _doc_id()
        record = svc.record_text_source(
            document_id=doc_id,
            page_number=1,
            source_type="digital_text",
            provider="pdfminer",
            settings={"version": "1"},
            image_data=None,
            success=True,
            raw_text="hello world",
        )
        assert record.id is not None
        assert record.document_id == doc_id
        assert record.success is True
        assert record.raw_text == "hello world"

    def test_returns_existing_row_on_duplicate_cache_key(self, tmp_path: Path):
        svc, session = self._svc(tmp_path)
        doc_id = _doc_id()
        kwargs = dict(
            document_id=doc_id,
            page_number=1,
            source_type="digital_text",
            provider="pdfminer",
            settings={"version": "1"},
            image_data=None,
            success=True,
        )
        first = svc.record_text_source(**kwargs)
        second = svc.record_text_source(**kwargs)

        assert second.id == first.id

        # Assert that only ONE row was inserted — not two
        all_rows = svc.list_text_sources(doc_id)
        assert len(all_rows) == 1, f"expected 1 row but found {len(all_rows)}"

    def test_digital_text_path_has_non_null_image_hash(self, tmp_path: Path):
        """image_data=None must still produce a non-null sha256: image_hash."""
        svc, _ = self._svc(tmp_path)
        doc_id = _doc_id()
        record = svc.record_text_source(
            document_id=doc_id,
            page_number=3,
            source_type="digital_text",
            provider="pdfminer",
            settings=None,
            image_data=None,  # no image — synthetic hash must be used
            success=True,
        )
        assert record.image_hash is not None
        assert _SHA256_RE.match(record.image_hash), (
            f"image_hash must be sha256:<hex> but got {record.image_hash!r}"
        )

    def test_settings_hash_is_never_null(self, tmp_path: Path):
        """settings=None must still produce a non-null sha256: settings_hash."""
        svc, _ = self._svc(tmp_path)
        doc_id = _doc_id()
        record = svc.record_text_source(
            document_id=doc_id,
            page_number=1,
            source_type="digital_text",
            provider="pdfminer",
            settings=None,
            image_data=None,
            success=False,
            error="extraction failed",
        )
        assert record.settings_hash is not None
        assert _SHA256_RE.match(record.settings_hash), (
            f"settings_hash must be sha256:<hex> but got {record.settings_hash!r}"
        )

    def test_image_data_path_uses_image_hash(self, tmp_path: Path):
        """Providing image_data bytes must store image hash (not synthetic hash)."""
        svc, _ = self._svc(tmp_path)
        doc_id = _doc_id()
        image_bytes = b"fake-png-header-bytes"
        record = svc.record_text_source(
            document_id=doc_id,
            page_number=2,
            source_type="ocr",
            provider="tesseract",
            settings={"psm": "3"},
            image_data=image_bytes,
            success=True,
        )
        expected_image_hash = build_image_hash(image_bytes)
        assert record.image_hash == expected_image_hash


# ---------------------------------------------------------------------------
# EvidenceService delegation: document pages and field candidates
# ---------------------------------------------------------------------------

class TestEvidenceServiceDelegation:
    def _svc(self, tmp_path: Path) -> EvidenceService:
        return EvidenceService(_make_session(tmp_path))

    def test_upsert_and_get_document_page(self, tmp_path: Path):
        svc = self._svc(tmp_path)
        doc_id = _doc_id()
        page = svc.upsert_document_page(doc_id, 1, has_digital_text=True)
        assert page.document_id == doc_id
        assert page.page_number == 1

        fetched = svc.get_document_page(doc_id, 1)
        assert fetched is not None
        assert fetched.id == page.id
        assert fetched.has_digital_text is True

    def test_insert_and_list_field_candidates(self, tmp_path: Path):
        svc = self._svc(tmp_path)
        doc_id = _doc_id()
        c1 = svc.insert_field_candidate(
            document_id=doc_id,
            field_key="po_number",
            source_type="digital_text",
            selection_status="candidate",
            candidate_value="PO-001",
        )
        c2 = svc.insert_field_candidate(
            document_id=doc_id,
            field_key="po_number",
            source_type="digital_text",
            selection_status="candidate",
            candidate_value="PO-002",
        )
        all_candidates = svc.list_field_candidates(doc_id, field_key="po_number")
        assert len(all_candidates) == 2
        ids = {c.id for c in all_candidates}
        assert c1.id in ids
        assert c2.id in ids

    def test_select_field_candidate_marks_selected_and_rejects_siblings(self, tmp_path: Path):
        svc = self._svc(tmp_path)
        doc_id = _doc_id()
        c1 = svc.insert_field_candidate(
            document_id=doc_id,
            field_key="invoice_number",
            source_type="digital_text",
            selection_status="candidate",
            candidate_value="INV-001",
        )
        c2 = svc.insert_field_candidate(
            document_id=doc_id,
            field_key="invoice_number",
            source_type="digital_text",
            selection_status="candidate",
            candidate_value="INV-002",
        )
        selected = svc.select_field_candidate(c1.id)
        assert selected is not None
        assert selected.selection_status == "selected"

        candidates = svc.list_field_candidates(doc_id, field_key="invoice_number")
        statuses = {c.id: c.selection_status for c in candidates}
        assert statuses[c1.id] == "selected"
        assert statuses[c2.id] == "rejected"
