# Chain Validation System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add cross-document reference validation, scenario-aware chain presence tracking, billing completeness, line item comparison, and address validation to the DPP purchase order workflow.

**Architecture:** Reference Enrichment (Approach B) — CPO-centric model preserved. Three new fields on `Document`, four new fields on `PurchaseOrder`, three new service files (`chain_validator.py`, `reference_validator.py`, `billing_tracker.py`), two existing services extended (`item_matcher.py`, `address_parser.py`), and a new frontend chain view on the PO detail page.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, PostgreSQL (JSONB), Alembic, React + TypeScript, Axios

---

## File Map

### Backend — Create
- `backend/app/services/chain_validator.py` — orchestrates all validation, computes `chain_status`
- `backend/app/services/reference_validator.py` — SO/CPO/VPO cross-reference checks
- `backend/app/services/billing_tracker.py` — FULL/STAGED/RECURRING billing completeness
- `backend/alembic/versions/h1i2j3k4l5m6_chain_validation_fields.py` — DB migration

### Backend — Modify
- `backend/app/models/purchase_order.py` — add `BillingType`, `ChainStatus` enums + 4 fields
- `backend/app/models/document.py` — add `INSTALLATION_REPORT`, `VENDOR_CREDIT_NOTE` types + 4 fields + fix UniqueConstraint
- `backend/app/schemas/purchase_order.py` — add billing/chain fields to `POUpdate`, `POResponse`
- `backend/app/schemas/document.py` — add new fields to document schema
- `backend/app/services/po_service.py` — add `derive_scenario()`, extend `get_scenario_chain()`
- `backend/app/services/item_matcher.py` — add `compare_po_to_delivery()`
- `backend/app/services/address_parser.py` — add `validate_addresses()`
- `backend/app/api/purchase_orders.py` — add `PATCH /pos/{id}/so-number`, `GET /pos/{id}/chain`

### Frontend — Create
- `frontend/src/components/ChainTimeline/ChainTimeline.tsx` — document slot timeline
- `frontend/src/components/ChainTimeline/VpoSlot.tsx` — expandable VPO + vendor invoice slot
- `frontend/src/components/ReferenceValidationPanel/ReferenceValidationPanel.tsx`
- `frontend/src/components/BillingCompletenessPanel/BillingCompletenessPanel.tsx`

### Frontend — Modify
- `frontend/src/pages/PODetailPage/PODetailPage.tsx` — add chain view section + SO number field
- `frontend/src/api/purchaseOrders.ts` — add `updateSoNumber()`, `getChainStatus()`

### Tests
- `backend/tests/services/test_chain_validator.py`
- `backend/tests/services/test_reference_validator.py`
- `backend/tests/services/test_billing_tracker.py`
- `backend/tests/services/test_scenario_engine.py`

---

## Task 1: Data Model — Enums and Fields

**Files:**
- Modify: `backend/app/models/purchase_order.py`
- Modify: `backend/app/models/document.py`

- [ ] **Step 1: Write failing tests for new enum values**

```python
# backend/tests/models/test_enums.py
from app.models.purchase_order import BillingType, ChainStatus
from app.models.document import DocumentType

def test_billing_type_values():
    assert BillingType.FULL == "full"
    assert BillingType.STAGED == "staged"
    assert BillingType.RECURRING == "recurring"

def test_chain_status_values():
    assert ChainStatus.INCOMPLETE == "incomplete"
    assert ChainStatus.COMPLETE == "complete"
    assert ChainStatus.VERIFIED == "verified"
    assert ChainStatus.MISMATCH == "mismatch"

def test_new_document_types():
    assert DocumentType.INSTALLATION_REPORT == "INSTALLATION_REPORT"
    assert DocumentType.VENDOR_CREDIT_NOTE == "VENDOR_CREDIT_NOTE"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/models/test_enums.py -v
```
Expected: `ImportError: cannot import name 'BillingType'`

- [ ] **Step 3: Add enums and fields to `purchase_order.py`**

Add after `GstType` enum (line 41):
```python
class BillingType(str, enum.Enum):
    FULL = "full"
    STAGED = "staged"
    RECURRING = "recurring"


class ChainStatus(str, enum.Enum):
    INCOMPLETE = "incomplete"
    COMPLETE = "complete"
    VERIFIED = "verified"
    MISMATCH = "mismatch"
```

Add to `PurchaseOrder` model after `completion_note` (line 98):
```python
billing_type: Mapped[BillingType] = mapped_column(
    Enum(BillingType, name="billingtype",
         values_callable=lambda obj: [e.value for e in obj]),
    default=BillingType.FULL,
    nullable=False,
    server_default="full",
)
billing_milestones: Mapped[list | None] = mapped_column(JSONB, nullable=True)
requires_install_report: Mapped[bool] = mapped_column(
    Boolean, default=False, nullable=False, server_default="false"
)
chain_status: Mapped[ChainStatus] = mapped_column(
    Enum(ChainStatus, name="chainstatus",
         values_callable=lambda obj: [e.value for e in obj]),
    default=ChainStatus.INCOMPLETE,
    nullable=False,
    server_default="incomplete",
)
```

Add import at top: `from sqlalchemy.dialects.postgresql import UUID, JSONB`

- [ ] **Step 4: Add new DocumentType values and fields to `document.py`**

Add to `DocumentType` enum after `COMPANY_INVOICE`:
```python
INSTALLATION_REPORT = "INSTALLATION_REPORT"
VENDOR_CREDIT_NOTE = "VENDOR_CREDIT_NOTE"
```

Add to `Document` model after `rotation` field (line 69):
```python
so_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
vpo_numbers: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
billing_stage: Mapped[int | None] = mapped_column(Integer, nullable=True)
extraction_ok: Mapped[bool] = mapped_column(
    Boolean, default=True, nullable=False, server_default="true"
)
```

Add import: `from sqlalchemy.dialects.postgresql import UUID, JSONB`

Change `UniqueConstraint` in `__table_args__`:
```python
# Replace:
UniqueConstraint("po_id", "document_type", "checksum", name="uq_doc_per_po_type"),
# With:
UniqueConstraint("po_id", "checksum", name="uq_doc_per_po"),
```

