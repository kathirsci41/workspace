"""
Unit tests for the response parser module.

Tests cover:
  - _extract_json: JSON extraction from raw LLM output (direct, code blocks, braces, cleanup)
  - _parse_date:   Date parsing across 12 Indian / international formats
  - parse_ocr_response: Full pipeline (extract → validate → promote → confidence)
"""

import pytest
from datetime import date

from app.services.extraction.response_parser import (
    parse_ocr_response,
    _extract_json,
    _parse_date,
    _validate_against_schema,
    _calculate_confidence,
)


# ═══════════════════════════════════════════════════════════════════════
# _extract_json
# ═══════════════════════════════════════════════════════════════════════

class TestExtractJson:
    """JSON extraction from various raw LLM output formats."""

    def test_direct_json(self):
        result = _extract_json('{"invoice_no": "INV-001", "date": "15-01-2026"}')
        assert result == {"invoice_no": "INV-001", "date": "15-01-2026"}

    def test_json_in_code_block(self):
        raw = '```json\n{"po_no": "PO-123"}\n```'
        result = _extract_json(raw)
        assert result == {"po_no": "PO-123"}

    def test_json_in_plain_code_block(self):
        raw = '```\n{"dc_no": "DC-789"}\n```'
        result = _extract_json(raw)
        assert result == {"dc_no": "DC-789"}

    def test_json_with_surrounding_text(self):
        raw = 'Here is the extracted data:\n{"dc_no": "DC-456"}\nDone processing.'
        result = _extract_json(raw)
        assert result == {"dc_no": "DC-456"}

    def test_trailing_comma_in_object(self):
        raw = '{"invoice_no": "INV-001", "date": "01-01-2026",}'
        result = _extract_json(raw)
        assert result is not None
        assert result["invoice_no"] == "INV-001"

    def test_trailing_comma_in_array(self):
        raw = '{"items": ["a", "b",]}'
        result = _extract_json(raw)
        assert result is not None

    def test_single_quotes(self):
        raw = "{'invoice_no': 'INV-002', 'customer': 'ABC Corp'}"
        result = _extract_json(raw)
        assert result is not None
        assert result["invoice_no"] == "INV-002"

    def test_invalid_json_returns_none(self):
        result = _extract_json("This is not JSON at all")
        assert result is None

    def test_empty_string(self):
        result = _extract_json("")
        assert result is None

    def test_whitespace_only(self):
        result = _extract_json("   \n  \t  ")
        assert result is None

    def test_json_with_newlines_inside(self):
        raw = '{\n  "invoice_no": "INV-003",\n  "customer": "XYZ Ltd"\n}'
        result = _extract_json(raw)
        assert result == {"invoice_no": "INV-003", "customer": "XYZ Ltd"}

    def test_nested_braces_in_text(self):
        raw = 'Result: {"ref": "R-1"} end'
        result = _extract_json(raw)
        assert result is not None
        assert result["ref"] == "R-1"


# ═══════════════════════════════════════════════════════════════════════
# _parse_date
# ═══════════════════════════════════════════════════════════════════════

