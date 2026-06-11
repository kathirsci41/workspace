import pytest

from app.services.extraction.structured_text_parser import FailureCode, _clean_vendor_name, _looks_like_code, parse_structured_text
from app.services.extraction.model_layer2 import extract_structured_fields_with_model, validate_model_json


def test_vendor_invoice_ocr_text_extracts_references_and_amount():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        TAX INVOICE
        Invoice No: 2526PSI25087738
        Invoice Date: 12-02-2026
        Vendor Name: SUPREME COMPUTERS INDIA P LTD
        PO No: 1PTR2526000467
        Grand Total: 554600
        """,
        extraction_route="scanned",
        filename="Vendor Bill 2526PSI25087738.pdf",
    )

    assert result["fields"]["vendor_invoice_no"] == "2526PSI25087738"
    assert result["fields"]["vendor_invoice_date"] == "12-02-2026"
    assert result["fields"]["po_reference"] == "1PTR2526000467"
    assert result["fields"]["invoice_total"] == 554600
    assert result["diagnostics"]["failure_code"] is None
    assert result["field_metadata"]["vendor_invoice_no"]["source"] == "rules"
    assert result["field_metadata"]["vendor_invoice_no"]["confidence"] >= 0.8


def test_vendor_invoice_derives_taxable_amount_from_explicit_split_gst_basis():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        TAX INVOICE
        Invoice No: 2526PSI25087738
        Invoice Date: 12-02-2026
        PO No: 1PTR2526000467
        Taxable Value CGST SGST
        3,20,000.00 9 % 28,800.00 9 % 28,800.00 3,77,600.00
        60,000.00 9 % 5,400.00 9 % 5,400.00 70,800.00
        Total Invoice Value: Rs 554600
        """,
        extraction_route="scanned",
    )

    assert result["fields"]["taxable_amount"] == 470000
    assert result["fields"]["subtotal_amount"] == 470000
    assert result["diagnostics"]["taxable_amount_source"] == "invoice_total_split_gst_9_9"


def test_vendor_invoice_skips_irn_hash_when_later_invoice_number_is_available():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        TAX INVOICE
        Invoice No.: 1a795d8d41301807788b3d0b9ce6b71755abeb9d9f1c8bb126a648a2f80fa0a3
        Invoice No.: 2526PSI25087738
        Date: 12-02-2026
        External doc. No: PO 1PTR2526000467
        Total Invoice Value: Rs 554600
        """,
        extraction_route="scanned",
    )

    assert result["fields"]["vendor_invoice_no"] == "2526PSI25087738"


def test_vendor_invoice_uses_filename_fallback_when_invoice_number_missing():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        TAX INVOICE
        IRN No.: 1a795d8d41301807788b3d0b9ce6b71755abeb9d9f1c8bb126a648a2f80fa0a3
        Date: 12-02-2026
        External doc. No: PO 1PTR2526000467
        Total Invoice Value: Rs 554600
        """,
        extraction_route="scanned",
        filename="Vendor Bill 2526PSI25087738.pdf",
    )

    assert result["fields"]["vendor_invoice_no"] == "2526PSI25087738"
    assert result["diagnostics"]["vendor_invoice_no_source"] == "filename_fallback"
    assert result["field_metadata"]["vendor_invoice_no"]["source"] == "filename_fallback"


def test_vendor_invoice_filename_fallback_keeps_trade_style_bill_number():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        TAX INVOICE
        Date: 02-01-2026
        PO No: 1POC2526000408
        Invoice Total: 502430.78
        """,
        extraction_route="scanned",
        filename="TRADE - VENDOR BILL -C190224826.pdf",
    )

    assert result["fields"]["vendor_invoice_no"] == "C190224826"


def test_vendor_invoice_filename_fallback_rejects_po_number():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        TAX INVOICE
        Date: 02-01-2026
        Invoice Total: 502430.78
        """,
        extraction_route="scanned",
        filename="Vendor Bill 1PTR2526000467.pdf",
    )

    assert "vendor_invoice_no" not in result["fields"]


