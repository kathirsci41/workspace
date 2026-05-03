# Validation Gap Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 3 silent validation gaps: enrich reference check API responses with extracted/expected detail, wire the existing address validator into the chain pipeline, and fix VPO OR-logic to AND-logic.

**Architecture:** All 3 fixes are backend-only except Task 1 which also updates the frontend reference check pills to show mismatch detail. No new files — every change is a targeted edit to existing services, one API endpoint, and one frontend component.

**Tech Stack:** Python 3.12, FastAPI, pytest, React 18 + TypeScript, TanStack Query

---

## Files touched

| File | Change |
|------|--------|
| `backend/app/services/chain_validator.py` | Add `extracted`, `expected`, `skip_reason` to each reference_check dict; call `validate_addresses()` |
| `backend/app/api/v1/purchase_orders.py` | Add `delivery_address` field to `docs_payload` |
| `backend/app/services/reference_validator.py` | Change VPO OR-logic → AND-logic |
| `backend/tests/services/test_chain_validator.py` | Add tests for address check + enriched fields |
| `backend/tests/services/test_reference_validator.py` | Add VPO AND-logic tests |
| `frontend/src/api/purchaseOrders.ts` | Add `extracted`, `expected`, `skip_reason` to `ChainStatusResponse.reference_checks` type |
| `frontend/src/pages/PODetailPage.tsx` | Show mismatch detail in reference check pills |

---

## Task 1: Enrich reference_checks with extracted/expected/skip_reason

**Context:** Currently `reference_checks` entries only carry `{document_type, check, result}`. When result is `mismatch`, the user sees `✗ cpo_reference` but doesn't know what value was extracted vs what was expected. When result is `skip`, they can't tell if extraction failed or the field just doesn't apply. This task adds `extracted`, `expected`, and `skip_reason` to every check entry, and updates the frontend pills to show the detail on mismatch.

**Files:**
- Modify: `backend/app/services/chain_validator.py:74-120`
- Modify: `backend/tests/services/test_chain_validator.py`
- Modify: `frontend/src/api/purchaseOrders.ts:83-89`
- Modify: `frontend/src/pages/PODetailPage.tsx:299-312`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/services/test_chain_validator.py`:

```python
def test_reference_checks_include_extracted_and_expected_on_mismatch():
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc(DocumentType.CUSTOMER_PO),
            _doc(DocumentType.COMPANY_DC, so_number="SO-WRONG", cpo_ref="CPO-001"),
            _doc(DocumentType.COMPANY_INVOICE, so_number="SO-001", cpo_ref="CPO-001"),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    so_checks = [rc for rc in result["reference_checks"] if rc["check"] == "so_consistency"]
    assert len(so_checks) > 0
    mismatch_check = next(rc for rc in so_checks if rc["result"] == "mismatch")
    assert mismatch_check["extracted"] == "SO-WRONG"
    assert mismatch_check["expected"] == "SO-001"


def test_reference_checks_include_skip_reason_when_extraction_failed():
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc(DocumentType.CUSTOMER_PO),
            _doc(DocumentType.COMPANY_DC, so_number=None, cpo_ref=None, extraction_ok=False),
            _doc(DocumentType.COMPANY_INVOICE, so_number="SO-001", cpo_ref="CPO-001"),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    dc_checks = [
        rc for rc in result["reference_checks"]
        if rc["document_type"] == DocumentType.COMPANY_DC
    ]
    assert all(rc["result"] == "skip" for rc in dc_checks)
    assert all(rc["skip_reason"] == "extraction_failed" for rc in dc_checks)


def test_reference_checks_skip_reason_no_so_when_so_not_set():
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number=None,   # no SO set on PO
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc(DocumentType.CUSTOMER_PO),
            _doc(DocumentType.COMPANY_DC, so_number=None, cpo_ref="CPO-001"),
        ],
        requires_install_report=False,
    )
    so_checks = [
        rc for rc in result["reference_checks"]
        if rc["check"] == "so_consistency"
    ]
    assert all(rc["result"] == "skip" for rc in so_checks)
    assert all(rc["skip_reason"] == "no_so_number" for rc in so_checks)
