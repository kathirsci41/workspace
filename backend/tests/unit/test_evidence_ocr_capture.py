"""TDD tests for Phase 1g: OCR text evidence capture behind the EVIDENCE_CAPTURE_ENABLED flag.

All tests use a blank PDF (no digital text) to trigger the OCR extraction path,
and mock extract_text_with_ocr to avoid live OCR calls.

Covers:
  - flag OFF → no OCR evidence rows written
  - flag ON  → one text_sources row with source_type="ocr"
  - duplicate run → no duplicate rows (cache key deduplication)
  - provider="glm_ocr" on the OCR row
  - provider_version matches configured OCR model
  - settings_hash and image_hash are non-null
  - extraction output (fields + status) identical flag OFF vs ON
  - Phase 1e digital capture tests still unaffected
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, replace_settings
from app.migrations.runner import run
from app.models.document import DocumentRecord
from app.models.order_bundle import OrderBundleRecord
from app.models.text_source import TextSourceRecord
from app.services.extraction.glm_ocr_client import OcrResult
from app.services.extraction_service import extract_document


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OCR_TEXT = (
    "Tax Invoice\n"
    "Invoice No\n"
    "1ITR2526001878\n"
    "Invoice Date 13/02/2026\n"
    "Nett Amount 874439\n"
    "Tax Amount 133389\n"
)

_MOCK_OCR_DIAGNOSTICS = {
    "ocr_provider": "glm_ocr",
    "ocr_model": "glm-ocr:latest",
    "ocr_duration_ms": 1234,
    "ocr_text_length": len(_OCR_TEXT),
    "ocr_pages_attempted": 1,
    "ocr_page_results": [{"page_number": 1, "ocr_text_length": len(_OCR_TEXT)}],
    "ocr_context_length": 8192,
    "ocr_base_url_host_only": "localhost:11434",
    "ocr_rotation_degrees": 0,
}

_MOCK_OCR_RESULT = OcrResult(
    text=_OCR_TEXT,
    pages=[{"page_number": 1, "ocr_text_length": len(_OCR_TEXT)}],
    provider="glm_ocr",
    model="glm-ocr:latest",
    diagnostics=_MOCK_OCR_DIAGNOSTICS,
)


def _make_blank_pdf(path: Path) -> None:
    """Create a PDF with no extractable digital text — triggers the OCR path."""
    import fitz
    doc = fitz.open()
    doc.new_page()
    doc.save(str(path))
    doc.close()


def _make_session(
    tmp_path: Path,
    name: str,
    *,
    evidence_capture_enabled: bool,
    ocr_enabled: bool = True,
) -> Session:
    db_url = f"sqlite:///{tmp_path / name}"
    replace_settings(Settings(
        database_url=db_url,
        evidence_capture_enabled=evidence_capture_enabled,
        digital_text_enabled=True,
        structured_rules_enabled=True,
        ocr_enabled=ocr_enabled,
        ocr_provider="glm_ocr",
        ocr_model="glm-ocr:latest",
        model_layer2_enabled=False,
    ))
    run("up")
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _setup_document(db: Session, storage_path: str) -> DocumentRecord:
    now = datetime.now(timezone.utc)
    bundle = OrderBundleRecord(
        id=str(uuid4()),
        bundle_number=f"OCR-TEST-{uuid4().hex[:6]}",
        created_at=now,
        updated_at=now,
    )
    db.add(bundle)
    db.flush()
    doc = DocumentRecord(
        id=str(uuid4()),
        order_bundle_id=bundle.id,
        document_type="COMPANY_INVOICE",
        filename="scanned_invoice.pdf",
        storage_path=storage_path,
        status="UPLOADED",
        created_at=now,
        updated_at=now,
    )
    db.add(doc)
    db.flush()
    return doc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestOcrEvidenceCaptureFlag:
    def test_flag_off_does_not_write_ocr_evidence(self, tmp_path: Path):
        pdf = tmp_path / "blank.pdf"
        _make_blank_pdf(pdf)
        db = _make_session(tmp_path, "flag_off.db", evidence_capture_enabled=False)
        doc = _setup_document(db, str(pdf))

        with patch("app.services.extraction_service.extract_text_with_ocr", return_value=_MOCK_OCR_RESULT):
            extract_document(db, doc, force=True)

        rows = db.scalars(select(TextSourceRecord).where(TextSourceRecord.document_id == doc.id)).all()
        ocr_rows = [r for r in rows if r.source_type == "ocr"]
        assert len(ocr_rows) == 0

    def test_flag_on_writes_ocr_text_source(self, tmp_path: Path):
        pdf = tmp_path / "blank.pdf"
        _make_blank_pdf(pdf)
        db = _make_session(tmp_path, "flag_on.db", evidence_capture_enabled=True)
        doc = _setup_document(db, str(pdf))

        with patch("app.services.extraction_service.extract_text_with_ocr", return_value=_MOCK_OCR_RESULT):
            extract_document(db, doc, force=True)

        ocr_rows = db.scalars(
            select(TextSourceRecord).where(
                TextSourceRecord.document_id == doc.id,
                TextSourceRecord.source_type == "ocr",
            )
        ).all()
        assert len(ocr_rows) == 1


class TestOcrEvidenceContent:
    def test_ocr_text_source_has_correct_provider(self, tmp_path: Path):
        pdf = tmp_path / "blank.pdf"
        _make_blank_pdf(pdf)
        db = _make_session(tmp_path, "provider.db", evidence_capture_enabled=True)
        doc = _setup_document(db, str(pdf))

        with patch("app.services.extraction_service.extract_text_with_ocr", return_value=_MOCK_OCR_RESULT):
            extract_document(db, doc, force=True)

        row = db.scalars(
            select(TextSourceRecord).where(
                TextSourceRecord.document_id == doc.id,
                TextSourceRecord.source_type == "ocr",
            )
        ).first()
        assert row is not None
        assert row.provider == "glm_ocr"

    def test_ocr_text_source_has_provider_version(self, tmp_path: Path):
        pdf = tmp_path / "blank.pdf"
        _make_blank_pdf(pdf)
        db = _make_session(tmp_path, "version.db", evidence_capture_enabled=True)
        doc = _setup_document(db, str(pdf))

        with patch("app.services.extraction_service.extract_text_with_ocr", return_value=_MOCK_OCR_RESULT):
            extract_document(db, doc, force=True)

        row = db.scalars(
            select(TextSourceRecord).where(
                TextSourceRecord.document_id == doc.id,
                TextSourceRecord.source_type == "ocr",
            )
        ).first()
        assert row is not None
        assert row.provider_version == "glm-ocr:latest"

    def test_settings_hash_and_image_hash_are_non_null(self, tmp_path: Path):
        pdf = tmp_path / "blank.pdf"
        _make_blank_pdf(pdf)
        db = _make_session(tmp_path, "hashes.db", evidence_capture_enabled=True)
        doc = _setup_document(db, str(pdf))

        with patch("app.services.extraction_service.extract_text_with_ocr", return_value=_MOCK_OCR_RESULT):
            extract_document(db, doc, force=True)

        row = db.scalars(
            select(TextSourceRecord).where(
                TextSourceRecord.document_id == doc.id,
                TextSourceRecord.source_type == "ocr",
            )
        ).first()
        assert row is not None
        assert row.settings_hash is not None
        assert row.settings_hash.startswith("sha256:")
        assert row.image_hash is not None
        assert row.image_hash.startswith("sha256:")


class TestOcrEvidenceCacheDedup:
    def test_duplicate_run_does_not_create_duplicate_rows(self, tmp_path: Path):
        pdf = tmp_path / "blank.pdf"
        _make_blank_pdf(pdf)
        db = _make_session(tmp_path, "dedup.db", evidence_capture_enabled=True)
        doc = _setup_document(db, str(pdf))

        with patch("app.services.extraction_service.extract_text_with_ocr", return_value=_MOCK_OCR_RESULT):
            extract_document(db, doc, force=True)
            db.expire(doc)
            extract_document(db, doc, force=True)

        ocr_rows = db.scalars(
            select(TextSourceRecord).where(
                TextSourceRecord.document_id == doc.id,
                TextSourceRecord.source_type == "ocr",
            )
        ).all()
        assert len(ocr_rows) == 1


class TestExtractionOutputUnchanged:
    def test_extraction_output_unchanged_flag_off(self, tmp_path: Path):
        pdf = tmp_path / "blank.pdf"
        _make_blank_pdf(pdf)
        db = _make_session(tmp_path, "unchanged_off.db", evidence_capture_enabled=False)
        doc = _setup_document(db, str(pdf))

        with patch("app.services.extraction_service.extract_text_with_ocr", return_value=_MOCK_OCR_RESULT):
            result = extract_document(db, doc, force=True)

        assert result["metadata"].status in ("EXTRACTED", "PENDING_REVIEW", "FAILED", "MANUAL_ENTRY")
        extracted = result["metadata"].extracted_data
        assert isinstance(extracted, dict)

    def test_extraction_output_unchanged_flag_on(self, tmp_path: Path):
        pdf_off = tmp_path / "blank_off.pdf"
        pdf_on = tmp_path / "blank_on.pdf"
        _make_blank_pdf(pdf_off)
        _make_blank_pdf(pdf_on)

        db_off = _make_session(tmp_path, "output_off.db", evidence_capture_enabled=False)
        doc_off = _setup_document(db_off, str(pdf_off))
        with patch("app.services.extraction_service.extract_text_with_ocr", return_value=_MOCK_OCR_RESULT):
            result_off = extract_document(db_off, doc_off, force=True)

        db_on = _make_session(tmp_path, "output_on.db", evidence_capture_enabled=True)
        doc_on = _setup_document(db_on, str(pdf_on))
        with patch("app.services.extraction_service.extract_text_with_ocr", return_value=_MOCK_OCR_RESULT):
            result_on = extract_document(db_on, doc_on, force=True)

        assert result_off["metadata"].status == result_on["metadata"].status
        assert result_off["metadata"].extracted_data == result_on["metadata"].extracted_data
