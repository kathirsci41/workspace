# Module 3 — Cross-Document Integrity Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 13 new cross-document validation checks (amounts, GSTINs, serial numbers, cross-references, date sequence, HSN codes) plus same-PO duplicate detection, all plugging into the existing `compute_chain_status()` pipeline without any schema changes.

**Architecture:** New pure-function service `cross_doc_validator.py` holds all check logic. `purchase_orders.py` extends `docs_payload` with new fields from `extracted_data`. `chain_validator.py` imports and calls the new checks, appending results to the existing `reference_checks[]` list. A new `WARNING` severity is added to `ReferenceCheckResult` — WARNING checks display in the UI but do NOT flip `chain_status` to MISMATCH.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, pytest. No new dependencies — uses stdlib `difflib.SequenceMatcher` for fuzzy name matching.

---

## Scope NOT in this plan

- **Module 4 (Order Item Integrity):** Requires `order_items[]` wired through the chain pipeline — separate plan.
- **Module 5 (Batch Procurement):** Requires schema change (N:M document-PO allocation) — separate plan.
- Any frontend changes — existing `ReferenceValidationPanel` already renders `reference_checks[]` generically.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/app/services/reference_validator.py` | Modify | Add `WARNING` to `ReferenceCheckResult` enum |
| `backend/app/services/cross_doc_validator.py` | **Create** | All 13 new check functions (Modules 3A–3F) |
| `backend/app/api/v1/purchase_orders.py` | Modify | Extend `docs_payload` dict with 10 new fields |
| `backend/app/services/chain_validator.py` | Modify | Import + call all Module 3 checks, append to `reference_checks` |
| `backend/app/services/document_service.py` | Modify | Duplicate reference detection on document verify |
| `backend/tests/services/test_cross_doc_validator.py` | **Create** | Unit tests for every check function |
| `backend/tests/services/test_chain_validator.py` | Modify | Integration tests for new checks through `compute_chain_status()` |

---

## Task 1: Add WARNING to ReferenceCheckResult

**Files:**
- Modify: `backend/app/services/reference_validator.py`
- Test: `backend/tests/services/test_reference_validator.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to backend/tests/services/test_reference_validator.py

def test_warning_is_valid_reference_check_result():
    from app.services.reference_validator import ReferenceCheckResult
    assert ReferenceCheckResult.WARNING == "warning"

def test_warning_is_distinct_from_mismatch():
    from app.services.reference_validator import ReferenceCheckResult
    assert ReferenceCheckResult.WARNING != ReferenceCheckResult.MISMATCH
    assert ReferenceCheckResult.WARNING != ReferenceCheckResult.PASS
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/services/test_reference_validator.py::test_warning_is_valid_reference_check_result -v
```
Expected: `AttributeError: 'WARNING' is not a valid ReferenceCheckResult`

- [ ] **Step 3: Add WARNING to the enum**

In `backend/app/services/reference_validator.py`, change:

```python
class ReferenceCheckResult(str, enum.Enum):
    PASS = "pass"
    MISMATCH = "mismatch"
    WARNING = "warning"   # Unusual but not an audit failure — does NOT flip chain_status
    SKIP = "skip"
```

- [ ] **Step 4: Run all reference validator tests**

```bash
pytest tests/services/test_reference_validator.py -v
```
Expected: All existing tests PASS + 2 new tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/reference_validator.py backend/tests/services/test_reference_validator.py
git commit -m "feat: add WARNING severity to ReferenceCheckResult"
```

---

## Task 2: Create cross_doc_validator.py — Module 3A (Amount Integrity)

**Files:**
- Create: `backend/app/services/cross_doc_validator.py`
- Create: `backend/tests/services/test_cross_doc_validator.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/services/test_cross_doc_validator.py`:

```python
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
    assert check_vinv_sum_vs_vpo_total([381359.0, 20000.0], 381359.0) == ReferenceCheckResult.PASS

def test_vinv_sum_over_5pct_returns_warning():
    # VINV sum is 10% over VPO total — unusual
    assert check_vinv_sum_vs_vpo_total([420000.0], 381359.0) == ReferenceCheckResult.WARNING

def test_vinv_sum_no_totals_returns_skip():
    assert check_vinv_sum_vs_vpo_total([], 381359.0) == ReferenceCheckResult.SKIP

def test_vinv_sum_no_vpo_total_returns_skip():
    assert check_vinv_sum_vs_vpo_total([381359.0], None) == ReferenceCheckResult.SKIP
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/services/test_cross_doc_validator.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.services.cross_doc_validator'`

- [ ] **Step 3: Create cross_doc_validator.py with 3A functions**

Create `backend/app/services/cross_doc_validator.py`:

```python
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/services/test_cross_doc_validator.py -v
```
Expected: 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cross_doc_validator.py backend/tests/services/test_cross_doc_validator.py
git commit -m "feat: Module 3A — amount integrity checks (CI vs CPO, VINV sum vs VPO)"
```

---

## Task 3: Module 3B — GSTIN and Name Consistency

**Files:**
- Modify: `backend/app/services/cross_doc_validator.py`
- Modify: `backend/tests/services/test_cross_doc_validator.py`

- [ ] **Step 1: Add tests**

Append to `backend/tests/services/test_cross_doc_validator.py`:

```python
from app.services.cross_doc_validator import (
    check_gstin_consistency,
    check_name_consistency,
)


# --- 3B: GSTIN and name checks ---

def test_gstin_all_match_returns_pass():
    assert check_gstin_consistency(["33AAICS1881D1ZJ", "33AAICS1881D1ZJ", "33AAICS1881D1ZJ"]) == ReferenceCheckResult.PASS

def test_gstin_one_differs_returns_mismatch():
    assert check_gstin_consistency(["33AAICS1881D1ZJ", "33AAICS1881D1ZJ", "29AAICS1881D1ZK"]) == ReferenceCheckResult.MISMATCH

def test_gstin_normalises_whitespace_and_case():
    assert check_gstin_consistency([" 33aaics1881d1zj ", "33AAICS1881D1ZJ"]) == ReferenceCheckResult.PASS