```

- [ ] **Step 2: Run failing tests**

```
cd backend
pytest tests/services/test_chain_validator.py::test_reference_checks_include_extracted_and_expected_on_mismatch tests/services/test_chain_validator.py::test_reference_checks_include_skip_reason_when_extraction_failed tests/services/test_chain_validator.py::test_reference_checks_skip_reason_no_so_when_so_not_set -v
```

Expected: FAIL — `KeyError: 'extracted'`

- [ ] **Step 3: Update chain_validator.py — enrich reference_check dicts**

Replace the reference checks section in `backend/app/services/chain_validator.py` (lines 74–119):

```python
    # Reference checks
    reference_checks = []
    has_mismatch = False

    for doc in documents:
        doc_type = doc.get("document_type")
        if doc_type is None:
            continue
        ok = doc.get("extraction_ok", True)

        if doc_type in (DocumentType.COMPANY_DC, DocumentType.COMPANY_INVOICE):
            extracted_so = doc.get("so_number") if ok else None
            so_result = check_so_consistency(
                extracted_so=extracted_so,
                expected_so=so_number,
            )
            # Determine skip_reason for SO check
            if so_result == ReferenceCheckResult.SKIP:
                so_skip_reason = "extraction_failed" if not ok else ("no_so_number" if not so_number else "no_extracted_value")
            else:
                so_skip_reason = None

            extracted_cpo = doc.get("cpo_ref") if ok else None
            cpo_result = check_cpo_reference(
                extracted_cpo_ref=extracted_cpo,
                expected_po_number=po_number,
            )
            cpo_skip_reason = "extraction_failed" if cpo_result == ReferenceCheckResult.SKIP and not ok else None

            reference_checks.append({
                "document_type": doc_type,
                "check": "so_consistency",
                "result": so_result,
                "extracted": extracted_so,
                "expected": so_number,
                "skip_reason": so_skip_reason,
            })
            reference_checks.append({
                "document_type": doc_type,
                "check": "cpo_reference",
                "result": cpo_result,
                "extracted": extracted_cpo,
                "expected": po_number,
                "skip_reason": cpo_skip_reason,
            })
            if so_result == ReferenceCheckResult.MISMATCH:
                has_mismatch = True
            if cpo_result == ReferenceCheckResult.MISMATCH:
                has_mismatch = True

        if doc_type == DocumentType.VENDOR_INVOICE:
            doc_vpo_numbers = doc.get("vpo_numbers") or []
            vpo_result = check_vpo_reference(
                doc_vpo_numbers=doc_vpo_numbers,
                registered_vpo_numbers=vpo_numbers or [],
            )
            vpo_skip_reason = None
            if vpo_result == ReferenceCheckResult.SKIP:
                vpo_skip_reason = "no_vpo_registered" if not (vpo_numbers or []) else "no_extracted_vpo"
            reference_checks.append({
                "document_type": doc_type,
                "check": "vpo_reference",
                "result": vpo_result,
                "extracted": ", ".join(doc_vpo_numbers) if doc_vpo_numbers else None,
                "expected": ", ".join(vpo_numbers or []) if vpo_numbers else None,
                "skip_reason": vpo_skip_reason,
            })
            if vpo_result == ReferenceCheckResult.MISMATCH:
                has_mismatch = True
```

- [ ] **Step 4: Run tests — expect PASS**

```
cd backend
pytest tests/services/test_chain_validator.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Update frontend type in purchaseOrders.ts**

In `frontend/src/api/purchaseOrders.ts`, update the `reference_checks` array type (lines 83–89):

```typescript
  reference_checks: Array<{
    document_type: string;
    check: string;
    result: 'pass' | 'mismatch' | 'skip';
    extracted?: string | null;
    expected?: string | null;
    skip_reason?: string | null;
  }>;
```

- [ ] **Step 6: Update reference check pills in PODetailPage.tsx to show mismatch detail**

In `frontend/src/pages/PODetailPage.tsx`, replace the `referenceChecks.map(...)` block (lines 299–312):

