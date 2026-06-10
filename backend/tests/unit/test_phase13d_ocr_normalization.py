from __future__ import annotations

from types import SimpleNamespace

import app.services.extraction_service as extraction_service
from app.config import Settings
from app.services.extraction.digital_text_extractor import normalize_ocr_text
from app.services.extraction.glm_ocr_client import OcrResult


def test_joins_grouped_number():
    assert normalize_ocr_text("4 63 365.55") == "463365.55"


def test_does_not_join_separate_decimal_amounts():
    assert normalize_ocr_text("000.00 3,20,000.00 3,20,000.00") == "000.00 3,20,000.00 3,20,000.00"


def test_removes_spaces_around_separators():
    assert normalize_ocr_text("PMCH &RI /024/ 2025-2026") == "PMCH&RI/024/2025-2026"


def test_rejoins_split_reference_code():
    assert normalize_ocr_text("1OTM 2526 001611") == "1OTM2526001611"
    assert normalize_ocr_text("1OTM 2526001611") == "1OTM2526001611"
    assert normalize_ocr_text("SOSC 2526000429") == "SOSC2526000429"


def test_does_not_corrupt_prose():
    for value in [
        "Panimalar Medical Hospital",
        "Laptop Dell Latitude 5420",
        "Order 5 units",
        "Page 2 of 3",
        "GST 18 percent",
        "Qty 2 Nos",
        "Tax 12 percent extra",
    ]:
        assert normalize_ocr_text(value) == value, f"corrupted: {value!r} -> {normalize_ocr_text(value)!r}"


def test_already_clean_text_unchanged():
    assert normalize_ocr_text("PMCH&RI/024/2025-2026") == "PMCH&RI/024/2025-2026"
    assert normalize_ocr_text("463365.55") == "463365.55"


