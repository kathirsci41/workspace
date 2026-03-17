"""
Unit tests for field_validator.py — all OCR correction functions
and the validate_extracted_fields entrypoint.

Covers:
  - fix_invoice_number   (RC2: I vs 1 confusion)
  - fix_dc_number        (RC2: D/0/N/T transposition)
  - fix_so_number        (RC2: O vs 0 confusion)
  - fix_po_reference     (RC4: person name / date rejection, label stripping)
  - fix_purchase_bill_no (1PBTR prefix fixes)
  - fix_company_po_number (1PTR/1PFR confusion)
  - normalize_amount     (currency symbols, Indian comma format)
  - validate_extracted_fields (entrypoint: applies all fixes, attaches _validation)
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))

import pytest
from app.services.extraction.field_validator import (
    fix_invoice_number,
    fix_dc_number,
    fix_so_number,
    fix_po_reference,
    fix_purchase_bill_no,
    fix_company_po_number,
    normalize_amount,
    validate_extracted_fields,
)


# ── fix_invoice_number ───────────────────────────────────────────────────────

class TestFixInvoiceNumber:

    def test_11tr_fixed(self):
        assert fix_invoice_number("11TR2526001841") == "1ITR2526001841"

    def test_11sr_fixed(self):
        assert fix_invoice_number("11SR2526000166") == "1ISR2526000166"

    def test_it1r_fixed(self):
        assert fix_invoice_number("IT1R2526001234") == "1ITR2526001234"

    def test_it1_digit_r_dropped(self):
        assert fix_invoice_number("IT12526001748") == "1ITR2526001748"

    def test_lowercase_l_itr_fixed(self):
        assert fix_invoice_number("lITR2526001234") == "1ITR2526001234"

    def test_lowercase_l_isr_fixed(self):
        assert fix_invoice_number("lISR2526000166") == "1ISR2526000166"

    def test_label_colon_stripped(self):
        result = fix_invoice_number("C: 240847449")
        assert result == "C240847449"

    def test_valid_value_unchanged(self):
        assert fix_invoice_number("1ITR2526001841") == "1ITR2526001841"

    def test_none_returns_none(self):
        assert fix_invoice_number(None) is None

    def test_empty_string_returns_empty(self):
        assert fix_invoice_number("") == ""


# ── fix_dc_number ────────────────────────────────────────────────────────────

class TestFixDcNumber:

    def test_lowercase_l_fixed(self):
        assert fix_dc_number("lDNT2526DC2865") == "1DNT2526DC2865"

    def test_10tn_transposition_fixed(self):
        assert fix_dc_number("10TN2528DC2865") == "1DNT2528DC2865"

    def test_10nt_fixed(self):
        assert fix_dc_number("10NT2526DC2626") == "1DNT2526DC2626"

    def test_10n7_t_as_7_fixed(self):
        assert fix_dc_number("10N72526DC2626") == "1DNT2526DC2626"

    def test_valid_value_unchanged(self):
        assert fix_dc_number("1DNT2526DC2865") == "1DNT2526DC2865"

    def test_none_returns_none(self):
        assert fix_dc_number(None) is None


# ── fix_so_number ────────────────────────────────────────────────────────────

class TestFixSoNumber:

    def test_10tm_fixed(self):
        assert fix_so_number("10TM2526001596") == "1OTM2526001596"

    def test_1otmz_spurious_z_removed(self):
        assert fix_so_number("1OTMZ2526001596") == "1OTM2526001596"

    def test_valid_value_unchanged(self):
        assert fix_so_number("1OTM2526001596") == "1OTM2526001596"

    def test_none_returns_none(self):
        assert fix_so_number(None) is None

    def test_whitespace_stripped(self):
        assert fix_so_number("  1OTM2526001596  ") == "1OTM2526001596"


# ── fix_po_reference ─────────────────────────────────────────────────────────

class TestFixPoReference:

    def test_label_colon_stripped(self):
        assert fix_po_reference("Our Order: 502812554") == "502812554"

    def test_your_ref_stripped(self):
        assert fix_po_reference("Your Ref: PO-123") == "PO-123"

    def test_fy_notation_restored(self):
        result = fix_po_reference("BHAS-PO-IT-2025-06-022")
        assert "2025/26" in result

    def test_date_string_rejected(self):
        assert fix_po_reference("30/01/2026") is None

    def test_iso_date_rejected(self):
        assert fix_po_reference("2026-01-30") is None

    def test_person_name_rejected(self):
        assert fix_po_reference("Rajesh Kumar") is None

    def test_valid_po_number_unchanged(self):
        assert fix_po_reference("IGKPO/106399/2526") == "IGKPO/106399/2526"

    def test_numeric_po_number_kept(self):
        assert fix_po_reference("1PTR2526000405") == "1PTR2526000405"

    def test_none_returns_none(self):
        assert fix_po_reference(None) is None


# ── fix_purchase_bill_no ─────────────────────────────────────────────────────

class TestFixPurchaseBillNo:

    def test_spurious_2_removed(self):
        assert fix_purchase_bill_no("1PBT2R252600529") == "1PBTR252600529"

    def test_missing_b_restored(self):
        assert fix_purchase_bill_no("1PTR2526000483") == "1PBTR2526000483"

    def test_valid_value_unchanged(self):
        assert fix_purchase_bill_no("1PBTR252600529") == "1PBTR252600529"

    def test_none_returns_none(self):
        assert fix_purchase_bill_no(None) is None


# ── fix_company_po_number ────────────────────────────────────────────────────

class TestFixCompanyPoNumber:

    def test_pfr_fixed_to_ptr(self):
        assert fix_company_po_number("1PFR2526000405") == "1PTR2526000405"

    def test_valid_ptr_unchanged(self):
        assert fix_company_po_number("1PTR2526000405") == "1PTR2526000405"

    def test_none_returns_none(self):
        assert fix_company_po_number(None) is None


# ── normalize_amount ─────────────────────────────────────────────────────────

class TestNormalizeAmount:

    def test_rupee_symbol_stripped(self):
        assert normalize_amount("₹ 97,500.00") == 97500.0

    def test_indian_comma_format(self):
        assert normalize_amount("1,77,000") == 177000.0

    def test_international_comma(self):
        assert normalize_amount("10,000.50") == 10000.5

    def test_numeric_int(self):
        assert normalize_amount(86678) == 86678.0

    def test_numeric_float(self):
        assert normalize_amount(86678.5) == 86678.5

    def test_none_returns_none(self):
        assert normalize_amount(None) is None

    def test_non_numeric_string_returns_none(self):
        assert normalize_amount("N/A") is None

    def test_dollar_symbol_stripped(self):
        assert normalize_amount("$1,000.00") == 1000.0

    def test_zero_string(self):
        assert normalize_amount("0") == 0.0


# ── validate_extracted_fields ────────────────────────────────────────────────

class TestValidateExtractedFields:

    def test_empty_dict_returns_empty(self):
        assert validate_extracted_fields({}, "CUSTOMER_PO") == {}

    def test_invoice_number_corrected(self):
        result = validate_extracted_fields(
            {"invoice_number": "11TR2526001841"}, "VENDOR_INVOICE"
        )
        assert result["invoice_number"] == "1ITR2526001841"
        assert result["_validation"]["invoice_number"] == "CORRECTED"

    def test_dc_number_corrected(self):
        result = validate_extracted_fields(
            {"dc_number": "10TN2526DC2865"}, "VENDOR_DC"
        )
        assert result["dc_number"] == "1DNT2526DC2865"
        assert result["_validation"]["dc_number"] == "CORRECTED"

    def test_so_number_corrected(self):
        result = validate_extracted_fields(
            {"so_number": "10TM2526001596"}, "COMPANY_DC"
        )
        assert result["so_number"] == "1OTM2526001596"
        assert result["_validation"]["so_number"] == "CORRECTED"

    def test_amount_normalized(self):
        result = validate_extracted_fields(
            {"total_amount": "₹ 50,000.00"}, "VENDOR_INVOICE"
        )
        assert result["total_amount"] == 50000.0

    def test_po_reference_date_rejected(self):
        result = validate_extracted_fields(
            {"po_reference": "30/01/2026"}, "CUSTOMER_PO"
        )
        assert result["po_reference"] is None
        assert result["_validation"]["po_reference"] == "REJECTED_PERSON_NAME"

    def test_purchase_bill_no_fixed_for_company_po(self):
        result = validate_extracted_fields(
            {"purchase_bill_no": "1PBT2R252600529"}, "COMPANY_PO"
        )
        assert result["purchase_bill_no"] == "1PBTR252600529"

    def test_purchase_bill_no_not_fixed_for_other_doc_types(self):
        """purchase_bill_no fix only runs for COMPANY_PO."""
        result = validate_extracted_fields(
            {"purchase_bill_no": "1PBT2R252600529"}, "VENDOR_INVOICE"
        )
        assert result["purchase_bill_no"] == "1PBT2R252600529"

    def test_valid_fields_no_validation_key(self):
        """If nothing was corrected, _validation key should NOT appear."""
        result = validate_extracted_fields(
            {"invoice_number": "1ITR2526001841"}, "VENDOR_INVOICE"
        )
        assert "_validation" not in result

    def test_low_confidence_flagged(self):
        """A field that doesn't match its pattern gets LOW_CONFIDENCE."""
        result = validate_extracted_fields(
            {"dc_number": "INVALID-DC-123"}, "VENDOR_DC"
        )
        assert result["_validation"]["dc_number"] == "LOW_CONFIDENCE"
