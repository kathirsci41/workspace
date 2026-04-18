from app.services.cross_doc_validator import (
    check_ci_vs_cpo_total,
    check_vinv_sum_vs_vpo_total,
    check_gstin_consistency,
    check_name_consistency,
    check_serial_chain,
    check_vdc_vs_vinv_serials,
)
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
