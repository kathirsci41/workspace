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


# ── Module 3D: Document Cross-References ────────────────────────────────────

def check_dc_ref_on_ci(
    cdc_dc_numbers: list[str],
    ci_dc_refs: list[str | None],
) -> ReferenceCheckResult:
    """Company Invoice should reference at least one Company DC number. WARNING if missing."""
    if not cdc_dc_numbers:
        return ReferenceCheckResult.SKIP
    refs_text = " ".join(r for r in ci_dc_refs if r)
    if not refs_text:
        return ReferenceCheckResult.SKIP
    for dc_num in cdc_dc_numbers:
        if dc_num and dc_num.upper() in refs_text.upper():
            return ReferenceCheckResult.PASS
    return ReferenceCheckResult.WARNING


def check_vpo_ref_on_vdc(
    vdc_po_refs: list[str | None],
    vpo_numbers: list[str],
) -> ReferenceCheckResult:
    """Vendor DC should cite Company PO number. WARNING if missing."""
    if not vpo_numbers:
        return ReferenceCheckResult.SKIP
    refs = {r.upper().strip() for r in vdc_po_refs if r}
    if not refs:
        return ReferenceCheckResult.SKIP
    vpos = {v.upper().strip() for v in vpo_numbers}
    return ReferenceCheckResult.PASS if refs & vpos else ReferenceCheckResult.WARNING


def check_vdc_ref_on_vinv(
    vdc_dc_numbers: list[str],
    vinv_dc_refs: list[str | None],
) -> ReferenceCheckResult:
    """Vendor Invoice should reference Vendor DC number. WARNING if missing."""
    if not vdc_dc_numbers:
        return ReferenceCheckResult.SKIP
    refs_text = " ".join(r for r in vinv_dc_refs if r)
    if not refs_text:
        return ReferenceCheckResult.SKIP
    for dc_num in vdc_dc_numbers:
        if dc_num and dc_num.upper() in refs_text.upper():
            return ReferenceCheckResult.PASS
    return ReferenceCheckResult.WARNING


# ── Module 3E: Date Sequence Validation ─────────────────────────────────────

_DATE_ORDER = [
    "CUSTOMER_PO",
    "COMPANY_PO",
    "VENDOR_DC",
    "VENDOR_INVOICE",
    "COMPANY_DC",
    "COMPANY_INVOICE",
]


def check_date_sequence(
    dated_docs: list[dict],
) -> list[dict]:
    """
    Check document dates follow logical order.
    dated_docs: [{"document_type": str, "doc_date": date | None}]
    Returns list of violation dicts; empty list = no violations.
    1-day tolerance for same-day processing edge cases.
    """
    by_type: dict[str, date] = {}
    for doc in dated_docs:
        dt = doc.get("doc_date")
        dtype = doc.get("document_type")
        if dt and dtype and dtype not in by_type:
            by_type[str(dtype)] = dt

    violations = []
    for i, earlier_type in enumerate(_DATE_ORDER):
        for later_type in _DATE_ORDER[i + 1:]:
            if earlier_type in by_type and later_type in by_type:
                delta = (by_type[later_type] - by_type[earlier_type]).days
                if delta < -1:
                    violations.append({
                        "earlier_type": earlier_type,
                        "later_type": later_type,
                        "delta_days": delta,
                        "result": ReferenceCheckResult.WARNING,
                    })
    return violations


# ── Module 3F: HSN Code Consistency ─────────────────────────────────────────

def check_hsn_consistency(
    loop_docs: list[dict],
) -> list[dict]:
    """
    Check that the same part_no has the same HSN code across all documents in a loop.
    loop_docs: [{"document_type": str, "order_items": [{"part_no": str, "hsn_code": str}]}]
    Returns list of violations — empty = consistent.
    """
    part_hsn: dict[str, set[str]] = {}
    for doc in loop_docs:
        for item in (doc.get("order_items") or []):
            part_no = str(item.get("part_no") or "").upper().strip()
            hsn = str(item.get("hsn_code") or "").strip()
            if part_no and hsn:
                part_hsn.setdefault(part_no, set()).add(hsn)

    return [
        {"part_no": part_no, "hsn_values": sorted(hsn_set), "result": ReferenceCheckResult.WARNING}
        for part_no, hsn_set in part_hsn.items()
        if len(hsn_set) > 1
    ]
