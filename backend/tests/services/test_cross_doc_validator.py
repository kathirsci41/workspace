from app.services.cross_doc_validator import (
    check_ci_vs_cpo_total,
    check_vinv_sum_vs_vpo_total,
    check_gstin_consistency,
    check_name_consistency,
    check_serial_chain,
    check_vdc_vs_vinv_serials,
    check_dc_ref_on_ci,
    check_vpo_ref_on_vdc,
    check_vdc_ref_on_vinv,
    check_date_sequence,
    check_hsn_consistency,
    check_order_item_coverage,
)
from datetime import date as _date

from app.services.reference_validator import ReferenceCheckResult


# --- 3A: Amount checks ---

def test_ci_matches_cpo_within_1pct_returns_pass():
    assert check_ci_vs_cpo_total(503137.0, 503137.0) == ReferenceCheckResult.PASS

def test_ci_vs_cpo_rounding_within_tolerance():
    # 1 rupee rounding difference on a ₹5L order (0.0002%) → PASS
    assert check_ci_vs_cpo_total(503136.0, 503137.0) == ReferenceCheckResult.PASS

def test_ci_vs_cpo_exceeds_1pct_returns_mismatch():
    # ₹5,000 difference on ₹5,03,137 = 0.99% → MISMATCH
    assert check_ci_vs_cpo_total(498000.0, 503137.0) == ReferenceCheckResult.MISMATCH

def test_ci_vs_cpo_none_ci_returns_skip():
    assert check_ci_vs_cpo_total(None, 503137.0) == ReferenceCheckResult.SKIP

def test_ci_vs_cpo_none_cpo_returns_skip():
    assert check_ci_vs_cpo_total(503137.0, None) == ReferenceCheckResult.SKIP

def test_vinv_sum_matches_vpo_within_5pct_returns_pass():
    # VINV total slightly over due to freight — within 5%
    assert check_vinv_sum_vs_vpo_total([381359.0, 19000.0], 381359.0) == ReferenceCheckResult.PASS

def test_vinv_sum_over_5pct_returns_warning():
    # VINV sum is 10% over VPO total — unusual
    assert check_vinv_sum_vs_vpo_total([420000.0], 381359.0) == ReferenceCheckResult.WARNING

def test_vinv_sum_no_totals_returns_skip():
    assert check_vinv_sum_vs_vpo_total([], 381359.0) == ReferenceCheckResult.SKIP

def test_vinv_sum_no_vpo_total_returns_skip():
    assert check_vinv_sum_vs_vpo_total([381359.0], None) == ReferenceCheckResult.SKIP


# --- 3B: GSTIN and name checks ---

def test_gstin_all_match_returns_pass():
    assert check_gstin_consistency(["33AAICS1881D1ZJ", "33AAICS1881D1ZJ", "33AAICS1881D1ZJ"]) == ReferenceCheckResult.PASS

def test_gstin_one_differs_returns_mismatch():
    assert check_gstin_consistency(["33AAICS1881D1ZJ", "33AAICS1881D1ZJ", "29AAICS1881D1ZK"]) == ReferenceCheckResult.MISMATCH

def test_gstin_normalises_whitespace_and_case():
    assert check_gstin_consistency([" 33aaics1881d1zj ", "33AAICS1881D1ZJ"]) == ReferenceCheckResult.PASS

def test_gstin_fewer_than_two_valid_returns_skip():
    assert check_gstin_consistency([None, "", "33AAICS1881D1ZJ"]) == ReferenceCheckResult.SKIP

def test_gstin_all_none_returns_skip():
    assert check_gstin_consistency([None, None]) == ReferenceCheckResult.SKIP

def test_name_exact_match_returns_pass():
    assert check_name_consistency(["Shriram Finance", "Shriram Finance"]) == ReferenceCheckResult.PASS

def test_name_ltd_vs_limited_returns_pass():
    assert check_name_consistency(["Shriram Finance Ltd", "Shriram Finance Limited"]) == ReferenceCheckResult.PASS

