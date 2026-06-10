"""TDD tests for Phase 1e: digital PDF text evidence capture behind a feature flag.

These tests call extract_document() directly with a real PDF on disk.
No mocks are used — the extraction pipeline is exercised end-to-end.
All three evidence-capture scenarios are covered:
  - flag OFF  → no text_sources rows written
  - flag ON   → one text_sources row per PDF page written
  - flag ON, duplicate run → no duplicate rows
  - flag OFF vs ON → extracted_data dict is identical
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session

from app.config import Settings, replace_settings
from app.migrations.runner import run
from app.models.document import DocumentRecord
from app.models.order_bundle import OrderBundleRecord
from app.models.text_source import TextSourceRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Enough text to exceed MIN_DIGITAL_TEXT_LENGTH (25) and trigger digital path
_PDF_TEXT = (
    "Tax Invoice\n"
    "1ITR2526001878\n"
    "1OTM2526001611\n"
    "PMCH/024/2025-2026\n"
    "Invoice Date\n"
    "13/02/2026\n"
    "Customer Name & Detail\n"
    "PANIMALAR MEDICAL HOSPITAL\n"
    "Nett Amount\n"
    "874439\n"
    "133389\n"
    "741050\n"
)


def _make_pdf(path: Path, text: str) -> None:
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((36, 36), text, fontsize=10)
    doc.save(str(path))
    doc.close()


def _make_pdf_2page(path: Path) -> None:
    import fitz
    doc = fitz.open()
    for i, label in enumerate(("Page one text for evidence.", "Page two text for evidence."), start=1):
        page = doc.new_page()
        page.insert_text((36, 36 + i * 12), label, fontsize=10)
    doc.save(str(path))
    doc.close()


def _make_session(tmp_path: Path, name: str, *, evidence_capture_enabled: bool) -> Session:
    db_url = f"sqlite:///{tmp_path / name}"
    replace_settings(Settings(
        database_url=db_url,
        evidence_capture_enabled=evidence_capture_enabled,
        digital_text_enabled=True,
        structured_rules_enabled=True,
        ocr_enabled=False,
        model_layer2_enabled=False,
    ))
    run("up")
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _setup_document(db: Session, storage_path: str, document_type: str = "COMPANY_INVOICE") -> DocumentRecord:
    now = datetime.now(timezone.utc)
    bundle = OrderBundleRecord(
        id=str(uuid4()),
        bundle_number=f"TEST-{uuid4().hex[:8]}",
        created_at=now,
        updated_at=now,
    )
    db.add(bundle)
    db.flush()
    document = DocumentRecord(
        id=str(uuid4()),
        order_bundle_id=bundle.id,
        document_type=document_type,
        filename="test.pdf",
        storage_path=storage_path,
        status="UPLOADED",
        created_at=now,
        updated_at=now,
    )
    db.add(document)
    db.flush()
    return document


# ---------------------------------------------------------------------------
# Imports under test — these will fail with TypeError until config is updated
# ---------------------------------------------------------------------------

def _require_flag_field() -> None:
    """Raise if Settings does not yet have evidence_capture_enabled."""
    Settings(evidence_capture_enabled=True)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Flag field presence (guards all other tests)
# ---------------------------------------------------------------------------

class TestEvidenceCaptureFlag:
    def test_settings_has_evidence_capture_enabled_field(self):
        s = Settings(evidence_capture_enabled=False)  # type: ignore[call-arg]
        assert s.evidence_capture_enabled is False

    def test_evidence_capture_enabled_defaults_to_false(self):
        s = Settings()
        assert s.evidence_capture_enabled is False


# ---------------------------------------------------------------------------
# Flag OFF — no evidence rows, unchanged extraction
# ---------------------------------------------------------------------------

class TestEvidenceCaptureOff:
    def test_no_text_sources_written_when_flag_off(self, tmp_path: Path):
        pdf_path = tmp_path / "invoice.pdf"
        _make_pdf(pdf_path, _PDF_TEXT)
        db = _make_session(tmp_path, "off.db", evidence_capture_enabled=False)
        document = _setup_document(db, str(pdf_path))

        from app.services.extraction_service import extract_document
        extract_document(db, document, force=True)

        rows = list(db.scalars(select(TextSourceRecord).where(
            TextSourceRecord.document_id == document.id
        )))
        assert len(rows) == 0, f"expected 0 text_sources rows with flag OFF, found {len(rows)}"

    def test_extraction_succeeds_with_flag_off(self, tmp_path: Path):
        pdf_path = tmp_path / "invoice.pdf"
        _make_pdf(pdf_path, _PDF_TEXT)
        db = _make_session(tmp_path, "off2.db", evidence_capture_enabled=False)
        document = _setup_document(db, str(pdf_path))

        from app.services.extraction_service import extract_document
        result = extract_document(db, document, force=True)

        assert result["metadata"].extracted_data is not None
        assert result["metadata"].status in ("EXTRACTED", "MANUAL_ENTRY", "FAILED")


# ---------------------------------------------------------------------------
# Flag ON — evidence rows written, extraction output unchanged
# ---------------------------------------------------------------------------

class TestEvidenceCaptureOn:
    def test_writes_one_text_source_row_per_page_when_flag_on(self, tmp_path: Path):
        pdf_path = tmp_path / "invoice_2pg.pdf"
        _make_pdf_2page(pdf_path)
        db = _make_session(tmp_path, "on.db", evidence_capture_enabled=True)
        document = _setup_document(db, str(pdf_path))

        from app.services.extraction_service import extract_document
        extract_document(db, document, force=True)

        rows = list(db.scalars(select(TextSourceRecord).where(
            TextSourceRecord.document_id == document.id
        )))
        assert len(rows) == 2, f"expected 2 text_sources rows (one per page), found {len(rows)}"
        assert all(r.provider == "digital_pdf" for r in rows)
        assert all(r.source_type == "digital_text" for r in rows)
        assert all(r.success is True for r in rows)

    def test_text_source_cache_keys_are_never_null(self, tmp_path: Path):
        pdf_path = tmp_path / "invoice.pdf"
        _make_pdf(pdf_path, _PDF_TEXT)
        db = _make_session(tmp_path, "on2.db", evidence_capture_enabled=True)
        document = _setup_document(db, str(pdf_path))

        from app.services.extraction_service import extract_document
        extract_document(db, document, force=True)

        rows = list(db.scalars(select(TextSourceRecord).where(
            TextSourceRecord.document_id == document.id
        )))
        assert len(rows) >= 1
        for row in rows:
            assert row.settings_hash is not None and row.settings_hash.startswith("sha256:")
            assert row.image_hash is not None and row.image_hash.startswith("sha256:")

    def test_duplicate_run_does_not_create_duplicate_rows(self, tmp_path: Path):
        pdf_path = tmp_path / "invoice.pdf"
        _make_pdf(pdf_path, _PDF_TEXT)
        db = _make_session(tmp_path, "dup.db", evidence_capture_enabled=True)
        document = _setup_document(db, str(pdf_path))

        from app.services.extraction_service import extract_document
        extract_document(db, document, force=True)
        first_count = db.scalars(select(TextSourceRecord).where(
            TextSourceRecord.document_id == document.id
        )).all()

        # Expire the document so SQLAlchemy re-queries document.metadata_record
        # on the next access (mirrors real-world per-request session lifecycle).
        db.expire(document)

        # Second extraction — same document, same PDF
        extract_document(db, document, force=True)
        second_count = db.scalars(select(TextSourceRecord).where(
            TextSourceRecord.document_id == document.id
        )).all()

        assert len(first_count) == len(second_count), (
            f"duplicate run added rows: first={len(first_count)}, second={len(second_count)}"
        )

    def test_extraction_output_identical_flag_off_vs_on(self, tmp_path: Path):
        pdf_path = tmp_path / "invoice.pdf"
        _make_pdf(pdf_path, _PDF_TEXT)

        # Run with flag OFF
        db_off = _make_session(tmp_path, "cmp_off.db", evidence_capture_enabled=False)
        doc_off = _setup_document(db_off, str(pdf_path))
        from app.services.extraction_service import extract_document
        result_off = extract_document(db_off, doc_off, force=True)
        fields_off = dict(result_off["metadata"].extracted_data or {})
        status_off = result_off["metadata"].status
        db_off.close()

        # Run with flag ON
        db_on = _make_session(tmp_path, "cmp_on.db", evidence_capture_enabled=True)
        doc_on = _setup_document(db_on, str(pdf_path))
        result_on = extract_document(db_on, doc_on, force=True)
        fields_on = dict(result_on["metadata"].extracted_data or {})
        status_on = result_on["metadata"].status
        db_on.close()

        assert fields_off == fields_on, (
            f"extracted_data differs between flag OFF and ON:\n"
            f"  OFF: {sorted(fields_off.keys())}\n"
            f"   ON: {sorted(fields_on.keys())}"
        )
        assert status_off == status_on
