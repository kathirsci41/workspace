"""Phase 13B parser regressions for real-document layout variants."""

import app.services.extraction.digital_text_extractor as digital_text_extractor
from app.services.extraction.digital_text_extractor import extract_digital_fields
from app.services.extraction.structured_text_parser import parse_structured_text


def test_so_number_prefers_otm_family_over_invoice():
    lines = ["Invoice No.", "Customer Order No.", "SO No.", "1ITR2526001878", "PMCH&RI/024/2025-2026", "1OTM2526001611"]

    assert digital_text_extractor._so_number_from_lines(lines) == "1OTM2526001611"


def test_so_number_sosc_family():
    lines = ["Invoice No.", "SO No.", "1IAM2526000527", "SOSC2526000429"]

    assert digital_text_extractor._so_number_from_lines(lines) == "SOSC2526000429"


def test_so_number_9otm_family():
    lines = ["Invoice No.", "SO No.", "9STG2526000009", "9OTM2526000011"]

    assert digital_text_extractor._so_number_from_lines(lines) == "9OTM2526000011"


def test_so_number_dc_only_so_present():
    lines = ["Sales Order No.", "1OTM2526001611", "Customer Order No.", "PMCH&RI/024"]

    assert digital_text_extractor._so_number_from_lines(lines) == "1OTM2526001611"


def test_so_number_fallback_when_no_family():
    lines = ["Invoice No.", "1ITR2526001878", "SO No.", "1ABC2526009999"]

    assert digital_text_extractor._so_number_from_lines(lines) == "1ABC2526009999"


def test_so_number_none_when_absent():
    lines = ["Invoice No.", "Date", "01-01-2026"]

    assert digital_text_extractor._so_number_from_lines(lines) is None


def test_company_invoice_so_not_invoice_number():
    text = "Invoice No.\nSO No.\n1ITR2526001878\n1OTM2526001611"

    fields = extract_digital_fields(text, "COMPANY_INVOICE")

    assert fields.get("invoice_number") == "1ITR2526001878"
    assert fields.get("so_number") == "1OTM2526001611"
    assert fields.get("so_number") != fields.get("invoice_number")


def test_company_invoice_invoice_number_prefers_later_invoice_label_over_so_code():
    text = """
    Invoice Order No. & Date: PWFA251127016 & 27/11/2025
    SO No. : 1OTM2526001429
    Invoice Due Date: 16/02/2026
    Invoice No. : 1ITR2526001785
    Customer Order No. & Date: PWFA251127016 & 27/11/2025
    """

    fields = extract_digital_fields(text, "COMPANY_INVOICE")

    assert fields.get("invoice_number") == "1ITR2526001785"
    assert fields.get("so_number") == "1OTM2526001429"
    assert fields.get("invoice_number") != fields.get("so_number")


def test_company_invoice_invoice_number_falls_back_without_so_number():
    fields = extract_digital_fields("Tax Invoice\n1ITR2526001785", "COMPANY_INVOICE")

    assert fields.get("invoice_number") == "1ITR2526001785"


def test_company_invoice_existing_label_first_invoice_stays_unchanged():
    text = "Invoice No. : 1ITR2526001878\nSO No. : 1OTM2526001611"

    fields = extract_digital_fields(text, "COMPANY_INVOICE")

    assert fields.get("invoice_number") == "1ITR2526001878"
    assert fields.get("so_number") == "1OTM2526001611"


def test_company_dc_so_uses_family_when_value_precedes_label():
    text = "Delivery Challan\n1OTM2526001429\nSales Order No."

    fields = extract_digital_fields(text, "COMPANY_DC")

    assert fields.get("so_number") == "1OTM2526001429"


REDINGTON_TEXT = """
REDINGTON LIMITED
C/O.PROCONNECT SUPPLY CHAIN
SOLUTION LTD
NO 79, KILMUDALAMBDU PANPAKKAM
VILLAGE,
GUMMIDIPUNDI
THIRUVALLUR DISTRICT
CHENNAI - 601206
Tamil Nadu
GST : 33AABCR0347P1ZA
Storage Location : 1010
TAX INVOICE
"""


def test_redington_vendor_name_is_redington_limited():
    result = parse_structured_text("VENDOR_INVOICE", REDINGTON_TEXT, extraction_route="digital")

    assert result["fields"].get("vendor_name") == "REDINGTON LIMITED"


def test_redington_vendor_name_not_care_of_line():
    result = parse_structured_text("VENDOR_INVOICE", REDINGTON_TEXT, extraction_route="digital")
    vendor = result["fields"].get("vendor_name", "")

    assert not vendor.startswith("C/O")


def test_vendor_name_no_from_label_in_parser():
    text = "TAX INVOICE\nVendor Co Private Limited\nInvoice No: ABC123\nFrom clause 14 arising from the date\nTotal 50000"

    result = parse_structured_text("VENDOR_INVOICE", text, extraction_route="digital")
    vendor = result["fields"].get("vendor_name", "")

    assert "arising" not in vendor.lower()
    assert "clause" not in vendor.lower()