def test_ocr_route_normalizes_text_before_parsing(monkeypatch):
    captured: dict[str, str] = {}
    ocr_text = "Purchase Order No\nPMCH &RI /024/ 2025-2026\nPO Date\n29.01.2026\nGrand Total\n4 63 365.55"

    def fake_parse(document_type, raw_text, extraction_route, filename=None, context=None):
        captured["text"] = raw_text
        return {
            "fields": {"customer_po_no": "PMCH&RI/024/2025-2026", "grand_total": 463365.55},
            "missing_required_fields": [],
            "confidence": 100.0,
            "parser_route": "ocr_rules",
            "diagnostics": {"failure_code": None, "failure_reason": None},
            "field_metadata": {},
        }

    monkeypatch.setattr(
        extraction_service,
        "settings",
        Settings(ocr_enabled=True, ocr_provider="glm_ocr", model_layer2_enabled=False),
    )
    monkeypatch.setattr(extraction_service, "extract_pdf_text_pages", lambda *_args, **_kwargs: [""])
    monkeypatch.setattr(
        extraction_service,
        "extract_text_with_ocr",
        lambda *_args, **_kwargs: OcrResult(
            text=ocr_text,
            pages=[],
            provider="glm_ocr",
            model="glm-ocr:latest",
            diagnostics={"ocr_provider": "glm_ocr", "ocr_model": "glm-ocr:latest", "ocr_text_length": len(ocr_text)},
        ),
    )
    monkeypatch.setattr(extraction_service, "parse_structured_text", fake_parse)
    monkeypatch.setattr(extraction_service, "build_field_locations", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(extraction_service, "ReferenceIndexRepository", _FakeReferenceRepository)

    metadata = _metadata()
    extraction_service.extract_document(_FakeDb(), _document("CUSTOMER_PO", metadata), force=True)

    assert "PMCH&RI/024/2025-2026" in captured["text"]
    assert "463365.55" in captured["text"]


def test_digital_route_does_not_normalize_text_before_parsing(monkeypatch):
    captured: dict[str, str] = {}
    digital_text = "Purchase Order No\nPMCH &RI /024/ 2025-2026\nGrand Total\n4 63 365.55"

    def fake_parse(document_type, raw_text, extraction_route, filename=None, context=None):
        captured["text"] = raw_text
        return {
            "fields": {"customer_po_no": "PMCH"},
            "missing_required_fields": [],
            "confidence": 100.0,
            "parser_route": "digital_rules",
            "diagnostics": {"failure_code": None, "failure_reason": None},
            "field_metadata": {},
        }

    monkeypatch.setattr(
        extraction_service,
        "settings",
        Settings(ocr_enabled=True, ocr_provider="glm_ocr", model_layer2_enabled=False),
    )
    monkeypatch.setattr(extraction_service, "extract_pdf_text_pages", lambda *_args, **_kwargs: [digital_text])
    monkeypatch.setattr(extraction_service, "parse_structured_text", fake_parse)
    monkeypatch.setattr(extraction_service, "build_field_locations", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(extraction_service, "ReferenceIndexRepository", _FakeReferenceRepository)

    metadata = _metadata()
    extraction_service.extract_document(_FakeDb(), _document("CUSTOMER_PO", metadata), force=True)

    assert captured["text"] == digital_text


def test_vendor_invoice_retries_sideways_ocr_for_missing_table_fields(monkeypatch):
    calls: list[int] = []

    def fake_ocr(*_args, **kwargs):
        rotation = kwargs.get("rotation_degrees", 0)
        calls.append(rotation)
        if rotation == 0:
            text = """
            Tax Invoice No: 2526PSI25087738
            Invoice Date: 12-02-2026
            Vendor Name: SUPREME COMPUTERS INDIA PVT LTD
            Total Invoice Value: Rs 554600
            """
        else:
            text = """
            External doc. No: PO 1PTR2526000467
            Sr. No. Description Disc Total Taxable Value CGST SGST Total
            1 Server 0% 000.00 3,20,000.00 3,20,000.00 9% 28,800.00 9% 28,800.00 3,77,600.00
            2 Controller 0% 000.00 1,50,000.00 1,50,000.00 9% 13,500.00 9% 13,500.00 1,77,000.00
            """
        return OcrResult(
            text=text,
            pages=[],
            provider="glm_ocr",
            model="glm-ocr:latest",
            diagnostics={"ocr_provider": "glm_ocr", "ocr_model": "glm-ocr:latest", "ocr_text_length": len(text)},
        )

    monkeypatch.setattr(
        extraction_service,
        "settings",
        Settings(ocr_enabled=True, ocr_provider="glm_ocr", model_layer2_enabled=False),
    )
    monkeypatch.setattr(extraction_service, "extract_pdf_text_pages", lambda *_args, **_kwargs: [""])
    monkeypatch.setattr(extraction_service, "extract_text_with_ocr", fake_ocr)
    monkeypatch.setattr(extraction_service, "build_field_locations", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(extraction_service, "ReferenceIndexRepository", _FakeReferenceRepository)

    metadata = _metadata()
    document = _document("VENDOR_INVOICE", metadata)
    extraction_service.extract_document(_FakeDb(), document, force=True)

    assert calls == [0, 0, 90]
    assert metadata.extracted_data["po_reference"] == "1PTR2526000467"
    assert metadata.extracted_data["taxable_amount"] == 470000
    assert metadata.diagnostics["ocr_orientation_retry_used"] is True
    assert document.status == "PENDING_REVIEW"


class _FakeDb:
    def flush(self) -> None:
        pass


class _FakeReferenceRepository:
    def __init__(self, _db):
        pass

    def replace_for_document(self, *_args, **_kwargs):
        return []


def _metadata():
    return SimpleNamespace(
        status="PENDING",
        extracted_data={},
        diagnostics={},
        primary_ref_no=None,
        po_ref_no=None,
        last_error=None,
    )


def _document(document_type: str, metadata):
    return SimpleNamespace(
        id="document-id",
        order_bundle_id="bundle-id",
        document_type=document_type,
        filename="document.pdf",
        storage_path="document.pdf",
        metadata_record=metadata,
        status="PENDING",
        last_error=None,
    )
