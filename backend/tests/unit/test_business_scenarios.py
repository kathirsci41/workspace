from __future__ import annotations

from app.services.document_normalizer import NormalizedDocument
from app.services.extraction.structured_text_parser import _ref_label_po, parse_structured_text
from app.services.order_bundle_verifier import verify_order_bundle


def _fields(document_type: str, text: str, route: str = "digital") -> dict:
    return parse_structured_text(document_type, text, extraction_route=route)["fields"]


def _doc(document_id: str, document_type: str, **fields) -> NormalizedDocument:
    return NormalizedDocument(document_id=document_id, document_type=document_type, fields=fields)


def _check(summary: dict, check_id: str) -> dict:
    return next(check for check in summary["checks"] if check["check_id"] == check_id)


def _issue(summary: dict, code: str) -> dict:
    return next(issue for issue in summary["issues"] if issue["code"] == code)


def test_company_invoice_so_number_is_not_confused_with_invoice_number():
    fields = _fields(
        "COMPANY_INVOICE",
        "Invoice No.\nSO No.\n1ITR2526001878\n1OTM2526001611",
    )

    assert fields["so_number"] == "1OTM2526001611"
    assert fields["so_no"] == "1OTM2526001611"
    assert fields["invoice_number"] == "1ITR2526001878"


def test_customer_po_grand_total_skips_line_item_count():
    fields = _fields(
        "CUSTOMER_PO",
        "Sub Total\n4,96,000.00\nPURCHASE ORDER\nTotal\n2\n4,96,000.00",
    )

    assert fields["grand_total"] == 496000


def test_vendor_invoice_total_uses_label_fallback_when_line_total_is_smaller():
    fields = _fields(
        "VENDOR_INVOICE",
        "Line Total\n9983.13\nInvoice Total\n463365.55",
    )

    assert fields["invoice_total"] == 463365.55


def test_vendor_invoice_total_guard_preserves_correct_invoice_total_label():
    fields = _fields(
        "VENDOR_INVOICE",
        "Sub Total\n425788.80\nTax\n76641.98\nInvoice Total\n502430.78",
    )

    assert fields["invoice_total"] == 502430.78


def test_ref_label_po_extracts_real_references_only():
    assert _ref_label_po("REF: PMCH&RI/024/2025-2026") == "PMCH&RI/024/2025-2026"
    assert _ref_label_po("REFERENCE DOCUMENT ATTACHED") is None


def test_customer_po_scanned_parse_uses_ref_label_helper():
    fields = _fields("CUSTOMER_PO", "REF: PMCH&RI/024/2025-2026", route="scanned")

    assert fields["customer_po_no"] == "PMCH&RI/024/2025-2026"
    assert fields["customer_order_no"] == "PMCH&RI/024/2025-2026"


def test_full_customer_side_match_passes_so_check():
    summary = verify_order_bundle(
        [
            _doc("cp-1", "CUSTOMER_PO", customer_po_no="PMCH/024", grand_total=874439, customer_name="PANIMALAR"),
            _doc(
                "ci-1",
                "CUSTOMER_INVOICE",
                invoice_no="1ITR2526001878",
                customer_order_no="PMCH/024",
                so_no="1OTM2526001611",
                customer_name="PANIMALAR",
                taxable_amount=741050,
                net_amount=874439,
                grand_total=874439,
            ),
            _doc(
                "dc-1",
                "DELIVERY_CHALLAN",
                dc_no="1DNT2526DC3100",
                customer_order_no="PMCH/024",
                so_no="1OTM2526001611",
                customer_name="PANIMALAR",
                estimated_amount=741050,
            ),
        ]
    )

    assert summary["customer_delivery_status"] in {"PASS", "PARTIAL_PASS"}
    assert _check(summary, "INVOICE_DC_SO_MATCH")["result"] == "PASS"


def test_mismatched_invoice_and_dc_so_numbers_are_caught():
    summary = verify_order_bundle(
        [
            _doc("ci-1", "CUSTOMER_INVOICE", customer_order_no="PMCH/024", so_no="1OTM2526001611"),
            _doc("dc-1", "DELIVERY_CHALLAN", customer_order_no="PMCH/024", so_no="1OTM2526009999"),
        ]
    )

    assert _check(summary, "INVOICE_DC_SO_MATCH")["result"] == "MISMATCH"


def test_unmatched_vendor_bill_reference_is_flagged():
    summary = verify_order_bundle(
        [
            _doc("vp-1", "VENDOR_PO", vendor_po_no="1PTR2526000467", net_amount=696200),
            _doc("vb-1", "VENDOR_INVOICE", po_reference="UNKNOWN-999", invoice_total=554600),
        ]
    )

    assert summary["vendor_procurement_status"] in {"REVIEW_REQUIRED", "BLOCKED"}
    assert _issue(summary, "VENDOR_BILL_REFERENCE_UNMATCHED")


def test_unmatched_vendor_bill_issue_carries_invoice_document_id():
    summary = verify_order_bundle(
        [
            _doc("vp-1", "VENDOR_PO", vendor_po_no="1PTR2526000467", net_amount=696200),
            _doc("vb-real-id", "VENDOR_INVOICE", po_reference="UNKNOWN-999", invoice_total=554600),
        ]
    )

    assert _issue(summary, "VENDOR_BILL_REFERENCE_UNMATCHED")["document_id"] == "vb-real-id"


def test_missing_document_issues_do_not_point_to_a_document():
    vendor_po_missing = verify_order_bundle(
        [_doc("ci-1", "CUSTOMER_INVOICE", invoice_no="1ITR2526001878", so_no="1OTM2526001611")]
    )
    vendor_invoice_missing = verify_order_bundle(
        [
            _doc("ci-1", "CUSTOMER_INVOICE", invoice_no="1ITR2526001878", so_no="1OTM2526001611"),
            _doc("vp-1", "VENDOR_PO", vendor_po_no="1PTR2526000467", net_amount=696200),
        ]
    )

    assert _issue(vendor_po_missing, "VENDOR_PO_MISSING")["document_id"] is None
    assert _issue(vendor_invoice_missing, "VENDOR_INVOICE_MISSING")["document_id"] is None
