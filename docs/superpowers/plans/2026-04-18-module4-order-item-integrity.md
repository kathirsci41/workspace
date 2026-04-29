# Module 4 — Order Item Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 3 order item coverage checks — CPO vs CDC, CPO vs CI, and VPO vs VINV — so the chain validator flags missing or short-delivered line items.

**Architecture:** A new `check_order_item_coverage()` pure function in the existing `cross_doc_validator.py` wraps the existing `compare_po_to_delivery()` from `item_matcher.py`. `chain_validator.py` calls it in 3 places and appends results to `reference_checks[]`. All checks produce WARNING (not MISMATCH) because partial/staged delivery is legitimate. Skipped when either document has no items with `part_no`.

**Tech Stack:** Python 3.12, pytest. No new dependencies — reuses `item_matcher.compare_po_to_delivery()` and the existing `ReferenceCheckResult` enum.

---

## Scope NOT in this plan

- **LLM-assisted description matching** (`match_items_by_description`) — async, requires Redis, Phase 2. This plan only uses part_no matching (synchronous, no external calls).
- **Customer PO description-only items** — CUSTOMER_PO items often have no `part_no`. Checks skip when part_nos are absent; this is correct Phase 1 behaviour.
- Any frontend changes — existing `ReferenceValidationPanel` renders `reference_checks[]` generically.

---

## What `order_items` looks like in `docs_payload`

Each item dict in `order_items[]` has these fields (all optional, from extracted_data):

```python
{
    "part_no":      "1490600",        # str — used for matching
    "description":  "FortiGate 81F",  # str
    "qty":          "1",              # str or int
    "hsn_code":     "84733099",       # str
    "unit_price":   "120000",         # str
    "total_price":  "120000",         # str
}
```

`compare_po_to_delivery()` in `item_matcher.py` matches on `part_no` (case-insensitive). Qty values are coerced to `int` inside the function.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/app/services/cross_doc_validator.py` | Modify | Add `check_order_item_coverage()` |
| `backend/app/services/chain_validator.py` | Modify | Call item checks in 3 places, append to `reference_checks` |
| `backend/tests/services/test_cross_doc_validator.py` | Modify | 6 unit tests for `check_order_item_coverage()` |
| `backend/tests/services/test_chain_validator.py` | Modify | 3 integration tests |

---

## Task 1: Add `check_order_item_coverage()` to cross_doc_validator.py

**Files:**
- Modify: `backend/app/services/cross_doc_validator.py`
- Modify: `backend/tests/services/test_cross_doc_validator.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/services/test_cross_doc_validator.py`:

```python
# ── Module 4: Order Item Coverage ────────────────────────────────────────────

def test_order_item_coverage_all_matched_returns_pass():
    po_items = [
        {"part_no": "FG81F", "description": "FortiGate 81F", "qty": "2"},
        {"part_no": "FS108E", "description": "FortiSwitch 108E", "qty": "1"},
    ]
    dc_items = [
        {"part_no": "FG81F", "description": "FortiGate 81F", "qty": "2"},
        {"part_no": "FS108E", "description": "FortiSwitch 108E", "qty": "1"},
    ]
    result = check_order_item_coverage(po_items, dc_items)
    assert result["result"] == ReferenceCheckResult.PASS
    assert result["missing_parts"] == []
    assert result["partial_parts"] == []


def test_order_item_coverage_missing_part_returns_warning():
    po_items = [
        {"part_no": "FG81F", "description": "FortiGate 81F", "qty": "1"},
        {"part_no": "FS108E", "description": "FortiSwitch 108E", "qty": "1"},
    ]
    dc_items = [
        {"part_no": "FG81F", "description": "FortiGate 81F", "qty": "1"},
        # FS108E missing
    ]
    result = check_order_item_coverage(po_items, dc_items)
    assert result["result"] == ReferenceCheckResult.WARNING
    assert "FS108E" in result["missing_parts"]


