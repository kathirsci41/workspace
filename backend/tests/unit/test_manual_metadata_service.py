from __future__ import annotations

import pytest

from app.services.extraction.structured_text_parser import parse_structured_text
from app.services.manual_metadata_service import allowed_manual_fields


REPRESENTATIVE_TEXT_BY_TYPE = {
    "CUSTOMER_PO": """
        Purchase Order No: PMCH&RI/024/2025-2026
        PO Date: 30/01/2026
        Customer Name: PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE
        Billing Address: Bill Addr
        Delivery Address: Ship Addr
        Subtotal: 1000
        Tax Amount: 180
        Grand Total: 1180
        Total Quantity: 2
    """,
    "COMPANY_INVOICE": """
        Tax Invoice
        Invoice No. : 1ITR2526001785
        Invoice Date
        12/02/2026
        SO No. : 1OTM2526001429
        PMCH&RI/024/2025-2026
        Customer Name & Detail
        PANIMALAR MEDICAL HOSPITAL
        Nett Amount
        118000
        18000
        100000
    """,
    "COMPANY_DC": """
        Delivery Challan
        1DNT2526DC3100
        SO No
        1OTM2526001429
        PMCH&RI/024/2025-2026
        Delivery To
        PANIMALAR MEDICAL HOSPITAL
        DC Date
        12/02/2026
        1000
        1000
        2
        Total
    """,
    "COMPANY_PO": """
        Purchase Order
        1PTR2526000467
        Order Date
        12/02/2026
        Vendor Name & Address
        Inflow Technologies Private Limited
        ON FULL DELIVERY
        NOT ALLOWED
        Net Amount
        1000
    """,
    "VENDOR_INVOICE": """
        Tax Invoice
        Inflow Technologies Private Limited
        Invoice No: RED/2526/00001
        Invoice Date: 12-02-2026
        PO No: 1PTR2526000467
        External Doc No: 1PTR2526000467
        Subtotal: 100000
        Tax Amount: 18000
        Invoice Total: 118000
        Bill To: SKYLARK INFORMATION TECHNOLOGIES PRIVATE LIMITED
        Ship To: SKYLARK INFORMATION TECHNOLOGIES PRIVATE LIMITED
        GSTIN: 29ABCDE1234F1Z5
        IRN: ABCDEF1234567890
        Ack No: 1234567890
    """,
}


@pytest.mark.parametrize("document_type", sorted(REPRESENTATIVE_TEXT_BY_TYPE))
def test_parser_emitted_fields_are_allowed_for_manual_correction(document_type: str):
    result = parse_structured_text(
        document_type,
        REPRESENTATIVE_TEXT_BY_TYPE[document_type],
        extraction_route="digital",
    )

    emitted = set(result["fields"])
    unsupported = sorted(emitted - allowed_manual_fields(document_type))

    assert emitted
    assert unsupported == []