```tsx
{referenceChecks.map((rc, i) => (
  <div key={i} className="relative group">
    <span
      className={clsx(
        'text-xs font-medium px-3 py-1.5 rounded-lg border flex items-center gap-1.5 cursor-default',
        rc.result === 'pass'     && 'bg-green-50 border-green-300 text-green-700',
        rc.result === 'mismatch' && 'bg-red-50 border-red-300 text-red-700',
        rc.result === 'skip' && rc.skip_reason === 'extraction_failed'
          ? 'bg-orange-50 border-orange-200 text-orange-600'
          : rc.result === 'skip' && 'bg-gray-50 border-gray-200 text-gray-400',
      )}
    >
      {rc.result === 'pass' ? '✓' : rc.result === 'mismatch' ? '✗' : rc.skip_reason === 'extraction_failed' ? '⚠' : '○'}
      {' '}{rc.check}
    </span>
    {(rc.result === 'mismatch' || (rc.result === 'skip' && rc.skip_reason === 'extraction_failed')) && (
      <div className="absolute bottom-full left-0 mb-1.5 hidden group-hover:block z-30 w-64 bg-[--ink] text-white text-[10px] rounded-lg px-3 py-2 shadow-lg">
        {rc.result === 'mismatch' && (
          <>
            <div className="font-bold mb-1">Mismatch</div>
            <div>Extracted: <span className="font-mono">{rc.extracted ?? '—'}</span></div>
            <div>Expected: <span className="font-mono">{rc.expected ?? '—'}</span></div>
          </>
        )}
        {rc.result === 'skip' && rc.skip_reason === 'extraction_failed' && (
          <div>Extraction failed — validate manually</div>
        )}
      </div>
    )}
  </div>
))}
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/chain_validator.py backend/tests/services/test_chain_validator.py frontend/src/api/purchaseOrders.ts frontend/src/pages/PODetailPage.tsx
git commit -m "feat: enrich reference_checks with extracted/expected values and skip_reason"
```

---

## Task 2: Wire delivery address validation into chain pipeline

**Context:** `validate_addresses()` exists in `address_parser.py` and correctly compares two address strings using PIN code and state/city fallback. It is never called during chain validation. Delivery address mismatches between CUSTOMER_PO and COMPANY_DC are completely silent. This task adds `delivery_address` to the docs payload and calls `validate_addresses()` in `compute_chain_status()`.

**Files:**
- Modify: `backend/app/api/v1/purchase_orders.py:153-164`
- Modify: `backend/app/services/chain_validator.py` (imports + new check block)
- Modify: `backend/tests/services/test_chain_validator.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/services/test_chain_validator.py`:

```python
def _doc_with_address(doc_type, delivery_address=None, so_number=None, cpo_ref=None, extraction_ok=True):
    return {
        "document_type": doc_type,
        "so_number": so_number,
        "vpo_numbers": [],
        "extraction_ok": extraction_ok,
        "cpo_ref": cpo_ref,
        "delivery_address": delivery_address,
    }


def test_address_mismatch_sets_mismatch_status():
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc_with_address(DocumentType.CUSTOMER_PO, delivery_address="123 Main St, Chennai, Tamil Nadu 600001"),
            _doc_with_address(DocumentType.COMPANY_DC,  delivery_address="456 Other St, Mumbai, Maharashtra 400001",
                              so_number="SO-001", cpo_ref="CPO-001"),
            _doc_with_address(DocumentType.COMPANY_INVOICE, so_number="SO-001", cpo_ref="CPO-001"),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    addr_checks = [rc for rc in result["reference_checks"] if rc["check"] == "delivery_address"]
    assert len(addr_checks) == 1
    assert addr_checks[0]["result"] == "mismatch"
    assert result["chain_status"] == ChainStatus.MISMATCH


def test_address_match_does_not_affect_chain_status():
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc_with_address(DocumentType.CUSTOMER_PO, delivery_address="123 Main St, Chennai, Tamil Nadu 600001"),
            _doc_with_address(DocumentType.COMPANY_DC,  delivery_address="123 Main St, Chennai, Tamil Nadu 600001",
                              so_number="SO-001", cpo_ref="CPO-001"),
            _doc_with_address(DocumentType.COMPANY_INVOICE, so_number="SO-001", cpo_ref="CPO-001"),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    addr_checks = [rc for rc in result["reference_checks"] if rc["check"] == "delivery_address"]
    assert len(addr_checks) == 1
    assert addr_checks[0]["result"] == "pass"
    assert result["chain_status"] == ChainStatus.COMPLETE


def test_address_skip_when_addresses_missing():
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc(DocumentType.CUSTOMER_PO),   # no delivery_address key
            _doc(DocumentType.COMPANY_DC, so_number="SO-001", cpo_ref="CPO-001"),
        ],
        requires_install_report=False,
    )
    addr_checks = [rc for rc in result["reference_checks"] if rc["check"] == "delivery_address"]
    assert len(addr_checks) == 1
    assert addr_checks[0]["result"] == "skip"
```