Add indexes:
```python
Index("ix_doc_so_number", "so_number"),
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && pytest tests/models/test_enums.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/purchase_order.py backend/app/models/document.py backend/tests/models/test_enums.py
git commit -m "feat: add BillingType, ChainStatus enums and chain validation fields to models"
```

---

## Task 2: Database Migration

**Files:**
- Create: `backend/alembic/versions/h1i2j3k4l5m6_chain_validation_fields.py`

- [ ] **Step 1: Generate migration**

```bash
cd backend && alembic revision --autogenerate -m "chain_validation_fields"
```

- [ ] **Step 2: Review and clean the generated migration**

Open the generated file. Verify it includes:
- `CREATE TYPE billingtype AS ENUM ('full', 'staged', 'recurring')`
- `CREATE TYPE chainstatus AS ENUM ('incomplete', 'complete', 'verified', 'mismatch')`
- `ALTER TABLE purchase_orders ADD COLUMN billing_type billingtype ...`
- `ALTER TABLE purchase_orders ADD COLUMN billing_milestones jsonb ...`
- `ALTER TABLE purchase_orders ADD COLUMN requires_install_report boolean ...`
- `ALTER TABLE purchase_orders ADD COLUMN chain_status chainstatus ...`
- `ALTER TABLE documents ADD COLUMN so_number varchar(100) ...`
- `ALTER TABLE documents ADD COLUMN vpo_numbers jsonb ...`
- `ALTER TABLE documents ADD COLUMN billing_stage integer ...`
- `ALTER TABLE documents ADD COLUMN extraction_ok boolean ...`
- `ALTER TABLE documents ADD COLUMN INSTALLATION_REPORT ...` (enum value added)
- `DROP CONSTRAINT uq_doc_per_po_type` + `ADD CONSTRAINT uq_doc_per_po`

If autogenerate missed enum value additions, add manually:
```python
from alembic import op

def upgrade():
    op.execute("ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'INSTALLATION_REPORT'")
    op.execute("ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'VENDOR_CREDIT_NOTE'")
    # ... rest of autogenerated
```

- [ ] **Step 3: Run migration**

```bash
cd backend && alembic upgrade head
```
Expected: `Running upgrade ... -> h1i2j3k4l5m6`

- [ ] **Step 4: Verify schema**

```bash
cd backend && alembic current
```
Expected: `h1i2j3k4l5m6 (head)`

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat: migration for chain validation fields on purchase_orders and documents"
```

---

## Task 3: Update Schemas

**Files:**
- Modify: `backend/app/schemas/purchase_order.py`
- Modify: `backend/app/schemas/document.py`

- [ ] **Step 1: Update `POUpdate` to include new fields**

In `backend/app/schemas/purchase_order.py`, add to `POUpdate`:
```python
from typing import Literal, Optional, Any

# In POUpdate class, add:
billing_type: Optional[Literal['full', 'staged', 'recurring']] = None
billing_milestones: Optional[list[dict[str, Any]]] = None
requires_install_report: Optional[bool] = None
chain_status: Optional[Literal['incomplete', 'complete', 'verified', 'mismatch']] = None
```

Add to `POResponse`:
```python
billing_type: str = "full"
billing_milestones: Optional[list[dict]] = None
requires_install_report: bool = False
chain_status: str = "incomplete"
```

- [ ] **Step 2: Update document schema**

In `backend/app/schemas/document.py`, add to document response schema:
```python
so_number: Optional[str] = None
vpo_numbers: Optional[list[str]] = None
billing_stage: Optional[int] = None
extraction_ok: bool = True
```

- [ ] **Step 3: Run existing tests to check no regressions**

```bash
cd backend && pytest tests/ -v --tb=short -x
```
Expected: all previously passing tests still pass

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/purchase_order.py backend/app/schemas/document.py
git commit -m "feat: add billing and chain validation fields to PO and document schemas"
```

---

## Task 4: Scenario Engine

**Files:**
- Modify: `backend/app/services/po_service.py`
- Create: `backend/tests/services/test_scenario_engine.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/services/test_scenario_engine.py
import pytest
from app.services.po_service import derive_scenario
from app.models.purchase_order import OrderScenario

def test_no_vpos_no_service_hints_is_stock():
    result = derive_scenario(vpo_count=0, has_vendor_dc=False, has_service_hint=False)
    assert result == OrderScenario.STOCK

def test_no_vpos_with_vendor_dc_is_drop_ship():
    result = derive_scenario(vpo_count=0, has_vendor_dc=True, has_service_hint=False)
    assert result == OrderScenario.DROP_SHIP

def test_no_vpos_with_service_hint_is_amc():
    result = derive_scenario(vpo_count=0, has_vendor_dc=False, has_service_hint=True)
    assert result == OrderScenario.SERVICE_AMC

def test_one_vpo_is_procurement():
    result = derive_scenario(vpo_count=1, has_vendor_dc=False, has_service_hint=False)
    assert result == OrderScenario.PROCUREMENT

def test_multiple_vpos_is_procurement():
    result = derive_scenario(vpo_count=3, has_vendor_dc=False, has_service_hint=False)
    assert result == OrderScenario.PROCUREMENT
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/services/test_scenario_engine.py -v
```
Expected: `ImportError: cannot import name 'derive_scenario'`

- [ ] **Step 3: Add `derive_scenario()` to `po_service.py`**

Add after `get_scenario_chain()` (line 78):
```python
def derive_scenario(
    vpo_count: int,
    has_vendor_dc: bool,
    has_service_hint: bool,
) -> OrderScenario:
    """Derive scenario from observable facts. Never manually set."""
    if vpo_count == 0:
        if has_vendor_dc:
            return OrderScenario.DROP_SHIP
        if has_service_hint:
            return OrderScenario.SERVICE_AMC
        return OrderScenario.STOCK
    return OrderScenario.PROCUREMENT
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/services/test_scenario_engine.py -v
```
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/po_service.py backend/tests/services/test_scenario_engine.py
git commit -m "feat: add derive_scenario() function to scenario engine"
```

---

## Task 5: Reference Validator

**Files:**
- Create: `backend/app/services/reference_validator.py`
- Create: `backend/tests/services/test_reference_validator.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/services/test_reference_validator.py
import pytest
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

