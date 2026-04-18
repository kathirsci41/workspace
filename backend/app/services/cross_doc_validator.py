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


# ── Module 3B: GSTIN and Name Consistency ────────────────────────────────────

def check_gstin_consistency(gstins: list[str | None]) -> ReferenceCheckResult:
    """All GSTINs in the list must be identical (case/whitespace normalised)."""
    valid = [g.strip().upper() for g in gstins if g and g.strip()]
    if len(valid) < 2:
        return ReferenceCheckResult.SKIP
    return ReferenceCheckResult.PASS if len(set(valid)) == 1 else ReferenceCheckResult.MISMATCH


def check_name_consistency(names: list[str | None]) -> ReferenceCheckResult:
    """Names should fuzzy-match at ≥85% ratio. Returns WARNING (not MISMATCH) — typos are common."""
    valid = [n.strip().lower() for n in names if n and n.strip()]
    if len(valid) < 2:
        return ReferenceCheckResult.SKIP
    first = valid[0]
    for name in valid[1:]:
        if SequenceMatcher(None, first, name).ratio() < _NAME_FUZZY_RATIO:
            return ReferenceCheckResult.WARNING
    return ReferenceCheckResult.PASS


# ── Module 3C: Serial Number Chain of Custody ────────────────────────────────

def check_serial_chain(
    vinv_serials: list[list[str]],
    cdc_serials: list[list[str]],
) -> dict:
    """
    All serials received from vendor (VINV) must appear in at least one Company DC.
    CDC can have MORE serials (stock items) — only FEWER is a problem.
    """
    received = {s.upper().strip() for sl in vinv_serials for s in sl if s.strip()}
    shipped  = {s.upper().strip() for sl in cdc_serials  for s in sl if s.strip()}
    if not received:
        return {"result": ReferenceCheckResult.SKIP, "missing": [], "skip_reason": "no_vendor_serials"}
    if not shipped:
        return {"result": ReferenceCheckResult.SKIP, "missing": [], "skip_reason": "no_cdc_serials"}
    missing = sorted(received - shipped)
    return {
        "result": ReferenceCheckResult.MISMATCH if missing else ReferenceCheckResult.PASS,
        "missing": missing,
        "skip_reason": None,
    }


def check_vdc_vs_vinv_serials(
    vdc_serials: list[str],
    vinv_serials: list[list[str]],
) -> dict:
    """All serials on Vendor DC must appear on at least one Vendor Invoice."""
    vdc_set  = {s.upper().strip() for s in vdc_serials if s.strip()}
    vinv_set = {s.upper().strip() for sl in vinv_serials for s in sl if s.strip()}
    if not vdc_set:
        return {"result": ReferenceCheckResult.SKIP, "missing": [], "skip_reason": "no_vdc_serials"}
    if not vinv_set:
        return {"result": ReferenceCheckResult.SKIP, "missing": [], "skip_reason": "no_vinv_serials"}
    missing = sorted(vdc_set - vinv_set)
    return {
        "result": ReferenceCheckResult.MISMATCH if missing else ReferenceCheckResult.PASS,
        "missing": missing,
        "skip_reason": None,
    }