- [ ] **Step 2: Run failing tests**

```
cd backend
pytest tests/services/test_chain_validator.py::test_address_mismatch_sets_mismatch_status tests/services/test_chain_validator.py::test_address_match_does_not_affect_chain_status tests/services/test_chain_validator.py::test_address_skip_when_addresses_missing -v
```

Expected: FAIL — `AssertionError: [] != 1 item`

- [ ] **Step 3: Add delivery_address to docs_payload in purchase_orders.py**

In `backend/app/api/v1/purchase_orders.py`, update `docs_payload` (lines 153–164):

```python
    docs_payload = [
        {
            "document_type": doc.document_type,
            "so_number": doc.so_number,
            "vpo_numbers": doc.vpo_numbers or [],
            "extraction_ok": doc.extraction_ok,
            "cpo_ref": doc.doc_metadata.po_ref_no if doc.doc_metadata else None,
            "billing_stage": doc.billing_stage,
            "amount": float(doc.doc_metadata.total_amount or 0) if doc.doc_metadata else 0,
            "delivery_address": (
                doc.doc_metadata.extracted_data.get("delivery_address")
                if doc.doc_metadata and doc.doc_metadata.extracted_data
                else None
            ),
        }
        for doc in po.documents
    ]
```

- [ ] **Step 4: Add address validation block in chain_validator.py**

At the top of `backend/app/services/chain_validator.py`, add the import after existing imports:

```python
from app.services.address_parser import validate_addresses, AddressMatchResult
```

Then in `compute_chain_status()`, add the following block **after** the VPO reference checks loop (after line ~119, before the `# Billing completeness` comment):

```python
    # Address consistency: CUSTOMER_PO delivery address vs COMPANY_DC delivery address
    cpo_address = next(
        (d.get("delivery_address") for d in documents if d.get("document_type") == DocumentType.CUSTOMER_PO),
        None,
    )
    cdc_address = next(
        (d.get("delivery_address") for d in documents if d.get("document_type") == DocumentType.COMPANY_DC),
        None,
    )
    addr_result = validate_addresses(cpo_address, cdc_address)
    # Map AddressMatchResult → ReferenceCheckResult
    if addr_result == AddressMatchResult.MATCH or addr_result == AddressMatchResult.PARTIAL:
        addr_check_result = ReferenceCheckResult.PASS
    elif addr_result == AddressMatchResult.MISMATCH:
        addr_check_result = ReferenceCheckResult.MISMATCH
        has_mismatch = True
    else:
        addr_check_result = ReferenceCheckResult.SKIP
    reference_checks.append({
        "document_type": DocumentType.CUSTOMER_PO,
        "check": "delivery_address",
        "result": addr_check_result,
        "extracted": cpo_address,
        "expected": cdc_address,
        "skip_reason": "missing_address" if addr_check_result == ReferenceCheckResult.SKIP else None,
    })
```

- [ ] **Step 5: Run all chain_validator tests**

```
cd backend
pytest tests/services/test_chain_validator.py -v
```

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/chain_validator.py backend/app/api/v1/purchase_orders.py backend/tests/services/test_chain_validator.py
git commit -m "feat: wire delivery address validation into chain pipeline"
```

---

## Task 3: Fix VPO AND-logic (all registered VPOs must appear on invoices)

**Context:** `check_vpo_reference()` currently returns PASS if ANY registered VPO appears on the vendor invoice (OR-logic). This means if PO has VPO-001 and VPO-002 but only VPO-001 appears on the invoice, the check passes silently. The correct behaviour is AND-logic: every registered VPO must be covered by at least one vendor invoice across all vendor invoice documents.

**Note:** The fix also needs to consider that `compute_chain_status()` calls `check_vpo_reference()` per vendor invoice document. For AND-logic, the check must be performed across ALL vendor invoice documents, not per-document. This means moving the VPO cross-check to a single aggregated call after the document loop.

**Files:**
- Modify: `backend/app/services/reference_validator.py:39-52`
- Modify: `backend/app/services/chain_validator.py` (call site)
- Modify: `backend/tests/services/test_reference_validator.py` (create if absent)
- Modify: `backend/tests/services/test_chain_validator.py`

- [ ] **Step 1: Write failing tests for reference_validator**

Create `backend/tests/services/test_reference_validator.py` if it doesn't exist:

```python
from app.services.reference_validator import check_vpo_reference, ReferenceCheckResult