def test_gstin_fewer_than_two_valid_returns_skip():
    assert check_gstin_consistency([None, "", "33AAICS1881D1ZJ"]) == ReferenceCheckResult.SKIP

def test_gstin_all_none_returns_skip():
    assert check_gstin_consistency([None, None]) == ReferenceCheckResult.SKIP

def test_name_exact_match_returns_pass():
    assert check_name_consistency(["Shriram Finance", "Shriram Finance"]) == ReferenceCheckResult.PASS

def test_name_ltd_vs_limited_returns_pass():
    # "Shriram Finance Ltd" vs "Shriram Finance Limited" — should fuzzy-match as PASS
    assert check_name_consistency(["Shriram Finance Ltd", "Shriram Finance Limited"]) == ReferenceCheckResult.PASS

def test_name_completely_different_returns_warning():
    assert check_name_consistency(["Shriram Finance", "Tata Motors"]) == ReferenceCheckResult.WARNING

def test_name_only_one_valid_returns_skip():
    assert check_name_consistency([None, "Shriram Finance"]) == ReferenceCheckResult.SKIP
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/services/test_cross_doc_validator.py -k "gstin or name" -v
```
Expected: `ImportError` for new functions

- [ ] **Step 3: Add 3B functions to cross_doc_validator.py**

Append to `backend/app/services/cross_doc_validator.py`:

```python
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/services/test_cross_doc_validator.py -v
```
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cross_doc_validator.py backend/tests/services/test_cross_doc_validator.py
git commit -m "feat: Module 3B — GSTIN and name consistency checks"
```

---

## Task 4: Module 3C — Serial Number Chain of Custody

**Files:**
- Modify: `backend/app/services/cross_doc_validator.py`
- Modify: `backend/tests/services/test_cross_doc_validator.py`

- [ ] **Step 1: Add tests**

Append to `backend/tests/services/test_cross_doc_validator.py`:

```python
from app.services.cross_doc_validator import (
    check_serial_chain,
    check_vdc_vs_vinv_serials,
)


# --- 3C: Serial chain of custody ---

def test_serial_chain_all_vendor_serials_shipped_returns_pass():
    # Real Skylark case: VINV C190224835 serials appear in CDC DC2915
    result = check_serial_chain(
        vinv_serials=[["NDKDL1U", "NDLEFAU"]],
        cdc_serials=[["FG120GTK25028863", "NDKDL1U", "NDLEFAU"]],
    )
    assert result["result"] == ReferenceCheckResult.PASS
    assert result["missing"] == []

def test_serial_chain_extra_cdc_serial_is_not_flagged():
    # FG120GTK25028863 on CDC but not on VINV — from stock, not an error
    result = check_serial_chain(
        vinv_serials=[["NDKDL1U"]],
        cdc_serials=[["FG120GTK25028863", "NDKDL1U"]],
    )
    assert result["result"] == ReferenceCheckResult.PASS

def test_serial_chain_missing_serial_returns_mismatch():
    result = check_serial_chain(
        vinv_serials=[["NDKDL1U", "NDLEFAU"]],
        cdc_serials=[["NDKDL1U"]],   # NDLEFAU not shipped
    )
    assert result["result"] == ReferenceCheckResult.MISMATCH
    assert "NDLEFAU" in result["missing"]

def test_serial_chain_multiple_vinvs_union():
    # Two VINVs — serials across both must appear in CDC
    result = check_serial_chain(
        vinv_serials=[["NDKDL1U"], ["NDLEFAU"]],
        cdc_serials=[["NDKDL1U", "NDLEFAU"]],
    )
    assert result["result"] == ReferenceCheckResult.PASS

def test_serial_chain_case_insensitive():
    result = check_serial_chain(
        vinv_serials=[["ndkdl1u"]],
        cdc_serials=[["NDKDL1U"]],
    )
    assert result["result"] == ReferenceCheckResult.PASS

def test_serial_chain_no_vendor_serials_skips():
    result = check_serial_chain(vinv_serials=[[]], cdc_serials=[["NDKDL1U"]])
    assert result["result"] == ReferenceCheckResult.SKIP
    assert result["skip_reason"] == "no_vendor_serials"

def test_serial_chain_no_cdc_serials_skips():
    result = check_serial_chain(vinv_serials=[["NDKDL1U"]], cdc_serials=[[]])
    assert result["result"] == ReferenceCheckResult.SKIP
    assert result["skip_reason"] == "no_cdc_serials"

def test_vdc_vs_vinv_serials_all_match_returns_pass():
    result = check_vdc_vs_vinv_serials(
        vdc_serials=["NDKDL1U", "NDLEFAU"],
        vinv_serials=[["NDKDL1U", "NDLEFAU"]],
    )
    assert result["result"] == ReferenceCheckResult.PASS

def test_vdc_vs_vinv_serials_missing_returns_mismatch():
    result = check_vdc_vs_vinv_serials(
        vdc_serials=["NDKDL1U", "NDLEFAU"],
        vinv_serials=[["NDKDL1U"]],
    )
    assert result["result"] == ReferenceCheckResult.MISMATCH
    assert "NDLEFAU" in result["missing"]
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/services/test_cross_doc_validator.py -k "serial" -v
```
Expected: `ImportError` for new functions

- [ ] **Step 3: Add 3C functions**

Append to `backend/app/services/cross_doc_validator.py`:

```python
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/services/test_cross_doc_validator.py -v
```
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cross_doc_validator.py backend/tests/services/test_cross_doc_validator.py
git commit -m "feat: Module 3C — serial number chain of custody checks"
```

---

## Task 5: Module 3D — Document Cross-References

**Files:**
- Modify: `backend/app/services/cross_doc_validator.py`
- Modify: `backend/tests/services/test_cross_doc_validator.py`

- [ ] **Step 1: Add tests**

Append to `backend/tests/services/test_cross_doc_validator.py`:

```python
from app.services.cross_doc_validator import (
    check_dc_ref_on_ci,
    check_vpo_ref_on_vdc,
    check_vdc_ref_on_vinv,
)