def test_order_item_coverage_partial_qty_returns_warning():
    po_items = [{"part_no": "FG81F", "description": "FortiGate 81F", "qty": "3"}]
    dc_items = [{"part_no": "FG81F", "description": "FortiGate 81F", "qty": "2"}]
    result = check_order_item_coverage(po_items, dc_items)
    assert result["result"] == ReferenceCheckResult.WARNING
    assert "FG81F" in result["partial_parts"]


def test_order_item_coverage_no_part_nos_skips():
    po_items = [{"description": "Some item", "qty": "1"}]   # no part_no
    dc_items = [{"description": "Some item", "qty": "1"}]
    result = check_order_item_coverage(po_items, dc_items)
    assert result["result"] == ReferenceCheckResult.SKIP
    assert result["skip_reason"] == "no_part_nos"


def test_order_item_coverage_empty_po_items_skips():
    result = check_order_item_coverage([], [{"part_no": "FG81F", "qty": "1"}])
    assert result["result"] == ReferenceCheckResult.SKIP
    assert result["skip_reason"] == "no_po_items"


def test_order_item_coverage_case_insensitive_part_matching():
    po_items = [{"part_no": "fg81f", "qty": "1"}]
    dc_items = [{"part_no": "FG81F", "qty": "1"}]
    result = check_order_item_coverage(po_items, dc_items)
    assert result["result"] == ReferenceCheckResult.PASS
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend
pytest tests/services/test_cross_doc_validator.py -k "order_item_coverage" -v
```
Expected: `ImportError: cannot import name 'check_order_item_coverage'`

- [ ] **Step 3: Add the function to cross_doc_validator.py**

Add this import at the top of `backend/app/services/cross_doc_validator.py` (after the existing imports):

```python
from app.services.item_matcher import compare_po_to_delivery, ItemMatchStatus
```

Then append this function at the END of `backend/app/services/cross_doc_validator.py`:

```python
# ── Module 4: Order Item Coverage ────────────────────────────────────────────

