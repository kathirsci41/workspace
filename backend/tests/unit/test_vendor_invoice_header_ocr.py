from __future__ import annotations

import inspect
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import fitz
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.services.extraction.glm_ocr_client as glm_ocr_client
import app.services.extraction_service as extraction_service
from app.config import Settings, replace_settings
from app.migrations.runner import run
from app.models.document import DocumentRecord
from app.models.order_bundle import OrderBundleRecord
from app.models.text_source import TextSourceRecord
from app.services.extraction.glm_ocr_client import OcrResult


_BASE_TEXT = (
    "TAX INVOICE\n"
    "Taxable Amount: 100000\n"
    "Invoice Total: 118000\n"
)


def _make_blank_pdf(path: Path, *, width: float = 400, height: float = 1000) -> None:
    document = fitz.open()
    document.new_page(width=width, height=height)
    document.save(str(path))
    document.close()


def _ocr_result(text: str) -> OcrResult:
    return OcrResult(
        text=text,
        pages=[{"page_number": 1, "ocr_text_length": len(text)}],
        provider="glm_ocr",
        model="glm-ocr:latest",
        diagnostics={
            "ocr_provider": "glm_ocr",
            "ocr_model": "glm-ocr:latest",
            "ocr_duration_ms": 20,
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
        image_data=b"header-crop-png",
        error=None,
        diagnostics={
            "ocr_header_duration_ms": 17,
            "ocr_header_crop_fraction": 0.4,
            "ocr_header_text_length": len(text),
        },
    )


def _make_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    *,
    evidence_capture_enabled: bool = False,
) -> Session:
    db_url = f"sqlite:///{tmp_path / name}"
    current = Settings(
        database_url=db_url,
        evidence_capture_enabled=evidence_capture_enabled,
        digital_text_enabled=True,
        structured_rules_enabled=True,
        ocr_enabled=True,
        ocr_provider="glm_ocr",
        ocr_model="glm-ocr:latest",
        model_layer2_enabled=False,
    )
    replace_settings(current)
    monkeypatch.setattr(extraction_service, "settings", current)
    monkeypatch.setattr(glm_ocr_client, "settings", current)
    run("up")
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _setup_document(
    db: Session,
    storage_path: str,
    *,
    document_type: str = "VENDOR_INVOICE",
    filename: str = "Vendor Invoice Document.pdf",
) -> DocumentRecord:
    now = datetime.now(timezone.utc)
    bundle = OrderBundleRecord(
        id=str(uuid4()),
        bundle_number=f"HEADER-OCR-{uuid4().hex[:8]}",
        created_at=now,
        updated_at=now,
    )
    db.add(bundle)
    db.flush()
    document = DocumentRecord(
        id=str(uuid4()),
        order_bundle_id=bundle.id,
        document_type=document_type,
        filename=filename,
        storage_path=storage_path,
        status="UPLOADED",
        created_at=now,
        updated_at=now,
    )
    db.add(document)
    db.flush()
    return document


def _extract_with_mocks(
    db: Session,
    document: DocumentRecord,
    *,
    normal_text: str,
    header_text: str,
):
    with (
        patch.object(extraction_service, "extract_text_with_ocr", return_value=_ocr_result(normal_text)),
        patch.object(
            extraction_service,
            "extract_header_text_with_ocr",
            return_value=_header_result(header_text),
            create=True,
        ) as header_ocr,
    ):
        result = extraction_service.extract_document(db, document, force=True)
    return result, header_ocr


def test_header_ocr_is_attempted_for_vendor_invoice_with_missing_header_field(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    pdf = tmp_path / "vendor.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, "vendor_missing.db")
    document = _setup_document(db, str(pdf))

    result, header_ocr = _extract_with_mocks(
        db,
        document,
        normal_text=_BASE_TEXT + "Invoice Date: 04-03-2026\nPO No: PO-76432\n",
        header_text="Invoice No: ACME/INV/76432\n",
    )

    header_ocr.assert_called_once()
    assert result["metadata"].extracted_data["vendor_invoice_no"] == "ACME/INV/76432"


def test_header_ocr_is_not_attempted_when_normal_parser_has_strong_header_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    pdf = tmp_path / "strong.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, "strong.db")
    document = _setup_document(db, str(pdf))

    result, header_ocr = _extract_with_mocks(
        db,
        document,
        normal_text=(
            _BASE_TEXT
            + "Invoice No: ACME/INV/10001\n"
            + "Invoice Date: 04-03-2026\n"
            + "PO No: PO-10001\n"
        ),
        header_text="Invoice No: WRONG/99999\n",
    )

    header_ocr.assert_not_called()
    assert result["metadata"].extracted_data["vendor_invoice_no"] == "ACME/INV/10001"


@pytest.mark.parametrize(
    "document_type",
    ["CUSTOMER_PO", "COMPANY_INVOICE", "COMPANY_DC", "COMPANY_PO"],
)
def test_header_ocr_does_not_run_for_non_vendor_invoice_documents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    document_type: str,
):
    pdf = tmp_path / f"{document_type}.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, f"{document_type}.db")
    document = _setup_document(db, str(pdf), document_type=document_type)

    _, header_ocr = _extract_with_mocks(
        db,
        document,
        normal_text=_BASE_TEXT,
        header_text="Invoice No: ACME/INV/20001\n",
    )

    header_ocr.assert_not_called()


