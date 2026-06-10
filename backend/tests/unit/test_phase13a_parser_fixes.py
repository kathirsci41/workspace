from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.services.extraction_service as extraction_service
from app.config import Settings
from app.services.document_normalizer import NormalizedDocument
from app.services.extraction.digital_text_extractor import extract_digital_fields
from app.services.extraction.structured_text_parser import parse_structured_text
from app.services.order_bundle_verifier import verify_order_bundle


def test_digital_customer_po_uses_customer_po_parser():
    result = parse_structured_text(
        "CUSTOMER_PO",
        """
        Purchase Order No: PMCH&RI/024/2025-2026
        PO Date: 30/01/2026
        Customer Name: PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE
        """,
        extraction_route="digital",
    )

    assert result["fields"]["customer_po_no"] == "PMCH&RI/024/2025-2026"
    assert result["parser_route"] == "digital_rules"


def test_digital_vendor_invoice_uses_vendor_invoice_parser():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        TAX INVOICE
        Inflow Technologies Private Limited
        Invoice No: RED/2526/00001
        Invoice Date: 12-02-2026
        PO No: 1PTR2526000467
        Invoice Total: 554600
        """,
        extraction_route="digital",
    )

    assert result["fields"]["vendor_invoice_no"] == "RED/2526/00001"
    assert result["fields"]["po_reference"] == "1PTR2526000467"
    assert result["fields"]["invoice_total"] == 554600
    assert result["parser_route"] == "digital_rules"


@pytest.mark.parametrize("invoice_no", ["1ITR2526001878", "1IAM2526000527", "9STG2526000009"])
def test_company_invoice_patterns_support_known_invoice_series(invoice_no: str):
    result = extract_digital_fields(invoice_no, "COMPANY_INVOICE")

    assert result["invoice_number"] == invoice_no


@pytest.mark.parametrize("dc_no", ["1DNT2526DC3100", "MBDNT2526DC010", "MBDNT2526DC011"])
def test_company_dc_patterns_support_known_dc_series(dc_no: str):
    result = extract_digital_fields(dc_no, "COMPANY_DC")

    assert result["dc_number"] == dc_no


@pytest.mark.parametrize("po_no", ["1PTR2526000467", "1POC2526000408", "9POT2526000007", "9POT2526000008"])
def test_company_po_patterns_support_known_po_series(po_no: str):
    result = extract_digital_fields(po_no, "COMPANY_PO")

    assert result["po_number"] == po_no


@pytest.mark.parametrize("so_no", ["1OTM2526001611", "SOSC2526000429"])
def test_company_invoice_patterns_support_known_so_series(so_no: str):
    result = extract_digital_fields(f"SO No\n{so_no}", "COMPANY_INVOICE")

    assert result["so_number"] == so_no


def test_invoice_so_number_uses_label_and_does_not_collide_with_invoice_number():
    result = extract_digital_fields(
        """
        Tax Invoice
        1ITR2526001878
        SO No
        1OTM2526001611
        """,
        "COMPANY_INVOICE",
    )

    assert result["invoice_number"] == "1ITR2526001878"
    assert result["so_number"] == "1OTM2526001611"


def test_dc_number_does_not_become_so_number_without_so_value():
    result = extract_digital_fields("Delivery Challan\n1DNT2526DC3100", "COMPANY_DC")

    assert result["dc_number"] == "1DNT2526DC3100"
    assert result.get("so_number") is None


@pytest.mark.parametrize(
    ("po_text", "expected"),
    [
        ("Order No. CHIPL/2025-26/682", "CHIPL/2025-26/682"),
        ("Purchase Order No: PMCH&RI/024/2025-2026", "PMCH&RI/024/2025-2026"),
    ],
)
def test_customer_po_label_variants_extract_reference(po_text: str, expected: str):
    result = parse_structured_text("CUSTOMER_PO", po_text, extraction_route="digital")

    assert result["fields"]["customer_po_no"] == expected


@pytest.mark.parametrize(
    "date_value",
    ["12/02/2026", "12-02-2026", "12.01.2026", "12 Jan 2026", "12 January 2026"],
)
def test_vendor_invoice_supports_date_variants(date_value: str):
    result = parse_structured_text(
        "VENDOR_INVOICE",
        f"Invoice No: RED/001\nInvoice date\n: {date_value}",
        extraction_route="digital",
    )

    assert result["fields"]["vendor_invoice_date"] == date_value


def test_vendor_invoice_your_ref_and_header_vendor_name_are_extracted():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        TAX INVOICE
        Inflow Technologies Private Limited
        Invoice No: RED/2526/00001
        Invoice date
        : 12.01.2026
        Your Ref.
        : 1PTR2526000400
        Any claim arising from overdue payment is governed by these terms.
        Invoice Total: 502430.78
        """,
        extraction_route="digital",
    )

    assert result["fields"]["po_reference"] == "1PTR2526000400"
    assert result["fields"]["vendor_name"] == "Inflow Technologies Private Limited"
    assert "arising" not in result["fields"]["vendor_name"].lower()
    assert "overdue" not in result["fields"]["vendor_name"].lower()
    assert result["fields"]["vendor_invoice_date"] == "12.01.2026"