class TestParseDate:
    """Date parsing across multiple Indian and international formats."""

    def test_dd_mm_yyyy_dash(self):
        result = _parse_date("15-01-2026")
        assert result == date(2026, 1, 15)

    def test_dd_mm_yyyy_slash(self):
        result = _parse_date("15/01/2026")
        assert result == date(2026, 1, 15)

    def test_dd_mm_yyyy_dot(self):
        result = _parse_date("15.01.2026")
        assert result == date(2026, 1, 15)

    def test_iso_format(self):
        result = _parse_date("2026-01-15")
        assert result == date(2026, 1, 15)

    def test_named_month_short_dash(self):
        result = _parse_date("15-Jan-2026")
        assert result == date(2026, 1, 15)

    def test_named_month_short_space(self):
        result = _parse_date("15 Jan 2026")
        assert result == date(2026, 1, 15)

    def test_named_month_full(self):
        result = _parse_date("15 January 2026")
        assert result == date(2026, 1, 15)

    def test_two_digit_year_dash(self):
        result = _parse_date("15-01-26")
        assert result is not None
        assert result.day == 15
        assert result.month == 1

    def test_two_digit_year_slash(self):
        result = _parse_date("15/01/26")
        assert result is not None

    def test_us_format(self):
        result = _parse_date("01/15/2026")
        assert result is not None

    def test_month_comma_format(self):
        result = _parse_date("Jan 15, 2026")
        assert result == date(2026, 1, 15)

    def test_full_month_comma(self):
        result = _parse_date("January 15, 2026")
        assert result == date(2026, 1, 15)

    def test_empty_string(self):
        assert _parse_date("") is None

    def test_none_like_empty(self):
        assert _parse_date("   ") is None

    def test_invalid_date(self):
        assert _parse_date("not-a-date") is None

    def test_partial_garbage(self):
        assert _parse_date("abc123") is None


# ═══════════════════════════════════════════════════════════════════════
# _validate_against_schema
# ═══════════════════════════════════════════════════════════════════════

class TestValidateAgainstSchema:
    """Schema validation: filtering, type coercion, key enforcement."""

    def test_keeps_only_schema_keys(self):
        data = {"invoice_no": "INV-1", "extra_field": "NOPE"}
        schema = {"invoice_no": "", "customer": ""}
        result = _validate_against_schema(data, schema)
        assert "invoice_no" in result
        assert "customer" in result
        assert "extra_field" not in result

    def test_missing_keys_become_empty_string(self):
        data = {"invoice_no": "INV-1"}
        schema = {"invoice_no": "", "customer": ""}
        result = _validate_against_schema(data, schema)
        assert result["customer"] == ""

    def test_none_values_become_empty_string(self):
        data = {"invoice_no": None}
        schema = {"invoice_no": ""}
        result = _validate_against_schema(data, schema)
        assert result["invoice_no"] == ""

    def test_numeric_values_become_string(self):
        data = {"amount": 12345}
        schema = {"amount": ""}
        result = _validate_against_schema(data, schema)
        assert result["amount"] == "12345"

    def test_strips_whitespace(self):
        data = {"invoice_no": "  INV-1  "}
        schema = {"invoice_no": ""}
        result = _validate_against_schema(data, schema)
        assert result["invoice_no"] == "INV-1"


# ═══════════════════════════════════════════════════════════════════════
# _calculate_confidence
# ═══════════════════════════════════════════════════════════════════════

class TestCalculateConfidence:
    """Confidence score: filled fields / total fields * 100."""

    def test_all_fields_filled(self):
        data = {"a": "1", "b": "2", "c": "3"}
        schema = {"a": "", "b": "", "c": ""}
        assert _calculate_confidence(data, schema) == 100.0

    def test_no_fields_filled(self):
        data = {"a": "", "b": "", "c": ""}
        schema = {"a": "", "b": "", "c": ""}
        assert _calculate_confidence(data, schema) == 0.0

    def test_half_fields_filled(self):
        data = {"a": "1", "b": "", "c": "3", "d": ""}
        schema = {"a": "", "b": "", "c": "", "d": ""}
        assert _calculate_confidence(data, schema) == 50.0

    def test_empty_schema(self):
        assert _calculate_confidence({}, {}) == 0.0

    def test_whitespace_only_not_counted(self):
        data = {"a": "   ", "b": "val"}
        schema = {"a": "", "b": ""}
        assert _calculate_confidence(data, schema) == 50.0


# ═══════════════════════════════════════════════════════════════════════
# parse_ocr_response (full pipeline)
# ═══════════════════════════════════════════════════════════════════════