def test_name_completely_different_returns_warning():
    assert check_name_consistency(["Shriram Finance", "Tata Motors"]) == ReferenceCheckResult.WARNING

def test_name_only_one_valid_returns_skip():
    assert check_name_consistency([None, "Shriram Finance"]) == ReferenceCheckResult.SKIP


# --- 3C: Serial chain of custody ---

def test_serial_chain_all_vendor_serials_shipped_returns_pass():
    # Real Skylark case: VINV C190224835 serials appear in CDC DC2915
    result = check_serial_chain(
        vinv_serials=[["NDKDL1U", "NDLEFAU"]],
        cdc_serials=[["FG120GTK25028863", "NDKDL1U", "NDLEFAU"]],
    )
    assert result["result"] == ReferenceCheckResult.PASS
    assert result["missing"] == []

def test_serial_chain_extra_cdc_serial_is_not_flagged():
    result = check_serial_chain(
        vinv_serials=[["NDKDL1U"]],
        cdc_serials=[["FG120GTK25028863", "NDKDL1U"]],
    )
    assert result["result"] == ReferenceCheckResult.PASS

def test_serial_chain_missing_serial_returns_mismatch():
    result = check_serial_chain(
        vinv_serials=[["NDKDL1U", "NDLEFAU"]],
        cdc_serials=[["NDKDL1U"]],
    )
    assert result["result"] == ReferenceCheckResult.MISMATCH
    assert "NDLEFAU" in result["missing"]

def test_serial_chain_multiple_vinvs_union():
    result = check_serial_chain(
        vinv_serials=[["NDKDL1U"], ["NDLEFAU"]],
        cdc_serials=[["NDKDL1U", "NDLEFAU"]],
    )
    assert result["result"] == ReferenceCheckResult.PASS

def test_serial_chain_case_insensitive():
    result = check_serial_chain(
        vinv_serials=[["ndkdl1u"]],
        cdc_serials=[["NDKDL1U"]],
    )
    assert result["result"] == ReferenceCheckResult.PASS

def test_serial_chain_no_vendor_serials_skips():
    result = check_serial_chain(vinv_serials=[[]], cdc_serials=[["NDKDL1U"]])
    assert result["result"] == ReferenceCheckResult.SKIP
    assert result["skip_reason"] == "no_vendor_serials"

def test_serial_chain_no_cdc_serials_skips():
    result = check_serial_chain(vinv_serials=[["NDKDL1U"]], cdc_serials=[[]])
    assert result["result"] == ReferenceCheckResult.SKIP
    assert result["skip_reason"] == "no_cdc_serials"

def test_vdc_vs_vinv_serials_all_match_returns_pass():
    result = check_vdc_vs_vinv_serials(
        vdc_serials=["NDKDL1U", "NDLEFAU"],
        vinv_serials=[["NDKDL1U", "NDLEFAU"]],
    )
    assert result["result"] == ReferenceCheckResult.PASS

def test_vdc_vs_vinv_serials_missing_returns_mismatch():
    result = check_vdc_vs_vinv_serials(
        vdc_serials=["NDKDL1U", "NDLEFAU"],
        vinv_serials=[["NDKDL1U"]],
    )
    assert result["result"] == ReferenceCheckResult.MISMATCH
    assert "NDLEFAU" in result["missing"]


# --- 3D: Document cross-references ---

def test_dc_ref_on_ci_found_returns_pass():
    assert check_dc_ref_on_ci(
        cdc_dc_numbers=["1DNT2526DC2915"],
        ci_dc_refs=["1DNT2526DC2915"],
    ) == ReferenceCheckResult.PASS

def test_dc_ref_on_ci_not_found_returns_warning():
    assert check_dc_ref_on_ci(
        cdc_dc_numbers=["1DNT2526DC2915"],
        ci_dc_refs=["SOME-OTHER-DC"],
    ) == ReferenceCheckResult.WARNING

