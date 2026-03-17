"""
Unit tests for invoice_validator.py — math validation, date validation,
amount sanity checks, and the ValidationResult class.

Covers:
  - validate_invoice_math  (math check skipped for non-invoice types)
  - _validate_math         (line items + tax vs total)
  - _validate_date         (future dates, very old dates, unparseable dates)
  - _validate_amount_sanity (negative, zero, very large amounts)
  - ValidationResult       (route transitions: AUTO_APPROVED → PENDING_REVIEW)
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))

import pytest
from datetime import date, timedelta
from app.services.extraction.invoice_validator import (
    validate_invoice_math,
    ValidationResult,
)


# ── ValidationResult state machine ──────────────────────────────────────────

class TestValidationResult:

    def test_default_state_is_approved(self):
        r = ValidationResult()
        assert r.passed is True
        assert r.route == "AUTO_APPROVED"
        assert r.errors == []
        assert r.warnings == []

    def test_add_error_fails_and_routes_to_review(self):
        r = ValidationResult()
        r.add_error("Something wrong")
        assert r.passed is False
        assert r.route == "PENDING_REVIEW"
        assert len(r.errors) == 1

    def test_add_warning_routes_to_review(self):
        r = ValidationResult()
        r.add_warning("Minor issue")
        assert r.passed is True
        assert r.route == "PENDING_REVIEW"
        assert len(r.warnings) == 1

    def test_multiple_errors_accumulate(self):
        r = ValidationResult()
        r.add_error("Error 1")
        r.add_error("Error 2")
        assert len(r.errors) == 2
        assert r.passed is False


# ── Math validation skipped for non-invoice types ────────────────────────────

class TestMathSkippedForNonInvoice:

    @pytest.mark.parametrize("doc_type", [
        "CUSTOMER_PO", "COMPANY_PO", "VENDOR_DC", "COMPANY_DC"
    ])
    def test_no_math_check_for_non_invoice(self, doc_type):
        """Math validation only runs for VENDOR_INVOICE and COMPANY_INVOICE."""
        result = validate_invoice_math(
            {"total_amount": 1000, "line_items": [{"quantity": 99999, "unit_price": 99999}]},
            doc_type,
        )
        assert result.passed is True


# ── Math validation ───────────────────────────────────────────────────────────

class TestMathValidation:

    def test_no_line_items_skips_math(self):
        result = validate_invoice_math(
            {"total_amount": 10000},
            "VENDOR_INVOICE",
        )
        assert result.passed is True

    def test_correct_math_passes(self):
        result = validate_invoice_math(
            {
                "total_amount": 11800,
                "tax_amount": 1800,
                "line_items": [{"quantity": 10, "unit_price": 1000, "discount": 0}],
            },
            "VENDOR_INVOICE",
        )
        assert result.passed is True

    def test_wrong_math_fails(self):
        result = validate_invoice_math(
            {
                "total_amount": 99999,
                "tax_amount": 0,
                "line_items": [{"quantity": 1, "unit_price": 100, "discount": 0}],
            },
            "VENDOR_INVOICE",
        )
        assert result.passed is False
        assert any("mismatch" in e.lower() for e in result.errors)

    def test_missing_total_warns(self):
        result = validate_invoice_math(
            {"line_items": [{"quantity": 1, "unit_price": 100}]},
            "VENDOR_INVOICE",
        )
        assert any("total_amount" in w for w in result.warnings)

    def test_zero_total_warns(self):
        result = validate_invoice_math(
            {
                "total_amount": 0,
                "line_items": [{"quantity": 1, "unit_price": 100}],
            },
            "VENDOR_INVOICE",
        )
        assert any("0" in w for w in result.warnings)


# ── Date validation ───────────────────────────────────────────────────────────

class TestDateValidation:

    def test_valid_today_date_passes(self):
        result = validate_invoice_math(
            {"invoice_date": date.today().strftime("%d/%m/%Y")},
            "VENDOR_INVOICE",
        )
        assert result.passed is True
        assert result.errors == []

    def test_future_date_fails(self):
        future = (date.today() + timedelta(days=30)).strftime("%d/%m/%Y")
        result = validate_invoice_math(
            {"invoice_date": future},
            "VENDOR_INVOICE",
        )
        assert result.passed is False
        assert any("future" in e.lower() for e in result.errors)

    def test_very_old_date_warns(self):
        old_date = "01/01/2010"
        result = validate_invoice_math(
            {"invoice_date": old_date},
            "VENDOR_INVOICE",
        )
        assert any("old" in w.lower() or "years" in w.lower() for w in result.warnings)

    def test_unparseable_date_warns(self):
        result = validate_invoice_math(
            {"invoice_date": "not-a-date"},
            "VENDOR_INVOICE",
        )
        assert any("parsed" in w.lower() or "parse" in w.lower() for w in result.warnings)

    def test_missing_date_passes(self):
        result = validate_invoice_math({}, "VENDOR_INVOICE")
        assert result.passed is True

    def test_po_date_field_validated(self):
        future = (date.today() + timedelta(days=1)).strftime("%d/%m/%Y")
        result = validate_invoice_math(
            {"po_date": future},
            "CUSTOMER_PO",
        )
        assert result.passed is False


# ── Amount sanity ─────────────────────────────────────────────────────────────

class TestAmountSanity:

    def test_negative_amount_fails(self):
        result = validate_invoice_math(
            {"total_amount": -500},
            "VENDOR_INVOICE",
        )
        assert result.passed is False
        assert any("negative" in e.lower() for e in result.errors)

    def test_very_large_amount_warns(self):
        result = validate_invoice_math(
            {"total_amount": 200_000_000},
            "VENDOR_INVOICE",
        )
        assert any("large" in w.lower() for w in result.warnings)

    def test_fractional_amount_warns(self):
        result = validate_invoice_math(
            {"total_amount": 0.5},
            "VENDOR_INVOICE",
        )
        assert any("decimal" in w.lower() or "less than 1" in w.lower() for w in result.warnings)

    def test_normal_amount_passes(self):
        result = validate_invoice_math(
            {"total_amount": 50000},
            "VENDOR_INVOICE",
        )
        assert result.passed is True
        assert result.errors == []

    def test_non_numeric_amount_warns(self):
        result = validate_invoice_math(
            {"total_amount": "N/A"},
            "VENDOR_INVOICE",
        )
        assert any("numeric" in w.lower() or "not numeric" in w.lower() for w in result.warnings)