def test_vpo_pass_when_all_registered_vpos_covered():
    # Both registered VPOs appear across the provided invoice VPO lists
    result = check_vpo_reference(
        doc_vpo_numbers_list=[["VPO-001", "VPO-002"]],
        registered_vpo_numbers=["VPO-001", "VPO-002"],
    )
    assert result == ReferenceCheckResult.PASS


def test_vpo_mismatch_when_one_registered_vpo_missing():
    # VPO-002 registered but not present in any invoice
    result = check_vpo_reference(
        doc_vpo_numbers_list=[["VPO-001"]],
        registered_vpo_numbers=["VPO-001", "VPO-002"],
    )
    assert result == ReferenceCheckResult.MISMATCH


def test_vpo_pass_when_vpos_spread_across_multiple_invoices():
    # VPO-001 in first invoice, VPO-002 in second invoice
    result = check_vpo_reference(
        doc_vpo_numbers_list=[["VPO-001"], ["VPO-002"]],
        registered_vpo_numbers=["VPO-001", "VPO-002"],
    )
    assert result == ReferenceCheckResult.PASS


def test_vpo_skip_when_no_registered_vpos():
    result = check_vpo_reference(
        doc_vpo_numbers_list=[["VPO-001"]],
        registered_vpo_numbers=[],
    )
    assert result == ReferenceCheckResult.SKIP


def test_vpo_skip_when_no_invoice_vpos():
    result = check_vpo_reference(
        doc_vpo_numbers_list=[[]],
        registered_vpo_numbers=["VPO-001"],
    )
    assert result == ReferenceCheckResult.SKIP
