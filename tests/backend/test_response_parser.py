"""
Unit tests for ResponseParser — JSON extraction, date parsing,
confidence calculation, and JSON cleaning.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))

import pytest
from datetime import date
from app.services.extraction.response_parser import ResponseParser, ParseError


@pytest.fixture
def parser():
    return ResponseParser()


# ── parse_response: JSON extraction strategies ────────────────────────────────

class TestParseResponse:

    def test_strategy1_direct_json(self, parser):
        raw = '{"po_number": "PO-001", "amount": 5000}'
        result = parser.parse_response(raw)
        assert result["po_number"] == "PO-001"
        assert result["amount"] == 5000

    def test_strategy2_json_code_block(self, parser):
        raw = '```json\n{"invoice_no": "INV-123"}\n```'
        result = parser.parse_response(raw)
        assert result["invoice_no"] == "INV-123"

    def test_strategy2_plain_code_block(self, parser):
        raw = '```\n{"dc_number": "DC-456"}\n```'
        result = parser.parse_response(raw)
        assert result["dc_number"] == "DC-456"

    def test_strategy3_brace_extraction(self, parser):
        raw = 'Here is the result: {"po_number": "PO-002"} extracted from the document.'
        result = parser.parse_response(raw)
        assert result["po_number"] == "PO-002"

    def test_strategy4_trailing_comma_cleaned(self, parser):
        raw = '{"po_number": "PO-003", "amount": 1000,}'
        result = parser.parse_response(raw)
        assert result["po_number"] == "PO-003"

    def test_raises_parse_error_on_garbage(self, parser):
        with pytest.raises(ParseError):
            parser.parse_response("this is not json at all")

    def test_raises_parse_error_on_empty_string(self, parser):
        with pytest.raises(ParseError):
            parser.parse_response("")

    def test_nested_json(self, parser):
        raw = '{"customer": {"name": "ABC Ltd"}, "total": 9999.0}'
        result = parser.parse_response(raw)
        assert result["customer"]["name"] == "ABC Ltd"


# ── parse_and_merge: multi-page merge ────────────────────────────────────────

class TestParseAndMerge:

    def test_first_non_null_wins(self, parser):
        pages = [
            '{"po_number": "PO-001", "amount": null}',
            '{"po_number": null, "amount": 5000}',
        ]
        result = parser.parse_and_merge(pages, "CUSTOMER_PO")
        assert result["po_number"] == "PO-001"
        assert result["amount"] == 5000

    def test_single_page(self, parser):
        pages = ['{"invoice_no": "INV-007"}']
        result = parser.parse_and_merge(pages, "VENDOR_INVOICE")
        assert result["invoice_no"] == "INV-007"

    def test_failed_page_skipped(self, parser):
        pages = ["not valid json", '{"dc_number": "DC-999"}']
        result = parser.parse_and_merge(pages, "VENDOR_DC")
        assert result["dc_number"] == "DC-999"

    def test_all_pages_fail_returns_empty(self, parser):
        pages = ["garbage", "also garbage"]
        result = parser.parse_and_merge(pages, "CUSTOMER_PO")
        assert result == {}

    def test_empty_pages_list(self, parser):
        result = parser.parse_and_merge([], "CUSTOMER_PO")
        assert result == {}


# ── calculate_confidence ─────────────────────────────────────────────────────

class TestCalculateConfidence:

    def test_all_fields_filled(self, parser):
        extracted = {"po_number": "PO-001", "amount": 5000, "date": "01/01/2025"}
        schema = ["po_number", "amount", "date"]
        assert parser.calculate_confidence(extracted, schema) == 100.0

    def test_no_fields_filled(self, parser):
        extracted = {"po_number": None, "amount": None}
        schema = ["po_number", "amount"]
        assert parser.calculate_confidence(extracted, schema) == 0.0

    def test_half_fields_filled(self, parser):
        extracted = {"po_number": "PO-001", "amount": None}
        schema = ["po_number", "amount"]
        assert parser.calculate_confidence(extracted, schema) == 50.0

    def test_low_confidence_flag_counts_half(self, parser):
        extracted = {
            "amount": 5000,
            "_validation": {"amount": "LOW_CONFIDENCE"},
        }
        schema = ["amount"]
        assert parser.calculate_confidence(extracted, schema) == 50.0

    def test_amount_parse_failed_counts_half(self, parser):
        extracted = {
            "amount": "unparseable",
            "_validation": {"amount": "AMOUNT_PARSE_FAILED"},
        }
        schema = ["amount"]
        assert parser.calculate_confidence(extracted, schema) == 50.0

    def test_empty_string_not_counted(self, parser):
        extracted = {"po_number": ""}
        schema = ["po_number"]
        assert parser.calculate_confidence(extracted, schema) == 0.0

    def test_empty_schema_returns_zero(self, parser):
        assert parser.calculate_confidence({"po_number": "PO-001"}, []) == 0.0

    def test_missing_field_in_extracted(self, parser):
        # Field in schema but not present in extracted → 0
        extracted = {}
        schema = ["po_number", "amount"]
        assert parser.calculate_confidence(extracted, schema) == 0.0


# ── parse_date ────────────────────────────────────────────────────────────────

class TestParseDate:

    def test_dd_mm_yyyy_dash(self, parser):
        assert parser.parse_date("18-12-2025") == date(2025, 12, 18)

    def test_dd_mm_yyyy_slash(self, parser):
        assert parser.parse_date("18/12/2025") == date(2025, 12, 18)

    def test_dd_mm_yyyy_dot(self, parser):
        assert parser.parse_date("18.12.2025") == date(2025, 12, 18)

    def test_yyyy_mm_dd(self, parser):
        assert parser.parse_date("2025-12-18") == date(2025, 12, 18)

    def test_dd_mon_yyyy(self, parser):
        assert parser.parse_date("18-Dec-2025") == date(2025, 12, 18)

    def test_dd_mon_yyyy_space(self, parser):
        assert parser.parse_date("18 Dec 2025") == date(2025, 12, 18)

    def test_month_dd_year(self, parser):
        assert parser.parse_date("December 18, 2025") == date(2025, 12, 18)

    def test_two_digit_year(self, parser):
        assert parser.parse_date("18/12/25") == date(2025, 12, 18)

    def test_none_input(self, parser):
        assert parser.parse_date(None) is None

    def test_empty_string(self, parser):
        assert parser.parse_date("") is None

    def test_invalid_date(self, parser):
        assert parser.parse_date("not-a-date") is None

    def test_whitespace_stripped(self, parser):
        assert parser.parse_date("  18/12/2025  ") == date(2025, 12, 18)

    def test_non_string_input(self, parser):
        assert parser.parse_date(20251218) is None


# ── _clean_json ───────────────────────────────────────────────────────────────

class TestCleanJson:

    def test_trailing_comma_object(self, parser):
        result = parser._clean_json('{"a": 1, "b": 2,}')
        import json
        assert json.loads(result) == {"a": 1, "b": 2}

    def test_trailing_comma_array(self, parser):
        result = parser._clean_json('{"items": [1, 2, 3,]}')
        import json
        assert json.loads(result)["items"] == [1, 2, 3]

    def test_comma_formatted_number_as_value(self, parser):
        result = parser._clean_json('{"amount": 86678.5}')
        import json
        assert json.loads(result)["amount"] == 86678.5

    def test_no_change_on_clean_json(self, parser):
        clean = '{"po_number": "PO-001", "amount": 5000}'
        import json
        assert json.loads(parser._clean_json(clean)) == json.loads(clean)