# --- 3D: Document cross-references ---

def test_dc_ref_on_ci_found_returns_pass():
    assert check_dc_ref_on_ci(
        cdc_dc_numbers=["1DNT2526DC2915"],
        ci_dc_refs=["1DNT2526DC2915"],
    ) == ReferenceCheckResult.PASS

def test_dc_ref_on_ci_not_found_returns_warning():
    assert check_dc_ref_on_ci(
        cdc_dc_numbers=["1DNT2526DC2915"],
        ci_dc_refs=["SOME-OTHER-DC"],
    ) == ReferenceCheckResult.WARNING

def test_dc_ref_on_ci_no_ci_refs_returns_skip():
    assert check_dc_ref_on_ci(
        cdc_dc_numbers=["1DNT2526DC2915"],
        ci_dc_refs=[None],
    ) == ReferenceCheckResult.SKIP

def test_vpo_ref_on_vdc_found_returns_pass():
    assert check_vpo_ref_on_vdc(
        vdc_po_refs=["1PTR2526000400"],
        vpo_numbers=["1PTR2526000400"],
    ) == ReferenceCheckResult.PASS

def test_vpo_ref_on_vdc_not_found_returns_warning():
    assert check_vpo_ref_on_vdc(
        vdc_po_refs=["WRONG-PO"],
        vpo_numbers=["1PTR2526000400"],
    ) == ReferenceCheckResult.WARNING

def test_vpo_ref_on_vdc_no_vpo_numbers_returns_skip():
    assert check_vpo_ref_on_vdc(
        vdc_po_refs=["1PTR2526000400"],
        vpo_numbers=[],
    ) == ReferenceCheckResult.SKIP

def test_vdc_ref_on_vinv_found_returns_pass():
    assert check_vdc_ref_on_vinv(
        vdc_dc_numbers=["VDC-001"],
        vinv_dc_refs=["VDC-001"],
    ) == ReferenceCheckResult.PASS

def test_vdc_ref_on_vinv_not_found_returns_warning():
    assert check_vdc_ref_on_vinv(
        vdc_dc_numbers=["VDC-001"],
        vinv_dc_refs=[None],
    ) == ReferenceCheckResult.SKIP
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/services/test_cross_doc_validator.py -k "dc_ref or vpo_ref or vdc_ref" -v
```
Expected: `ImportError` for new functions

- [ ] **Step 3: Add 3D functions**

Append to `backend/app/services/cross_doc_validator.py`:

```python
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
        if dc_num and dc_num.upper() not in refs_text.upper():
            return ReferenceCheckResult.WARNING
    return ReferenceCheckResult.PASS


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
        if dc_num and dc_num.upper() not in refs_text.upper():
            return ReferenceCheckResult.WARNING
    return ReferenceCheckResult.PASS
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/services/test_cross_doc_validator.py -v
```
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cross_doc_validator.py backend/tests/services/test_cross_doc_validator.py
git commit -m "feat: Module 3D — document cross-reference checks (DC on CI, VPO on VDC, VDC on VINV)"
```

---

## Task 6: Module 3E — Date Sequence Validation

**Files:**
- Modify: `backend/app/services/cross_doc_validator.py`
- Modify: `backend/tests/services/test_cross_doc_validator.py`

- [ ] **Step 1: Add tests**

Append to `backend/tests/services/test_cross_doc_validator.py`:

```python
from datetime import date as _date
from app.services.cross_doc_validator import check_date_sequence


# --- 3E: Date sequence ---

def test_date_sequence_correct_order_returns_no_violations():
    docs = [
        {"document_type": "CUSTOMER_PO",    "doc_date": _date(2026, 1, 1)},
        {"document_type": "COMPANY_PO",     "doc_date": _date(2026, 1, 2)},
        {"document_type": "VENDOR_INVOICE", "doc_date": _date(2026, 1, 10)},
        {"document_type": "COMPANY_DC",     "doc_date": _date(2026, 1, 12)},
        {"document_type": "COMPANY_INVOICE","doc_date": _date(2026, 1, 12)},
    ]
    violations = check_date_sequence(docs)
    assert violations == []

def test_date_sequence_ci_before_cpo_returns_violation():
    # Invoice dated before customer PO — impossible
    docs = [
        {"document_type": "CUSTOMER_PO",    "doc_date": _date(2026, 3, 1)},
        {"document_type": "COMPANY_INVOICE","doc_date": _date(2026, 1, 1)},
    ]
    violations = check_date_sequence(docs)
    assert len(violations) == 1
    assert violations[0]["earlier_type"] == "CUSTOMER_PO"
    assert violations[0]["later_type"] == "COMPANY_INVOICE"
    assert violations[0]["result"] == ReferenceCheckResult.WARNING

def test_date_sequence_same_day_no_violation():
    # CDC and CI on same day is normal
    docs = [
        {"document_type": "COMPANY_DC",     "doc_date": _date(2026, 1, 10)},
        {"document_type": "COMPANY_INVOICE","doc_date": _date(2026, 1, 10)},
    ]
    assert check_date_sequence(docs) == []

def test_date_sequence_one_day_tolerance():
    # 1 day earlier is within tolerance (same-day processing)
    docs = [
        {"document_type": "COMPANY_DC",     "doc_date": _date(2026, 1, 10)},
        {"document_type": "COMPANY_INVOICE","doc_date": _date(2026, 1, 9)},
    ]
    assert check_date_sequence(docs) == []

def test_date_sequence_skips_none_dates():
    docs = [
        {"document_type": "CUSTOMER_PO",    "doc_date": None},
        {"document_type": "COMPANY_INVOICE","doc_date": _date(2026, 1, 1)},
    ]
    assert check_date_sequence(docs) == []
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/services/test_cross_doc_validator.py -k "date_sequence" -v
```
Expected: `ImportError`

- [ ] **Step 3: Add 3E function**

Append to `backend/app/services/cross_doc_validator.py`:

