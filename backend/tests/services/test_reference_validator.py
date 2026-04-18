from app.services.reference_validator import (
    check_so_consistency,
    check_cpo_reference,
    check_vpo_reference,
    ReferenceCheckResult,
)


def test_so_match_returns_pass():
    result = check_so_consistency(
        extracted_so="1OTM2526001429",
        expected_so="1OTM2526001429",
    )
    assert result == ReferenceCheckResult.PASS


def test_so_mismatch_returns_mismatch():
    result = check_so_consistency(
        extracted_so="1OTM9999999999",
        expected_so="1OTM2526001429",
    )
    assert result == ReferenceCheckResult.MISMATCH


def test_so_none_extracted_returns_skip():
    result = check_so_consistency(extracted_so=None, expected_so="1OTM2526001429")
    assert result == ReferenceCheckResult.SKIP


def test_cpo_reference_match():
    result = check_cpo_reference(
        extracted_cpo_ref="PWFA251127016",
        expected_po_number="PWFA251127016",
    )
    assert result == ReferenceCheckResult.PASS


def test_cpo_reference_mismatch():
    result = check_cpo_reference(
        extracted_cpo_ref="WRONG123",
        expected_po_number="PWFA251127016",
    )
    assert result == ReferenceCheckResult.MISMATCH


def test_vpo_reference_all_vpos_covered_returns_pass():
    """All registered VPOs present → PASS."""
    result = check_vpo_reference(
        doc_vpo_numbers_list=[["1PTR2526000400", "1PTR2526000401"]],
        registered_vpo_numbers=["1PTR2526000400", "1PTR2526000401"],
    )
    assert result == ReferenceCheckResult.PASS


def test_vpo_reference_partial_coverage_returns_mismatch():
    """Only one of two registered VPOs present → MISMATCH (AND-logic)."""
    result = check_vpo_reference(
        doc_vpo_numbers_list=[["1PTR2526000400"]],
        registered_vpo_numbers=["1PTR2526000400", "1PTR2526000401"],
    )
    assert result == ReferenceCheckResult.MISMATCH


def test_vpo_reference_vpos_spread_across_invoices_returns_pass():
    """VPOs split across multiple invoices → all covered → PASS."""
    result = check_vpo_reference(
        doc_vpo_numbers_list=[["1PTR2526000400"], ["1PTR2526000401"]],
        registered_vpo_numbers=["1PTR2526000400", "1PTR2526000401"],
    )
    assert result == ReferenceCheckResult.PASS


def test_vpo_reference_no_match_returns_mismatch():
    result = check_vpo_reference(
        doc_vpo_numbers_list=[["9POT9999999999"]],
        registered_vpo_numbers=["1PTR2526000400"],
    )
    assert result == ReferenceCheckResult.MISMATCH


def test_vpo_reference_empty_doc_vpos_returns_skip():
    result = check_vpo_reference(
        doc_vpo_numbers_list=[[]],
        registered_vpo_numbers=["1PTR2526000400"],
    )
    assert result == ReferenceCheckResult.SKIP


def test_vpo_reference_empty_registered_vpos_returns_skip():
    result = check_vpo_reference(
        doc_vpo_numbers_list=[["1PTR2526000400"]],
        registered_vpo_numbers=[],
    )
    assert result == ReferenceCheckResult.SKIP