def test_dc_ref_on_ci_no_ci_refs_returns_skip():
    assert check_dc_ref_on_ci(
        cdc_dc_numbers=["1DNT2526DC2915"],
        ci_dc_refs=[None],
    ) == ReferenceCheckResult.SKIP

def test_vpo_ref_on_vdc_found_returns_pass():
    assert check_vpo_ref_on_vdc(
        vdc_po_refs=["1PTR2526000400"],
        vpo_numbers=["1PTR2526000400"],
    ) == ReferenceCheckResult.PASS

def test_vpo_ref_on_vdc_not_found_returns_warning():
    assert check_vpo_ref_on_vdc(
        vdc_po_refs=["WRONG-PO"],
        vpo_numbers=["1PTR2526000400"],
    ) == ReferenceCheckResult.WARNING

def test_vpo_ref_on_vdc_no_vpo_numbers_returns_skip():
    assert check_vpo_ref_on_vdc(
        vdc_po_refs=["1PTR2526000400"],
        vpo_numbers=[],
    ) == ReferenceCheckResult.SKIP

def test_vdc_ref_on_vinv_found_returns_pass():
    assert check_vdc_ref_on_vinv(
        vdc_dc_numbers=["VDC-001"],
        vinv_dc_refs=["VDC-001"],
    ) == ReferenceCheckResult.PASS

def test_vdc_ref_on_vinv_no_refs_returns_skip():
    assert check_vdc_ref_on_vinv(
        vdc_dc_numbers=["VDC-001"],
        vinv_dc_refs=[None],
    ) == ReferenceCheckResult.SKIP


# --- 3E: Date sequence ---

def test_date_sequence_correct_order_returns_no_violations():
    docs = [
        {"document_type": "CUSTOMER_PO",    "doc_date": _date(2026, 1, 1)},
        {"document_type": "COMPANY_PO",     "doc_date": _date(2026, 1, 2)},
        {"document_type": "VENDOR_INVOICE", "doc_date": _date(2026, 1, 10)},
        {"document_type": "COMPANY_DC",     "doc_date": _date(2026, 1, 12)},
        {"document_type": "COMPANY_INVOICE","doc_date": _date(2026, 1, 12)},
    ]
    assert check_date_sequence(docs) == []

def test_date_sequence_ci_before_cpo_returns_violation():
    docs = [
        {"document_type": "CUSTOMER_PO",    "doc_date": _date(2026, 3, 1)},
        {"document_type": "COMPANY_INVOICE","doc_date": _date(2026, 1, 1)},
    ]
    violations = check_date_sequence(docs)
    assert len(violations) == 1
    assert violations[0]["earlier_type"] == "CUSTOMER_PO"
    assert violations[0]["later_type"] == "COMPANY_INVOICE"
    assert violations[0]["result"] == ReferenceCheckResult.WARNING

def test_date_sequence_same_day_no_violation():
    docs = [
        {"document_type": "COMPANY_DC",     "doc_date": _date(2026, 1, 10)},
        {"document_type": "COMPANY_INVOICE","doc_date": _date(2026, 1, 10)},
    ]
    assert check_date_sequence(docs) == []

def test_date_sequence_one_day_tolerance():
    docs = [
        {"document_type": "COMPANY_DC",     "doc_date": _date(2026, 1, 10)},
        {"document_type": "COMPANY_INVOICE","doc_date": _date(2026, 1, 9)},
    ]
    assert check_date_sequence(docs) == []

def test_date_sequence_skips_none_dates():
    docs = [
        {"document_type": "CUSTOMER_PO",    "doc_date": None},
        {"document_type": "COMPANY_INVOICE","doc_date": _date(2026, 1, 1)},
    ]
    assert check_date_sequence(docs) == []


# --- 3F: HSN consistency ---

def test_hsn_consistent_across_docs_returns_empty():
    docs = [
        {"document_type": "CUSTOMER_PO",    "order_items": [{"part_no": "FG-120G", "hsn_code": "84733099"}]},
        {"document_type": "COMPANY_INVOICE","order_items": [{"part_no": "FG-120G", "hsn_code": "84733099"}]},
    ]
    assert check_hsn_consistency(docs) == []