@pytest.mark.parametrize(
    ("missing_field", "normal_header", "header_text", "expected"),
    [
        (
            "vendor_invoice_no",
            "Invoice Date: 04-03-2026\nPO No: PO-30001\n",
            "Invoice No: ACME/INV/30001\n",
            "ACME/INV/30001",
        ),
        (
            "vendor_invoice_date",
            "Invoice No: ACME/INV/30002\nPO No: PO-30002\n",
            "Invoice Date: 05-03-2026\n",
            "05-03-2026",
        ),
        (
            "po_reference",
            "Invoice No: ACME/INV/30003\nInvoice Date: 06-03-2026\n",
            "Buyer PO No: PO-30003\n",
            "PO-30003",
        ),
    ],
)
def test_header_ocr_fills_each_missing_target_field(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    missing_field: str,
    normal_header: str,
    header_text: str,
    expected: str,
):
    pdf = tmp_path / f"{missing_field}.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, f"{missing_field}.db")
    document = _setup_document(db, str(pdf))

    result, _ = _extract_with_mocks(
        db,
        document,
        normal_text=_BASE_TEXT + normal_header,
        header_text=header_text,
    )

    assert result["metadata"].extracted_data[missing_field] == expected
    assert result["metadata"].diagnostics["field_metadata"][missing_field]["source"] == "ocr_header"


def test_header_ocr_does_not_overwrite_stronger_parser_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    pdf = tmp_path / "no-overwrite.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, "no_overwrite.db")
    document = _setup_document(db, str(pdf))

    result, header_ocr = _extract_with_mocks(
        db,
        document,
        normal_text=(
            _BASE_TEXT
            + "Invoice No: ACME/INV/40001\n"
            + "Invoice Date: 07-03-2026\n"
        ),
        header_text=(
            "Invoice No: WRONG/40001\n"
            "Invoice Date: 01-01-2000\n"
            "PO No: PO-40001\n"
        ),
    )

    header_ocr.assert_called_once()
    fields = result["metadata"].extracted_data
    assert fields["vendor_invoice_no"] == "ACME/INV/40001"
    assert fields["vendor_invoice_date"] == "07-03-2026"
    assert fields["po_reference"] == "PO-40001"


def test_header_ocr_replaces_weak_filename_fallback_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    pdf = tmp_path / "weak-fallback.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, "weak_fallback.db")
    document = _setup_document(
        db,
        str(pdf),
        filename="Vendor Bill FALLBACK50001.pdf",
    )

    result, header_ocr = _extract_with_mocks(
        db,
        document,
        normal_text=_BASE_TEXT + "Invoice Date: 08-03-2026\nPO No: PO-50001\n",
        header_text="Invoice No: ACME/INV/50001\n",
    )

    header_ocr.assert_called_once()
    assert result["metadata"].extracted_data["vendor_invoice_no"] == "ACME/INV/50001"
    assert result["metadata"].diagnostics["field_metadata"]["vendor_invoice_no"]["source"] == "ocr_header"


def test_header_ocr_remains_stronger_after_existing_orientation_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    pdf = tmp_path / "orientation-priority.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, "orientation_priority.db")
    document = _setup_document(
        db,
        str(pdf),
        filename="Vendor Bill FALLBACK54001.pdf",
    )
    normal = _ocr_result(
        "TAX INVOICE\n"
        "Invoice Date: 08-03-2026\n"
        "PO No: PO-54001\n"
        "Invoice Total: 118000\n"
    )
    orientation_retry = _ocr_result("Taxable Amount: 100000\n")

    with (
        patch.object(
            extraction_service,
            "extract_text_with_ocr",
            side_effect=[normal, orientation_retry],
        ),
        patch.object(
            extraction_service,
            "extract_header_text_with_ocr",
            return_value=_header_result("Invoice No: ACME/INV/54001\n"),
        ),
    ):
        result = extraction_service.extract_document(db, document, force=True)

    assert result["metadata"].extracted_data["vendor_invoice_no"] == "ACME/INV/54001"
    assert result["metadata"].diagnostics["field_metadata"]["vendor_invoice_no"]["source"] == "ocr_header"