```

- [ ] **Step 2: Add chain_validator test for AND-logic**

Add to `backend/tests/services/test_chain_validator.py`:

```python
def test_vpo_and_logic_both_vpos_must_appear():
    """VPO-002 registered but missing from invoice → MISMATCH (not PASS)."""
    result = compute_chain_status(
        scenario=OrderScenario.PROCUREMENT,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=["VPO-001", "VPO-002"],
        documents=[
            _doc(DocumentType.CUSTOMER_PO),
            _doc(DocumentType.COMPANY_PO),
            _doc(DocumentType.COMPANY_DC, so_number="SO-001", cpo_ref="CPO-001"),
            _doc(DocumentType.COMPANY_INVOICE, so_number="SO-001", cpo_ref="CPO-001"),
            {
                "document_type": DocumentType.VENDOR_INVOICE,
                "so_number": "SO-001",
                "vpo_numbers": ["VPO-001"],   # VPO-002 missing
                "extraction_ok": True,
                "cpo_ref": None,
                "delivery_address": None,
            },
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    vpo_checks = [rc for rc in result["reference_checks"] if rc["check"] == "vpo_reference"]
    assert len(vpo_checks) == 1
    assert vpo_checks[0]["result"] == "mismatch"
    assert result["chain_status"] == ChainStatus.MISMATCH
```

- [ ] **Step 3: Run failing tests**

```
cd backend
pytest tests/services/test_reference_validator.py tests/services/test_chain_validator.py::test_vpo_and_logic_both_vpos_must_appear -v
```

Expected: FAIL — signature mismatch + AND-logic not implemented

- [ ] **Step 4: Update reference_validator.py — new AND-logic signature**

Replace `check_vpo_reference()` in `backend/app/services/reference_validator.py`:

```python
def check_vpo_reference(
    doc_vpo_numbers_list: list[list[str]],
    registered_vpo_numbers: list[str],
) -> ReferenceCheckResult:
    """
    Check that ALL registered VPO numbers are covered by at least one vendor invoice.

    doc_vpo_numbers_list: list of vpo_numbers lists, one per VENDOR_INVOICE document.
    registered_vpo_numbers: VPOs registered on the CPO (COMPANY_PO extracted vpo_numbers).

    Returns PASS only when every registered VPO appears in at least one invoice.
    """
    if not registered_vpo_numbers:
        return ReferenceCheckResult.SKIP
    # Flatten all VPOs across all invoices
    all_invoice_vpos = {v.strip() for vpo_list in doc_vpo_numbers_list for v in vpo_list}
    if not all_invoice_vpos:
        return ReferenceCheckResult.SKIP
    registered_set = {v.strip() for v in registered_vpo_numbers}
    if registered_set.issubset(all_invoice_vpos):
        return ReferenceCheckResult.PASS
    return ReferenceCheckResult.MISMATCH
```

- [ ] **Step 5: Update chain_validator.py — aggregate VPO check outside the per-doc loop**

In `backend/app/services/chain_validator.py`, remove the per-document VPO check block from inside the `for doc in documents` loop, and replace it with a single aggregated call after the loop. The final per-document loop becomes:

```python
    for doc in documents:
        doc_type = doc.get("document_type")
        if doc_type is None:
            continue
        ok = doc.get("extraction_ok", True)

        if doc_type in (DocumentType.COMPANY_DC, DocumentType.COMPANY_INVOICE):
            extracted_so = doc.get("so_number") if ok else None
            so_result = check_so_consistency(
                extracted_so=extracted_so,
                expected_so=so_number,
            )
            if so_result == ReferenceCheckResult.SKIP:
                so_skip_reason = "extraction_failed" if not ok else ("no_so_number" if not so_number else "no_extracted_value")
            else:
                so_skip_reason = None

            extracted_cpo = doc.get("cpo_ref") if ok else None
            cpo_result = check_cpo_reference(
                extracted_cpo_ref=extracted_cpo,
                expected_po_number=po_number,
            )
            cpo_skip_reason = "extraction_failed" if cpo_result == ReferenceCheckResult.SKIP and not ok else None

            reference_checks.append({
                "document_type": doc_type,
                "check": "so_consistency",
                "result": so_result,
                "extracted": extracted_so,
                "expected": so_number,
                "skip_reason": so_skip_reason,
            })
            reference_checks.append({
                "document_type": doc_type,
                "check": "cpo_reference",
                "result": cpo_result,
                "extracted": extracted_cpo,
                "expected": po_number,
                "skip_reason": cpo_skip_reason,
            })
            if so_result == ReferenceCheckResult.MISMATCH:
                has_mismatch = True
            if cpo_result == ReferenceCheckResult.MISMATCH:
                has_mismatch = True

    # VPO check — aggregated across all VENDOR_INVOICE documents (AND-logic)
    vendor_invoices = [d for d in documents if d.get("document_type") == DocumentType.VENDOR_INVOICE]
    if vendor_invoices or (vpo_numbers or []):
        doc_vpo_numbers_list = [d.get("vpo_numbers") or [] for d in vendor_invoices]
        vpo_result = check_vpo_reference(
            doc_vpo_numbers_list=doc_vpo_numbers_list,
            registered_vpo_numbers=vpo_numbers or [],
        )
        vpo_skip_reason = None
        if vpo_result == ReferenceCheckResult.SKIP:
            vpo_skip_reason = "no_vpo_registered" if not (vpo_numbers or []) else "no_extracted_vpo"
        all_invoice_vpos = [v for vpo_list in doc_vpo_numbers_list for v in vpo_list]
        reference_checks.append({
            "document_type": DocumentType.VENDOR_INVOICE,
            "check": "vpo_reference",
            "result": vpo_result,
            "extracted": ", ".join(all_invoice_vpos) if all_invoice_vpos else None,
            "expected": ", ".join(vpo_numbers or []) if vpo_numbers else None,
            "skip_reason": vpo_skip_reason,
        })
        if vpo_result == ReferenceCheckResult.MISMATCH:
            has_mismatch = True
```

- [ ] **Step 6: Run all tests**

```
cd backend
pytest tests/services/test_chain_validator.py tests/services/test_reference_validator.py -v
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/reference_validator.py backend/app/services/chain_validator.py backend/tests/services/test_reference_validator.py backend/tests/services/test_chain_validator.py
git commit -m "fix: VPO validation uses AND-logic — all registered VPOs must appear on invoices"
```

---

## Final smoke test

After all 3 tasks, run the full backend test suite:

```
cd backend
pytest tests/ -v --tb=short
```

Then open `http://localhost:5174/purchase-orders/[any-PO-with-docs]` and verify:
- Reference check pills now show `⚠` in orange when extraction failed (not plain grey `○`)
- Hovering a red `✗` pill shows a tooltip with `Extracted: X | Expected: Y`
- Address mismatch (if any PO has different delivery address on CUSTOMER_PO vs COMPANY_DC) shows a `✗ delivery_address` pill

---

*Plan saved 2026-04-18. Covers audit gaps: reference check detail (HIGH), address validation wiring (HIGH), VPO AND-logic (MEDIUM).*
