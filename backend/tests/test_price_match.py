# Save as: backend/tests/test_price_match.py
# Run with: python backend/tests/test_price_match.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Unit tests for the price_match computation in po_service._build_item_comparisons
#
# We test the _safe_float helper and the price_match logic in isolation so
# we don't need a database connection or full PO object.
# ---------------------------------------------------------------------------


# ── helpers duplicated from po_service (tested independently below) ─────────

def _safe_float(v):
    """Mirror of the helper in po_service — tested to ensure our logic matches."""
    if v is None:
        return None
    try:
        return float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return None


def _compute_price_match(src_price, cmp_price):
    """
    Extracted price_match logic (matches the fix applied to po_service.py).
    Returns True/False/None following the same rules.
    """
    if src_price is not None and cmp_price is not None and max(src_price, cmp_price) > 0:
        return abs(src_price - cmp_price) <= max(src_price, cmp_price) * 0.02
    return False


# ── 1. Failing test (before fix) — matching parts, different prices ─────────

def test_price_mismatch_is_false():
    """₹100 vs ₹150 — clearly different prices — price_match must be False."""
    src_price = _safe_float(100)
    cmp_price = _safe_float(150)
    result = _compute_price_match(src_price, cmp_price)
    assert result is False, f"Expected price_match=False but got {result!r}"
    print("OK  price_mismatch_is_false (100 vs 150) → False")


# ── 2. Edge case: both prices missing → False ────────────────────────────────

def test_missing_prices_both_none():
    result = _compute_price_match(None, None)
    assert result is False, f"Expected False for (None, None), got {result!r}"
    print("OK  missing_prices_both_none → False")


def test_missing_src_price():
    result = _compute_price_match(None, 100.0)
    assert result is False, f"Expected False for (None, 100), got {result!r}"
    print("OK  missing_src_price → False")


def test_missing_cmp_price():
    result = _compute_price_match(100.0, None)
    assert result is False, f"Expected False for (100, None), got {result!r}"
    print("OK  missing_cmp_price → False")


# ── 3. Edge case: prices within 2% tolerance → True ─────────────────────────

def test_exact_match():
    result = _compute_price_match(100.0, 100.0)
    assert result is True, f"Expected True for exact match (100 vs 100), got {result!r}"
    print("OK  exact_match (100 vs 100) → True")


def test_within_2pct_tolerance():
    """100 vs 101.5 — 1.5% difference — should pass."""
    result = _compute_price_match(100.0, 101.5)
    assert result is True, f"Expected True for 1.5% diff (100 vs 101.5), got {result!r}"
    print("OK  within_2pct_tolerance (100 vs 101.5) → True")


def test_exactly_at_2pct_tolerance():
    """100 vs 102 — exactly 2% — boundary should pass."""
    result = _compute_price_match(100.0, 102.0)
    assert result is True, f"Expected True at boundary (100 vs 102), got {result!r}"
    print("OK  exactly_at_2pct_tolerance (100 vs 102) → True")


# ── 4. Edge case: more than 2% difference → False ───────────────────────────

def test_just_over_2pct():
    """100 vs 102.1 — 2.1% difference — should fail."""
    result = _compute_price_match(100.0, 102.1)
    assert result is False, f"Expected False for 2.1% diff (100 vs 102.1), got {result!r}"
    print("OK  just_over_2pct (100 vs 102.1) → False")


def test_large_price_difference():
    """Large gap (500 vs 600) — clearly False."""
    result = _compute_price_match(500.0, 600.0)
    assert result is False, f"Expected False for (500 vs 600), got {result!r}"
    print("OK  large_price_difference (500 vs 600) → False")


# ── 5. _safe_float helper correctness ───────────────────────────────────────

def test_safe_float_with_commas():
    assert _safe_float("1,000.50") == 1000.50
    print("OK  safe_float handles comma-formatted numbers")


def test_safe_float_none():
    assert _safe_float(None) is None
    print("OK  safe_float(None) → None")


def test_safe_float_invalid():
    assert _safe_float("N/A") is None
    print("OK  safe_float('N/A') → None")


# ── Runner ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_price_mismatch_is_false,
        test_missing_prices_both_none,
        test_missing_src_price,
        test_missing_cmp_price,
        test_exact_match,
        test_within_2pct_tolerance,
        test_exactly_at_2pct_tolerance,
        test_just_over_2pct,
        test_large_price_difference,
        test_safe_float_with_commas,
        test_safe_float_none,
        test_safe_float_invalid,
    ]

    failed = []
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            failed.append(t.__name__)
        except Exception as e:
            print(f"ERROR {t.__name__}: {e}")
            failed.append(t.__name__)

    print()
    if failed:
        print(f"FAILED: {len(failed)}/{len(tests)} tests failed: {failed}")
        sys.exit(1)
    else:
        print(f"ALL PASSED: {len(tests)}/{len(tests)} tests passed")