def test_header_ocr_normalizes_json_style_target_labels_for_existing_parser(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    pdf = tmp_path / "json-header.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, "json_header.db")
    document = _setup_document(db, str(pdf))

    result, _ = _extract_with_mocks(
        db,
        document,
        normal_text=_BASE_TEXT,
        header_text=(
            '```json\n'
            '{\n'
            '  "Invoice No": "ACME/INV/55001",\n'
            '  "Invoice Date": "08-03-2026",\n'
            '  "PO Reference": "PO 1PTR55001"\n'
            '}\n'
            '```'
        ),
    )

    fields = result["metadata"].extracted_data
    assert fields["vendor_invoice_no"] == "ACME/INV/55001"
    assert fields["vendor_invoice_date"] == "08-03-2026"
    assert fields["po_reference"] == "1PTR55001"


def test_header_ocr_failure_is_swallowed_and_existing_result_is_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    pdf = tmp_path / "failure.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, "failure.db")
    document = _setup_document(
        db,
        str(pdf),
        filename="Vendor Bill FALLBACK60001.pdf",
    )
    normal = _ocr_result(
        _BASE_TEXT + "Invoice Date: 09-03-2026\nPO No: PO-60001\n"
    )

    with (
        patch.object(extraction_service, "extract_text_with_ocr", return_value=normal),
        patch.object(
            extraction_service,
            "extract_header_text_with_ocr",
            side_effect=RuntimeError("header provider unavailable"),
            create=True,
        ),
    ):
        result = extraction_service.extract_document(db, document, force=True)

    assert result["metadata"].extracted_data["vendor_invoice_no"] == "FALLBACK60001"
    assert result["metadata"].diagnostics["field_metadata"]["vendor_invoice_no"]["source"] == "filename_fallback"
    assert result["metadata"].diagnostics["ocr_header_status"] == "provider_error"


def test_header_ocr_evidence_is_written_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    pdf = tmp_path / "evidence-on.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(
        tmp_path,
        monkeypatch,
        "evidence_on.db",
        evidence_capture_enabled=True,
    )
    document = _setup_document(db, str(pdf))

    _extract_with_mocks(
        db,
        document,
        normal_text=_BASE_TEXT + "Invoice Date: 10-03-2026\nPO No: PO-70001\n",
        header_text="Invoice No: ACME/INV/70001\n",
    )

    row = db.scalars(
        select(TextSourceRecord).where(
            TextSourceRecord.document_id == document.id,
            TextSourceRecord.source_type == "ocr_header",
        )
    ).one()
    assert row.provider == "glm_ocr"
    assert row.provider_version == "glm-ocr:latest"
    assert row.success is True
    assert row.duration_ms == 17
    assert row.settings_hash is not None
    assert row.image_hash is not None


def test_header_ocr_evidence_is_not_written_when_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    pdf = tmp_path / "evidence-off.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, "evidence_off.db")
    document = _setup_document(db, str(pdf))

    _extract_with_mocks(
        db,
        document,
        normal_text=_BASE_TEXT + "Invoice Date: 11-03-2026\nPO No: PO-80001\n",
        header_text="Invoice No: ACME/INV/80001\n",
    )

    rows = db.scalars(
        select(TextSourceRecord).where(
            TextSourceRecord.document_id == document.id,
            TextSourceRecord.source_type == "ocr_header",
        )
    ).all()
    assert rows == []


def test_header_ocr_failure_evidence_records_error_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    pdf = tmp_path / "evidence-failure.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(
        tmp_path,
        monkeypatch,
        "evidence_failure.db",
        evidence_capture_enabled=True,
    )
    document = _setup_document(
        db,
        str(pdf),
        filename="Vendor Bill FALLBACK90001.pdf",
    )
    normal = _ocr_result(
        _BASE_TEXT + "Invoice Date: 12-03-2026\nPO No: PO-90001\n"
    )

    with (
        patch.object(extraction_service, "extract_text_with_ocr", return_value=normal),
        patch.object(
            extraction_service,
            "extract_header_text_with_ocr",
            side_effect=RuntimeError("header OCR timed out"),
            create=True,
        ),
    ):
        extraction_service.extract_document(db, document, force=True)

    row = db.scalars(
        select(TextSourceRecord).where(
            TextSourceRecord.document_id == document.id,
            TextSourceRecord.source_type == "ocr_header",
        )
    ).one()
    assert row.success is False
    assert "timed out" in (row.error or "")
    assert row.settings_hash is not None
    assert row.image_hash is not None


