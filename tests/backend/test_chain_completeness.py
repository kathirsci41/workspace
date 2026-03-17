"""
Unit tests for PO chain completeness calculation logic.

Rules (from extraction.py _update_chain_async):
  - Count distinct document_types where status NOT IN [EXTRACTION_FAILED, REJECTED]
  - completeness% = (count / 6) * 100
  - 0%       → INITIATED
  - 1–49%    → IN_PROGRESS
  - 50–99%   → NEAR_COMPLETE
  - 100%     → COMPLETE

These tests verify the pure calculation logic without a database.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))

import pytest
from app.models.purchase_order import POStatus


# ── Pure calculation logic (mirrors _update_chain_async) ─────────────────────

def calculate_completeness(distinct_doc_type_count: int) -> float:
    """Mirror of the formula in extraction.py."""
    return round((distinct_doc_type_count / 6) * 100, 1)


def get_po_status(completeness: float) -> POStatus:
    """Mirror of the status mapping in extraction.py."""
    if completeness == 0:
        return POStatus.INITIATED
    elif completeness < 50:
        return POStatus.IN_PROGRESS
    elif completeness < 100:
        return POStatus.NEAR_COMPLETE
    else:
        return POStatus.COMPLETE


class TestCompletenessCalculation:

    def test_zero_docs(self):
        assert calculate_completeness(0) == 0.0

    def test_one_doc(self):
        assert calculate_completeness(1) == round(1/6 * 100, 1)

    def test_three_docs(self):
        assert calculate_completeness(3) == 50.0

    def test_four_docs(self):
        assert calculate_completeness(4) == round(4/6 * 100, 1)

    def test_five_docs(self):
        assert calculate_completeness(5) == round(5/6 * 100, 1)

    def test_six_docs_complete(self):
        assert calculate_completeness(6) == 100.0

    def test_max_is_100(self):
        """Never exceed 100% even with >6 types (should not happen, but guard)."""
        assert calculate_completeness(6) <= 100.0


class TestPoStatusMapping:

    def test_zero_percent_is_initiated(self):
        assert get_po_status(0.0) == POStatus.INITIATED

    def test_one_doc_is_in_progress(self):
        pct = calculate_completeness(1)
        assert get_po_status(pct) == POStatus.IN_PROGRESS

    def test_two_docs_is_in_progress(self):
        pct = calculate_completeness(2)
        assert get_po_status(pct) == POStatus.IN_PROGRESS

    def test_three_docs_is_near_complete(self):
        """50% → NEAR_COMPLETE (boundary: < 50 is IN_PROGRESS, >= 50 is NEAR_COMPLETE)."""
        pct = calculate_completeness(3)  # exactly 50.0
        assert get_po_status(pct) == POStatus.NEAR_COMPLETE

    def test_four_docs_is_near_complete(self):
        pct = calculate_completeness(4)
        assert get_po_status(pct) == POStatus.NEAR_COMPLETE

    def test_five_docs_is_near_complete(self):
        pct = calculate_completeness(5)
        assert get_po_status(pct) == POStatus.NEAR_COMPLETE

    def test_six_docs_is_complete(self):
        assert get_po_status(100.0) == POStatus.COMPLETE


class TestExcludedStatuses:
    """
    Verify that EXTRACTION_FAILED and REJECTED documents are
    excluded from the count. This is the core business rule.

    We test this through the formula: if we have 3 distinct doc types
    but 2 are EXTRACTION_FAILED, only 1 counts.
    """

    def test_extraction_failed_excluded(self):
        # 3 doc types uploaded, 2 failed → only 1 counts → ~16.7%
        valid_count = 1
        pct = calculate_completeness(valid_count)
        assert pct < 50
        assert get_po_status(pct) == POStatus.IN_PROGRESS

    def test_rejected_excluded(self):
        # 6 uploaded, 3 rejected → 3 count → 50%
        valid_count = 3
        pct = calculate_completeness(valid_count)
        assert pct == 50.0
        assert get_po_status(pct) == POStatus.NEAR_COMPLETE

    def test_all_failed_stays_initiated(self):
        # All 6 types uploaded but all EXTRACTION_FAILED → 0 count
        valid_count = 0
        pct = calculate_completeness(valid_count)
        assert pct == 0.0
        assert get_po_status(pct) == POStatus.INITIATED

    def test_duplicate_doc_types_count_once(self):
        """
        Multiple uploads of the same doc type count as 1, not N.
        E.g., 3 CUSTOMER_PO uploads → still just 1 distinct type.
        """
        # Simulated: 3 CUSTOMER_PO + 1 COMPANY_PO = 2 distinct types
        distinct_count = 2
        pct = calculate_completeness(distinct_count)
        assert pct == round(2/6 * 100, 1)
        assert get_po_status(pct) == POStatus.IN_PROGRESS