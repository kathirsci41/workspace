from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.services.extraction_service as extraction_service
from app.config import Settings, replace_settings
from app.migrations.runner import run
from app.models.document import DocumentRecord
from app.models.field_candidate import FieldCandidateRecord
from app.models.order_bundle import OrderBundleRecord
from app.services.extraction.glm_ocr_client import OcrResult


_VENDOR_TEXT = (
    "Tax Invoice\n"
    "Invoice No: INV-10001\n"
    "Invoice Date: 01-04-2026\n"
    "PO No: PO-10001\n"
    "Taxable Amount: 100000\n"
    "Invoice Total: 118000\n"
)

_VENDOR_TEXT_WITHOUT_INVOICE_NO = (
    "Tax Invoice\n"
    "Invoice Date: 02-04-2026\n"
    "PO No: PO-20001\n"
    "Taxable Amount: 200000\n"
    "Invoice Total: 236000\n"
)


def _make_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    *,
    evidence_capture_enabled: bool,
    ocr_enabled: bool = False,
) -> Session:
    db_url = f"sqlite:///{tmp_path / name}"
    current = Settings(
        database_url=db_url,
        evidence_capture_enabled=evidence_capture_enabled,
        digital_text_enabled=True,
        structured_rules_enabled=True,
        ocr_enabled=ocr_enabled,
        ocr_provider="glm_ocr",
        ocr_model="glm-ocr:latest",
        model_layer2_enabled=False,
    )
    replace_settings(current)
    monkeypatch.setattr(extraction_service, "settings", current)
    run("up")
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _setup_document(
    db: Session,
    *,
    filename: str = "vendor_invoice.pdf",
    storage_path: str = "vendor_invoice.pdf",
) -> DocumentRecord:
    now = datetime.now(timezone.utc)
    bundle = OrderBundleRecord(
        id=str(uuid4()),
        bundle_number=f"FC-{uuid4().hex[:8]}",
        created_at=now,
        updated_at=now,
    )
    db.add(bundle)
    db.flush()
    document = DocumentRecord(
        id=str(uuid4()),
        order_bundle_id=bundle.id,
        document_type="VENDOR_INVOICE",
        filename=filename,
        storage_path=storage_path,
        status="UPLOADED",
        created_at=now,
        updated_at=now,
    )
    db.add(document)
    db.flush()
    return document


def _extract_from_digital_text(
    db: Session,
    document: DocumentRecord,
    text: str = _VENDOR_TEXT,
):
    with patch.object(extraction_service, "extract_pdf_text_pages", return_value=[text]):
        return extraction_service.extract_document(db, document, force=True)


def _ocr_result(text: str) -> OcrResult:
    return OcrResult(
        text=text,
        pages=[{"page_number": 1, "ocr_text_length": len(text)}],
        provider="glm_ocr",
        model="glm-ocr:latest",
        diagnostics={
            "ocr_provider": "glm_ocr",
            "ocr_model": "glm-ocr:latest",
            "ocr_duration_ms": 25,
            "ocr_text_length": len(text),
            "ocr_pages_attempted": 1,
            "ocr_page_results": [{"page_number": 1, "ocr_text_length": len(text)}],
        },
    )


def _header_result(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        provider="glm_ocr",
        model="glm-ocr:latest",
        image_data=b"header-image",
        error=None,
        diagnostics={
            "ocr_header_duration_ms": 12,
            "ocr_header_text_length": len(text),
        },
    )


def _extract_from_ocr_text(
    db: Session,
    document: DocumentRecord,
    text: str = _VENDOR_TEXT,
):
    with (
        patch.object(extraction_service, "extract_pdf_text_pages", return_value=[""]),
        patch.object(extraction_service, "extract_text_with_ocr", return_value=_ocr_result(text)),
    ):
        return extraction_service.extract_document(db, document, force=True)


def _field_candidates(db: Session, document: DocumentRecord) -> list[FieldCandidateRecord]:
    return list(
        db.scalars(
            select(FieldCandidateRecord).where(
                FieldCandidateRecord.document_id == document.id
            )
        )
    )


def _candidate_for(
    db: Session,
    document: DocumentRecord,
    field_key: str,
) -> FieldCandidateRecord:
    row = db.scalars(
        select(FieldCandidateRecord).where(
            FieldCandidateRecord.document_id == document.id,
            FieldCandidateRecord.field_key == field_key,
        )
    ).one()
    return row


def test_flag_off_does_not_write_field_candidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    db = _make_session(
        tmp_path,
        monkeypatch,
        "flag_off.db",
        evidence_capture_enabled=False,
    )
    document = _setup_document(db)

    _extract_from_digital_text(db, document)

    assert _field_candidates(db, document) == []


def test_selected_vendor_invoice_no_candidate_contains_required_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    db = _make_session(
        tmp_path,
        monkeypatch,
        "invoice_no.db",
        evidence_capture_enabled=True,
    )
    document = _setup_document(db)

    _extract_from_digital_text(db, document)

    candidate = _candidate_for(db, document, "vendor_invoice_no")
    assert candidate.field_key == "vendor_invoice_no"
    assert candidate.candidate_value == "INV-10001"
    assert candidate.source_type == "digital_text"
    assert candidate.confidence == pytest.approx(0.9)
    assert candidate.selection_status == "selected"


