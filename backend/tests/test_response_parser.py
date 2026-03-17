"""Unit tests for the ResponseParser (JSON extraction, merging, confidence, date parsing)."""
import pytest
from datetime import date
from app.services.extraction.response_parser import ResponseParser, ParseError


@pytest.fixture
def parser():
    return ResponseParser()


# ---------------------------------------------------------------------------
# parse_response — JSON extraction strategies
# ---------------------------------------------------------------------------
class TestParseResponse:
    def test_direct_json(self, parser):
        raw = '{"invoice_number": "INV-001", "total_amount": 1500.50}'
        result = parser.parse_response(raw)
        assert result["invoice_number"] == "INV-001"
        assert result["total_amount"] == 1500.50

    def test_json_in_code_block(self, parser):
        raw = '```json\n{"dc_number": "DC-100"}\n```'
        result = parser.parse_response(raw)
        assert result["dc_number"] == "DC-100"

    def test_json_in_generic_code_block(self, parser):
        raw = '```\n{"dc_number": "DC-100"}\n```'
        result = parser.parse_response(raw)
        assert result["dc_number"] == "DC-100"

    def test_json_with_surrounding_text(self, parser):
        raw = 'Here is the result: {"po_number": "PO-999"} end.'
        result = parser.parse_response(raw)
        assert result["po_number"] == "PO-999"

    def test_trailing_comma_cleaned(self, parser):
        raw = '{"a": 1, "b": 2,}'
        result = parser.parse_response(raw)
        assert result == {"a": 1, "b": 2}

    def test_comma_formatted_numbers_cleaned(self, parser):
        raw = '{"subtotal": 86,678.50, "total_amount": 1,02,345.00}'
        result = parser.parse_response(raw)
        assert result["subtotal"] == 86678.50

    def test_raises_parse_error_on_garbage(self, parser):
        with pytest.raises(ParseError):
            parser.parse_response("this is not json at all")

    def test_null_fields_preserved(self, parser):
        raw = '{"invoice_number": "INV-1", "irn_number": null}'
        result = parser.parse_response(raw)
        assert result["irn_number"] is None


# ---------------------------------------------------------------------------
# parse_and_merge — multi-page merging
# ---------------------------------------------------------------------------
class TestParseAndMerge:
    def test_first_non_null_wins(self, parser):
        pages = [
            '{"dc_number": "DC-1", "po_reference": null}',
            '{"dc_number": null, "po_reference": "PO-1"}',
        ]
        merged = parser.parse_and_merge(pages, "COMPANY_DC")
        assert merged["dc_number"] == "DC-1"
        assert merged["po_reference"] == "PO-1"

    def test_skips_unparseable_pages(self, parser):
        pages = [
            "garbage text",
            '{"dc_number": "DC-2"}',
        ]
        merged = parser.parse_and_merge(pages, "COMPANY_DC")
        assert merged["dc_number"] == "DC-2"

    def test_all_pages_unparseable_returns_empty(self, parser):
        pages = ["nope", "also nope"]
        merged = parser.parse_and_merge(pages, "COMPANY_DC")
        assert merged == {}

    def test_empty_page_list(self, parser):
        merged = parser.parse_and_merge([], "COMPANY_DC")
        assert merged == {}

    def test_new_company_dc_fields_merge(self, parser):
        """Ensure new Phase 1 fields merge correctly across pages."""
        pages = [
            '{"dc_number": "DC-100", "sales_order_no": "SO-200", "customer_order_date": null}',
            '{"dc_number": null, "sales_order_no": null, "customer_order_date": "15/01/2026"}',
        ]
        merged = parser.parse_and_merge(pages, "COMPANY_DC")
        assert merged["dc_number"] == "DC-100"
        assert merged["sales_order_no"] == "SO-200"
        assert merged["customer_order_date"] == "15/01/2026"

    def test_new_company_invoice_fields_merge(self, parser):
        """Ensure new Phase 1 fields merge correctly across pages."""
        pages = [
            '{"invoice_number": "INV-1", "acct_manager": "John", "customer_order_date": null}',
            '{"invoice_number": null, "acct_manager": null, "customer_order_date": "10/02/2026"}',
        ]
        merged = parser.parse_and_merge(pages, "COMPANY_INVOICE")
        assert merged["invoice_number"] == "INV-1"
        assert merged["acct_manager"] == "John"
        assert merged["customer_order_date"] == "10/02/2026"


# ---------------------------------------------------------------------------
# calculate_confidence
# ---------------------------------------------------------------------------
class TestConfidence:
    def test_all_filled(self, parser):
        data = {"a": "x", "b": 10, "c": True}
        assert parser.calculate_confidence(data, ["a", "b", "c"]) == 100.0

    def test_none_filled(self, parser):
        data = {"a": None, "b": None}
        assert parser.calculate_confidence(data, ["a", "b"]) == 0.0

    def test_partial(self, parser):
        data = {"a": "x", "b": None, "c": "", "d": "y"}
        score = parser.calculate_confidence(data, ["a", "b", "c", "d"])
        assert score == 50.0  # 2 out of 4

    def test_empty_schema_returns_zero(self, parser):
        assert parser.calculate_confidence({"a": 1}, []) == 0.0

    def test_missing_keys_count_as_unfilled(self, parser):
        data = {"a": "x"}
        score = parser.calculate_confidence(data, ["a", "b", "c"])
        assert score == pytest.approx(33.3, abs=0.1)


# ---------------------------------------------------------------------------
# parse_date
# ---------------------------------------------------------------------------
class TestParseDate:
    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("18/12/2025", date(2025, 12, 18)),
            ("18-12-2025", date(2025, 12, 18)),
            ("2025-12-18", date(2025, 12, 18)),
            ("18.12.2025", date(2025, 12, 18)),
            ("18-Dec-2025", date(2025, 12, 18)),
            ("18 Dec 2025", date(2025, 12, 18)),
            ("December 18, 2025", date(2025, 12, 18)),
        ],
    )
    def test_various_formats(self, parser, input_str, expected):
        assert parser.parse_date(input_str) == expected

    def test_none_input(self, parser):
        assert parser.parse_date(None) is None

    def test_empty_string(self, parser):
        assert parser.parse_date("") is None

    def test_non_string(self, parser):
        assert parser.parse_date(12345) is None

    def test_unparseable_string(self, parser):
        assert parser.parse_date("not a date") is None

    def test_whitespace_trimmed(self, parser):
        assert parser.parse_date("  18/12/2025  ") == date(2025, 12, 18)
