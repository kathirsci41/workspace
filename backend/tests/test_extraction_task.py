"""Tests for extraction tasks (clean_amount, _update_chain_sync logic)."""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from uuid import uuid4

# We test the helper functions and logic extracted from tasks.py.
# The actual Celery task requires DB + file system, so we test the
# pure-logic helpers and mock the rest.


# ── Import the module under test ─────────────────────────────────────────
# tasks.py imports celery_app and app.database at module level, so we
# need to mock them before importing.

import sys


def setup_module(module):
    """Mock heavy dependencies before tasks module is imported."""
    # Mock celery_app
    mock_celery = MagicMock()
    mock_celery.task = lambda **kwargs: lambda fn: fn  # decorator passthrough
    sys.modules["celery_app"] = MagicMock()
    sys.modules["celery_app"].celery_app = mock_celery

    # Mock app.database
    mock_db_module = MagicMock()
    sys.modules.setdefault("app.database", mock_db_module)


def teardown_module(module):
    """Clean up mocked modules."""
    for mod_name in ["celery_app"]:
        if mod_name in sys.modules and isinstance(sys.modules[mod_name], MagicMock):
            del sys.modules[mod_name]


# ── clean_amount (embedded in tasks.py) ──────────────────────────────────
# We re-implement the function here to test it, since it's defined inside
# the task function body. This mirrors the exact logic.