def test_vendor_invoice_uses_last_total_not_line_item_total():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        Invoice No: INV/001
        Total: 50000
        Invoice Total 502430.78
        """,
        extraction_route="digital",
    )

    assert result["fields"]["invoice_total"] == 502430.78


def test_customer_po_uses_last_grand_total():
    result = parse_structured_text(
        "CUSTOMER_PO",
        """
        Order No. CHIPL/2025-26/682
        Total: 50000
        Grand Total: 118000
        """,
        extraction_route="digital",
    )

    assert result["fields"]["grand_total"] == 118000


def _doc(document_id: str, document_type: str, **fields) -> NormalizedDocument:
    return NormalizedDocument(document_id=document_id, document_type=document_type, fields=fields)


def test_customer_delivery_sums_all_delivery_challan_amounts():
    summary = verify_order_bundle(
        [
            _doc("inv", "CUSTOMER_INVOICE", taxable_amount=1264481, customer_order_no="PO-1", so_no="SO-1", customer_name="Acme Ltd"),
            _doc("dc-1", "DELIVERY_CHALLAN", estimated_amount=1064481, customer_order_no="PO-1", so_no="SO-1", customer_name="Acme Ltd"),
            _doc("dc-2", "DELIVERY_CHALLAN", estimated_amount=200000, customer_order_no="PO-1", so_no="SO-1", customer_name="Acme Ltd"),
        ]
    )
    check = next(item for item in summary["checks"] if item["check_id"] == "INVOICE_DC_AMOUNT_MATCH")

    assert check["right_value"] == 1264481
    assert check["result"] == "PASS"


def test_customer_delivery_sums_three_delivery_challans():
    summary = verify_order_bundle(
        [
            _doc("inv", "CUSTOMER_INVOICE", taxable_amount=600, customer_order_no="PO-1", so_no="SO-1", customer_name="Acme Ltd"),
            _doc("dc-1", "DELIVERY_CHALLAN", estimated_amount=100, customer_order_no="PO-1", so_no="SO-1", customer_name="Acme Ltd"),
            _doc("dc-2", "DELIVERY_CHALLAN", estimated_amount=200, customer_order_no="PO-1", so_no="SO-1", customer_name="Acme Ltd"),
            _doc("dc-3", "DELIVERY_CHALLAN", estimated_amount=300, customer_order_no="PO-1", so_no="SO-1", customer_name="Acme Ltd"),
        ]
    )
    check = next(item for item in summary["checks"] if item["check_id"] == "INVOICE_DC_AMOUNT_MATCH")

    assert check["right_value"] == 600
    assert check["result"] == "PASS"


def test_missing_dc_so_is_review_not_mismatch():
    summary = verify_order_bundle(
        [
            _doc("inv", "CUSTOMER_INVOICE", taxable_amount=100, customer_order_no="PO-1", so_no="SO-1", customer_name="Acme Ltd"),
            _doc("dc", "DELIVERY_CHALLAN", estimated_amount=100, customer_order_no="PO-1", customer_name="Acme Ltd"),
        ]
    )
    check = next(item for item in summary["checks"] if item["check_id"] == "INVOICE_DC_SO_MATCH")

    assert check["result"] == "REVIEW_REQUIRED"
    assert summary["customer_delivery_status"] != "MISMATCH"


class _FakeDb:
    def flush(self) -> None:
        pass


class _FakeReferenceRepository:
    def __init__(self, _db):
        pass

    def replace_for_document(self, *_args, **_kwargs):
        return []


def _extract_with_existing_metadata(
    monkeypatch: pytest.MonkeyPatch,
    document_type: str,
    extracted_data: dict,
    field_metadata: dict,
    raw_text: str,
):
    metadata = SimpleNamespace(
        status="EXTRACTED",
        extracted_data=dict(extracted_data),
        diagnostics={"field_metadata": field_metadata},
        primary_ref_no=None,
        po_ref_no=None,
        last_error=None,
    )
    document = SimpleNamespace(
        id="document-id",
        order_bundle_id="bundle-id",
        document_type=document_type,
        filename="document.pdf",
        storage_path="document.pdf",
        metadata_record=metadata,
        status="PENDING_REVIEW",
        last_error=None,
    )
    monkeypatch.setattr(extraction_service, "settings", Settings(ocr_enabled=False))
    monkeypatch.setattr(extraction_service, "extract_pdf_text_pages", lambda *_args, **_kwargs: [raw_text])
    monkeypatch.setattr(extraction_service, "build_field_locations", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(extraction_service, "ReferenceIndexRepository", _FakeReferenceRepository)
    extraction_service.extract_document(_FakeDb(), document, force=True)
    return metadata


def test_reextract_preserves_manual_vendor_po_number(monkeypatch: pytest.MonkeyPatch):
    metadata = _extract_with_existing_metadata(
        monkeypatch,
        "COMPANY_PO",
        {"vendor_po_no": "MANUAL-PO-001"},
        {"vendor_po_no": {"source": "manual_entry"}},
        "Purchase Order\n1PTR2526000467",
    )

    assert metadata.extracted_data["vendor_po_no"] == "MANUAL-PO-001"
    assert metadata.diagnostics["field_metadata"]["vendor_po_no"]["source"] == "manual_entry"
    assert metadata.diagnostics["manual_fields_preserved"] == ["vendor_po_no"]


def test_reextract_preserves_manual_vendor_invoice_po_reference(monkeypatch: pytest.MonkeyPatch):
    metadata = _extract_with_existing_metadata(
        monkeypatch,
        "VENDOR_INVOICE",
        {"po_reference": "MANUAL-PO-001"},
        {"po_reference": {"source": "manual_entry"}},
        "Invoice No: INV/001\nPO No: PARSED-PO-001\nInvoice Total: 100",
    )

    assert metadata.extracted_data["po_reference"] == "MANUAL-PO-001"
    assert metadata.diagnostics["field_metadata"]["po_reference"]["source"] == "manual_entry"
    assert metadata.diagnostics["manual_fields_preserved"] == ["po_reference"]


def test_reextract_still_updates_non_manual_field(monkeypatch: pytest.MonkeyPatch):
    metadata = _extract_with_existing_metadata(
        monkeypatch,
        "COMPANY_PO",
        {"vendor_po_no": "OLD-RULE-VALUE"},
        {"vendor_po_no": {"source": "rules"}},
        "Purchase Order\n1PTR2526000467",
    )

    assert metadata.extracted_data["vendor_po_no"] == "1PTR2526000467"
    assert metadata.diagnostics["manual_fields_preserved"] == []