def test_hsn_inconsistent_returns_violation():
    docs = [
        {"document_type": "CUSTOMER_PO",    "order_items": [{"part_no": "FG-120G", "hsn_code": "84733099"}]},
        {"document_type": "COMPANY_INVOICE","order_items": [{"part_no": "FG-120G", "hsn_code": "85176990"}]},
    ]
    violations = check_hsn_consistency(docs)
    assert len(violations) == 1
    assert violations[0]["part_no"] == "FG-120G"
    assert set(violations[0]["hsn_values"]) == {"84733099", "85176990"}
    assert violations[0]["result"] == ReferenceCheckResult.WARNING

def test_hsn_no_items_returns_empty():
    assert check_hsn_consistency([{"document_type": "CUSTOMER_PO", "order_items": []}]) == []

def test_hsn_only_one_doc_with_hsn_returns_empty():
    docs = [
        {"document_type": "CUSTOMER_PO",    "order_items": [{"part_no": "FG-120G", "hsn_code": "84733099"}]},
        {"document_type": "COMPANY_INVOICE","order_items": [{"part_no": "FG-120G", "hsn_code": ""}]},
    ]
    assert check_hsn_consistency(docs) == []


# ── Module 4: Order Item Coverage ────────────────────────────────────────────

def test_order_item_coverage_all_matched_returns_pass():
    po_items = [
        {"part_no": "FG81F", "description": "FortiGate 81F", "qty": "2"},
        {"part_no": "FS108E", "description": "FortiSwitch 108E", "qty": "1"},
    ]
    dc_items = [
        {"part_no": "FG81F", "description": "FortiGate 81F", "qty": "2"},
        {"part_no": "FS108E", "description": "FortiSwitch 108E", "qty": "1"},
    ]
    result = check_order_item_coverage(po_items, dc_items)
    assert result["result"] == ReferenceCheckResult.PASS
    assert result["missing_parts"] == []
    assert result["partial_parts"] == []


def test_order_item_coverage_missing_part_returns_warning():
    po_items = [
        {"part_no": "FG81F", "description": "FortiGate 81F", "qty": "1"},
        {"part_no": "FS108E", "description": "FortiSwitch 108E", "qty": "1"},
    ]
    dc_items = [
        {"part_no": "FG81F", "description": "FortiGate 81F", "qty": "1"},
        # FS108E missing
    ]
    result = check_order_item_coverage(po_items, dc_items)
    assert result["result"] == ReferenceCheckResult.WARNING
    assert "FS108E" in result["missing_parts"]


def test_order_item_coverage_partial_qty_returns_warning():
    po_items = [{"part_no": "FG81F", "description": "FortiGate 81F", "qty": "3"}]
    dc_items = [{"part_no": "FG81F", "description": "FortiGate 81F", "qty": "2"}]
    result = check_order_item_coverage(po_items, dc_items)
    assert result["result"] == ReferenceCheckResult.WARNING
    assert "FG81F" in result["partial_parts"]


def test_order_item_coverage_no_part_nos_skips():
    po_items = [{"description": "Some item", "qty": "1"}]   # no part_no
    dc_items = [{"description": "Some item", "qty": "1"}]
    result = check_order_item_coverage(po_items, dc_items)
    assert result["result"] == ReferenceCheckResult.SKIP
    assert result["skip_reason"] == "no_part_nos"


def test_order_item_coverage_empty_po_items_skips():
    result = check_order_item_coverage([], [{"part_no": "FG81F", "qty": "1"}])
    assert result["result"] == ReferenceCheckResult.SKIP
    assert result["skip_reason"] == "no_po_items"


def test_order_item_coverage_case_insensitive_part_matching():
    po_items = [{"part_no": "fg81f", "qty": "1"}]
    dc_items = [{"part_no": "FG81F", "qty": "1"}]
    result = check_order_item_coverage(po_items, dc_items)
    assert result["result"] == ReferenceCheckResult.PASS