def check_order_item_coverage(
    po_items: list[dict],
    delivery_items: list[dict],
) -> dict:
    """
    Compare PO line items against delivery document items using part_no matching.

    SKIP if either list is empty or has no part_nos.
    WARNING if any item is missing or partially delivered.
    PASS if all items are fully delivered.

    Returns {result, missing_parts, partial_parts, comparison, skip_reason}.
    """
    if not po_items:
        return {
            "result": ReferenceCheckResult.SKIP,
            "missing_parts": [],
            "partial_parts": [],
            "comparison": [],
            "skip_reason": "no_po_items",
        }

    po_has_part_nos = any(it.get("part_no") for it in po_items)
    if not po_has_part_nos:
        return {
            "result": ReferenceCheckResult.SKIP,
            "missing_parts": [],
            "partial_parts": [],
            "comparison": [],
            "skip_reason": "no_part_nos",
        }

    comparison = compare_po_to_delivery(po_items, delivery_items or [])

    missing_parts = [r["part_no"] for r in comparison if r["status"] == ItemMatchStatus.MISSING]
    partial_parts = [r["part_no"] for r in comparison if r["status"] == ItemMatchStatus.PARTIAL]

    if missing_parts or partial_parts:
        result = ReferenceCheckResult.WARNING
    else:
        result = ReferenceCheckResult.PASS

    return {
        "result": result,
        "missing_parts": missing_parts,
        "partial_parts": partial_parts,
        "comparison": comparison,
        "skip_reason": None,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/services/test_cross_doc_validator.py -k "order_item_coverage" -v
```
Expected: All 6 PASS

- [ ] **Step 5: Run full cross_doc_validator test suite**

```bash
pytest tests/services/test_cross_doc_validator.py -v
```
Expected: All 50 tests PASS (44 existing + 6 new)

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/cross_doc_validator.py backend/tests/services/test_cross_doc_validator.py
git commit -m "feat: add check_order_item_coverage() — Module 4 item-level delivery check"
```

---

## Task 2: Wire Module 4 checks into chain_validator.py

**Files:**
- Modify: `backend/app/services/chain_validator.py`
- Modify: `backend/tests/services/test_chain_validator.py`

Three checks to wire in:
1. **CPO vs CDC** — did the company deliver all customer-ordered items?
2. **VPO vs VINV** — did the vendor supply all company-ordered items?
3. **CDC vs CI** — does the company invoice cover all items on the DC?

All are WARNING (never MISMATCH) — partial delivery is normal.

- [ ] **Step 1: Add integration tests first**

Append to `backend/tests/services/test_chain_validator.py`:

```python
def test_missing_item_in_cdc_produces_warning():
    """CPO has two items; CDC only delivers one → WARNING on cpo_vs_cdc check."""
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=200000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc_full(DocumentType.CUSTOMER_PO, order_items=[
                {"part_no": "FG81F", "description": "FortiGate 81F", "qty": "1"},
                {"part_no": "FS108E", "description": "FortiSwitch 108E", "qty": "1"},
            ]),
            _doc_full(DocumentType.COMPANY_DC,
                      so_number="SO-001", cpo_ref="CPO-001",
                      order_items=[
                          {"part_no": "FG81F", "description": "FortiGate 81F", "qty": "1"},
                          # FS108E missing
                      ]),
            _doc_full(DocumentType.COMPANY_INVOICE,
                      so_number="SO-001", cpo_ref="CPO-001",
                      amount=200000.0),
        ],
        requires_install_report=False,
        invoiced_total=200000.0,
    )
    item_checks = [rc for rc in result["reference_checks"] if rc["check"] == "cpo_vs_cdc_items"]
    assert len(item_checks) == 1
    assert item_checks[0]["result"] == "warning"
    # WARNING must not flip chain_status to MISMATCH
    assert result["chain_status"] != ChainStatus.MISMATCH


def test_all_items_delivered_produces_pass():
    """All CPO items present in CDC → PASS on cpo_vs_cdc check."""
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=200000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc_full(DocumentType.CUSTOMER_PO, order_items=[
                {"part_no": "FG81F", "qty": "2"},
            ]),
            _doc_full(DocumentType.COMPANY_DC,
                      so_number="SO-001", cpo_ref="CPO-001",
                      order_items=[
                          {"part_no": "FG81F", "qty": "2"},
                      ]),
            _doc_full(DocumentType.COMPANY_INVOICE,
                      so_number="SO-001", cpo_ref="CPO-001",
                      amount=200000.0),
        ],
        requires_install_report=False,
        invoiced_total=200000.0,
    )
    item_checks = [rc for rc in result["reference_checks"] if rc["check"] == "cpo_vs_cdc_items"]
    assert item_checks[0]["result"] == "pass"


def test_no_part_nos_on_cpo_skips_item_check():
    """Customer PO items have only descriptions (no part_no) → SKIP."""
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc_full(DocumentType.CUSTOMER_PO, order_items=[
                {"description": "Firewall unit", "qty": "1"},  # no part_no
            ]),
            _doc_full(DocumentType.COMPANY_DC,
                      so_number="SO-001", cpo_ref="CPO-001"),
            _doc_full(DocumentType.COMPANY_INVOICE,
                      so_number="SO-001", cpo_ref="CPO-001",
                      amount=100000.0),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    item_checks = [rc for rc in result["reference_checks"] if rc["check"] == "cpo_vs_cdc_items"]
    assert item_checks[0]["result"] == "skip"
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend
pytest tests/services/test_chain_validator.py -k "missing_item_in_cdc or all_items_delivered or no_part_nos_on_cpo" -v
```
Expected: All 3 FAIL (checks not yet wired)

- [ ] **Step 3: Add import to chain_validator.py**

In `backend/app/services/chain_validator.py`, add `check_order_item_coverage` to the existing cross_doc_validator import block:

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
    check_order_item_coverage,
)
```

- [ ] **Step 4: Add Module 4 block to chain_validator.py**

In `compute_chain_status()`, append the following AFTER the 3F HSN consistency block (after the second `check_hsn_consistency` loop), BEFORE the `# Billing completeness` comment:

