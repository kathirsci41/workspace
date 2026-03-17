"""
Unit tests for SO Number Cross-Document Validator.

Business rules:
  - Only COMPANY_DC and COMPANY_INVOICE are validated.
  - If PO has no SO number → block with "not set" error.
  - If extracted SO does not match PO SO → block with mismatch error.
  - Matching is normalized (strip, uppercase, remove spaces/dashes/slashes).
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))

import pytest
from app.services.extraction.so_validator import validate_so_number


# ── Doc types that are NOT validated ─────────────────────────────────────────

class TestSkippedDocTypes:

    @pytest.mark.parametrize("doc_type", [
        "CUSTOMER_PO", "COMPANY_PO", "VENDOR_DC", "VENDOR_INVOICE"
    ])
    def test_non_so_doc_types_always_pass(self, doc_type):
        errors = validate_so_number(
            extracted_data={"so_number": "MISMATCH-999"},
            doc_type=doc_type,
            po_so_number="1OTM2526001234",
        )
        assert errors == []

    @pytest.mark.parametrize("doc_type", [
        "CUSTOMER_PO", "COMPANY_PO", "VENDOR_DC", "VENDOR_INVOICE"
    ])
    def test_non_so_doc_types_pass_even_with_no_po_so(self, doc_type):
        errors = validate_so_number(
            extracted_data={},
            doc_type=doc_type,
            po_so_number=None,
        )
        assert errors == []


# ── Case 1: PO has no SO number set ──────────────────────────────────────────

class TestNoSoOnPo:

    @pytest.mark.parametrize("doc_type", ["COMPANY_DC", "COMPANY_INVOICE"])
    def test_blocks_when_po_has_no_so(self, doc_type):
        errors = validate_so_number(
            extracted_data={"so_number": "1OTM2526001234"},
            doc_type=doc_type,
            po_so_number=None,
        )
        assert len(errors) == 1
        assert "not set" in errors[0].lower()

    @pytest.mark.parametrize("doc_type", ["COMPANY_DC", "COMPANY_INVOICE"])
    def test_blocks_when_po_has_empty_so(self, doc_type):
        errors = validate_so_number(
            extracted_data={"so_number": "1OTM2526001234"},
            doc_type=doc_type,
            po_so_number="",
        )
        assert len(errors) == 1
        assert "not set" in errors[0].lower()


# ── Case 2: Matching SO numbers ───────────────────────────────────────────────

class TestMatchingSo:

    @pytest.mark.parametrize("doc_type", ["COMPANY_DC", "COMPANY_INVOICE"])
    def test_exact_match_passes(self, doc_type):
        errors = validate_so_number(
            extracted_data={"so_number": "1OTM2526001234"},
            doc_type=doc_type,
            po_so_number="1OTM2526001234",
        )
        assert errors == []

    def test_case_insensitive_match(self):
        errors = validate_so_number(
            extracted_data={"so_number": "1otm2526001234"},
            doc_type="COMPANY_DC",
            po_so_number="1OTM2526001234",
        )
        assert errors == []

    def test_whitespace_normalized(self):
        errors = validate_so_number(
            extracted_data={"so_number": "  1OTM2526001234  "},
            doc_type="COMPANY_DC",
            po_so_number="1OTM2526001234",
        )
        assert errors == []

    def test_dash_normalized(self):
        errors = validate_so_number(
            extracted_data={"so_number": "1OTM-2526-001234"},
            doc_type="COMPANY_DC",
            po_so_number="1OTM2526001234",
        )
        assert errors == []

    def test_slash_normalized(self):
        errors = validate_so_number(
            extracted_data={"so_number": "1OTM/2526/001234"},
            doc_type="COMPANY_DC",
            po_so_number="1OTM2526001234",
        )
        assert errors == []

    def test_sales_order_no_field_used(self):
        """Fallback to sales_order_no when so_number is absent."""
        errors = validate_so_number(
            extracted_data={"sales_order_no": "1OTM2526001234"},
            doc_type="COMPANY_DC",
            po_so_number="1OTM2526001234",
        )
        assert errors == []


# ── Case 3: Mismatched SO numbers ─────────────────────────────────────────────

class TestMismatchedSo:

    @pytest.mark.parametrize("doc_type", ["COMPANY_DC", "COMPANY_INVOICE"])
    def test_mismatch_returns_error(self, doc_type):
        errors = validate_so_number(
            extracted_data={"so_number": "1OTM2526009999"},
            doc_type=doc_type,
            po_so_number="1OTM2526001234",
        )
        assert len(errors) == 1
        assert "mismatch" in errors[0].lower()
        assert "1OTM2526001234" in errors[0]
        assert "1OTM2526009999" in errors[0]

    def test_completely_different_so(self):
        errors = validate_so_number(
            extracted_data={"so_number": "COMPLETELY-DIFFERENT"},
            doc_type="COMPANY_INVOICE",
            po_so_number="1OTM2526001234",
        )
        assert len(errors) == 1
        assert "mismatch" in errors[0].lower()


# ── Edge cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_no_so_field_in_extracted_skips_comparison(self):
        """If the document has no SO field extracted, validator skips comparison."""
        errors = validate_so_number(
            extracted_data={"po_number": "PO-001"},  # no so_number or sales_order_no
            doc_type="COMPANY_DC",
            po_so_number="1OTM2526001234",
        )
        assert errors == []

    def test_both_so_fields_absent(self):
        errors = validate_so_number(
            extracted_data={},
            doc_type="COMPANY_INVOICE",
            po_so_number="1OTM2526001234",
        )
        assert errors == []

    def test_so_number_takes_priority_over_sales_order_no(self):
        """so_number field takes priority; sales_order_no is fallback."""
        errors = validate_so_number(
            extracted_data={
                "so_number": "1OTM2526001234",      # correct
                "sales_order_no": "WRONG-SO-999",   # would mismatch
            },
            doc_type="COMPANY_DC",
            po_so_number="1OTM2526001234",
        )
        assert errors == []