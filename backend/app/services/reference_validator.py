"""Cross-document reference validation: SO, CPO, and VPO consistency checks."""
import enum


class ReferenceCheckResult(str, enum.Enum):
    PASS = "pass"
    MISMATCH = "mismatch"
    WARNING = "warning"   # Unusual but not an audit failure - does NOT flip chain_status
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
    doc_vpo_numbers_list: list[list[str]],
    registered_vpo_numbers: list[str],
) -> ReferenceCheckResult:
    """
    Check that ALL registered VPO numbers are covered by at least one vendor invoice.

    doc_vpo_numbers_list: one list per VENDOR_INVOICE document.
    registered_vpo_numbers: VPOs registered on the CPO.

    Returns PASS only when every registered VPO appears in at least one invoice.
    """
    if not registered_vpo_numbers:
        return ReferenceCheckResult.SKIP
    if not doc_vpo_numbers_list:
        return ReferenceCheckResult.SKIP  # no invoices present at all — missing slot, not mismatch
    all_invoice_vpos = {v.strip() for vpo_list in doc_vpo_numbers_list for v in vpo_list}
    if not all_invoice_vpos:
        return ReferenceCheckResult.MISMATCH  # invoices exist but no VPO found on any of them
    registered_set = {v.strip() for v in registered_vpo_numbers}
    if registered_set.issubset(all_invoice_vpos):
        return ReferenceCheckResult.PASS
    return ReferenceCheckResult.MISMATCH
