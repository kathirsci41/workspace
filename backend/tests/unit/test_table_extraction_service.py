"""
Unit tests for table_extraction_service.py (Sprint 2, Task 2.2).

All tests run without paddleocr installed — PPStructure is fully mocked.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.table_extraction_service import (
    LineItem,
    _parse_html_table,
    _to_float,
    extract_line_items_from_image,
    extract_tables,
    parse_line_items,
)


# ---------------------------------------------------------------------------
# _to_float
# ---------------------------------------------------------------------------

class TestToFloat:
    def test_plain_number(self):
        assert _to_float("1234.56") == pytest.approx(1234.56)

    def test_indian_comma_format(self):
        assert _to_float("1,23,456.00") == pytest.approx(123456.0)

    def test_rupee_symbol_stripped(self):
        assert _to_float("₹500.00") == pytest.approx(500.0)

    def test_empty_string_returns_zero(self):
        assert _to_float("") == 0.0

    def test_none_returns_zero(self):
        assert _to_float(None) == 0.0

    def test_invalid_text_returns_zero(self):
        assert _to_float("N/A") == 0.0


# ---------------------------------------------------------------------------
# _parse_html_table
# ---------------------------------------------------------------------------

class TestParseHtmlTable:
    def test_simple_two_column_table(self):
        html = """
        <table>
          <tr><th>Description</th><th>Amount</th></tr>
          <tr><td>Widget A</td><td>1000.00</td></tr>
          <tr><td>Widget B</td><td>500.00</td></tr>
        </table>
        """
        rows = _parse_html_table(html)
        assert len(rows) == 2
        assert rows[0]["Description"] == "Widget A"
        assert rows[0]["Amount"] == "1000.00"

    def test_empty_html_returns_empty_list(self):
        assert _parse_html_table("") == []

    def test_header_only_table_returns_empty_list(self):
        html = "<table><tr><th>Description</th><th>Qty</th></tr></table>"
        rows = _parse_html_table(html)
        assert rows == []

    def test_malformed_html_does_not_raise(self):
        result = _parse_html_table("<table><tr><td>BROKEN")
        assert isinstance(result, list)

    def test_missing_cell_pads_with_empty_string(self):
        html = """
        <table>
          <tr><th>A</th><th>B</th><th>C</th></tr>
          <tr><td>1</td><td>2</td></tr>
        </table>
        """
        rows = _parse_html_table(html)
        assert rows[0]["C"] == ""


# ---------------------------------------------------------------------------
# parse_line_items
# ---------------------------------------------------------------------------

class TestParseLineItems:
    def _row(self, **kwargs):
        return kwargs

    def test_standard_invoice_columns(self):
        rows = [
            self._row(Description="Laptop Stand", **{"HSN/SAC": "8473", "Qty": "2", "Rate": "500",
                                                      "Taxable Amount": "1000", "IGST": "180", "Total": "1180"}),
        ]
        items = parse_line_items(rows)
        assert len(items) == 1
        item = items[0]
        assert item.description == "Laptop Stand"
        assert item.hsn_sac == "8473"
        assert item.quantity == pytest.approx(2.0)
        assert item.unit_price == pytest.approx(500.0)
        assert item.taxable_amount == pytest.approx(1000.0)
        assert item.igst == pytest.approx(180.0)
        assert item.total == pytest.approx(1180.0)

    def test_alternative_column_names(self):
        rows = [self._row(Particulars="Cable", **{"HSN": "8544", "Nos": "10", "Taxable Value": "2000"})]
        items = parse_line_items(rows)
        assert items[0].description == "Cable"
        assert items[0].hsn_sac == "8544"
        assert items[0].quantity == pytest.approx(10.0)

    def test_row_with_no_description_and_no_amount_skipped(self):
        rows = [self._row(**{"Unit": "pcs"})]
        items = parse_line_items(rows)
        assert items == []

    def test_row_with_only_taxable_amount_included(self):
        rows = [self._row(**{"Taxable Amount": "500"})]
        items = parse_line_items(rows)
        assert len(items) == 1
        assert items[0].taxable_amount == pytest.approx(500.0)

    def test_cgst_sgst_parsed(self):
        rows = [self._row(Description="X", **{"CGST": "90", "SGST": "90", "Taxable Amount": "1000"})]
        items = parse_line_items(rows)
        assert items[0].cgst == pytest.approx(90.0)
        assert items[0].sgst == pytest.approx(90.0)

    def test_raw_dict_preserved(self):
        row = {"Description": "Y", "Qty": "1"}
        items = parse_line_items([row])
        assert items[0].raw == row

    def test_empty_input_returns_empty_list(self):
        assert parse_line_items([]) == []


# ---------------------------------------------------------------------------
# extract_tables — PPStructure mocked
# ---------------------------------------------------------------------------

class TestExtractTables:
    def _mock_structure_result(self, html: str):
        region = {"type": "table", "res": {"html": html}}
        return [region]

    def test_returns_empty_when_paddleocr_not_available(self):
        with patch("app.services.table_extraction_service._ppstructure_available", return_value=False):
            result = extract_tables("/tmp/fake.png")
        assert result == []

    def test_returns_empty_on_exception(self):
        with patch("app.services.table_extraction_service._ppstructure_available", return_value=True), \
             patch("app.services.table_extraction_service._init_structure", side_effect=RuntimeError("GPU error")):
            # Force re-init by resetting module-level _structure_model
            import app.services.table_extraction_service as svc
            svc._structure_model = None
            result = extract_tables("/tmp/fake.png")
        assert result == []

    def test_extracts_table_rows_from_html(self):
        html = """<table>
        <tr><th>Description</th><th>Qty</th></tr>
        <tr><td>Widget</td><td>5</td></tr>
        </table>"""
        mock_model = MagicMock()
        mock_model.return_value = self._mock_structure_result(html)

        import app.services.table_extraction_service as svc
        original = svc._structure_model
        svc._structure_model = mock_model
        try:
            with patch("app.services.table_extraction_service._ppstructure_available", return_value=True):
                tables = extract_tables("/tmp/invoice.png")
        finally:
            svc._structure_model = original

        assert len(tables) == 1
        assert tables[0][0]["Description"] == "Widget"

    def test_ignores_non_table_regions(self):
        result_with_text_region = [{"type": "text", "res": {"text": "some text"}}]
        mock_model = MagicMock(return_value=result_with_text_region)

        import app.services.table_extraction_service as svc
        original = svc._structure_model
        svc._structure_model = mock_model
        try:
            with patch("app.services.table_extraction_service._ppstructure_available", return_value=True):
                tables = extract_tables("/tmp/invoice.png")
        finally:
            svc._structure_model = original

        assert tables == []

    def test_returns_empty_for_empty_html(self):
        mock_model = MagicMock(return_value=[{"type": "table", "res": {"html": ""}}])

        import app.services.table_extraction_service as svc
        original = svc._structure_model
        svc._structure_model = mock_model
        try:
            with patch("app.services.table_extraction_service._ppstructure_available", return_value=True):
                tables = extract_tables("/tmp/invoice.png")
        finally:
            svc._structure_model = original

        assert tables == []


# ---------------------------------------------------------------------------
# extract_line_items_from_image — high-level entry point
# ---------------------------------------------------------------------------

class TestExtractLineItemsFromImage:
    def test_returns_empty_when_no_tables(self):
        with patch("app.services.table_extraction_service.extract_tables", return_value=[]):
            result = extract_line_items_from_image("/tmp/fake.png")
        assert result == []

    def test_returns_line_items_as_dicts(self):
        table_rows = [{"Description": "Pen", "Qty": "10", "Taxable Amount": "100"}]
        with patch("app.services.table_extraction_service.extract_tables", return_value=[table_rows]):
            result = extract_line_items_from_image("/tmp/invoice.png")
        assert len(result) == 1
        assert result[0]["description"] == "Pen"
        assert result[0]["quantity"] == pytest.approx(10.0)

    def test_uses_first_table_with_items(self):
        empty_table: list[dict] = []
        good_table = [{"Description": "Cable", "Taxable Amount": "200"}]
        with patch("app.services.table_extraction_service.extract_tables", return_value=[empty_table, good_table]):
            result = extract_line_items_from_image("/tmp/invoice.png")
        assert len(result) == 1
        assert result[0]["description"] == "Cable"

    def test_result_items_are_plain_dicts_not_dataclasses(self):
        table_rows = [{"Description": "Pad", "Taxable Amount": "50"}]
        with patch("app.services.table_extraction_service.extract_tables", return_value=[table_rows]):
            result = extract_line_items_from_image("/tmp/invoice.png")
        assert isinstance(result[0], dict)
        assert not isinstance(result[0], LineItem)