def test_vendor_invoice_prefers_rupee_total_over_inflated_ocr_table_artifact():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        TAX INVOICE
        Invoice No.: 2526PSI25087738
        Date: 12-02-2026
        External doc. No: PO 1PTR2526000467
        Taxable Value CGST SGST Total
        3,20,000.00 9 % 28,800.00 9 % 28,800.00 3,77,600.00
        4,70,000.00 42,300.00 42,300.00 5,546,000.00
        Total Invoice Value: Rs 554600
        """,
        extraction_route="scanned",
    )

    assert result["fields"]["invoice_total"] == 554600
    assert result["fields"]["taxable_amount"] == 470000


def test_vendor_invoice_does_not_use_interest_rate_as_invoice_total():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        TAX INVOICE
        Invoice No.: 2526PSI25087738
        Date: 12-02-2026
        External doc. No: PO 1PTR2526000467
        Taxable Value CGST SGST Total
        Total Invoice Value: ***** FIVE LAKH FIFTY FOUR THOUSAND SIX HUNDRED RUPEES
        Terms of payment: Interest @ 36 % Per Annum will be payable.
        Total
        Rate Amount Rate Amount
        9 % 42,300.00 9 % 42,300.00
        000.00 84,000.00 84,000.00 4,70,000.00 4,70,000.00 42,300.00 42,300.00 5,54,600.00
        """,
        extraction_route="scanned",
    )

    assert result["fields"]["invoice_total"] == 554600
    assert result["fields"]["taxable_amount"] == 470000


def test_vendor_invoice_derives_taxable_from_gst_total_components_without_taxable_label():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        TAX INVOICE
        Invoice No.: 2526PSI25087738
        Date: 12-02-2026
        External doc. No: PO 1PTR2526000467
        CGST
        SGST
        Rate Amount Rate Amount
        Total
        000.00 84,000.00 84,000.00 4,70,000.00 4,70,000.00 42,300.00 42,300.00 5,54,600.00
        Total Invoice Value: Rs 554600
        """,
        extraction_route="scanned",
    )

    assert result["fields"]["taxable_amount"] == 470000
    assert result["diagnostics"]["taxable_amount_source"] == "invoice_total_minus_split_gst_components"


def test_customer_po_partial_parse_reports_required_fields_missing_not_empty():
    result = parse_structured_text(
        "CUSTOMER_PO",
        """
        Purchase Order No: PMCH&RI/024/2025-2026
        PO Date: 30/01/2026
        Customer Name: PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE
        """,
        extraction_route="scanned",
    )

    assert result["fields"]["customer_po_no"] == "PMCH&RI/024/2025-2026"
    assert result["diagnostics"]["failure_code"] == FailureCode.REQUIRED_FIELDS_MISSING
    assert result["diagnostics"]["failure_code"] != FailureCode.OCR_EMPTY


def test_empty_scanned_text_reports_ocr_empty():
    result = parse_structured_text("VENDOR_INVOICE", "", extraction_route="scanned")

    assert result["fields"] == {}
    assert result["diagnostics"]["failure_code"] == FailureCode.OCR_EMPTY


def test_model_layer2_disabled_does_not_call_provider():
    diagnostics = {}
    result = extract_structured_fields_with_model(
        "VENDOR_INVOICE",
        "Invoice No: 2526PSI25087738",
        {"vendor_invoice_no": None},
        ["vendor_invoice_no"],
        diagnostics,
    )

    assert result["fields"] == {}
    assert diagnostics["model_layer2_used"] is False


def test_model_layer2_json_validation_rejects_status_decisions():
    payload = validate_model_json(
        '{"document_type": "VENDOR_INVOICE", "extracted_fields": {"vendor_invoice_no": "2526PSI25087738", "bundle_status": "OK"}, "field_evidence": {"vendor_invoice_no": "Invoice No: 2526PSI25087738"}, "missing_required_fields": [], "confidence": 0.8, "bundle_status": "OK", "issues": []}',
        {"vendor_invoice_no": None},
    )

    assert payload["fields"] == {"vendor_invoice_no": "2526PSI25087738"}
    assert "forbidden output fields removed" in payload["diagnostics"]["warnings"][0].lower()
    assert payload["field_metadata"]["vendor_invoice_no"]["source"] == "model_layer2"
    assert payload["field_metadata"]["vendor_invoice_no"]["confidence"] == 0.8


@pytest.mark.parametrize("value", ["SIGNATURE", "&Date", "Customer", "Our Order"])
def test_looks_like_code_rejects_plain_words(value: str):
    assert _looks_like_code(value) is None


@pytest.mark.parametrize(
    "value",
    [
        "1POC2526000408",
        "1PTR2526000400",
        "PMCH&RI/024/2025-2026",
        "1IAM2526000527",
        "1OTM2526001429",
        "333335674",
    ],
)
def test_looks_like_code_keeps_real_codes(value: str):
    assert _looks_like_code(value) == value


@pytest.mark.parametrize("value", ["Our Order", "SKYLARK INFORMATION TECHNOLOGIES PRIVATE LIMITED"])
def test_clean_vendor_name_rejects_labels_and_buyer(value: str):
    assert _clean_vendor_name(value, buyer_name="SKYLARK INFORMATION TECHNOLOGIES PRIVATE LIMITED") is None


@pytest.mark.parametrize(
    "value",
    [
        "SKYLARK INFORMATION TECHNOLOGIES PRIVATE LIMITED",
        "SKYLARK INFORMATION TECHNOLOGIES PVT LTD",
    ],
)
def test_clean_vendor_name_rejects_known_buyer_without_bill_to_label(value: str):
    assert _clean_vendor_name(value) is None


@pytest.mark.parametrize("value", ["Billing Address:", "Delivery Address", "Invoice date", "Due Date: 13-03-2026"])
def test_clean_vendor_name_rejects_address_and_header_labels(value: str):
    assert _clean_vendor_name(value) is None


@pytest.mark.parametrize("value", ["Inflow Technologies Private Limited", "Redington (India) Limited"])
def test_clean_vendor_name_keeps_real_sellers(value: str):
    assert _clean_vendor_name(value, buyer_name="SKYLARK INFORMATION TECHNOLOGIES PRIVATE LIMITED") == value


def test_customer_po_rejects_signature_as_po_number():
    result = parse_structured_text(
        "CUSTOMER_PO",
        """
        Purchase Order No
        SIGNATURE
        Grand Total: 503137
        """,
        extraction_route="digital",
    )

    assert "customer_po_no" not in result["fields"]
    assert "customer_po_no" in result["missing_required_fields"]


def test_vendor_invoice_rejects_label_words_as_reference_and_vendor_name():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        TAX INVOICE
        Invoice
        Our Order
        Invoice date
        Your Ref.
        Customer
        GST NO
        SHIP-TO:
        SKYLARK INFORMATION TECHNOLOGIES PVT LTD
        Invoice Total: 502430.78
        """,
        extraction_route="digital",
    )

    assert "po_reference" not in result["fields"]
    assert "customer_ref_no" not in result["fields"]
    assert "vendor_name" not in result["fields"]