def test_selected_vendor_invoice_date_candidate_written(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    db = _make_session(
        tmp_path,
        monkeypatch,
        "invoice_date.db",
        evidence_capture_enabled=True,
    )
    document = _setup_document(db)

    _extract_from_digital_text(db, document)

    candidate = _candidate_for(db, document, "vendor_invoice_date")
    assert candidate.candidate_value == "01-04-2026"
    assert candidate.source_type == "digital_text"
    assert candidate.selection_status == "selected"


def test_selected_po_reference_candidate_written(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    db = _make_session(
        tmp_path,
        monkeypatch,
        "po_reference.db",
        evidence_capture_enabled=True,
    )
    document = _setup_document(db)

    _extract_from_digital_text(db, document)

    candidate = _candidate_for(db, document, "po_reference")
    assert candidate.candidate_value == "PO-10001"
    assert candidate.source_type == "digital_text"
    assert candidate.confidence == pytest.approx(0.9)
    assert candidate.selection_status == "selected"


def test_selected_amount_candidates_written(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    db = _make_session(
        tmp_path,
        monkeypatch,
        "amounts.db",
        evidence_capture_enabled=True,
    )
    document = _setup_document(db)

    _extract_from_digital_text(db, document)

    taxable = _candidate_for(db, document, "taxable_amount")
    total = _candidate_for(db, document, "invoice_total")
    assert taxable.candidate_value == "100000"
    assert taxable.source_type == "digital_text"
    assert taxable.selection_status == "selected"
    assert total.candidate_value == "118000"
    assert total.source_type == "digital_text"
    assert total.selection_status == "selected"


def test_ocr_rule_candidate_uses_ocr_source_and_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    db = _make_session(
        tmp_path,
        monkeypatch,
        "ocr_rule.db",
        evidence_capture_enabled=True,
        ocr_enabled=True,
    )
    document = _setup_document(db)

    _extract_from_ocr_text(db, document)

    candidate = _candidate_for(db, document, "vendor_invoice_no")
    assert candidate.candidate_value == "INV-10001"
    assert candidate.source_type == "ocr"
    assert candidate.provider == "glm_ocr"
    assert candidate.selection_status == "selected"


def test_ocr_header_candidate_written_when_header_supplies_invoice_no(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    db = _make_session(
        tmp_path,
        monkeypatch,
        "ocr_header.db",
        evidence_capture_enabled=True,
        ocr_enabled=True,
    )
    document = _setup_document(db, storage_path="header.pdf")

    with (
        patch.object(extraction_service, "extract_pdf_text_pages", return_value=[""]),
        patch.object(
            extraction_service,
            "extract_text_with_ocr",
            return_value=_ocr_result(_VENDOR_TEXT_WITHOUT_INVOICE_NO),
        ),
        patch.object(
            extraction_service,
            "extract_header_text_with_ocr",
            return_value=_header_result("Invoice No: HDR-30001\n"),
        ),
    ):
        extraction_service.extract_document(db, document, force=True)

    candidate = _candidate_for(db, document, "vendor_invoice_no")
    assert candidate.candidate_value == "HDR-30001"
    assert candidate.source_type == "ocr_header"
    assert candidate.provider == "glm_ocr"
    assert candidate.confidence == pytest.approx(0.9)
    assert candidate.selection_status == "selected"


def test_filename_fallback_candidate_written_when_fallback_supplies_invoice_no(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    db = _make_session(
        tmp_path,
        monkeypatch,
        "filename_fallback.db",
        evidence_capture_enabled=True,
    )
    document = _setup_document(db, filename="Vendor Bill FALLBACK40001.pdf")

    _extract_from_digital_text(db, document, _VENDOR_TEXT_WITHOUT_INVOICE_NO)

    candidate = _candidate_for(db, document, "vendor_invoice_no")
    assert candidate.candidate_value == "FALLBACK40001"
    assert candidate.source_type == "filename_fallback"
    assert candidate.provider is None
    assert candidate.confidence == pytest.approx(0.45)
    assert candidate.selection_status == "selected"


def test_repeated_extraction_does_not_duplicate_selected_candidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    db = _make_session(
        tmp_path,
        monkeypatch,
        "dedupe.db",
        evidence_capture_enabled=True,
    )
    document = _setup_document(db)

    _extract_from_digital_text(db, document)
    first = _field_candidates(db, document)
    db.expire(document)
    _extract_from_digital_text(db, document)
    second = _field_candidates(db, document)

    assert len(first) == 5
    assert len(second) == 5


def test_extraction_output_unchanged_by_candidate_recording(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    db_off = _make_session(
        tmp_path,
        monkeypatch,
        "output_off.db",
        evidence_capture_enabled=False,
    )
    doc_off = _setup_document(db_off)
    result_off = _extract_from_digital_text(db_off, doc_off)
    fields_off = dict(result_off["metadata"].extracted_data or {})
    status_off = result_off["metadata"].status

    db_on = _make_session(
        tmp_path,
        monkeypatch,
        "output_on.db",
        evidence_capture_enabled=True,
    )
    doc_on = _setup_document(db_on)
    result_on = _extract_from_digital_text(db_on, doc_on)
    fields_on = dict(result_on["metadata"].extracted_data or {})
    status_on = result_on["metadata"].status

    assert fields_on == fields_off
    assert status_on == status_off
