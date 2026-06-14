from types import SimpleNamespace

from openpyxl import Workbook

from app.services.export_service import _write_summary
from app.services.extraction.structured_text_parser import parse_structured_text


def test_company_po_summary_extracts_taxable_tax_and_net_amounts():
    result = parse_structured_text(
        "COMPANY_PO",
        """
        PURCHASE ORDER
        Order No.
        : 1PTR2526000467
        Order Date
        30/01/2026
        Amount
        :
        Tax
        :
        Net Amount
        :
        590000.00
        106200.00
        696200.00
        """,
        extraction_route="digital",
    )

    assert result["fields"]["taxable_amount"] == 590000
    assert result["fields"]["tax_amount"] == 106200
    assert result["fields"]["net_amount"] == 696200


def test_company_po_vendor_po_date_alias_from_po_date():
    """Phase 1xI Step 8.1: vendor_po_date should alias po_date so the review UI shows a value."""
    result = parse_structured_text(
        "COMPANY_PO",
        """
        PURCHASE ORDER
        Order No.
        : 1PTR2526000467
        Order Date
        30/01/2026
        """,
        extraction_route="digital",
    )

    assert result["fields"]["po_date"] == "30/01/2026"
    assert result["fields"]["vendor_po_date"] == "30/01/2026"
    assert result["fields"]["vendor_po_no"] == "1PTR2526000467"


def test_vendor_invoice_observed_external_document_po_alias_is_supported():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        TAX INVOICE
        Invoice No.: 2526PSI25087738
        Invoice Date: 12-02-2026
        Vendor Name: SUPREME COMPUTERS INDIA PVT LTD
        External doc. No: PO 1PTR2526000467
        Total Invoice Value: Rs 554600
        """,
        extraction_route="scanned",
    )

    assert result["fields"]["po_reference"] == "1PTR2526000467"


def test_vendor_invoice_taxable_amount_sums_explicit_gst_table_rows():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        Sr. No. Description Disc Total Taxable Value CGST SGST Total
        1 Server 0% 000.00 3,20,000.00 3,20,000.00 9% 28,800.00 9% 28,800.00 3,77,600.00
        2 Cable 900.00 0% 000.00 900.00 900.00 9% 081.00 9% 081.00 1,062.00
        3 Controller 600.00 0% 000.00 60,000.00 60,000.00 9% 5,400.00 9% 5,400.00 70,800.00
        4 Battery 5100.00 0% 000.00 5,100.00 5,100.00 9% 459.00 9% 459.00 6,018.00
        5 Disk 8400.00 0% 000.00 84,000.00 84,000.00 9% 7,560.00 9% 7,560.00 99,120.00
        Total 5,54,600.00
        """,
        extraction_route="scanned",
    )

    assert result["fields"]["taxable_amount"] == 470000
    assert result["diagnostics"]["taxable_amount_source"] == "gst_table_sum"


def test_customer_po_build1_minimum_fields_are_extracted_with_review_not_failed():
    result = parse_structured_text(
        "CUSTOMER_PO",
        """
        Purchase Order No: PMCH&RI/024/2025-2026
        PO Date: 29.01.2026
        Grand Total: 920459.00
        """,
        extraction_route="scanned",
    )

    assert result["diagnostics"]["failure_code"] is None
    assert result["missing_required_fields"] == []


def test_export_summary_falls_back_to_extracted_vendor_document_totals():
    workbook = Workbook()
    documents = [
        SimpleNamespace(
            document_type="COMPANY_PO",
            metadata_record=SimpleNamespace(extracted_data={"net_amount": 696200}),
        ),
        SimpleNamespace(
            document_type="VENDOR_INVOICE",
            metadata_record=SimpleNamespace(extracted_data={"invoice_total": 554600}),
        ),
    ]

    _write_summary(
        workbook.active,
        {"bundle_status": "REVIEW_REQUIRED", "extracted_summary": {}, "issues": []},
        documents,
    )
    rows = {row[0].value: row[1].value for row in workbook.active.iter_rows(max_col=2)}

    assert rows["Vendor PO Total"] == 696200
    assert rows["Vendor Invoice Total"] == 554600
