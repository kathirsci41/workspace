from app.services.extraction.structured_text_parser import parse_structured_text


def test_trade_customer_po_extracts_footer_po_reference_date_and_customer_name():
    result = parse_structured_text(
        "CUSTOMER_PO",
        """
        Order No
        SIGNATURE
        Purchase Order
        SKYLARK INFORMATION TECHNOLOGIES PRIVATE LIMITED
        As per your quotation dated 20.03.2025, we are pleased to place order.
        Grand Total
        503137.00
        location wise Separate Invoice required.
        SHRIRAM FINANCE LIMITED
        Admin Office :- 6th Floor(level 2), Building No. Q2, Aurum Q Parc
        Registered Office :- 14A, South Phase, Industrial Estate, Guindy
        website :- www.shriramfinance.in | Corporate Identity Number ( CIN ) :- L65191TN1979PLC007874
        PWFA251127016
        27 November 2025
        Original Tax Invoice to be submitted at SHRIRAM FINANCE LIMITED., Ghansoli office to the undersigned,
        Tax Invoice to be raised as under:
        SHRIRAM FINANCE LIMITED
        """,
        extraction_route="digital",
    )

    assert result["fields"]["customer_po_no"] == "PWFA251127016"
    assert result["fields"]["customer_po_date"] == "27 November 2025"
    assert result["fields"]["customer_name"] == "SHRIRAM FINANCE LIMITED"
    assert result["fields"]["grand_total"] == 503137
    assert result["diagnostics"]["failure_code"] is None


def test_trade_company_invoice_extracts_alpha_customer_order_reference():
    result = parse_structured_text(
        "COMPANY_INVOICE",
        """
        Invoice No.
        Invoice Date
        Customer Order No.
        Customer Order Date
        SO No.
        Acct Manager
        1ITR2526001785
        17/01/2026
        PWFA251127016
        27/11/2025
        1OTM2526001429
        Total
        593701.66
        503137.00
        90564.66
        Tax Total :
        90564.66
        """,
        extraction_route="digital",
    )

    assert result["fields"]["invoice_no"] == "1ITR2526001785"
    assert result["fields"]["customer_order_no"] == "PWFA251127016"
    assert result["fields"]["so_no"] == "1OTM2526001429"


def test_trade_company_dc_extracts_customer_order_ref_without_hsn_as_amount():
    result = parse_structured_text(
        "COMPANY_DC",
        """
        Sales Order No.
        1OTM2526001429
        Customer Order No.
        PWFA251127016
        DC No.
        1DNT2526DC2915
        DC Date
        17/01/2026
        SNo.
        Product Description
        Qty.
        Unit Rate
        Est. Amount
        UOM
        HSN/SAC Code
        SKU
        Serial
        Warehouse
        Dispatch
        Receiver
        Batch
        Model
        Brand
        Tax Category
        Remarks
        1.000
        NM
        FG-120G
        851769
        1
        4.000
        Total
        """,
        extraction_route="digital",
    )

    assert result["fields"]["dc_no"] == "1DNT2526DC2915"
    assert result["fields"]["customer_order_no"] == "PWFA251127016"
    assert result["fields"]["so_no"] == "1OTM2526001429"
    assert "estimated_amount" not in result["fields"]
    assert "total_amount" not in result["fields"]


def test_trade_company_dc_keeps_clear_estimated_amount_total():
    result = parse_structured_text(
        "COMPANY_DC",
        """
        Sales Order No.
        1OTM2526001611
        Customer Order No.
        PMCH&RI/024/2025-2026
        DC No.
        1DNT2526DC3100
        DC Date
        13/02/2026
        Est. Amount
        UOM
        HSN/SAC Code
        1.000
        518000.00
        518000.00
        NM
        997331
        518000.00
        518000.00
        7.000
        Total
        """,
        extraction_route="digital",
    )

    assert result["fields"]["estimated_amount"] == 518000
    assert result["fields"]["total_quantity"] == 7


def test_company_dc_keeps_whole_rupee_total_when_supported_by_quantity_context():
    result = parse_structured_text(
        "COMPANY_DC",
        """
        Delivery Challan
        Sales Order No.
        1OTM2526001611
        Customer Order No.
        PMCH&RI/024/2025-2026
        DC No.
        1DNT2526DC3100
        DC Date
        13/02/2026
        Delivery To
        PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE
        741050
        0
        9
        Total
        """,
        extraction_route="digital",
    )

    assert result["fields"]["estimated_amount"] == 741050
    assert result["fields"]["total_quantity"] == 9


def test_trade_vendor_invoice_extracts_redington_header_and_tax_totals():
    result = parse_structured_text(
        "VENDOR_INVOICE",
        """
        REDINGTON LIMITED
        C/O.PROCONNECT SUPPLY CHAIN SOLUTION LTD
        GST : 33AABCR0347P1ZA
        TAX INVOICE
        Invoice
        : C190224826
        Invoice date
        : 12.01.2026
        Your Ref.
        : 1PTR2526000400
        SHIP-TO:
        SKYLARK INFORMATION TECHNOLOGIES PVT LTD
        BILL-TO:
        SKYLARK INFORMATION TECHNOLOGIES PVT LTD
        Remarks
        SHRIRAM TRANSPORT FINANCE CO LTD-MH
        Invoice value in Words: FIVE LAKH TWO THOUSAND FOUR HUNDRED THIRTY RUPEES SEVENTY EIGHT PAISE
        Tax Total
        38,320.99
        38,320.99
        Total before Tax
        425,788.80
        Tax Total
        76,641.98
        Invoice Total
        502,430.78
        The person signing this document agrees to abide by the terms and conditions.
        For REDINGTON Limited
        """,
        extraction_route="digital",
    )

    assert result["fields"]["vendor_invoice_no"] == "C190224826"
    assert result["fields"]["vendor_name"] == "REDINGTON LIMITED"
    assert result["fields"]["po_reference"] == "1PTR2526000400"
    assert result["fields"]["taxable_amount"] == 425788.8
    assert result["fields"]["tax_amount"] == 76641.98
    assert result["fields"]["invoice_total"] == 502430.78