def test_header_ocr_renders_top_40_percent_of_first_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    pdf = tmp_path / "crop.pdf"
    _make_blank_pdf(pdf, width=400, height=1000)
    monkeypatch.setattr(
        glm_ocr_client,
        "_call_ollama_generate_with_retries",
        lambda *args, **kwargs: "Invoice No: ACME/INV/91001",
    )

    result = glm_ocr_client.extract_header_text_with_ocr(
        str(pdf),
        dpi=72,
        timeout_seconds=30,
    )

    assert result.text == "Invoice No: ACME/INV/91001"
    assert result.image_data
    assert result.diagnostics["ocr_header_page_number"] == 1
    assert result.diagnostics["ocr_header_crop_fraction"] == 0.4
    assert result.diagnostics["ocr_header_image_width"] == 400
    assert result.diagnostics["ocr_header_image_height"] == 400


def test_header_ocr_renders_top_fraction_of_rotated_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """At rotation=90°, a 400×1000 portrait becomes 1000×400 landscape;
    the top 40% crop should be 1000×160, not the unrotated 400×400."""
    pdf = tmp_path / "crop-rotated.pdf"
    _make_blank_pdf(pdf, width=400, height=1000)
    monkeypatch.setattr(
        glm_ocr_client,
        "_call_ollama_generate_with_retries",
        lambda *args, **kwargs: "Invoice No: ACME/INV/91002",
    )

    result = glm_ocr_client.extract_header_text_with_ocr(
        str(pdf),
        dpi=72,
        timeout_seconds=30,
        rotation_degrees=90,
    )

    assert result.diagnostics["ocr_header_rotation_degrees"] == 90
    assert result.diagnostics["ocr_header_image_width"] == 1000
    assert result.diagnostics["ocr_header_image_height"] == 160


