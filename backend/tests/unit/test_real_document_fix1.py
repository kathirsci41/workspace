from app.services.export_service import _financial_summary, _main_finding
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


def test_financial_summary_reads_totals_from_billing_check():
    """
    _financial_summary must use check values (canonical), not raw document scan.
    This prevents double-counting when both COMPANY_PO and VENDOR_PO alias docs exist.
    """
    summary = {
        "issues": [],
        "checks": [
            {
                "check_id": "VENDOR_BILLING_COVERAGE",
                "result": "REVIEW_REQUIRED",
                "left_value": 696200,
                "right_value": 554600,
            }
        ],
        "extracted_summary": {},
    }
    fin = _financial_summary(summary)
    assert fin["vendor_po_total"] == 696200
    assert fin["vendor_invoice_total"] == 554600
    assert fin["difference"] == 141600


def test_financial_summary_reads_totals_from_billing_issue():
    """
    When a VENDOR_PARTIAL_BILLING_REVIEW_REQUIRED issue is present, its values
    must take precedence (they come from the verified canonical computation).
    """
    summary = {
        "issues": [
            {
                "code": "VENDOR_PARTIAL_BILLING_REVIEW_REQUIRED",
                "vendor_po_total": 512741.20,
                "vendor_invoice_total": 513376.98,
                "difference": -635.78,
            }
        ],
        "checks": [
            {
                "check_id": "VENDOR_BILLING_COVERAGE",
                "result": "REVIEW_REQUIRED",
                "left_value": 512741.20,
                "right_value": 513376.98,
            }
        ],
        "extracted_summary": {},
    }
    fin = _financial_summary(summary)
    assert fin["vendor_po_total"] == 512741.20
    assert fin["vendor_invoice_total"] == 513376.98
    assert fin["difference"] == -635.78


def test_financial_summary_does_not_double_count_alias_docs():
    """
    When summary has no billing issue, values come from the billing check, not from
    raw document totals — so alias records (COMPANY_PO + VENDOR_PO same file) cannot
    cause doubling.
    """
    summary = {
        "issues": [],
        "checks": [
            {
                "check_id": "VENDOR_BILLING_COVERAGE",
                "result": "PASS",
                "left_value": 512741.20,   # single canonical PO total
                "right_value": 513376.98,
            }
        ],
        "extracted_summary": {},
    }
    fin = _financial_summary(summary)
    # Must be the canonical single value, not doubled
    assert fin["vendor_po_total"] == 512741.20
    assert fin["vendor_po_total"] != 1025482.40, "Vendor PO total was doubled"


# ── _main_finding correctness when issues=[] ─────────────────────────────────

def test_main_finding_not_all_passed_when_billing_check_review_required():
    """
    _main_finding must NOT say 'All checks passed' when billing check is REVIEW_REQUIRED,
    even when issues[] is empty.
    """
    summary = {
        "issues": [],
        "checks": [
            {
                "check_id": "VENDOR_BILLING_COVERAGE",
                "result": "REVIEW_REQUIRED",
                "left_value": 512741.20,
                "right_value": 513376.98,
            }
        ],
        "bundle_status": "REVIEW_REQUIRED",
        "vendor_procurement_status": "REVIEW_REQUIRED",
        "customer_delivery_status": "PASS",
    }
    financial = _financial_summary(summary)
    finding = _main_finding(summary, financial)
    text = finding.lower()
    assert not ("all" in text and "passed" in text), (
        "Main finding must not say 'All checks passed' when billing check is REVIEW_REQUIRED"
    )


def test_main_finding_includes_billing_amounts_when_check_review_required():
    """
    When issues=[] but VENDOR_BILLING_COVERAGE is REVIEW_REQUIRED,
    _main_finding must describe the billing discrepancy with actual amounts.
    """
    summary = {
        "issues": [],
        "checks": [
            {
                "check_id": "VENDOR_BILLING_COVERAGE",
                "result": "REVIEW_REQUIRED",
                "left_value": 512741.20,
                "right_value": 513376.98,
            }
        ],
        "bundle_status": "REVIEW_REQUIRED",
        "customer_delivery_status": "PASS",
        "vendor_procurement_status": "REVIEW_REQUIRED",
    }
    financial = _financial_summary(summary)
    finding = _main_finding(summary, financial)
    assert "512,741" in finding or "513,376" in finding or "513,377" in finding, (
        f"Main finding must include billing amounts, got: {finding!r}"
    )


def test_main_finding_all_passed_only_when_truly_passing():
    """
    _main_finding may only say 'All checks passed' when bundle_status is PASS/OK
    and no check has a non-passing result.
    """
    summary = {
        "issues": [],
        "checks": [
            {
                "check_id": "VENDOR_BILLING_COVERAGE",
                "result": "PASS",
                "left_value": 512741.20,
                "right_value": 512741.20,
            }
        ],
        "bundle_status": "PASS",
        "customer_delivery_status": "PASS",
        "vendor_procurement_status": "PASS",
    }
    financial = _financial_summary(summary)
    finding = _main_finding(summary, financial)
    assert "all" in finding.lower() and "passed" in finding.lower()


# ── _write_review_actions from checks when issues=[] ─────────────────────────

def test_review_actions_generated_from_billing_check_when_no_issues():
    """
    _write_review_actions must produce rows from REVIEW_REQUIRED checks
    when issues[] is empty — not the 'All checks passed' empty-state message.
    """
    from openpyxl import Workbook
    from app.services.export_service import _write_review_actions

    summary = {
        "issues": [],
        "checks": [
            {
                "check_id": "VENDOR_BILLING_COVERAGE",
                "check_name": "Vendor Billing Coverage",
                "result": "REVIEW_REQUIRED",
                "left_value": 512741.20,
                "right_value": 513376.98,
                "message": "Billing mismatch",
            }
        ],
    }
    financial = _financial_summary(summary)
    wb = Workbook()
    ws = wb.active
    _write_review_actions(ws, summary, financial)

    all_values = [cell.value for row in ws.iter_rows() for cell in row if cell.value is not None]
    assert "No review actions required. All checks passed." not in all_values, (
        "Review Actions must not show 'All checks passed' when billing check is REVIEW_REQUIRED"
    )
    assert any(
        "procurement" in str(v).lower() or "finance" in str(v).lower()
        for v in all_values
    ), f"Expected procurement/finance team in review actions, got: {all_values}"