def test_vendor_invoice_rejects_external_doc_label_value():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        TAX INVOICE
        Invoice No: C190224826
        External Doc No
        &Date
        Invoice Total: 502430.78
        """,
        extraction_route="digital",
    )

    assert "external_doc_no" not in result["fields"]


def test_vendor_invoice_rejects_buyer_as_vendor_name():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        TAX INVOICE
        Vendor Name: SKYLARK INFORMATION TECHNOLOGIES PRIVATE LIMITED
        Bill To: SKYLARK INFORMATION TECHNOLOGIES PRIVATE LIMITED
        Invoice No: INV12345
        PO No: 1PTR2526000400
        Invoice Total: 1000
        """,
        extraction_route="digital",
    )

    assert "vendor_name" not in result["fields"]


def test_vendor_invoice_missing_vendor_name_does_not_fail_minimum_extraction():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        Tax Invoice No: 2526PSI25087738
        Invoice Date: 12-02-2026
        Your Ref.: 1PTR2526000467
        Invoice Total
        554600.00
        """,
        extraction_route="ocr",
    )

    assert result["fields"]["vendor_invoice_no"] == "2526PSI25087738"
    assert result["fields"]["vendor_invoice_date"] == "12-02-2026"
    assert result["fields"]["po_reference"] == "1PTR2526000467"
    assert result["fields"]["invoice_total"] == 554600
    assert "vendor_name" not in result["fields"]
    assert result["diagnostics"]["failure_code"] is None


def test_vendor_invoice_keeps_inflow_reference_and_vendor_fields():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        TAX INVOICE
        Inflow Technologies Private Limited
        Invoice No: 333335674
        Invoice Date: 02-01-2026
        Your Ref.
        : 1POC2526000408
        Invoice Total: 463365.55
        """,
        extraction_route="digital",
    )

    assert result["fields"]["vendor_invoice_no"] == "333335674"
    assert result["fields"]["po_reference"] == "1POC2526000408"
    assert result["fields"]["vendor_name"] == "Inflow Technologies Private Limited"
    assert result["fields"]["invoice_total"] == 463365.55


# ---------------------------------------------------------------------------
# Phase 1i: Fallback extraction safety and provenance
# ---------------------------------------------------------------------------

def test_vendor_invoice_uuid_prefixed_storage_filename_does_not_contaminate():
    uuid_prefixed = "c5638bf9-161e-4cf7-88ac-47f11cf258bb_Vendor Bill 2526PSI25087738.pdf"
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        TAX INVOICE
        Total Invoice Value: Rs 554600
        Taxable Value 4,70,000.00
        """,
        extraction_route="scanned",
        filename=uuid_prefixed,
    )
    inv_no = result["fields"].get("vendor_invoice_no")
    assert inv_no == "2526PSI25087738", (
        f"UUID prefix contaminated invoice number: got {inv_no!r}"
    )


def test_vendor_invoice_ocr_value_beats_filename_fallback_when_both_present():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        TAX INVOICE
        Invoice No.: 9999XYZ12345
        Total Invoice Value: Rs 554600
        """,
        extraction_route="scanned",
        filename="Vendor Bill DIFFERENT99999.pdf",
    )
    assert result["fields"]["vendor_invoice_no"] == "9999XYZ12345"
    assert result["field_metadata"]["vendor_invoice_no"]["source"] == "rules"