```python
    # ── Module 4: Order Item Coverage ────────────────────────────────────────

    # 4A: CPO vs CDC — did the company deliver all customer-ordered items?
    cpo_items = next((d.get("order_items", []) for d in cpo_docs), [])
    cdc_items_flat = [item for d in cdc_docs for item in (d.get("order_items") or [])]
    cpo_cdc = check_order_item_coverage(cpo_items, cdc_items_flat)
    reference_checks.append({
        "document_type": DocumentType.CUSTOMER_PO,
        "check": "cpo_vs_cdc_items",
        "result": cpo_cdc["result"],
        "extracted": ", ".join(cpo_cdc["missing_parts"] + cpo_cdc["partial_parts"]) or None,
        "expected": None,
        "skip_reason": cpo_cdc.get("skip_reason"),
    })
    # WARNING only — partial delivery is legitimate

    # 4B: VPO vs VINV — did the vendor supply all company-ordered items?
    if vpo_docs and vinv_docs:
        vpo_items = next((d.get("order_items", []) for d in vpo_docs), [])
        vinv_items_flat = [item for d in vinv_docs for item in (d.get("order_items") or [])]
        vpo_vinv = check_order_item_coverage(vpo_items, vinv_items_flat)
        reference_checks.append({
            "document_type": DocumentType.COMPANY_PO,
            "check": "vpo_vs_vinv_items",
            "result": vpo_vinv["result"],
            "extracted": ", ".join(vpo_vinv["missing_parts"] + vpo_vinv["partial_parts"]) or None,
            "expected": None,
            "skip_reason": vpo_vinv.get("skip_reason"),
        })
        # WARNING only

    # 4C: CDC vs CI — does the invoice cover all items on the delivery note?
    if cdc_docs and ci_docs:
        ci_items_flat = [item for d in ci_docs for item in (d.get("order_items") or [])]
        cdc_ci = check_order_item_coverage(cdc_items_flat, ci_items_flat)
        reference_checks.append({
            "document_type": DocumentType.COMPANY_DC,
            "check": "cdc_vs_ci_items",
            "result": cdc_ci["result"],
            "extracted": ", ".join(cdc_ci["missing_parts"] + cdc_ci["partial_parts"]) or None,
            "expected": None,
            "skip_reason": cdc_ci.get("skip_reason"),
        })
        # WARNING only
```

- [ ] **Step 5: Run the 3 new integration tests**

```bash
pytest tests/services/test_chain_validator.py -k "missing_item_in_cdc or all_items_delivered or no_part_nos_on_cpo" -v
```
Expected: All 3 PASS

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -15
```
Expected: No regressions (same baseline pass count ±3 for new tests)

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/chain_validator.py backend/tests/services/test_chain_validator.py
git commit -m "feat: wire Module 4 order item coverage into compute_chain_status() — 3 checks (CPO/CDC, VPO/VINV, CDC/CI)"
```

---

## Self-Review

**Spec coverage:**
- ✅ CPO vs CDC item check (Task 2, 4A)
- ✅ VPO vs VINV item check (Task 2, 4B)
- ✅ CDC vs CI item check (Task 2, 4C)
- ✅ SKIP when no part_nos (Task 1, `check_order_item_coverage`)
- ✅ WARNING not MISMATCH (Task 2 — no `has_mismatch = True` for Module 4 checks)
- ✅ Uses existing `compare_po_to_delivery()` (Task 1 imports it)
- ✅ `order_items` already in `docs_payload` (done in Module 3 Task 8)

**Placeholder scan:** None found.

**Type consistency:**
- `check_order_item_coverage` returns `{result, missing_parts, partial_parts, comparison, skip_reason}` — used consistently in Task 1 tests and Task 2 wiring.
- `_doc_full()` helper in test file already accepts `order_items` kwarg (added in Module 3 Task 9) — tests use it directly.

**Edge cases handled:**
- Empty `po_items` → SKIP with `no_po_items`
- Items with no `part_no` → SKIP with `no_part_nos`
- Empty `delivery_items` + valid `po_items` → WARNING (all items missing)
- Multiple DCs/Invoices → items flattened with list comprehension before passing to check