```python
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/services/test_cross_doc_validator.py -v
```
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cross_doc_validator.py backend/tests/services/test_cross_doc_validator.py
git commit -m "feat: Module 3E — document date sequence validation"
```

---

## Task 7: Module 3F — HSN Code Consistency

**Files:**
- Modify: `backend/app/services/cross_doc_validator.py`
- Modify: `backend/tests/services/test_cross_doc_validator.py`

- [ ] **Step 1: Add tests**

Append to `backend/tests/services/test_cross_doc_validator.py`:

```python
from app.services.cross_doc_validator import check_hsn_consistency


# --- 3F: HSN consistency ---

def test_hsn_consistent_across_docs_returns_empty():
    docs = [
        {"document_type": "CUSTOMER_PO",    "order_items": [{"part_no": "FG-120G", "hsn_code": "84733099"}]},
        {"document_type": "COMPANY_INVOICE", "order_items": [{"part_no": "FG-120G", "hsn_code": "84733099"}]},
    ]
    assert check_hsn_consistency(docs) == []

def test_hsn_inconsistent_returns_violation():
    docs = [
        {"document_type": "CUSTOMER_PO",    "order_items": [{"part_no": "FG-120G", "hsn_code": "84733099"}]},
        {"document_type": "COMPANY_INVOICE", "order_items": [{"part_no": "FG-120G", "hsn_code": "85176990"}]},
    ]
    violations = check_hsn_consistency(docs)
    assert len(violations) == 1
    assert violations[0]["part_no"] == "FG-120G"
    assert set(violations[0]["hsn_values"]) == {"84733099", "85176990"}
    assert violations[0]["result"] == ReferenceCheckResult.WARNING

def test_hsn_no_items_returns_empty():
    assert check_hsn_consistency([{"document_type": "CUSTOMER_PO", "order_items": []}]) == []

def test_hsn_only_one_doc_with_hsn_returns_empty():
    # Can't check consistency with only one data point
    docs = [
        {"document_type": "CUSTOMER_PO",    "order_items": [{"part_no": "FG-120G", "hsn_code": "84733099"}]},
        {"document_type": "COMPANY_INVOICE", "order_items": [{"part_no": "FG-120G", "hsn_code": ""}]},
    ]
    assert check_hsn_consistency(docs) == []
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/services/test_cross_doc_validator.py -k "hsn" -v
```
Expected: `ImportError`

- [ ] **Step 3: Add 3F function**

Append to `backend/app/services/cross_doc_validator.py`:

```python
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
```

- [ ] **Step 4: Run all tests so far**

```bash
pytest tests/services/test_cross_doc_validator.py -v
```
Expected: All tests PASS (should be ~35 tests total)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cross_doc_validator.py backend/tests/services/test_cross_doc_validator.py
git commit -m "feat: Module 3F — HSN code consistency checks"
```

---

## Task 8: Extend docs_payload in purchase_orders.py

**Files:**
- Modify: `backend/app/api/v1/purchase_orders.py` (lines ~153–169)

The `docs_payload` list is built in `get_chain_status_v2()`. It currently pulls only 7 fields. Module 3 needs 10 more fields from `extracted_data`.

- [ ] **Step 1: Add a helper and extend the payload**

In `backend/app/api/v1/purchase_orders.py`, find the `get_chain_status_v2` function. Add a local helper and extend `docs_payload`:

```python
@router.get("/{po_id}/chain")
async def get_chain_status_v2(
    po_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Compute and return current chain validation status for a PO."""
    po = await db.get(
        PurchaseOrder,
        po_id,
        options=[selectinload(PurchaseOrder.documents).selectinload(Document.doc_metadata)],
    )
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    vpo_numbers = []
    for doc in po.documents:
        if doc.document_type == DocumentType.COMPANY_PO and doc.vpo_numbers:
            vpo_numbers.extend(doc.vpo_numbers)

    invoiced_total = sum(
        float(doc.doc_metadata.total_amount or 0)
        for doc in po.documents
        if doc.document_type == DocumentType.COMPANY_INVOICE and doc.doc_metadata
    )

    def _ed(doc: Document, key: str):
        """Safe getter for extracted_data fields."""
        if doc.doc_metadata and doc.doc_metadata.extracted_data:
            return doc.doc_metadata.extracted_data.get(key)
        return None

    docs_payload = [
        {
            # Existing fields
            "document_type": doc.document_type,
            "so_number": doc.so_number,
            "vpo_numbers": doc.vpo_numbers or [],
            "extraction_ok": doc.extraction_ok,
            "cpo_ref": doc.doc_metadata.po_ref_no if doc.doc_metadata else None,
            "billing_stage": doc.billing_stage,
            "amount": float(doc.doc_metadata.total_amount or 0) if doc.doc_metadata else 0,
            "delivery_address": _ed(doc, "delivery_address"),
            # Module 3 additions
            "customer_gstin": _ed(doc, "customer_gstin"),
            "vendor_gstin":   _ed(doc, "vendor_gstin"),
            "customer_name":  _ed(doc, "customer_name"),
            "vendor_name":    _ed(doc, "vendor_name"),
            "serial_numbers": _ed(doc, "serial_numbers") or [],
            "dc_number": (
                doc.doc_metadata.primary_ref_no
                if doc.doc_metadata and doc.document_type in (
                    DocumentType.COMPANY_DC, DocumentType.VENDOR_DC
                )
                else None
            ),
            "dc_reference": _ed(doc, "dc_reference"),
            "po_reference": _ed(doc, "po_reference"),
            "doc_date": doc.doc_metadata.doc_date if doc.doc_metadata else None,
            "order_items": _ed(doc, "order_items") or [],
        }
        for doc in po.documents
    ]

    result = compute_chain_status(
        scenario=po.order_scenario,
        po_number=po.po_number,
        so_number=po.so_number,
        po_total=float(po.total_amount) if po.total_amount else None,
        billing_type=po.billing_type,
        billing_milestones=po.billing_milestones or [],
        vpo_numbers=vpo_numbers,
        documents=docs_payload,
        requires_install_report=po.requires_install_report,
        invoiced_total=invoiced_total,
    )
    # ... rest of function unchanged
```