class TestParseOcrResponse:
    """End-to-end: raw OCR text → (data, ref, date, confidence)."""

    def test_full_vendor_invoice(self):
        raw = (
            '{"invoice_no":"INV-2026-001","our_order":"ORD-123",'
            '"invoice_date":"15-01-2026","customer":"ABC Corp",'
            '"def_pmnt":"Net 30","ack_no":"ACK-001",'
            '"ack_date":"16-01-2026","customer_po_no":"PO-456"}'
        )
        schema = {
            "invoice_no": "", "our_order": "", "invoice_date": "",
            "customer": "", "def_pmnt": "", "ack_no": "",
            "ack_date": "", "customer_po_no": "",
        }
        data, ref, dt, conf = parse_ocr_response(
            raw, schema, "invoice_no", "invoice_date"
        )

        assert ref == "INV-2026-001"
        assert dt == date(2026, 1, 15)
        assert conf == 100.0
        assert data["customer"] == "ABC Corp"
        assert data["def_pmnt"] == "Net 30"

    def test_partial_extraction(self):
        raw = '{"dc_no":"DC-001","customer_order_no":"","dc_date":"","so_no":"SO-999"}'
        schema = {"dc_no": "", "customer_order_no": "", "dc_date": "", "so_no": ""}
        data, ref, dt, conf = parse_ocr_response(
            raw, schema, "dc_no", "dc_date"
        )

        assert ref == "DC-001"
        assert dt is None
        assert conf == 50.0  # 2 of 4 fields filled
        assert data["so_no"] == "SO-999"
        assert data["customer_order_no"] == ""

    def test_customer_po(self):
        raw = '{"ref_no":"REF-100","po_no":"PO-200","reference_no":"QT-300","po_date":"20/03/2026"}'
        schema = {"ref_no": "", "po_no": "", "reference_no": "", "po_date": ""}
        data, ref, dt, conf = parse_ocr_response(
            raw, schema, "ref_no", "po_date"
        )

        assert ref == "REF-100"
        assert dt == date(2026, 3, 20)
        assert conf == 100.0

    def test_pod_document(self):
        raw = '{"pod_no":"POD-555","delivery_date":"10-Feb-2026","receiver_name":"John","dc_ref_no":"DC-888","so_no":"SO-777"}'
        schema = {
            "pod_no": "", "delivery_date": "", "receiver_name": "",
            "dc_ref_no": "", "so_no": "",
        }
        data, ref, dt, conf = parse_ocr_response(
            raw, schema, "pod_no", "delivery_date"
        )

        assert ref == "POD-555"
        assert dt == date(2026, 2, 10)
        assert conf == 100.0
        assert data["receiver_name"] == "John"

    def test_invalid_response_returns_empty(self):
        data, ref, dt, conf = parse_ocr_response(
            "I could not read this document",
            {"field1": "", "field2": ""},
            "field1",
            "field2",
        )

        assert data == {}
        assert ref is None
        assert dt is None
        assert conf == 0.0

    def test_code_block_wrapped_response(self):
        raw = '```json\n{"invoice_no":"INV-999","invoice_date":"01-06-2026"}\n```'
        schema = {"invoice_no": "", "invoice_date": ""}
        data, ref, dt, conf = parse_ocr_response(
            raw, schema, "invoice_no", "invoice_date"
        )

        assert ref == "INV-999"
        assert dt == date(2026, 6, 1)
        assert conf == 100.0

    def test_extra_fields_stripped(self):
        raw = '{"invoice_no":"INV-1","rogue_field":"HACK","invoice_date":"01-01-2026"}'
        schema = {"invoice_no": "", "invoice_date": ""}
        data, ref, dt, conf = parse_ocr_response(
            raw, schema, "invoice_no", "invoice_date"
        )

        assert "rogue_field" not in data
        assert len(data) == 2

    def test_ref_field_whitespace_only(self):
        raw = '{"dc_no":"   ","dc_date":"10-10-2026"}'
        schema = {"dc_no": "", "dc_date": ""}
        data, ref, dt, conf = parse_ocr_response(
            raw, schema, "dc_no", "dc_date"
        )

        # Whitespace-only ref should be None
        assert ref is None
        assert dt == date(2026, 10, 10)
        assert conf == 50.0  # only dc_date filled