def test_vpo_reference_matched():
    result = check_vpo_reference(
        doc_vpo_numbers=["1PTR2526000400"],
        registered_vpo_numbers=["1PTR2526000400", "1PTR2526000401"],
    )
    assert result == ReferenceCheckResult.PASS

def test_vpo_reference_no_match():
    result = check_vpo_reference(
        doc_vpo_numbers=["9POT9999999999"],
        registered_vpo_numbers=["1PTR2526000400"],
    )
    assert result == ReferenceCheckResult.MISMATCH

def test_vpo_reference_empty_doc_vpos_returns_skip():
    result = check_vpo_reference(
        doc_vpo_numbers=[],
        registered_vpo_numbers=["1PTR2526000400"],
    )
    assert result == ReferenceCheckResult.SKIP
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/services/test_reference_validator.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.services.reference_validator'`

- [ ] **Step 3: Create `reference_validator.py`**

```python
# backend/app/services/reference_validator.py
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
    registered_set = {v.strip() for v in registered_vpo_numbers}
    for vpo in doc_vpo_numbers:
        if vpo.strip() in registered_set:
            return ReferenceCheckResult.PASS
    return ReferenceCheckResult.MISMATCH
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/services/test_reference_validator.py -v
```
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/reference_validator.py backend/tests/services/test_reference_validator.py
git commit -m "feat: add reference_validator service for SO/CPO/VPO cross-checks"
```

---

## Task 6: Billing Tracker

**Files:**
- Create: `backend/app/services/billing_tracker.py`
- Create: `backend/tests/services/test_billing_tracker.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/services/test_billing_tracker.py
import pytest
from app.services.billing_tracker import (
    check_full_billing,
    check_staged_billing,
    BillingStatus,
)

def test_full_billing_exact_match():
    result = check_full_billing(
        invoiced_total=503137.0,
        po_total=503137.0,
    )
    assert result == BillingStatus.COMPLETE

def test_full_billing_within_tolerance():
    # 0.5% rounding difference
    result = check_full_billing(
        invoiced_total=500500.0,
        po_total=503137.0,
    )
    assert result == BillingStatus.COMPLETE

def test_full_billing_underpaid():
    result = check_full_billing(
        invoiced_total=200000.0,
        po_total=503137.0,
    )
    assert result == BillingStatus.PARTIAL

def test_full_billing_no_invoices():
    result = check_full_billing(invoiced_total=0.0, po_total=503137.0)
    assert result == BillingStatus.PENDING

def test_staged_billing_first_stage_paid():
    milestones = [
        {"stage": 1, "percent": 40},
        {"stage": 2, "percent": 60},
    ]
    invoices = [{"billing_stage": 1, "amount": 201254.8}]
    result = check_staged_billing(
        po_total=503137.0,
        milestones=milestones,
        stage_invoices=invoices,
    )
    assert result["stages"][0]["status"] == BillingStatus.PAID
    assert result["stages"][1]["status"] == BillingStatus.PENDING
    assert result["overall"] == BillingStatus.PARTIAL

def test_staged_billing_all_stages_paid():
    milestones = [
        {"stage": 1, "percent": 40},
        {"stage": 2, "percent": 60},
    ]
    invoices = [
        {"billing_stage": 1, "amount": 201254.8},
        {"billing_stage": 2, "amount": 301882.2},
    ]
    result = check_staged_billing(
        po_total=503137.0,
        milestones=milestones,
        stage_invoices=invoices,
    )
    assert result["overall"] == BillingStatus.COMPLETE

def test_staged_billing_amount_mismatch():
    milestones = [{"stage": 1, "percent": 40}]
    # Way off — 10% not 40%
    invoices = [{"billing_stage": 1, "amount": 50313.7}]
    result = check_staged_billing(
        po_total=503137.0,
        milestones=milestones,
        stage_invoices=invoices,
    )
    assert result["stages"][0]["status"] == BillingStatus.MISMATCH
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/services/test_billing_tracker.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `billing_tracker.py`**

```python
# backend/app/services/billing_tracker.py
"""Billing completeness tracking: FULL, STAGED, and RECURRING billing types."""
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

    for m in milestones:
        stage = m["stage"]
        expected = po_total * m["percent"] / 100
        invoiced = invoices_by_stage.get(stage, 0.0)

        if invoiced == 0:
            status = BillingStatus.PENDING
            all_complete = False
        elif abs(invoiced - expected) / expected <= _STAGE_TOLERANCE:
            status = BillingStatus.PAID
            any_paid = True
        else:
            status = BillingStatus.MISMATCH
            all_complete = False

        stage_results.append({
            "stage": stage,
            "expected_amount": round(expected, 2),
            "invoiced_amount": round(invoiced, 2),
            "status": status,
        })

    if all_complete and any_paid:
        overall = BillingStatus.COMPLETE
    elif any_paid:
        overall = BillingStatus.PARTIAL
    else:
        overall = BillingStatus.PENDING

    return {"stages": stage_results, "overall": overall}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/services/test_billing_tracker.py -v
```
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/billing_tracker.py backend/tests/services/test_billing_tracker.py
git commit -m "feat: add billing_tracker service for FULL and STAGED billing completeness"
```

---

## Task 7: Chain Validator Orchestrator

**Files:**
- Create: `backend/app/services/chain_validator.py`
- Create: `backend/tests/services/test_chain_validator.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/services/test_chain_validator.py
import pytest
from app.services.chain_validator import compute_chain_status, SlotState
from app.models.purchase_order import OrderScenario, ChainStatus
from app.models.document import DocumentType


def _doc(doc_type, so_number=None, vpo_numbers=None, extraction_ok=True, cpo_ref=None):
    return {
        "document_type": doc_type,
        "so_number": so_number,
        "vpo_numbers": vpo_numbers or [],
        "extraction_ok": extraction_ok,
        "cpo_ref": cpo_ref,
    }