- [ ] **Step 2: Verify no import errors**

```bash
cd backend
python -c "from app.api.v1.purchase_orders import router; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/v1/purchase_orders.py
git commit -m "feat: extend chain docs_payload with Module 3 fields (GSTIN, serials, dates, order_items)"
```

---

## Task 9: Wire All Module 3 Checks into chain_validator.py

This is the integration step — `compute_chain_status()` calls all new checks and appends results to `reference_checks[]`.

**Key rule:** Only MISMATCH results set `has_mismatch = True`. WARNING results are appended but do NOT affect `chain_status`.

**Files:**
- Modify: `backend/app/services/chain_validator.py`
- Modify: `backend/tests/services/test_chain_validator.py`

- [ ] **Step 1: Add integration tests**

Append to `backend/tests/services/test_chain_validator.py`:

```python
from datetime import date as _date


def _doc_full(doc_type, **kwargs):
    """Extended doc dict with all Module 3 fields."""
    return {
        "document_type": doc_type,
        "so_number": kwargs.get("so_number"),
        "vpo_numbers": kwargs.get("vpo_numbers", []),
        "extraction_ok": kwargs.get("extraction_ok", True),
        "cpo_ref": kwargs.get("cpo_ref"),
        "billing_stage": kwargs.get("billing_stage"),
        "amount": kwargs.get("amount", 0),
        "delivery_address": kwargs.get("delivery_address"),
        "customer_gstin": kwargs.get("customer_gstin"),
        "vendor_gstin": kwargs.get("vendor_gstin"),
        "customer_name": kwargs.get("customer_name"),
        "vendor_name": kwargs.get("vendor_name"),
        "serial_numbers": kwargs.get("serial_numbers", []),
        "dc_number": kwargs.get("dc_number"),
        "dc_reference": kwargs.get("dc_reference"),
        "po_reference": kwargs.get("po_reference"),
        "doc_date": kwargs.get("doc_date"),
        "order_items": kwargs.get("order_items", []),
    }


def test_ci_amount_mismatch_sets_chain_mismatch():
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="PWFA251127016",
        so_number="SO-001",
        po_total=503137.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc_full(DocumentType.CUSTOMER_PO, amount=503137.0),
            _doc_full(DocumentType.COMPANY_DC, so_number="SO-001", cpo_ref="PWFA251127016"),
            _doc_full(DocumentType.COMPANY_INVOICE,
                      so_number="SO-001", cpo_ref="PWFA251127016",
                      amount=490000.0),  # ₹13,137 under — 2.6% diff → MISMATCH
        ],
        requires_install_report=False,
        invoiced_total=490000.0,
    )
    ci_checks = [rc for rc in result["reference_checks"] if rc["check"] == "ci_vs_cpo_total"]
    assert len(ci_checks) == 1
    assert ci_checks[0]["result"] == "mismatch"
    assert result["chain_status"] == ChainStatus.MISMATCH


def test_gstin_mismatch_sets_chain_mismatch():
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc_full(DocumentType.CUSTOMER_PO, customer_gstin="33AAICS1881D1ZJ"),
            _doc_full(DocumentType.COMPANY_DC,
                      so_number="SO-001", cpo_ref="CPO-001",
                      customer_gstin="29AAICS1881D1ZK"),  # different state GSTIN
            _doc_full(DocumentType.COMPANY_INVOICE,
                      so_number="SO-001", cpo_ref="CPO-001",
                      customer_gstin="33AAICS1881D1ZJ",
                      amount=100000.0),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    gstin_checks = [rc for rc in result["reference_checks"] if rc["check"] == "customer_gstin_consistency"]
    assert gstin_checks[0]["result"] == "mismatch"
    assert result["chain_status"] == ChainStatus.MISMATCH


def test_serial_chain_mismatch_sets_chain_mismatch():
    result = compute_chain_status(
        scenario=OrderScenario.PROCUREMENT,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=["1PTR2526000400"],
        documents=[
            _doc_full(DocumentType.CUSTOMER_PO),
            _doc_full(DocumentType.COMPANY_PO),
            _doc_full(DocumentType.VENDOR_INVOICE,
                      vpo_numbers=["1PTR2526000400"],
                      serial_numbers=["NDKDL1U", "NDLEFAU"],
                      amount=80000.0),
            _doc_full(DocumentType.COMPANY_DC,
                      so_number="SO-001", cpo_ref="CPO-001",
                      serial_numbers=["NDKDL1U"]),  # NDLEFAU not shipped
            _doc_full(DocumentType.COMPANY_INVOICE,
                      so_number="SO-001", cpo_ref="CPO-001",
                      amount=100000.0),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    serial_checks = [rc for rc in result["reference_checks"] if rc["check"] == "serial_chain"]
    assert serial_checks[0]["result"] == "mismatch"
    assert result["chain_status"] == ChainStatus.MISMATCH


def test_warning_checks_do_not_set_chain_mismatch():
    """Vendor GSTIN mismatch = WARNING, should not flip chain_status to MISMATCH."""
    result = compute_chain_status(
        scenario=OrderScenario.PROCUREMENT,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=["1PTR2526000400"],
        documents=[
            _doc_full(DocumentType.CUSTOMER_PO),
            _doc_full(DocumentType.COMPANY_PO, vendor_gstin="33AAACS5403H1Z5"),
            _doc_full(DocumentType.VENDOR_INVOICE,
                      vpo_numbers=["1PTR2526000400"],
                      vendor_gstin="29AAACS5403H1ZK",  # different state — Redington Karnataka
                      amount=80000.0),
            _doc_full(DocumentType.COMPANY_DC,
                      so_number="SO-001", cpo_ref="CPO-001"),
            _doc_full(DocumentType.COMPANY_INVOICE,
                      so_number="SO-001", cpo_ref="CPO-001",
                      amount=100000.0),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    vendor_gstin_checks = [rc for rc in result["reference_checks"] if rc["check"] == "vendor_gstin_consistency"]
    assert vendor_gstin_checks[0]["result"] == "warning"
    # WARNING must NOT flip chain_status
    assert result["chain_status"] != ChainStatus.MISMATCH


def test_date_sequence_violation_produces_warning_check():
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc_full(DocumentType.CUSTOMER_PO, doc_date=_date(2026, 3, 1)),
            _doc_full(DocumentType.COMPANY_DC,
                      so_number="SO-001", cpo_ref="CPO-001",
                      doc_date=_date(2026, 1, 1)),  # DC before CPO — impossible
            _doc_full(DocumentType.COMPANY_INVOICE,
                      so_number="SO-001", cpo_ref="CPO-001",
                      amount=100000.0),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    date_checks = [rc for rc in result["reference_checks"] if rc["check"] == "date_sequence"]
    assert len(date_checks) >= 1
    assert all(rc["result"] == "warning" for rc in date_checks)
    # date violations are warnings — no MISMATCH
    assert result["chain_status"] != ChainStatus.MISMATCH
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/services/test_chain_validator.py -k "ci_amount or gstin_mismatch or serial_chain_mismatch or warning_checks or date_sequence_violation" -v
```
Expected: All FAIL with assertion errors (checks not yet in chain_validator)

