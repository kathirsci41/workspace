from app.services.cross_doc_validator import (
    check_ci_vs_cpo_total,
    check_vinv_sum_vs_vpo_total,
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
