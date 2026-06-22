from app.services.tolerance_config import DEFAULT_TOLERANCE, ToleranceConfig


def test_exact_match_passes():
    assert DEFAULT_TOLERANCE.passes(1000, 1000)


def test_within_percentage_passes():
    # 2% of 1000 = 20
    assert DEFAULT_TOLERANCE.passes(1000, 1015)
    assert not DEFAULT_TOLERANCE.passes(1000, 1025)


def test_absolute_floor_for_small_amounts():
    # 2% of 100 = 2, but ₹5 floor wins
    assert DEFAULT_TOLERANCE.passes(100, 104)
    assert not DEFAULT_TOLERANCE.passes(100, 106)


def test_large_partial_billing_gap_stays_flagged():
    assert not DEFAULT_TOLERANCE.passes(696200, 554600)


def test_per_field_override():
    tol = ToleranceConfig(per_field={"quantity": 0.0})
    assert tol.passes(10, 10, "quantity")
    assert tol.passes(10, 11, "quantity")
    # The absolute floor still applies; use a bigger gap to fail.
    assert not tol.passes(10, 20, "quantity")


def test_diff_pct():
    assert round(DEFAULT_TOLERANCE.diff_pct(1000, 1100), 1) == 9.1