def test_vendor_invoice_po_reference_not_extracted_from_filename():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        TAX INVOICE
        Invoice No.: 2526PSI25087738
        Total Invoice Value: Rs 554600
        """,
        extraction_route="scanned",
        filename="Vendor Bill 1PTR2526000467.pdf",
    )
    assert result["fields"].get("po_reference") is None


def test_vendor_invoice_po_reference_not_injected_from_context():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        TAX INVOICE
        Invoice No.: 2526PSI25087738
        Total Invoice Value: Rs 554600
        """,
        extraction_route="scanned",
        context={"po_reference": "1PTR2526999999"},
    )
    assert result["fields"].get("po_reference") is None


def test_vendor_invoice_generic_filename_does_not_fire_fallback():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        TAX INVOICE
        Total Invoice Value: Rs 554600
        """,
        extraction_route="scanned",
        filename="Vendor Invoice.pdf",
    )
    assert result["fields"].get("vendor_invoice_no") is None


# ---------------------------------------------------------------------------
# Phase 1j: Improved vendor invoice header-field extraction
# ---------------------------------------------------------------------------


def test_vendor_invoice_extracts_invoice_no_from_inv_no_label():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        "TAX INVOICE\nInv No: 2526PSI25087738\nInvoice Date: 12-02-2026\nTotal: 554600\n",
        extraction_route="scanned",
        filename="scan.pdf",
    )
    assert result["fields"].get("vendor_invoice_no") == "2526PSI25087738"
    assert result["field_metadata"]["vendor_invoice_no"]["source"] == "rules"


def test_vendor_invoice_extracts_invoice_no_from_nearby_line():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        "TAX INVOICE\nInvoice No\n2526PSI25087738\nInvoice Date: 12-02-2026\nTotal: 554600\n",
        extraction_route="scanned",
        filename="scan.pdf",
    )
    assert result["fields"].get("vendor_invoice_no") == "2526PSI25087738"
    assert result["field_metadata"]["vendor_invoice_no"]["source"] == "rules"


def test_vendor_invoice_extracts_invoice_no_from_two_column_header():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        "Invoice No.        Invoice Date\n2526PSI25087738    12-02-2026\nTotal Invoice Value: Rs 554600\n",
        extraction_route="scanned",
        filename="scan.pdf",
    )
    assert result["fields"].get("vendor_invoice_no") == "2526PSI25087738"
    assert result["field_metadata"]["vendor_invoice_no"]["source"] == "rules"


def test_vendor_invoice_extracts_date_from_invoice_dt_label():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        "TAX INVOICE\nInvoice No: RED/001\nInvoice Dt: 12-02-2026\nTotal: 554600\n",
        extraction_route="scanned",
        filename="scan.pdf",
    )
    assert result["fields"].get("vendor_invoice_date") == "12-02-2026"


def test_vendor_invoice_extracts_po_from_buyer_order_no_label():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        "TAX INVOICE\nInvoice No: RED/001\nBuyer Order No: 1PTR2526000467\nTotal: 554600\n",
        extraction_route="scanned",
        filename="scan.pdf",
    )
    assert result["fields"].get("po_reference") == "1PTR2526000467"


def test_vendor_invoice_extracts_po_from_po_number_label():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        "TAX INVOICE\nInvoice No: RED/001\nPO Number: 1PTR2526000467\nTotal: 554600\n",
        extraction_route="scanned",
        filename="scan.pdf",
    )
    assert result["fields"].get("po_reference") == "1PTR2526000467"


def test_vendor_invoice_inv_no_label_beats_filename_fallback():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        "TAX INVOICE\nInv No: RED/2025/12345\nTotal Invoice Value: Rs 100000\n",
        extraction_route="scanned",
        filename="Vendor Bill FALLBACK00001.pdf",
    )
    assert result["fields"].get("vendor_invoice_no") == "RED/2025/12345"
    assert result["field_metadata"]["vendor_invoice_no"]["source"] == "rules"


def test_vendor_invoice_missing_inv_no_with_generic_filename_remains_missing():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        "TAX INVOICE\nTotal Invoice Value: Rs 100000\n",
        extraction_route="scanned",
        filename="Vendor Invoice Document.pdf",
    )
    assert result["fields"].get("vendor_invoice_no") is None