def test_header_ocr_rotation_forwarded_from_manual_extraction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Manual rotation passed to extract_document propagates into extract_header_text_with_ocr."""
    pdf = tmp_path / "rotated-extract.pdf"
    _make_blank_pdf(pdf)
    db = _make_session(tmp_path, monkeypatch, "rotated_extract.db")
    document = _setup_document(db, str(pdf))

    captured_kwargs: dict = {}

    def fake_header_ocr(file_path, **kwargs):
        captured_kwargs.update(kwargs)
        return _header_result("Invoice No: ACME/INV/94001\n")

    with (
        patch.object(
            extraction_service,
            "extract_text_with_ocr",
            return_value=_ocr_result(
                "TAX INVOICE\nInvoice Date: 15-03-2026\nPO No: PO-94001\nInvoice Total: 118000\n"
            ),
        ),
        patch.object(
            extraction_service,
            "extract_header_text_with_ocr",
            side_effect=fake_header_ocr,
            create=True,
        ),
    ):
        extraction_service.extract_document(db, document, force=True, ocr_rotation_degrees=90)

    assert captured_kwargs.get("rotation_degrees") == 90


def test_header_ocr_uses_generic_label_preserving_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    pdf = tmp_path / "prompt.pdf"
    _make_blank_pdf(pdf)
    captured: dict[str, str] = {}

    def fake_ocr_call(*args, **kwargs):
        captured["prompt"] = kwargs.get("prompt", "")
        return "Invoice No: ACME/INV/92001"

    monkeypatch.setattr(
        glm_ocr_client,
        "_call_ollama_generate_with_retries",
        fake_ocr_call,
    )

    glm_ocr_client.extract_header_text_with_ocr(
        str(pdf),
        dpi=72,
        timeout_seconds=30,
    )

    prompt = captured["prompt"]
    assert "Invoice No" in prompt
    assert "Invoice Date" in prompt
    assert "PO Reference" in prompt
    assert "do not infer" in prompt.lower()
    assert "panimalar" not in prompt.lower()


def test_header_ocr_bounds_provider_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    pdf = tmp_path / "bounded-output.pdf"
    _make_blank_pdf(pdf)
    captured: dict[str, int | None] = {}

    def fake_ocr_call(*args, **kwargs):
        captured["max_output_tokens"] = kwargs.get("max_output_tokens")
        return "Invoice No: ACME/INV/93001"

    monkeypatch.setattr(
        glm_ocr_client,
        "_call_ollama_generate_with_retries",
        fake_ocr_call,
    )

    glm_ocr_client.extract_header_text_with_ocr(
        str(pdf),
        dpi=72,
        timeout_seconds=30,
    )

    assert captured["max_output_tokens"] == 256


def test_phase1k_production_code_has_no_document_specific_hardcoding():
    source = (
        inspect.getsource(extraction_service)
        + inspect.getsource(glm_ocr_client)
    ).lower()
    assert "panimalar" not in source


# ---------------------------------------------------------------------------
# Phase 1p: focused unit tests for _normalize_vendor_invoice_header_ocr_text
# ---------------------------------------------------------------------------

def test_normalize_header_repeated_json_blocks_does_not_crash():
    """Two JSON blocks with the same labels — stable, no exception, first match wins."""
    text = (
        '```json\n'
        '{\n'
        '  "Invoice No": "FIRST/001",\n'
        '  "Invoice Date": "01-01-2026"\n'
        '}\n'
        '```\n'
        '```json\n'
        '{\n'
        '  "Invoice No": "SECOND/002",\n'
        '  "Invoice Date": "02-01-2026"\n'
        '}\n'
        '```'
    )
    result = extraction_service._normalize_vendor_invoice_header_ocr_text(text)
    assert isinstance(result, str)
    assert "Invoice No: FIRST/001" in result
    assert "Invoice Date: 01-01-2026" in result


def test_normalize_header_extra_non_target_keys_are_ignored():
    """JSON with non-target keys like Total/GST — only target fields appear in parser lines."""
    text = (
        '```json\n'
        '{\n'
        '  "Invoice No": "EXT/001",\n'
        '  "Invoice Date": "03-01-2026",\n'
        '  "Total": "99000",\n'
        '  "GST": "9"\n'
        '}\n'
        '```'
    )
    result = extraction_service._normalize_vendor_invoice_header_ocr_text(text)
    assert "Invoice No: EXT/001" in result
    assert "Invoice Date: 03-01-2026" in result
    assert "Total: 99000" not in result
    assert "GST: 9" not in result


def test_normalize_header_po_prefix_stripped_when_remainder_contains_digit():
    """'PO 1ABC2345' loses the 'PO ' prefix because the remainder contains a digit."""
    text = '{"Invoice No": "DIG/001", "Invoice Date": "05-01-2026", "PO Reference": "PO 1ABC2345"}'
    result = extraction_service._normalize_vendor_invoice_header_ocr_text(text)
    assert "PO Reference: 1ABC2345" in result


def test_normalize_header_po_prefix_not_stripped_when_remainder_has_no_digit():
    """'PO BOX' has no digit in the remainder — the prefix is not stripped."""
    text = '{"PO No": "PO BOX"}'
    result = extraction_service._normalize_vendor_invoice_header_ocr_text(text)
    assert "PO Reference: PO BOX" in result


def test_normalize_header_wrong_ocr_value_passes_through_unchanged():
    """A visibly wrong OCR value is forwarded as-is — no guessing, no correction."""
    text = '{"Invoice No": "BADVAL999", "Invoice Date": "31-12-2025"}'
    result = extraction_service._normalize_vendor_invoice_header_ocr_text(text)
    assert "Invoice No: BADVAL999" in result
    assert "Invoice Date: 31-12-2025" in result


def test_normalize_header_malformed_json_like_text_does_not_crash():
    """Incomplete or invalid JSON-like text must not raise an exception."""
    malformed_inputs = [
        '{"Invoice No":',
        '"Invoice No" "NODOT/001"',
        '```json\n{\n```',
        "",
        "   ",
    ]
    for raw in malformed_inputs:
        result = extraction_service._normalize_vendor_invoice_header_ocr_text(raw)
        assert isinstance(result, str), f"Raised or returned non-str for {raw!r}"


def test_normalize_header_plain_text_label_value_still_works():
    """Plain 'Label: Value' OCR (non-JSON) produces parser-readable output."""
    text = "Invoice No: PLAIN/001\nInvoice Date: 04-01-2026\nPO No: PO-1001"
    result = extraction_service._normalize_vendor_invoice_header_ocr_text(text)
    assert "Invoice No: PLAIN/001" in result
    assert "Invoice Date: 04-01-2026" in result
