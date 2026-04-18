"""Cross-document integrity validation: Module 3A–3F checks."""
from datetime import date
from difflib import SequenceMatcher

from app.services.reference_validator import ReferenceCheckResult

_AMOUNT_TOLERANCE_CI   = 0.01   # 1% — Company Invoice vs Customer PO (strict)
_AMOUNT_TOLERANCE_VINV = 0.05   # 5% — Vendor Invoice sum vs Company PO (freight allowed)
_NAME_FUZZY_RATIO      = 0.85   # 85% similarity for name match


# ── Module 3A: Amount Integrity ──────────────────────────────────────────────

def check_ci_vs_cpo_total(
    ci_total: float | None,
    cpo_total: float | None,
) -> ReferenceCheckResult:
    """Company Invoice total must match Customer PO total within 1%."""
    if not ci_total or not cpo_total or cpo_total <= 0:
        return ReferenceCheckResult.SKIP
    if abs(ci_total - cpo_total) / cpo_total > _AMOUNT_TOLERANCE_CI:
        return ReferenceCheckResult.MISMATCH
    return ReferenceCheckResult.PASS


def check_vinv_sum_vs_vpo_total(
    vinv_totals: list[float],
    vpo_total: float | None,
) -> ReferenceCheckResult:
    """Sum of all Vendor Invoice totals vs Company PO total — WARNING if >5% diff (freight allowed)."""
    if not vinv_totals or not vpo_total or vpo_total <= 0:
        return ReferenceCheckResult.SKIP
    ratio = abs(sum(vinv_totals) - vpo_total) / vpo_total
    return ReferenceCheckResult.WARNING if ratio > _AMOUNT_TOLERANCE_VINV else ReferenceCheckResult.PASS