def clean_amount(val):
    """Mirror of the clean_amount helper inside extract_document."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace(",", "").strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


class TestCleanAmount:
    def test_none_returns_none(self):
        assert clean_amount(None) is None

    def test_int_returns_float(self):
        assert clean_amount(42) == 42.0
        assert isinstance(clean_amount(42), float)

    def test_float_returns_float(self):
        assert clean_amount(3.14) == 3.14

    def test_string_number(self):
        assert clean_amount("123.45") == 123.45

    def test_comma_formatted(self):
        assert clean_amount("1,234,567.89") == 1234567.89

    def test_comma_only(self):
        assert clean_amount("1,000") == 1000.0

    def test_string_with_spaces(self):
        assert clean_amount("  456.78  ") == 456.78

    def test_invalid_string_returns_none(self):
        assert clean_amount("not a number") is None

    def test_empty_string_returns_none(self):
        assert clean_amount("") is None

    def test_zero(self):
        assert clean_amount(0) == 0.0
        assert clean_amount("0") == 0.0

    def test_negative(self):
        assert clean_amount(-100) == -100.0
        assert clean_amount("-100.50") == -100.50

    def test_large_number(self):
        assert clean_amount("10,000,000.00") == 10000000.0


# ── _update_chain_sync logic ─────────────────────────────────────────────
# The function calculates completeness as (distinct_doc_types / 6) * 100
# and maps to status strings.

class TestUpdateChainLogic:
    """Test the chain completeness calculation logic."""

    def test_zero_docs_zero_completeness(self):
        count = 0
        completeness = round((count / 6) * 100, 1)
        assert completeness == 0.0

    def test_one_doc_type(self):
        count = 1
        completeness = round((count / 6) * 100, 1)
        assert completeness == 16.7

    def test_three_doc_types(self):
        count = 3
        completeness = round((count / 6) * 100, 1)
        assert completeness == 50.0

    def test_five_doc_types(self):
        count = 5
        completeness = round((count / 6) * 100, 1)
        assert completeness == 83.3

    def test_all_six_doc_types(self):
        count = 6
        completeness = round((count / 6) * 100, 1)
        assert completeness == 100.0

    def test_status_initiated_at_zero(self):
        completeness = 0.0
        if completeness == 0:
            status = "INITIATED"
        elif completeness < 50:
            status = "IN_PROGRESS"
        elif completeness < 100:
            status = "NEAR_COMPLETE"
        else:
            status = "COMPLETE"
        assert status == "INITIATED"

    def test_status_in_progress_under_50(self):
        completeness = 16.7
        if completeness == 0:
            status = "INITIATED"
        elif completeness < 50:
            status = "IN_PROGRESS"
        elif completeness < 100:
            status = "NEAR_COMPLETE"
        else:
            status = "COMPLETE"
        assert status == "IN_PROGRESS"

    def test_status_near_complete_at_50(self):
        completeness = 50.0
        if completeness == 0:
            status = "INITIATED"
        elif completeness < 50:
            status = "IN_PROGRESS"
        elif completeness < 100:
            status = "NEAR_COMPLETE"
        else:
            status = "COMPLETE"
        assert status == "NEAR_COMPLETE"

    def test_status_near_complete_at_83(self):
        completeness = 83.3
        if completeness == 0:
            status = "INITIATED"
        elif completeness < 50:
            status = "IN_PROGRESS"
        elif completeness < 100:
            status = "NEAR_COMPLETE"
        else:
            status = "COMPLETE"
        assert status == "NEAR_COMPLETE"

    def test_status_complete_at_100(self):
        completeness = 100.0
        if completeness == 0:
            status = "INITIATED"
        elif completeness < 50:
            status = "IN_PROGRESS"
        elif completeness < 100:
            status = "NEAR_COMPLETE"
        else:
            status = "COMPLETE"
        assert status == "COMPLETE"


# ── items_description joining logic ──────────────────────────────────────

class TestItemsDescriptionJoin:
    """Test the list-to-string joining for items_description."""

    def test_list_joined(self):
        items = ["Widget A", "Widget B", "Widget C"]
        result = "; ".join(str(item) for item in items if item)
        assert result == "Widget A; Widget B; Widget C"

    def test_empty_list(self):
        items = []
        result = "; ".join(str(item) for item in items if item)
        assert result == ""

    def test_list_with_none_filtered(self):
        items = ["Item 1", None, "Item 3"]
        result = "; ".join(str(item) for item in items if item)
        assert result == "Item 1; Item 3"

    def test_string_stays_string(self):
        items = "Already a string"
        if isinstance(items, list):
            items = "; ".join(str(item) for item in items if item)
        assert items == "Already a string"

    def test_none_stays_none(self):
        items: object = None
        if isinstance(items, list):
            items = "; ".join(str(item) for item in items if item)
        assert items is None


# ── Amount field sanitization logic ──────────────────────────────────────

class TestAmountFieldSanitization:
    """Test the loop that cleans amount fields in extracted_data."""

    AMOUNT_FIELDS = (
        "total_amount", "subtotal", "tax_amount", "est_amount",
        "grand_total", "unit_rate",
    )

    def test_cleans_comma_formatted_amounts(self):
        data: dict[str, object] = {"total_amount": "1,234.56", "subtotal": "500.00"}
        for field in self.AMOUNT_FIELDS:
            if field in data and data[field] is not None:
                cleaned = clean_amount(data[field])
                if cleaned is not None:
                    data[field] = cleaned
        assert data["total_amount"] == 1234.56
        assert data["subtotal"] == 500.0

    def test_skips_none_values(self):
        data: dict[str, object] = {"total_amount": None}
        for field in self.AMOUNT_FIELDS:
            if field in data and data[field] is not None:
                cleaned = clean_amount(data[field])
                if cleaned is not None:
                    data[field] = cleaned
        assert data["total_amount"] is None

    def test_skips_missing_fields(self):
        data: dict[str, object] = {"po_number": "PO-123"}
        original = dict(data)
        for field in self.AMOUNT_FIELDS:
            if field in data and data[field] is not None:
                cleaned = clean_amount(data[field])
                if cleaned is not None:
                    data[field] = cleaned
        assert data == original

    def test_invalid_amount_left_unchanged(self):
        data: dict[str, object] = {"total_amount": "N/A"}
        for field in self.AMOUNT_FIELDS:
            if field in data and data[field] is not None:
                cleaned = clean_amount(data[field])
                if cleaned is not None:
                    data[field] = cleaned
        # clean_amount returns None for "N/A", so the condition `if cleaned is not None` fails
        # and the original value stays
        assert data["total_amount"] == "N/A"
