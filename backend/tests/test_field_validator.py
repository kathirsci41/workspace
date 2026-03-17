"""Unit tests for the field_validator module (RC2/RC4 fixes, amount normalization)."""
import pytest
from app.services.extraction.field_validator import (
    fix_invoice_number,
    fix_dc_number,
    fix_po_reference,
    normalize_amount,
    validate_extracted_fields,
    PATTERNS,
)


# ---------------------------------------------------------------------------
# fix_invoice_number — RC2: I vs 1 confusion
# ---------------------------------------------------------------------------
class TestFixInvoiceNumber:
    def test_11TR_to_1ITR(self):
        assert fix_invoice_number("11TR2526001841") == "1ITR2526001841"

    def test_11SR_to_1ISR(self):
        assert fix_invoice_number("11SR2526000166") == "1ISR2526000166"

    def test_lowercase_l_ITR(self):
        assert fix_invoice_number("lITR2526001841") == "1ITR2526001841"

    def test_lowercase_l_ISR(self):
        assert fix_invoice_number("lISR2526000166") == "1ISR2526000166"

    def test_correct_value_unchanged(self):
        assert fix_invoice_number("1ITR2526001841") == "1ITR2526001841"

    def test_correct_ISR_unchanged(self):
        assert fix_invoice_number("1ISR2526000166") == "1ISR2526000166"

    def test_none_returns_none(self):
        assert fix_invoice_number(None) is None

    def test_empty_returns_empty(self):
        assert fix_invoice_number("") == ""

    def test_unrelated_value_unchanged(self):
        assert fix_invoice_number("INV-12345") == "INV-12345"

    def test_whitespace_stripped(self):
        assert fix_invoice_number("  11TR2526001841  ") == "1ITR2526001841"


# ---------------------------------------------------------------------------
# fix_dc_number — RC2: I vs 1 confusion in DC prefix
# ---------------------------------------------------------------------------
class TestFixDcNumber:
    def test_lDNT_to_1DNT(self):
        assert fix_dc_number("lDNT2526DC001841") == "1DNT2526DC001841"

    def test_correct_1DNT_unchanged(self):
        assert fix_dc_number("1DNT2526DC001841") == "1DNT2526DC001841"

    def test_none_returns_none(self):
        assert fix_dc_number(None) is None

    def test_empty_returns_empty(self):
        assert fix_dc_number("") == ""

    def test_unrelated_value_unchanged(self):
        assert fix_dc_number("DC-12345") == "DC-12345"


# ---------------------------------------------------------------------------
# fix_po_reference — RC4: person name rejection
# ---------------------------------------------------------------------------
class TestFixPoReference:
    def test_person_name_rejected(self):
        assert fix_po_reference("Rajesh Kumar") is None

    def test_multi_word_name_rejected(self):
        assert fix_po_reference("John Michael Smith") is None

    def test_po_number_with_digits_preserved(self):
        assert fix_po_reference("PO-12345") == "PO-12345"

    def test_po_number_alphanumeric_preserved(self):
        assert fix_po_reference("4500123456") == "4500123456"

    def test_mixed_spaces_and_digits_preserved(self):
        assert fix_po_reference("PO 12345 REV2") == "PO 12345 REV2"

    def test_single_word_preserved(self):
        """Single word without spaces is not flagged as person name."""
        assert fix_po_reference("Rajesh") == "Rajesh"

    def test_none_returns_none(self):
        assert fix_po_reference(None) is None

    def test_empty_returns_empty(self):
        assert fix_po_reference("") == ""


# ---------------------------------------------------------------------------
# normalize_amount
# ---------------------------------------------------------------------------
class TestNormalizeAmount:
    def test_currency_symbol_stripped(self):
        assert normalize_amount("₹ 97,500.00") == 97500.0

    def test_dollar_sign_stripped(self):
        assert normalize_amount("$1,200.50") == 1200.5

    def test_indian_comma_format(self):
        assert normalize_amount("1,77,000") == 177000.0

    def test_plain_float(self):
        assert normalize_amount("86678.5") == 86678.5

    def test_already_numeric_int(self):
        assert normalize_amount(1500) == 1500.0

    def test_already_numeric_float(self):
        assert normalize_amount(1500.75) == 1500.75

    def test_none_returns_none(self):
        assert normalize_amount(None) is None

    def test_garbage_returns_none(self):
        assert normalize_amount("not a number") is None

    def test_empty_string_returns_none(self):
        assert normalize_amount("") is None

    def test_euro_symbol_stripped(self):
        assert normalize_amount("€ 2,500.00") == 2500.0

    def test_whitespace_only_returns_none(self):
        assert normalize_amount("   ") is None