TECHKNOWLOGIC_SNIPPET = """Tax Invoice
IRN
: e8eadad437309cd411c2acefd9129582103004e69a18927f219adcc45481c633
Ack No.
: 112629303058637
Ack Date
: 3-Mar-26
e-Invoice
Techknowlogic Consultants India Private Limited
Muneesh Legacy
156/1, Domlur Village
GSTIN/UIN: 29AAECT4274A1ZF
Invoice No.
BLR/2025-26/694
Other References
PO NO :9POT2526000007, Date :29/01/2026
Invoice Total
11278.44
"""


def test_techknowlogic_vendor_name_skips_irn_block():
    result = parse_structured_text("VENDOR_INVOICE", TECHKNOWLOGIC_SNIPPET, extraction_route="digital")
    vendor = result["fields"].get("vendor_name", "")

    assert "TECHKNOWLOGIC" in vendor.upper()


def test_techknowlogic_vendor_name_not_ack_no():
    result = parse_structured_text("VENDOR_INVOICE", TECHKNOWLOGIC_SNIPPET, extraction_route="digital")

    assert result["fields"].get("vendor_name") != "Ack No"


def test_techknowlogic_po_reference_from_other_references():
    result = parse_structured_text("VENDOR_INVOICE", TECHKNOWLOGIC_SNIPPET, extraction_route="digital")

    assert result["fields"].get("po_reference") == "9POT2526000007"


def test_other_references_po_beats_misleading_purchase_order_label():
    text = "Purchase Order\nDated\nOther References\nPO NO :9POT2526000008, Date :29/01/2026\nTotal 183825"

    result = parse_structured_text("VENDOR_INVOICE", text, extraction_route="digital")

    assert result["fields"].get("po_reference") == "9POT2526000008"


def test_fix4_amc_count_trap():
    text = "Sub Total\n4,96,000.00\nGST Exempted\n0.00\nPURCHASE ORDER\nTotal\n2\n4,96,000.00"

    result = parse_structured_text("CUSTOMER_PO", text, extraction_route="digital")

    assert result["fields"].get("grand_total") == 496000.0


def test_fix4_skips_count_picks_grand_total():
    text = "Total\n3\n150000.00\nGrand Total\n150000.00"

    result = parse_structured_text("CUSTOMER_PO", text, extraction_route="digital")

    assert result["fields"].get("grand_total") == 150000.0


def test_fix4_subtotal_differs_from_grandtotal():
    text = "Sub Total\n400000.00\nGST\n96000.00\nTotal\n2\n496000.00"

    result = parse_structured_text("CUSTOMER_PO", text, extraction_route="digital")

    assert result["fields"].get("grand_total") == 496000.0


def test_fix4_does_not_overreach_next_section():
    text = "Total\n2\n496000.00\nAmount in words\nNEXT\nBank details\n999999.00"

    result = parse_structured_text("CUSTOMER_PO", text, extraction_route="digital")

    assert result["fields"].get("grand_total") == 496000.0


def test_fix4_legit_small_grand_total_still_found():
    text = "Grand Total\n5000.00"

    result = parse_structured_text("CUSTOMER_PO", text, extraction_route="digital")

    assert result["fields"].get("grand_total") == 5000.0


def test_fix4_vendor_invoice_total_unaffected():
    text = "Item A 38320.99\nItem B 76641.98\nTotal\n114962.97\nInvoice Total\n502430.78"

    result = parse_structured_text("VENDOR_INVOICE", text, extraction_route="digital")

    assert result["fields"].get("invoice_total") == 502430.78


def test_invoice_total_fallback_finds_last_large_decimal():
    text = """
    Description    Qty    Rate    Amount
    Item A         1      10000   10000.00
    Item B         2      5000    10000.00
    Item C         1      25000   25000.00
    Subtotal                      45000.00
    Tax                            8100.00
                                   53100.00
    """

    result = parse_structured_text("VENDOR_INVOICE", text, extraction_route="digital")

    assert result["fields"].get("invoice_total") == 53100.0
    assert result["diagnostics"].get("invoice_total_source") == "fallback_largest"
    assert result["field_metadata"]["invoice_total"]["confidence"] == 0.5
    assert result["confidence"] != 0.5


def test_invoice_total_label_wins_over_fallback():
    text = "Item 1: 5000.00\nItem 2: 3000.00\nInvoice Total\n8000.00"

    result = parse_structured_text("VENDOR_INVOICE", text, extraction_route="digital")

    assert result["fields"].get("invoice_total") == 8000.0
    assert result["diagnostics"].get("invoice_total_source") is None
    assert result["field_metadata"]["invoice_total"]["confidence"] != 0.5
