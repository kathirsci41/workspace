from app.services.extraction.structured_text_parser import _ref_label_po, parse_structured_text


# Legit cases
def test_ref_extracts_real_code():
    assert _ref_label_po("REF: PMCH&RI/024/2025-2026") == "PMCH&RI/024/2025-2026"


def test_ref_spaced_colon():
    assert _ref_label_po("REF : PMCH&RI/024/2025-2026") == "PMCH&RI/024/2025-2026"


def test_ref_long_alphanumeric_code():
    assert _ref_label_po("REF: 1OTM2526001611") == "1OTM2526001611"


# Adversarial - must all return None
def test_ref_does_not_match_inside_reference_word():
    assert _ref_label_po("REFERENCE DOCUMENT ATTACHED") is None


def test_ref_does_not_grab_next_field():
    assert _ref_label_po("REF: \nVendor Name: ACME") is None


def test_ref_rejects_prose_value():
    assert _ref_label_po("REF: INVALID TEXT HERE") is None
    assert _ref_label_po("Your REF: customer signature") is None


def test_ref_rejects_tiny_number():
    assert _ref_label_po("Delivery REF 12") is None


def test_ref_in_prose_no_match():
    assert _ref_label_po("Please REF to clause 5 for terms") is None


# Integration - REF fallback only fires when proper labels absent
def test_proper_label_still_wins():
    text = "Purchase Order No\nPMCH&RI/024/2025-2026\nREF: SOMETHINGELSE/99/2025"
    result = parse_structured_text("CUSTOMER_PO", text, extraction_route="digital")
    assert result["fields"]["customer_po_no"] == "PMCH&RI/024/2025-2026"


def test_ref_used_when_no_other_label():
    text = "REF: PMCH&RI/024/2025-2026"
    result = parse_structured_text("CUSTOMER_PO", text, extraction_route="scanned")
    assert result["fields"]["customer_po_no"] == "PMCH&RI/024/2025-2026"
