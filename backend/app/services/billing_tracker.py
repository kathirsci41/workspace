# backend/app/services/billing_tracker.py
"""Billing completeness tracking: FULL and STAGED billing types."""
import enum


class BillingStatus(str, enum.Enum):
    PENDING = "pending"       # No invoices yet
    PARTIAL = "partial"       # Some invoiced, not all
    COMPLETE = "complete"     # Fully invoiced within tolerance
    MISMATCH = "mismatch"     # Amount doesn't match expected milestone
    PAID = "paid"             # Stage is paid (used per-stage in STAGED)


_FULL_TOLERANCE = 0.01   # 1% tolerance for rounding on FULL billing
_STAGE_TOLERANCE = 0.05  # 5% tolerance per stage


def check_full_billing(
    invoiced_total: float,
    po_total: float,
) -> BillingStatus:
    """Check if total invoiced amount covers the PO total."""
    if po_total is None or po_total <= 0:
        return BillingStatus.PENDING
    if invoiced_total == 0:
        return BillingStatus.PENDING
    if invoiced_total >= po_total * (1 - _FULL_TOLERANCE):
        return BillingStatus.COMPLETE
    return BillingStatus.PARTIAL


def check_staged_billing(
    po_total: float,
    milestones: list[dict],
    stage_invoices: list[dict],
) -> dict:
    """
    Check staged billing completeness.

    milestones: [{stage: int, percent: float}]
    stage_invoices: [{billing_stage: int, amount: float}]

    Returns:
        {
          stages: [{stage, expected_amount, invoiced_amount, status}],
          overall: BillingStatus
        }
    """
    invoices_by_stage: dict[int, float] = {}
    for inv in stage_invoices:
        stage = inv.get("billing_stage")
        if stage is not None:
            invoices_by_stage[stage] = invoices_by_stage.get(stage, 0) + inv["amount"]

    stage_results = []
    all_complete = True
    any_paid = False
    any_mismatch = False

    for m in milestones:
        stage = m["stage"]
        expected = po_total * m["percent"] / 100
        invoiced = invoices_by_stage.get(stage, 0.0)

        if expected == 0:
            status = BillingStatus.PAID if invoiced == 0 else BillingStatus.MISMATCH
        elif invoiced == 0:
            status = BillingStatus.PENDING
            all_complete = False
        elif abs(invoiced - expected) / expected <= _STAGE_TOLERANCE:
            status = BillingStatus.PAID
            any_paid = True
        else:
            status = BillingStatus.MISMATCH
            all_complete = False
            any_mismatch = True

        stage_results.append({
            "stage": stage,
            "expected_amount": round(expected, 2),
            "invoiced_amount": round(invoiced, 2),
            "status": status,
        })

    if all_complete and any_paid:
        overall = BillingStatus.COMPLETE
    elif any_mismatch:
        overall = BillingStatus.MISMATCH
    elif any_paid:
        overall = BillingStatus.PARTIAL
    else:
        overall = BillingStatus.PENDING

    return {"stages": stage_results, "overall": overall}
