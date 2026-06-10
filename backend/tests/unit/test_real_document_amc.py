from app.services.extraction.structured_text_parser import parse_structured_text


def test_amc_customer_po_extracts_gst_exempt_subtotal_and_tax():
    result = parse_structured_text(
        "CUSTOMER_PO",
        """
        PURCHASE ORDER
        Order No.
        CHIPL/2025-26/682
        Dated
        01-12-2025
        Invoice To
        Corrohealth Infotech Private Limited
        Sub Total
        4,96,000.00
        GST Exempted
        0.00
        Total
        2
        4,96,000.00
        """,
        extraction_route="digital",
    )

    assert result["fields"]["subtotal_amount"] == 496000
    assert result["fields"]["tax_amount"] == 0
    assert result["fields"]["grand_total"] == 496000


def test_amc_company_invoice_extracts_lut_zero_tax_footer():
    result = parse_structured_text(
        "COMPANY_INVOICE",
        """
        TAX INVOICE
        Invoice No.
        Invoice Date
        Customer Order No.
        Customer Order Date
        SO No.
        1IAM2526000527
        03/01/2026
        CHIPL/2025-26/682
        01/12/2025
        SOSC2526000429
        Customer Name & Detail
        CORROHEALTH INFOTECH PRIVATE LIMITED
        Nett Amount
        Amount
        :
        :
        496000.00
        496000.00
        SUPPLY TO SEZ UNIT UNDER LETTER OF UNDERTAKING WITHOUT PAYMENT OF INTEGRATED TAX
        IGST 0%
        """,
        extraction_route="digital",
    )

    assert result["fields"]["taxable_amount"] == 496000
    assert result["fields"]["tax_amount"] == 0
    assert result["fields"]["net_amount"] == 496000
    assert result["fields"]["total_amount"] == 496000


def test_amc_vendor_invoice_derives_tax_from_explicit_cgst_sgst_basis():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        Inflow Technologies Private Limited
        TAX INVOICE
        Customer Ref No
        1POC2526000408
        Invoice Date
        02-01-2026
        Invoice Number
        333335674
        Taxable Value
        392,682.67
        CGST 9%
        35,341.44
        SGST 9%
        35,341.44
        Invoice Total
        463,365.55
        """,
        extraction_route="digital",
    )

    assert result["fields"]["taxable_amount"] == 392682.67
    assert result["fields"]["tax_amount"] == 70682.88
    assert result["fields"]["invoice_total"] == 463365.55