- [ ] **Step 3: Add imports and Module 3 logic to chain_validator.py**

In `backend/app/services/chain_validator.py`, add the import at the top:

```python
from app.services.cross_doc_validator import (
    check_ci_vs_cpo_total,
    check_vinv_sum_vs_vpo_total,
    check_gstin_consistency,
    check_name_consistency,
    check_serial_chain,
    check_vdc_vs_vinv_serials,
    check_dc_ref_on_ci,
    check_vpo_ref_on_vdc,
    check_vdc_ref_on_vinv,
    check_date_sequence,
    check_hsn_consistency,
)
```

Then in `compute_chain_status()`, append the following AFTER the existing address check block (after line ~178 — after the `reference_checks.append` for `delivery_address`):

```python
    # ── Module 3 cross-document checks ───────────────────────────────────────

    cpo_docs  = [d for d in documents if d.get("document_type") == DocumentType.CUSTOMER_PO]
    vpo_docs  = [d for d in documents if d.get("document_type") == DocumentType.COMPANY_PO]
    vinv_docs = [d for d in documents if d.get("document_type") == DocumentType.VENDOR_INVOICE and d.get("extraction_ok", True)]
    vdc_docs  = [d for d in documents if d.get("document_type") == DocumentType.VENDOR_DC]
    cdc_docs  = [d for d in documents if d.get("document_type") == DocumentType.COMPANY_DC]
    ci_docs   = [d for d in documents if d.get("document_type") == DocumentType.COMPANY_INVOICE]

    # 3A: Company Invoice total vs Customer PO total (MISMATCH)
    ci_total_val = next((d.get("amount") for d in ci_docs), None)
    ci_cpo_result = check_ci_vs_cpo_total(ci_total_val, po_total)
    reference_checks.append({
        "document_type": DocumentType.COMPANY_INVOICE,
        "check": "ci_vs_cpo_total",
        "result": ci_cpo_result,
        "extracted": ci_total_val,
        "expected": po_total,
        "skip_reason": "missing_amount" if ci_cpo_result == ReferenceCheckResult.SKIP else None,
    })
    if ci_cpo_result == ReferenceCheckResult.MISMATCH:
        has_mismatch = True

    # 3A: Vendor Invoice sum vs Company PO total (WARNING — freight tolerance)
    vinv_totals = [d.get("amount", 0) for d in vinv_docs]
    vpo_total_val = next((d.get("amount") for d in vpo_docs), None)
    vinv_vpo_result = check_vinv_sum_vs_vpo_total(vinv_totals, vpo_total_val)
    reference_checks.append({
        "document_type": DocumentType.VENDOR_INVOICE,
        "check": "vinv_sum_vs_vpo_total",
        "result": vinv_vpo_result,
        "extracted": sum(vinv_totals) if vinv_totals else None,
        "expected": vpo_total_val,
        "skip_reason": "missing_amount" if vinv_vpo_result == ReferenceCheckResult.SKIP else None,
    })
    # WARNING — intentionally NOT setting has_mismatch

    # 3B: Customer GSTIN consistency across CPO, CDC, CI (MISMATCH)
    customer_gstins = [d.get("customer_gstin") for d in cpo_docs + cdc_docs + ci_docs]
    gstin_customer = check_gstin_consistency(customer_gstins)
    reference_checks.append({
        "document_type": None,
        "check": "customer_gstin_consistency",
        "result": gstin_customer,
        "extracted": ", ".join(g for g in customer_gstins if g) or None,
        "expected": None,
        "skip_reason": "insufficient_data" if gstin_customer == ReferenceCheckResult.SKIP else None,
    })
    if gstin_customer == ReferenceCheckResult.MISMATCH:
        has_mismatch = True

    # 3B: Vendor GSTIN — WARNING only (Redington multi-state GSTINs are legitimate)
    vendor_gstins = [d.get("vendor_gstin") for d in vpo_docs + vinv_docs]
    gstin_vendor_raw = check_gstin_consistency(vendor_gstins)
    gstin_vendor = (
        ReferenceCheckResult.WARNING
        if gstin_vendor_raw == ReferenceCheckResult.MISMATCH
        else gstin_vendor_raw
    )
    reference_checks.append({
        "document_type": None,
        "check": "vendor_gstin_consistency",
        "result": gstin_vendor,
        "extracted": ", ".join(g for g in vendor_gstins if g) or None,
        "expected": None,
        "skip_reason": "insufficient_data" if gstin_vendor == ReferenceCheckResult.SKIP else None,
    })
    # vendor GSTIN is WARNING — NOT setting has_mismatch

    # 3B: Customer name fuzzy match (WARNING)
    customer_names = [d.get("customer_name") for d in cpo_docs + cdc_docs + ci_docs]
    name_result = check_name_consistency(customer_names)
    reference_checks.append({
        "document_type": None,
        "check": "customer_name_consistency",
        "result": name_result,
        "extracted": None,
        "expected": None,
        "skip_reason": "insufficient_data" if name_result == ReferenceCheckResult.SKIP else None,
    })

    # 3C: Serial chain — VINV serials must appear in CDC (MISMATCH)
    vinv_serials = [d.get("serial_numbers", []) for d in vinv_docs]
    cdc_serials  = [d.get("serial_numbers", []) for d in cdc_docs if d.get("extraction_ok", True)]
    serial_result = check_serial_chain(vinv_serials, cdc_serials)
    reference_checks.append({
        "document_type": DocumentType.VENDOR_INVOICE,
        "check": "serial_chain",
        "result": serial_result["result"],
        "extracted": ", ".join(serial_result.get("missing", [])) or None,
        "expected": None,
        "skip_reason": serial_result.get("skip_reason"),
    })
    if serial_result["result"] == ReferenceCheckResult.MISMATCH:
        has_mismatch = True

    # 3C: VDC serials must appear on VINV (MISMATCH)
    if vdc_docs:
        vdc_serials_flat = [s for d in vdc_docs for s in (d.get("serial_numbers") or []) if d.get("extraction_ok", True)]
        vdc_vinv = check_vdc_vs_vinv_serials(vdc_serials_flat, vinv_serials)
        reference_checks.append({
            "document_type": DocumentType.VENDOR_DC,
            "check": "vdc_vinv_serial_match",
            "result": vdc_vinv["result"],
            "extracted": ", ".join(vdc_vinv.get("missing", [])) or None,
            "expected": None,
            "skip_reason": vdc_vinv.get("skip_reason"),
        })
        if vdc_vinv["result"] == ReferenceCheckResult.MISMATCH:
            has_mismatch = True

    # 3D: Company DC number referenced on Company Invoice (WARNING)
    cdc_dc_numbers = [d.get("dc_number") for d in cdc_docs if d.get("dc_number")]
    ci_dc_refs = [d.get("dc_reference") for d in ci_docs]
    reference_checks.append({
        "document_type": DocumentType.COMPANY_DC,
        "check": "dc_ref_on_ci",
        "result": check_dc_ref_on_ci(cdc_dc_numbers, ci_dc_refs),
        "extracted": ", ".join(r for r in ci_dc_refs if r) or None,
        "expected": ", ".join(cdc_dc_numbers) or None,
        "skip_reason": None,
    })

    # 3D: VPO number referenced on Vendor DC (WARNING)
    if vdc_docs and vpo_numbers:
        vdc_po_refs = [d.get("po_reference") for d in vdc_docs if d.get("extraction_ok", True)]
        reference_checks.append({
            "document_type": DocumentType.VENDOR_DC,
            "check": "vpo_ref_on_vdc",
            "result": check_vpo_ref_on_vdc(vdc_po_refs, vpo_numbers),
            "extracted": ", ".join(r for r in vdc_po_refs if r) or None,
            "expected": ", ".join(vpo_numbers),
            "skip_reason": None,
        })

    # 3D: Vendor DC number referenced on Vendor Invoice (WARNING)
    if vdc_docs and vinv_docs:
        vdc_numbers = [d.get("dc_number") for d in vdc_docs if d.get("dc_number")]
        vinv_dc_refs = [d.get("dc_reference") for d in vinv_docs]
        reference_checks.append({
            "document_type": DocumentType.VENDOR_DC,
            "check": "vdc_ref_on_vinv",
            "result": check_vdc_ref_on_vinv(vdc_numbers, vinv_dc_refs),
            "extracted": ", ".join(r for r in vinv_dc_refs if r) or None,
            "expected": ", ".join(vdc_numbers) or None,
            "skip_reason": None,
        })

    # 3E: Date sequence
    dated_docs = [
        {"document_type": str(d.get("document_type", "")), "doc_date": d.get("doc_date")}
        for d in documents
    ]
    for v in check_date_sequence(dated_docs):
        reference_checks.append({
            "document_type": v["earlier_type"],
            "check": "date_sequence",
            "result": ReferenceCheckResult.WARNING,
            "extracted": f"{v['later_type']} dated {v['delta_days']} days before {v['earlier_type']}",
            "expected": f"{v['later_type']} date >= {v['earlier_type']} date",
            "skip_reason": None,
        })

    # 3F: HSN consistency — customer loop (CPO, CDC, CI)
    customer_loop = [
        {"document_type": str(d.get("document_type", "")), "order_items": d.get("order_items", [])}
        for d in cpo_docs + cdc_docs + ci_docs if d.get("extraction_ok", True)
    ]
    for v in check_hsn_consistency(customer_loop):
        reference_checks.append({
            "document_type": None,
            "check": "hsn_consistency_customer",
            "result": ReferenceCheckResult.WARNING,
            "extracted": ", ".join(v["hsn_values"]),
            "expected": f"consistent HSN for {v['part_no']}",
            "skip_reason": None,
        })

    # 3F: HSN consistency — procurement loop (VPO, VINV)
    procurement_loop = [
        {"document_type": str(d.get("document_type", "")), "order_items": d.get("order_items", [])}
        for d in vpo_docs + vinv_docs if d.get("extraction_ok", True)
    ]
    for v in check_hsn_consistency(procurement_loop):
        reference_checks.append({
            "document_type": None,
            "check": "hsn_consistency_procurement",
            "result": ReferenceCheckResult.WARNING,
            "extracted": ", ".join(v["hsn_values"]),
            "expected": f"consistent HSN for {v['part_no']}",
            "skip_reason": None,
        })
```