# ---------------------------------------------------------------------------
# PATTERNS — regex patterns for known formats
# ---------------------------------------------------------------------------
class TestPatterns:
    def test_dc_number_pattern_matches(self):
        assert PATTERNS["dc_number"].search("1DNT2526DC001841")

    def test_dc_number_pattern_rejects_bad(self):
        assert not PATTERNS["dc_number"].search("XDNT0000")



# ---------------------------------------------------------------------------
# validate_extracted_fields — end-to-end
# ---------------------------------------------------------------------------
class TestValidateExtractedFields:
    def test_empty_returns_empty(self):
        assert validate_extracted_fields({}, "COMPANY_DC") == {}

    def test_none_returns_empty(self):
        assert validate_extracted_fields(None, "COMPANY_DC") == {}

    def test_invoice_corrected_and_flagged(self):
        fields = {"invoice_number": "11TR2526001841", "total_amount": 1500}
        result = validate_extracted_fields(fields, "VENDOR_INVOICE")
        assert result["invoice_number"] == "1ITR2526001841"
        assert result["_validation"]["invoice_number"] == "CORRECTED"

    def test_dc_corrected_and_flagged(self):
        fields = {"dc_number": "lDNT2526DC001841"}
        result = validate_extracted_fields(fields, "COMPANY_DC")
        assert result["dc_number"] == "1DNT2526DC001841"
        assert result["_validation"]["dc_number"] == "CORRECTED"

    def test_po_reference_person_name_rejected(self):
        fields = {"po_reference": "Rajesh Kumar"}
        result = validate_extracted_fields(fields, "VENDOR_DC")
        assert result["po_reference"] is None
        assert result["_validation"]["po_reference"] == "REJECTED_PERSON_NAME"
        assert result["_po_reference_rejected"] == "Rajesh Kumar"

    def test_amount_normalized(self):
        fields = {"total_amount": "₹ 97,500.00", "subtotal": "1,77,000"}
        result = validate_extracted_fields(fields, "VENDOR_INVOICE")
        assert result["total_amount"] == 97500.0
        assert result["subtotal"] == 177000.0

    def test_invalid_amount_flagged(self):
        fields = {"total_amount": "not-a-number"}
        result = validate_extracted_fields(fields, "VENDOR_INVOICE")
        assert result["_validation"]["total_amount"] == "AMOUNT_PARSE_FAILED"
        assert result["_total_amount_raw"] == "not-a-number"

    def test_no_validation_key_when_all_clean(self):
        """A clean DC number with valid pattern should have no _validation key."""
        fields = {"dc_number": "1DNT2526DC001841"}
        result = validate_extracted_fields(fields, "COMPANY_DC")
        assert "_validation" not in result

    def test_low_confidence_on_bad_pattern(self):
        """A dc_number that doesn't match the known regex gets LOW_CONFIDENCE."""
        fields = {"dc_number": "DOESNOTMATCH"}
        result = validate_extracted_fields(fields, "COMPANY_DC")
        assert result["_validation"]["dc_number"] == "LOW_CONFIDENCE"

    def test_multiple_fixes_combined(self):
        """Invoice corrected + amount normalized + PO name rejected in one call."""
        fields = {
            "invoice_number": "11TR2526001841",
            "po_reference": "John Doe",
            "total_amount": "$5,000.00",
        }
        result = validate_extracted_fields(fields, "VENDOR_INVOICE")
        assert result["invoice_number"] == "1ITR2526001841"
        assert result["po_reference"] is None
        assert result["total_amount"] == 5000.0
        v = result["_validation"]
        assert "invoice_number" in v
        assert "po_reference" in v
