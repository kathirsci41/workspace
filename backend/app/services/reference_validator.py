"""Cross-document reference validation: SO, CPO, and VPO consistency checks."""
import enum


class ReferenceCheckResult(str, enum.Enum):
    PASS = "pass"
    MISMATCH = "mismatch"
    SKIP = "skip"   # extracted value was None/empty — cannot validate


def check_so_consistency(
    extracted_so: str | None,
    expected_so: str | None,
) -> ReferenceCheckResult:
    """Check that extracted SO number matches operator-entered SO number."""
    if not extracted_so or not expected_so:
        return ReferenceCheckResult.SKIP
    return (
        ReferenceCheckResult.PASS
        if extracted_so.strip() == expected_so.strip()
        else ReferenceCheckResult.MISMATCH
    )


def check_cpo_reference(
    extracted_cpo_ref: str | None,
    expected_po_number: str | None,
) -> ReferenceCheckResult:
    """Check that document's customer_order_no matches the CPO number."""
    if not extracted_cpo_ref or not expected_po_number:
        return ReferenceCheckResult.SKIP
    return (
        ReferenceCheckResult.PASS
        if extracted_cpo_ref.strip() == expected_po_number.strip()
        else ReferenceCheckResult.MISMATCH
    )


def check_vpo_reference(
    doc_vpo_numbers: list[str],
    registered_vpo_numbers: list[str],
) -> ReferenceCheckResult:
    """Check that vendor invoice VPO numbers intersect registered VPOs for this CPO."""
    if not doc_vpo_numbers:
        return ReferenceCheckResult.SKIP
    if not registered_vpo_numbers:
        return ReferenceCheckResult.SKIP
    registered_set = {v.strip() for v in registered_vpo_numbers}
    for vpo in doc_vpo_numbers:
        if vpo.strip() in registered_set:
            return ReferenceCheckResult.PASS
    return ReferenceCheckResult.MISMATCH
