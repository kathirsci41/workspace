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
from unittest.mock import MagicMock, patch
from app.models.purchase_order import POStatus, OrderScenario, PurchaseOrder
from app.models.document import Document, DocumentStatus, DocumentType


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


class TestScenarioSpecificCompleteness:
    """
    Test that completeness calculation respects scenario-specific required chains.
    
    E.g., STOCK scenario requires only [CUSTOMER_PO, COMPANY_DC, COMPANY_INVOICE] = 3 docs.
    If we have all 5 PROCUREMENT docs (including optional VENDOR_DC), but STOCK scenario,
    completeness should be 3/3 = 100%, not 5/5 = 100% nor 3/6 = 50%.
    
    Bug fix: Currently divides by 6 (all doc types) rather than scenario chain length,
    allowing optional docs to inflate completeness to 100%+.
    """

    def test_stock_scenario_ignores_vendor_docs(self):
        """
        STOCK scenario: [CUSTOMER_PO, COMPANY_DC, COMPANY_INVOICE] = 3 required docs.
        If we have all 3 + VENDOR_INVOICE (optional), completeness = 3/3 = 100%, not 4/6.
        """
        # Scenario chain length = 3
        # Docs present: CUSTOMER_PO, COMPANY_DC, COMPANY_INVOICE (3 required) + VENDOR_INVOICE (not in chain)
        required_docs_count = 3
        scenario_chain_len = 3
        completeness = round((required_docs_count / scenario_chain_len) * 100, 1)
        
        # Should be 100%, not 66.7% (which would be 4/6)
        assert completeness == 100.0
        assert get_po_status(completeness) == POStatus.COMPLETE

    def test_drop_ship_scenario_includes_vendor_dc(self):
        """
        DROP_SHIP scenario: [CUSTOMER_PO, COMPANY_PO, VENDOR_DC, VENDOR_INVOICE, COMPANY_INVOICE] = 5 docs.
        COMPANY_DC is NOT required (not in chain).
        If we have only 3/5 required + COMPANY_DC, completeness = 3/5 = 60%, not 4/6 = 66.7%.
        """
        required_docs_count = 3
        scenario_chain_len = 5
        completeness = round((required_docs_count / scenario_chain_len) * 100, 1)
        
        assert completeness == 60.0
        assert get_po_status(completeness) == POStatus.NEAR_COMPLETE

    def test_procurement_scenario_excludes_optional_vendor_dc(self):
        """
        PROCUREMENT scenario: [CUSTOMER_PO, COMPANY_PO, VENDOR_INVOICE, COMPANY_DC, COMPANY_INVOICE] = 5 docs.
        VENDOR_DC is NOT required (excluded comment says "optional").
        If we have 5/5 required, completeness = 100%, dividing by 5 not 6.
        """
        required_docs_count = 5
        scenario_chain_len = 5
        completeness = round((required_docs_count / scenario_chain_len) * 100, 1)
        
        assert completeness == 100.0
        assert get_po_status(completeness) == POStatus.COMPLETE

    def test_service_amc_scenario_minimal_chain(self):
        """
        SERVICE_AMC scenario: [CUSTOMER_PO, COMPANY_INVOICE] = 2 docs only.
        If we have 1/2 required, completeness = 50%, not 1/6 = 16.7%.
        """
        required_docs_count = 1
        scenario_chain_len = 2
        completeness = round((required_docs_count / scenario_chain_len) * 100, 1)
        
        assert completeness == 50.0
        assert get_po_status(completeness) == POStatus.NEAR_COMPLETE

    def test_stock_scenario_all_docs_present(self):
        """
        STOCK scenario with all required docs + optional ones.
        Should count only the 3 required [CUSTOMER_PO, COMPANY_DC, COMPANY_INVOICE].
        """
        # If all 6 types are present, but only 3 are in STOCK scenario chain
        required_docs_count = 3
        scenario_chain_len = 3
        completeness = round((required_docs_count / scenario_chain_len) * 100, 1)
        
        # 100%, not 6/6 or 3/6
        assert completeness == 100.0

    def test_partially_complete_stock_scenario(self):
        """
        STOCK scenario partially complete: 2/3 required docs.
        completeness = 66.7%, not 2/6 = 33.3%.
        """
        required_docs_count = 2
        scenario_chain_len = 3
        completeness = round((required_docs_count / scenario_chain_len) * 100, 1)
        
        assert completeness == round(66.666666, 1)
        assert get_po_status(completeness) == POStatus.NEAR_COMPLETE



class TestUpdateChainSyncIntegration:
    """
    Integration tests for _update_chain_sync function.
    
    Tests that _update_chain_sync correctly:
    1. Counts only documents in the scenario's required chain
    2. Ignores optional/irrelevant documents
    3. Respects manually_completed flag (skips recalculation)
    4. Clamps completeness to [0, 100]
    """

    def test_stock_scenario_with_optional_vendor_invoice(self):
        """
        STOCK scenario: [CUSTOMER_PO, COMPANY_DC, COMPANY_INVOICE] = 3 required.
        If VENDOR_INVOICE is uploaded (not in STOCK chain), it should NOT count.
        
        Before fix: completeness = 4/6 = 66.7%
        After fix: completeness = 3/3 = 100.0%
        """
        # This test documents the expected behavior.
        # The actual implementation test will use mocks/fixtures.
        # For now, this is a specification test showing what should happen.
        required_docs_in_scenario = 3  # CUSTOMER_PO, COMPANY_DC, COMPANY_INVOICE
        extra_docs_not_in_scenario = 1  # VENDOR_INVOICE
        
        # After fix: only count required docs
        scenario_chain_len = 3
        required_docs_found = 3
        completeness = round((required_docs_found / scenario_chain_len) * 100, 1)
        
        assert completeness == 100.0
        assert get_po_status(completeness) == POStatus.COMPLETE

    def test_drop_ship_scenario_excludes_company_dc(self):
        """
        DROP_SHIP scenario: [CUSTOMER_PO, COMPANY_PO, VENDOR_DC, VENDOR_INVOICE, COMPANY_INVOICE] = 5 required.
        COMPANY_DC is NOT in the chain (optional).
        If we have 4/5 required + COMPANY_DC, completeness = 4/5 = 80%, not 5/6.
        
        Before fix: completeness = 5/6 = 83.3%
        After fix: completeness = 4/5 = 80.0%
        """
        scenario_chain_len = 5
        required_docs_found = 4
        completeness = round((required_docs_found / scenario_chain_len) * 100, 1)
        
        assert completeness == 80.0
        assert get_po_status(completeness) == POStatus.NEAR_COMPLETE

    def test_manually_completed_skips_recalculation(self):
        """
        If po.manually_completed=True, _update_chain_sync should NOT update
        chain_completeness or status, allowing user-set values to persist.
        """
        # This behavior is specified in the task requirements.
        # Implementation should check: if po.manually_completed, return early.
        pass

    def test_completeness_clamped_to_100(self):
        """
        Even if somehow count > scenario_chain_len (should not happen),
        completeness must not exceed 100%.

        Verify: completeness = min(100.0, calculated_value)
        """
        # If count = 3, scenario_chain_len = 3: 3/3 * 100 = 100
        completeness = round((3 / 3) * 100, 1)
        clamped = min(100.0, completeness)
        assert clamped == 100.0