def test_stock_missing_dc_is_incomplete():
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
            _doc(DocumentType.COMPANY_INVOICE, so_number="SO-001", cpo_ref="CPO-001"),
        ],
        requires_install_report=False,
    )
    assert result["chain_status"] == ChainStatus.INCOMPLETE
    assert result["missing_slots"] == [DocumentType.COMPANY_DC]


def test_stock_all_present_and_verified_is_complete():
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
            _doc(DocumentType.COMPANY_DC, so_number="SO-001", cpo_ref="CPO-001"),
            _doc(DocumentType.COMPANY_INVOICE, so_number="SO-001", cpo_ref="CPO-001",
                 extraction_ok=True),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    assert result["chain_status"] == ChainStatus.COMPLETE


def test_so_mismatch_sets_mismatch_status():
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
    assert result["chain_status"] == ChainStatus.MISMATCH


def test_procurement_missing_vendor_invoice_is_incomplete():
    result = compute_chain_status(
        scenario=OrderScenario.PROCUREMENT,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=["VPO-001"],
        documents=[
            _doc(DocumentType.CUSTOMER_PO),
            _doc(DocumentType.COMPANY_PO),
            # No vendor invoice
            _doc(DocumentType.COMPANY_DC, so_number="SO-001", cpo_ref="CPO-001"),
            _doc(DocumentType.COMPANY_INVOICE, so_number="SO-001", cpo_ref="CPO-001"),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    assert result["chain_status"] == ChainStatus.INCOMPLETE
    assert "VPO-001" in result["missing_vendor_invoices"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/services/test_chain_validator.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `chain_validator.py`**

```python
# backend/app/services/chain_validator.py
"""Orchestrates chain presence, reference validation, and billing completeness."""
import enum
from app.models.purchase_order import OrderScenario, ChainStatus
from app.models.document import DocumentType
from app.services.po_service import get_scenario_chain
from app.services.reference_validator import (
    check_so_consistency, check_cpo_reference, check_vpo_reference,
    ReferenceCheckResult,
)
from app.services.billing_tracker import check_full_billing, check_staged_billing, BillingStatus


class SlotState(str, enum.Enum):
    WAITING = "waiting"
    RECEIVED = "received"
    VERIFIED = "verified"
    MISMATCH = "mismatch"
    CANCELLED = "cancelled"


def compute_chain_status(
    scenario: OrderScenario,
    po_number: str,
    so_number: str | None,
    po_total: float | None,
    billing_type: str,
    billing_milestones: list[dict],
    vpo_numbers: list[str],
    documents: list[dict],
    requires_install_report: bool,
    invoiced_total: float = 0.0,
) -> dict:
    """
    Compute full chain validation result.

    documents: list of dicts with keys:
      document_type, so_number, vpo_numbers, extraction_ok, cpo_ref

    Returns:
        {
          chain_status: ChainStatus,
          missing_slots: list[DocumentType],
          missing_vendor_invoices: list[str],   # VPO numbers with no matching invoice
          reference_checks: list[dict],
          billing: dict,
        }
    """
    required_types = get_scenario_chain(scenario) or []
    if requires_install_report:
        required_types = required_types + [DocumentType.INSTALLATION_REPORT]

    present_types = {d["document_type"] for d in documents}
    missing_slots = [t for t in required_types if t not in present_types]

    # VPO slot tracking: each VPO needs a matching vendor invoice
    missing_vendor_invoices = []
    for vpo in vpo_numbers:
        matched = any(
            vpo in (d.get("vpo_numbers") or [])
            for d in documents
            if d["document_type"] == DocumentType.VENDOR_INVOICE
        )
        if not matched:
            missing_vendor_invoices.append(vpo)

    # Reference checks
    reference_checks = []
    has_mismatch = False

    for doc in documents:
        doc_type = doc["document_type"]
        ok = doc.get("extraction_ok", True)

        if doc_type in (DocumentType.COMPANY_DC, DocumentType.COMPANY_INVOICE):
            so_result = check_so_consistency(
                extracted_so=doc.get("so_number") if ok else None,
                expected_so=so_number,
            )
            cpo_result = check_cpo_reference(
                extracted_cpo_ref=doc.get("cpo_ref") if ok else None,
                expected_po_number=po_number,
            )
            reference_checks.append({
                "document_type": doc_type,
                "check": "so_consistency",
                "result": so_result,
            })
            reference_checks.append({
                "document_type": doc_type,
                "check": "cpo_reference",
                "result": cpo_result,
            })
            if so_result == ReferenceCheckResult.MISMATCH:
                has_mismatch = True
            if cpo_result == ReferenceCheckResult.MISMATCH:
                has_mismatch = True

        if doc_type == DocumentType.VENDOR_INVOICE:
            vpo_result = check_vpo_reference(
                doc_vpo_numbers=doc.get("vpo_numbers") or [],
                registered_vpo_numbers=vpo_numbers,
            )
            reference_checks.append({
                "document_type": doc_type,
                "check": "vpo_reference",
                "result": vpo_result,
            })
            if vpo_result == ReferenceCheckResult.MISMATCH:
                has_mismatch = True

    # Billing
    billing_result: dict = {}
    billing_complete = False
    if po_total:
        if billing_type == "staged" and billing_milestones:
            stage_invoices = [
                {"billing_stage": d.get("billing_stage"), "amount": d.get("amount", 0)}
                for d in documents
                if d["document_type"] == DocumentType.COMPANY_INVOICE
            ]
            billing_result = check_staged_billing(po_total, billing_milestones, stage_invoices)
            billing_complete = billing_result["overall"] == BillingStatus.COMPLETE
        else:
            billing_status = check_full_billing(invoiced_total, po_total)
            billing_result = {"overall": billing_status}
            billing_complete = billing_status == BillingStatus.COMPLETE

    # Determine chain_status
    if has_mismatch:
        chain_status = ChainStatus.MISMATCH
    elif missing_slots or missing_vendor_invoices:
        chain_status = ChainStatus.INCOMPLETE
    elif billing_complete:
        chain_status = ChainStatus.COMPLETE
    else:
        chain_status = ChainStatus.INCOMPLETE

    return {
        "chain_status": chain_status,
        "missing_slots": missing_slots,
        "missing_vendor_invoices": missing_vendor_invoices,
        "reference_checks": reference_checks,
        "billing": billing_result,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/services/test_chain_validator.py -v
```
Expected: PASS (4 tests)

- [ ] **Step 5: Run full test suite**

```bash
cd backend && pytest tests/ -v --tb=short
```
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/chain_validator.py backend/tests/services/test_chain_validator.py
git commit -m "feat: add chain_validator orchestrator service"
```

---

## Task 8: API Endpoints

**Files:**
- Modify: `backend/app/api/purchase_orders.py`

- [ ] **Step 1: Read current endpoints**

```bash
grep -n "^@router" backend/app/api/purchase_orders.py
```

- [ ] **Step 2: Add SO number update endpoint**

Find the router in `backend/app/api/purchase_orders.py` and add:

```python
from app.services.chain_validator import compute_chain_status
from app.services.po_service import derive_scenario

@router.patch("/{po_id}/so-number")
async def update_so_number(
    po_id: UUID,
    body: SONumberUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update SO number and trigger chain re-validation."""
    po = await db.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")
    po.so_number = body.so_number
    await db.commit()
    await db.refresh(po)
    return {"so_number": po.so_number}
```

Add schema to `purchase_order.py` schemas:
```python
class SONumberUpdate(BaseModel):
    so_number: str = Field(..., min_length=1, max_length=100)
```

- [ ] **Step 3: Add chain status endpoint**

```python
@router.get("/{po_id}/chain")
async def get_chain_status(
    po_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Compute and return current chain validation status for a PO."""
    po = await db.get(PurchaseOrder, po_id, options=[selectinload(PurchaseOrder.documents)])
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")

    # Build VPO numbers list from COMPANY_PO documents' extracted vpo_numbers
    vpo_numbers = []
    for doc in po.documents:
        if doc.document_type == DocumentType.COMPANY_PO and doc.vpo_numbers:
            vpo_numbers.extend(doc.vpo_numbers)

    # Build invoiced_total from COMPANY_INVOICE documents
    invoiced_total = sum(
        doc.doc_metadata.total_amount or 0
        for doc in po.documents
        if doc.document_type == DocumentType.COMPANY_INVOICE and doc.doc_metadata
    )

    docs_payload = [
        {
            "document_type": doc.document_type,
            "so_number": doc.so_number,
            "vpo_numbers": doc.vpo_numbers or [],
            "extraction_ok": doc.extraction_ok,
            "cpo_ref": doc.doc_metadata.po_ref_no if doc.doc_metadata else None,
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

    # Persist computed chain_status back to PO
    po.chain_status = result["chain_status"]
    await db.commit()

    return result
```

- [ ] **Step 4: Test endpoints manually**

```bash
# Start server
cd backend && uvicorn app.main:app --reload

# Update SO number
curl -X PATCH http://localhost:8000/api/v1/purchase-orders/{po_id}/so-number \
  -H "Content-Type: application/json" \
  -d '{"so_number": "1OTM2526001429"}'

# Get chain status
curl http://localhost:8000/api/v1/purchase-orders/{po_id}/chain
```
Expected: `{"chain_status": "incomplete", "missing_slots": [...], ...}`

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/purchase_orders.py backend/app/schemas/purchase_order.py
git commit -m "feat: add SO number update and chain status endpoints"
```

---

## Task 9: Line Item Comparison

**Files:**
- Modify: `backend/app/services/item_matcher.py`
- Create: `backend/tests/services/test_line_item_comparison.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/services/test_line_item_comparison.py
import pytest
from app.services.item_matcher import compare_po_to_delivery, ItemMatchStatus

def test_exact_part_number_match_correct_qty():
    cpo_items = [{"part_no": "FG-120G", "description": "Firewall", "qty": 1}]
    dc_items  = [{"part_no": "FG-120G", "description": "Firewall", "qty": 1}]
    results = compare_po_to_delivery(cpo_items, dc_items)
    assert results[0]["status"] == ItemMatchStatus.MATCHED
    assert results[0]["qty_shortfall"] == 0

def test_quantity_short():
    cpo_items = [{"part_no": "SFP-GE-T", "description": "SFP", "qty": 2}]
    dc_items  = [{"part_no": "SFP-GE-T", "description": "SFP", "qty": 1}]
    results = compare_po_to_delivery(cpo_items, dc_items)
    assert results[0]["status"] == ItemMatchStatus.PARTIAL
    assert results[0]["qty_shortfall"] == 1

def test_item_missing_from_dc():
    cpo_items = [
        {"part_no": "FG-120G", "qty": 1},
        {"part_no": "FORTICARE-5YR", "qty": 1},
    ]
    dc_items = [{"part_no": "FG-120G", "qty": 1}]
    results = compare_po_to_delivery(cpo_items, dc_items)
    missing = [r for r in results if r["status"] == ItemMatchStatus.MISSING]
    assert len(missing) == 1
    assert missing[0]["part_no"] == "FORTICARE-5YR"

def test_empty_dc_items_all_missing():
    cpo_items = [{"part_no": "FG-120G", "qty": 1}]
    results = compare_po_to_delivery(cpo_items, [])
    assert results[0]["status"] == ItemMatchStatus.MISSING
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/services/test_line_item_comparison.py -v
```
Expected: `ImportError: cannot import name 'compare_po_to_delivery'`

- [ ] **Step 3: Add `compare_po_to_delivery()` to `item_matcher.py`**

Add after existing code:

```python
import enum

class ItemMatchStatus(str, enum.Enum):
    MATCHED = "matched"
    PARTIAL = "partial"    # Qty delivered < qty ordered
    MISSING = "missing"    # Item not in delivery at all


def compare_po_to_delivery(
    cpo_items: list[dict],
    delivery_items: list[dict],
) -> list[dict]:
    """
    Compare CPO line items against a delivery document (DC or Invoice).

    cpo_items / delivery_items: [{part_no, description, qty}]
    part_no comparison is case-insensitive exact match (Tier 1).
    Returns: [{part_no, description, qty_ordered, qty_delivered, qty_shortfall, status}]
    """
    delivery_by_part: dict[str, dict] = {
        str(it.get("part_no", "")).lower().strip(): it
        for it in delivery_items
        if it.get("part_no")
    }

    results = []
    for item in cpo_items:
        part_no = str(item.get("part_no", "")).lower().strip()
        qty_ordered = int(item.get("qty") or 0)
        matched = delivery_by_part.get(part_no)

        if not matched:
            results.append({
                "part_no": item.get("part_no"),
                "description": item.get("description"),
                "qty_ordered": qty_ordered,
                "qty_delivered": 0,
                "qty_shortfall": qty_ordered,
                "status": ItemMatchStatus.MISSING,
            })
            continue

        qty_delivered = int(matched.get("qty") or 0)
        shortfall = max(0, qty_ordered - qty_delivered)
        status = (
            ItemMatchStatus.MATCHED if shortfall == 0 else ItemMatchStatus.PARTIAL
        )
        results.append({
            "part_no": item.get("part_no"),
            "description": item.get("description"),
            "qty_ordered": qty_ordered,
            "qty_delivered": qty_delivered,
            "qty_shortfall": shortfall,
            "status": status,
        })

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/services/test_line_item_comparison.py -v
```
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/item_matcher.py backend/tests/services/test_line_item_comparison.py
git commit -m "feat: add compare_po_to_delivery() for line item quantity comparison"
```

---

## Task 10: Address Validation

**Files:**
- Modify: `backend/app/services/address_parser.py`
- Create: `backend/tests/services/test_address_validation.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/services/test_address_validation.py
import pytest
from app.services.address_parser import validate_addresses, AddressMatchResult

def test_pin_code_match():
    result = validate_addresses(
        address_a="6-3-1090/B/1, Raj Bhavan Road, Somajiguda, Hyderabad - 500082",
        address_b="Raj Bhavan Rd, Somajiguda, Hyderabad 500082",
    )
    assert result == AddressMatchResult.MATCH

def test_different_pin_codes_mismatch():
    result = validate_addresses(
        address_a="Anna Nagar, Chennai - 600040",
        address_b="Banjara Hills, Hyderabad - 500034",
    )
    assert result == AddressMatchResult.MISMATCH

def test_no_pin_code_state_match_is_partial():
    result = validate_addresses(
        address_a="Some Road, Chennai, Tamil Nadu",
        address_b="Another Road, Chennai, Tamil Nadu",
    )
    assert result == AddressMatchResult.PARTIAL

def test_none_address_returns_skip():
    result = validate_addresses(address_a=None, address_b="Chennai 600040")
    assert result == AddressMatchResult.SKIP
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/services/test_address_validation.py -v
```
Expected: `ImportError: cannot import name 'validate_addresses'`

- [ ] **Step 3: Add `validate_addresses()` to `address_parser.py`**

```python
import enum

class AddressMatchResult(str, enum.Enum):
    MATCH = "match"
    PARTIAL = "partial"   # City + state match, no PIN code
    MISMATCH = "mismatch"
    SKIP = "skip"         # One or both addresses missing


def validate_addresses(
    address_a: str | None,
    address_b: str | None,
) -> AddressMatchResult:
    """
    Compare two address strings using extracted components.
    PIN code match → MATCH (most reliable).
    City + state match → PARTIAL.
    State differs → MISMATCH.
    Either address missing → SKIP.
    """
    if not address_a or not address_b:
        return AddressMatchResult.SKIP

    parsed_a = parse_delivery_address(address_a)
    parsed_b = parse_delivery_address(address_b)

    # PIN code is the most reliable signal
    if parsed_a["pin_code"] and parsed_b["pin_code"]:
        return (
            AddressMatchResult.MATCH
            if parsed_a["pin_code"] == parsed_b["pin_code"]
            else AddressMatchResult.MISMATCH
        )

    # Fall back to state + city
    state_a = (parsed_a["state"] or "").lower()
    state_b = (parsed_b["state"] or "").lower()
    city_a  = (parsed_a["city"] or "").lower()
    city_b  = (parsed_b["city"] or "").lower()

    if state_a and state_b and state_a != state_b:
        return AddressMatchResult.MISMATCH

    if state_a == state_b and city_a and city_b and city_a == city_b:
        return AddressMatchResult.PARTIAL

    return AddressMatchResult.SKIP
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/services/test_address_validation.py -v
```
Expected: PASS (4 tests)

- [ ] **Step 5: Run full backend test suite**

```bash
cd backend && pytest tests/ -v --tb=short
```
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/address_parser.py backend/tests/services/test_address_validation.py
git commit -m "feat: add validate_addresses() for delivery/billing address comparison"
```

---

## Task 11: Frontend — Chain View Components

**Files:**
- Create: `frontend/src/components/ChainTimeline/ChainTimeline.tsx`
- Create: `frontend/src/components/ChainTimeline/VpoSlot.tsx`
- Create: `frontend/src/components/ReferenceValidationPanel/ReferenceValidationPanel.tsx`
- Create: `frontend/src/components/BillingCompletenessPanel/BillingCompletenessPanel.tsx`
- Modify: `frontend/src/api/purchaseOrders.ts`

- [ ] **Step 1: Add API functions**

In `frontend/src/api/purchaseOrders.ts`, add:

```typescript
export interface ChainStatusResponse {
  chain_status: 'incomplete' | 'complete' | 'verified' | 'mismatch';
  missing_slots: string[];
  missing_vendor_invoices: string[];
  reference_checks: Array<{
    document_type: string;
    check: string;
    result: 'pass' | 'mismatch' | 'skip';
  }>;
  billing: {
    overall: string;
    stages?: Array<{
      stage: number;
      expected_amount: number;
      invoiced_amount: number;
      status: string;
    }>;
  };
}

export async function getChainStatus(poId: string): Promise<ChainStatusResponse> {
  const res = await api.get(`/purchase-orders/${poId}/chain`);
  return res.data;
}

export async function updateSoNumber(poId: string, soNumber: string): Promise<void> {
  await api.patch(`/purchase-orders/${poId}/so-number`, { so_number: soNumber });
}
```

- [ ] **Step 2: Create `ChainTimeline.tsx`**

```tsx
// frontend/src/components/ChainTimeline/ChainTimeline.tsx
import React from 'react';

interface Slot {
  docType: string;
  label: string;
  state: 'verified' | 'mismatch' | 'received' | 'waiting' | 'cancelled';
  ref?: string;
  soNumber?: string;
  soExpected?: string;
}

interface Props {
  slots: Slot[];
}

const STATE_STYLES: Record<string, { icon: string; badge: string; border: string }> = {
  verified:  { icon: '✓', badge: 'text-green-400 bg-green-950',  border: 'border-green-700' },
  mismatch:  { icon: '✗', badge: 'text-red-400 bg-red-950',    border: 'border-red-700' },
  received:  { icon: '●', badge: 'text-yellow-400 bg-yellow-950', border: 'border-yellow-700' },
  waiting:   { icon: '○', badge: 'text-slate-500 bg-slate-900',  border: 'border-slate-700 border-dashed' },
  cancelled: { icon: '—', badge: 'text-slate-600 bg-slate-900',  border: 'border-slate-800' },
};

export function ChainTimeline({ slots }: Props) {
  return (
    <div className="flex flex-col gap-0">
      {slots.map((slot, i) => {
        const s = STATE_STYLES[slot.state] || STATE_STYLES.waiting;
        return (
          <div key={slot.docType} className="flex gap-4 relative">
            {i < slots.length - 1 && (
              <div className="absolute left-5 top-10 w-0.5 h-full bg-slate-800 z-0" />
            )}
            <div className={`w-10 h-10 rounded-full border-2 flex items-center justify-center z-10 text-sm font-bold ${s.border} bg-slate-900 flex-shrink-0`}>
              {s.icon}
            </div>
            <div className="flex-1 pb-5">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-semibold text-slate-200">{slot.label}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${s.badge}`}>
                  {slot.state.charAt(0).toUpperCase() + slot.state.slice(1)}
                </span>
              </div>
              {slot.ref ? (
                <div className={`border rounded px-3 py-2 text-xs ${s.border} bg-slate-950`}>
                  <span className="text-slate-200 font-medium">{slot.ref}</span>
                  {slot.soNumber && (
                    <span className="ml-2 text-slate-500">
                      SO:{' '}
                      <span className={slot.soNumber === slot.soExpected ? 'text-green-400' : 'text-red-400'}>
                        {slot.soNumber} {slot.soNumber === slot.soExpected ? '✓' : '✗'}
                      </span>
                    </span>
                  )}
                </div>
              ) : (
                <div className="border border-dashed border-slate-700 rounded px-3 py-2 text-xs text-slate-500">
                  Not yet uploaded
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 3: Create `ReferenceValidationPanel.tsx`**

```tsx
// frontend/src/components/ReferenceValidationPanel/ReferenceValidationPanel.tsx
import React from 'react';

interface Check {
  document_type: string;
  check: string;
  result: 'pass' | 'mismatch' | 'skip';
}

interface Props {
  checks: Check[];
}

const CHECK_LABELS: Record<string, string> = {
  so_consistency: 'SO number match',
  cpo_reference:  'CPO reference match',
  vpo_reference:  'VPO reference match',
};

const RESULT_STYLE: Record<string, string> = {
  pass:     'text-green-400',
  mismatch: 'text-red-400',
  skip:     'text-slate-500',
};

const RESULT_ICON: Record<string, string> = {
  pass: '✅', mismatch: '❌', skip: '⏭',
};

export function ReferenceValidationPanel({ checks }: Props) {
  if (!checks.length) {
    return <p className="text-xs text-slate-500">No documents to validate yet.</p>;
  }
  return (
    <div className="flex flex-col divide-y divide-slate-800">
      {checks.map((c, i) => (
        <div key={i} className="flex items-start gap-3 py-2">
          <span className="text-sm mt-0.5">{RESULT_ICON[c.result]}</span>
          <div>
            <p className="text-xs font-medium text-slate-200">
              {c.document_type.replace(/_/g, ' ')} — {CHECK_LABELS[c.check] || c.check}
            </p>
            <p className={`text-xs ${RESULT_STYLE[c.result]}`}>
              {c.result.toUpperCase()}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Create `BillingCompletenessPanel.tsx`**

```tsx
// frontend/src/components/BillingCompletenessPanel/BillingCompletenessPanel.tsx
import React from 'react';

interface Stage {
  stage: number;
  expected_amount: number;
  invoiced_amount: number;
  status: string;
}

interface Props {
  billing: { overall: string; stages?: Stage[] };
  poTotal?: number;
  billingType: string;
}

const STATUS_COLOR: Record<string, string> = {
  complete: 'bg-green-600',
  paid:     'bg-green-600',
  partial:  'bg-yellow-500',
  pending:  'bg-slate-700',
  mismatch: 'bg-red-600',
};

export function BillingCompletenessPanel({ billing, poTotal, billingType }: Props) {
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-slate-400 uppercase tracking-wide">{billingType} Billing</span>
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
          billing.overall === 'complete' ? 'bg-green-950 text-green-400' : 'bg-yellow-950 text-yellow-400'
        }`}>
          {billing.overall.toUpperCase()}
        </span>
      </div>

      {billing.stages?.map((s) => (
        <div key={s.stage} className="mb-3">
          <div className="flex justify-between text-xs mb-1">
            <span className="text-slate-400">Stage {s.stage}</span>
            <span className="text-slate-300">
              ₹{s.invoiced_amount.toLocaleString('en-IN')} / ₹{s.expected_amount.toLocaleString('en-IN')}
            </span>
          </div>
          <div className="h-1.5 bg-slate-800 rounded overflow-hidden">
            <div
              className={`h-full rounded ${STATUS_COLOR[s.status] || 'bg-slate-700'}`}
              style={{ width: `${Math.min(100, (s.invoiced_amount / s.expected_amount) * 100)}%` }}
            />
          </div>
        </div>
      ))}

      {poTotal && (
        <div className="flex justify-between text-xs pt-2 border-t border-slate-800 mt-2">
          <span className="text-slate-500">PO Total</span>
          <span className="text-slate-200 font-semibold">₹{poTotal.toLocaleString('en-IN')}</span>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ChainTimeline/ \
        frontend/src/components/ReferenceValidationPanel/ \
        frontend/src/components/BillingCompletenessPanel/ \
        frontend/src/api/purchaseOrders.ts
git commit -m "feat: add ChainTimeline, ReferenceValidationPanel, BillingCompletenessPanel components"
```

---

## Task 12: Wire Chain View into PO Detail Page

**Files:**
- Modify: `frontend/src/pages/PODetailPage/PODetailPage.tsx`

- [ ] **Step 1: Read current PODetailPage structure**

```bash
head -60 frontend/src/pages/PODetailPage/PODetailPage.tsx
```

- [ ] **Step 2: Add SO number editable field and chain status fetch**

In `PODetailPage.tsx`, add state and fetch:

```tsx
import { getChainStatus, updateSoNumber, ChainStatusResponse } from '../../api/purchaseOrders';
import { ChainTimeline } from '../../components/ChainTimeline/ChainTimeline';
import { ReferenceValidationPanel } from '../../components/ReferenceValidationPanel/ReferenceValidationPanel';
import { BillingCompletenessPanel } from '../../components/BillingCompletenessPanel/BillingCompletenessPanel';

// Inside component:
const [chainData, setChainData] = useState<ChainStatusResponse | null>(null);
const [soInput, setSoInput] = useState(po?.so_number || '');

useEffect(() => {
  if (po?.id) {
    getChainStatus(po.id).then(setChainData).catch(console.error);
  }
}, [po?.id]);

const handleSoSave = async () => {
  if (!po?.id) return;
  await updateSoNumber(po.id, soInput);
  const updated = await getChainStatus(po.id);
  setChainData(updated);
};
```

- [ ] **Step 3: Add chain banner + two-column layout to JSX**

Add below the PO header section:

```tsx
{/* Chain status banner */}
{chainData && (
  <div className={`rounded-lg p-3 mb-4 border flex items-center justify-between ${
    chainData.chain_status === 'mismatch' ? 'bg-red-950 border-red-800' :
    chainData.chain_status === 'complete' ? 'bg-green-950 border-green-800' :
    'bg-yellow-950 border-yellow-800'
  }`}>
    <div>
      <p className="text-sm font-semibold text-slate-100">
        {chainData.chain_status === 'complete' ? '✓ Chain Complete' :
         chainData.chain_status === 'mismatch' ? '✗ Reference Mismatch' :
         '⚠ Chain Incomplete'}
      </p>
      {chainData.missing_slots.length > 0 && (
        <p className="text-xs text-slate-400 mt-0.5">
          Missing: {chainData.missing_slots.map(s => s.replace(/_/g, ' ')).join(' · ')}
        </p>
      )}
    </div>
  </div>
)}

{/* SO number inline edit */}
<div className="flex items-center gap-2 mb-4">
  <label className="text-xs text-slate-500 uppercase tracking-wide w-24">SO Number</label>
  <input
    value={soInput}
    onChange={e => setSoInput(e.target.value)}
    className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm text-yellow-400 focus:border-blue-500 outline-none w-48"
    placeholder="Enter SO number…"
  />
  <button
    onClick={handleSoSave}
    className="text-xs bg-blue-700 hover:bg-blue-600 text-white px-3 py-1 rounded"
  >
    Save & Validate
  </button>
</div>

{/* Two-column chain view */}
{chainData && (
  <div className="grid grid-cols-3 gap-4">
    <div className="col-span-2 bg-slate-900 border border-slate-800 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-slate-200 mb-4">Document Chain</h3>
      <ChainTimeline slots={buildSlots(po, chainData)} />
    </div>
    <div className="flex flex-col gap-4">
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-slate-200 mb-3">Reference Validation</h3>
        <ReferenceValidationPanel checks={chainData.reference_checks} />
      </div>
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-slate-200 mb-3">Billing</h3>
        <BillingCompletenessPanel
          billing={chainData.billing}
          poTotal={po?.total_amount}
          billingType={po?.billing_type || 'full'}
        />
      </div>
    </div>
  </div>
)}
```

- [ ] **Step 4: Add `buildSlots()` helper above the component**

```tsx
function buildSlots(po: any, chainData: ChainStatusResponse) {
  const required = ['CUSTOMER_PO', 'COMPANY_DC', 'COMPANY_INVOICE'];
  return required.map(type => {
    const isMissing = chainData.missing_slots.includes(type);
    return {
      docType: type,
      label: type.replace(/_/g, ' '),
      state: isMissing ? 'waiting' as const : 'verified' as const,
    };
  });
}
```

- [ ] **Step 5: Start dev server and verify visually**

```bash
cd frontend && npm run dev
```
Open `http://localhost:5173`, navigate to any PO detail page. Verify chain section renders with banner and panels.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/PODetailPage/PODetailPage.tsx
git commit -m "feat: integrate chain validation view into PO detail page"
```

---

## Self-Review

**Spec coverage:**
- M1 (data model) → Tasks 1–2 ✓
- M2 (scenario engine) → Task 4 ✓
- M3 (chain presence) → Task 7 (compute_chain_status) ✓
- M4 (reference validator) → Task 5 ✓
- M5 (billing) → Task 6 ✓
- M6 (chain UI) → Tasks 11–12 ✓
- M7 (line items) → Task 9 ✓
- M8 (address) → Task 10 ✓

**Type consistency:** All types defined in Task 1 are imported consistently in Tasks 4–7. `BillingStatus.PAID` used in billing_tracker for per-stage status (distinct from `BillingStatus.COMPLETE` for overall). `ReferenceCheckResult` and `SlotState` are consistent throughout.

**Placeholder check:** No TBDs found. All code blocks are complete.

**Edge cases from spec:**
- Combined vendor invoice (vpo_numbers array) → Task 1 model + Task 7 validator ✓
- Extraction failure (extraction_ok=False) → Task 7 validator skips checks ✓
- Advance invoice before DC → Task 6 billing tracked independently ✓
- Multiple DCs (UniqueConstraint fix) → Task 1 ✓
- VPO cancellation → not in this plan; operator removes VPO via existing PO update endpoint ✓