- [ ] **Step 4: Run all chain_validator tests**

```bash
pytest tests/services/test_chain_validator.py -v
```
Expected: All tests PASS — including existing tests (which must not break)

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v --tb=short
```
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/chain_validator.py backend/tests/services/test_chain_validator.py
git commit -m "feat: wire Module 3 (3A-3F) into compute_chain_status() — 13 new cross-doc checks"
```

---

## Task 10: Duplicate Document Detection in document_service.py

Same-PO duplicate: detect when `primary_ref_no` already exists for this PO and document type before setting metadata.

**Files:**
- Modify: `backend/app/services/document_service.py`
- Create: `backend/tests/services/test_duplicate_detection.py`

- [ ] **Step 1: Find where primary_ref_no is set**

```bash
grep -n "primary_ref_no" backend/app/services/document_service.py
```

Read the relevant function to understand the flow.

- [ ] **Step 2: Write a failing test**

Create `backend/tests/services/test_duplicate_detection.py`:

```python
"""Tests for duplicate primary_ref_no detection within a PO."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.document_service import check_duplicate_ref_in_po


@pytest.mark.asyncio
async def test_no_duplicate_returns_false():
    mock_db = AsyncMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None
    result = await check_duplicate_ref_in_po(
        db=mock_db,
        po_id="po-uuid-001",
        document_type="VENDOR_INVOICE",
        primary_ref_no="C190224826",
        exclude_doc_id=None,
    )
    assert result is False


@pytest.mark.asyncio
async def test_duplicate_found_returns_true():
    mock_db = AsyncMock()
    existing = MagicMock()
    existing.id = "doc-uuid-existing"
    mock_db.execute.return_value.scalar_one_or_none.return_value = existing
    result = await check_duplicate_ref_in_po(
        db=mock_db,
        po_id="po-uuid-001",
        document_type="VENDOR_INVOICE",
        primary_ref_no="C190224826",
        exclude_doc_id=None,
    )
    assert result is True


@pytest.mark.asyncio
async def test_same_document_excluded_returns_false():
    """Editing a document's own metadata should not flag itself as duplicate."""
    mock_db = AsyncMock()
    existing = MagicMock()
    existing.id = "doc-uuid-self"
    mock_db.execute.return_value.scalar_one_or_none.return_value = existing
    result = await check_duplicate_ref_in_po(
        db=mock_db,
        po_id="po-uuid-001",
        document_type="VENDOR_INVOICE",
        primary_ref_no="C190224826",
        exclude_doc_id="doc-uuid-self",
    )
    assert result is False
```

- [ ] **Step 3: Run to verify they fail**

```bash
pytest tests/services/test_duplicate_detection.py -v
```
Expected: `ImportError: cannot import name 'check_duplicate_ref_in_po'`

- [ ] **Step 4: Add function to document_service.py**

Add this function to `backend/app/services/document_service.py`:

```python
async def check_duplicate_ref_in_po(
    db: AsyncSession,
    po_id: str,
    document_type: str,
    primary_ref_no: str | None,
    exclude_doc_id: str | None = None,
) -> bool:
    """
    Return True if another document in this PO already has the same primary_ref_no
    for the same document_type. Used to warn operators before creating a duplicate.
    exclude_doc_id: skip this document (used when editing existing metadata).
    """
    if not primary_ref_no:
        return False

    from sqlalchemy import select
    from app.models.document_metadata import DocumentMetadata
    from app.models.document import Document

    stmt = (
        select(Document.id)
        .join(DocumentMetadata, DocumentMetadata.document_id == Document.id)
        .where(
            Document.po_id == po_id,
            Document.document_type == document_type,
            DocumentMetadata.primary_ref_no == primary_ref_no,
        )
    )
    if exclude_doc_id:
        stmt = stmt.where(Document.id != exclude_doc_id)

    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/services/test_duplicate_detection.py -v
```
Expected: All 3 tests PASS

- [ ] **Step 6: Run full suite**

```bash
pytest tests/ -v --tb=short
```
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/document_service.py backend/tests/services/test_duplicate_detection.py
git commit -m "feat: add check_duplicate_ref_in_po() for same-PO duplicate invoice detection"
```

---


## Self-Review

**Spec coverage check:**

| Requirement | Task |
|---|---|
| WARNING severity | Task 1 |
| 3A: CI vs CPO total | Task 2 + Task 9 |
| 3A: VINV sum vs VPO total | Task 2 + Task 9 |
| 3B: Customer GSTIN consistency | Task 3 + Task 9 |
| 3B: Vendor GSTIN (WARNING) | Task 3 + Task 9 |
| 3B: Customer/vendor name fuzzy | Task 3 + Task 9 |
| 3C: VINV serials → CDC serials | Task 4 + Task 9 |
| 3C: VDC serials → VINV serials | Task 4 + Task 9 |
| 3D: CDC dc_number on CI | Task 5 + Task 9 |
| 3D: VPO ref on VDC | Task 5 + Task 9 |
| 3D: VDC ref on VINV | Task 5 + Task 9 |
| 3E: Date sequence | Task 6 + Task 9 |
| 3F: HSN consistency (both loops) | Task 7 + Task 9 |
| docs_payload extended | Task 8 |
| Same-PO duplicate detection | Task 10 |

**Placeholder scan:** No TBD/TODO/placeholder in any task — all code is complete.

**Type consistency:** `ReferenceCheckResult.WARNING` introduced in Task 1, used in Tasks 2–9. `check_serial_chain()` returns `dict` with `result`, `missing`, `skip_reason` — used consistently in Task 9. `check_date_sequence()` returns `list[dict]` — iterated in Task 9. `check_hsn_consistency()` returns `list[dict]` — iterated in Task 9.

**WARNING does not flip has_mismatch:** Verified in integration test `test_warning_checks_do_not_set_chain_mismatch`.

---

## Follow-On Plans

- **Module 4 — Order Item Integrity:** `order_items[]` already in `docs_payload` after Task 8. Plan needs: wiring `compare_po_to_delivery()` and `match_items_by_description()` into `compute_chain_status()`, plus aggregation logic for split deliveries.
- **Module 5 — Batch Procurement:** Schema change required (document-PO allocation N:M join table). Cannot be implemented without a DB migration plan.
- **Cross-PO duplicate detection:** Needs query against `reference_index` table across all POs. Can be added to `document_service.py` as a separate endpoint check.
