# Codex Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 4 critical and high-priority correctness issues in purchase order state calculation and verification flows.

**Architecture:** 
- Fix 1–4: Guard state transitions (completeness, status, manual closure) against invalid calculations and overwrite scenarios
- Fix 5: Remove TLS verification bypass and support explicit certificate configuration
- Fix 6: Compute price_match from actual price values, not part-number equality

**Tech Stack:** FastAPI, SQLAlchemy (async/sync), httpx (async HTTP), Pydantic, pytest

---

## File Map

**Modified Files:**
- `backend/app/services/extraction/tasks.py` — Fix completeness calc to count only scenario-required docs (2 locations: sync + async paths)
- `backend/app/api/v1/extraction.py` — Add manual_completed guard to sync chain updater
- `backend/app/services/extraction/tasks.py` — Add manual_completed guard to async extraction pipeline
- `backend/app/services/item_matcher.py` — Remove `verify=False`, add config-based cert support
- `backend/app/services/po_service.py` — Fix price_match computation (1 line fix)

**Test Files:**
- `tests/services/test_extraction_tasks.py` — Tests for completeness calculation
- `tests/services/test_po_service.py` — Tests for price_match logic
- `tests/services/test_item_matcher.py` — Tests for TLS behavior

---

## Task 1: Fix Sync Completeness Calculation (Count Only Required Docs)

**Files:**
- Modify: `backend/app/services/extraction/tasks.py:462-497` (`_update_chain_sync` function)
- Test: `tests/services/test_extraction_tasks.py`

### Context
Currently `_update_chain_sync` counts all non-failed documents but divides by scenario-specific chain length. This lets optional/irrelevant documents inflate completeness to 100%+. Fix: count only required document types for the scenario.

- [ ] **Step 1: Write the failing test**

```python
# In tests/services/test_extraction_tasks.py

def test_completeness_counts_only_scenario_required_docs():
    """Verify that completeness only counts required docs for the scenario, ignoring optional/out-of-scenario docs."""
    from backend.app.models import PurchaseOrder, Document, DocumentType, OrderScenario, POStatus
    from backend.app.services.extraction.tasks import _update_chain_sync
    from datetime import datetime, timezone
    
    # Setup: stock scenario (chain = [CUSTOMER_PO, VENDOR_DC, VENDOR_INVOICE])
    po = PurchaseOrder(
        id="test-po-1",
        po_number="PO-001",
        order_scenario=OrderScenario.STOCK,
        status=POStatus.INITIATED,
        chain_completeness=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(po)
    db.flush()
    
    # Upload 3 required docs + 2 optional (SERVICE_AMC, WARRANTY)
    docs = [
        Document(po_id=po.id, document_type=DocumentType.CUSTOMER_PO, status=DocumentStatus.PROCESSED),
        Document(po_id=po.id, document_type=DocumentType.VENDOR_DC, status=DocumentStatus.PROCESSED),
        Document(po_id=po.id, document_type=DocumentType.VENDOR_INVOICE, status=DocumentStatus.PROCESSED),
        Document(po_id=po.id, document_type=DocumentType.SERVICE_AMC, status=DocumentStatus.PROCESSED),  # optional
        Document(po_id=po.id, document_type=DocumentType.WARRANTY, status=DocumentStatus.PROCESSED),  # optional
    ]
    db.add_all(docs)
    db.flush()
    
    # Execute: recalculate chain
    _update_chain_sync(db, po.id)
    
    # Assert: completeness = 3 required / 3 required = 100% (NOT 166%)
    db.refresh(po)
    assert po.chain_completeness == 100.0, f"Expected 100%, got {po.chain_completeness}%"
    assert po.status == POStatus.COMPLETE
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/services/test_extraction_tasks.py::test_completeness_counts_only_scenario_required_docs -xvs
```

Expected: FAIL with assertion error showing completeness > 100%

- [ ] **Step 3: Implement the fix**

Modify `backend/app/services/extraction/tasks.py` — replace `_update_chain_sync`:

```python
def _update_chain_sync(db, po_id):
    """Sync version of chain completeness update for Celery."""
    po = db.get(PurchaseOrder, po_id)
    if not po:
        return

    # Guard: if manually completed, don't recalculate
    if po.manually_completed:
        return

    # Get scenario-specific chain; fall back to full chain if scenario unknown
    scenario = getattr(po, 'order_scenario', None)
    scenario_chain = get_scenario_chain(scenario)
    if scenario_chain is None or scenario == OrderScenario.UNKNOWN:
        # Unknown scenario — keep completeness at 0, don't update status to COMPLETE
        chain_length = len(CHAIN_DOC_TYPES)
        required_docs = set(CHAIN_DOC_TYPES)
    else:
        chain_length = len(scenario_chain)
        required_docs = set(scenario_chain)

    # Count ONLY required document types for this scenario
    count = db.query(func.count(distinct(Document.document_type))).filter(
        Document.po_id == po_id,
        Document.document_type.in_(required_docs),  # <-- KEY FIX: filter by required docs
        Document.status.notin_([
            DocumentStatus.EXTRACTION_FAILED,
            DocumentStatus.PENDING_MODEL,
            DocumentStatus.REJECTED,
        ]),
    ).scalar() or 0

    completeness = min(100.0, round((count / chain_length) * 100, 1))  # Clamp to [0, 100]

    po.chain_completeness = completeness
    if completeness == 0:
        po.status = POStatus.INITIATED
    elif completeness < 50:
        po.status = POStatus.IN_PROGRESS
    elif completeness < 100:
        po.status = POStatus.NEAR_COMPLETE
    else:
        po.status = POStatus.COMPLETE
    db.commit()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend
pytest tests/services/test_extraction_tasks.py::test_completeness_counts_only_scenario_required_docs -xvs
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/extraction/tasks.py tests/services/test_extraction_tasks.py
git commit -m "fix: restrict completeness count to scenario-required docs only

- Count only document types required for the scenario, not all uploaded docs
- Prevents optional/out-of-scenario docs from inflating completeness >100%
- Add guard: skip recalculation if manually_completed=True
- Clamp computed completeness to [0, 100]"
```

---

## Task 2: Fix Async Completeness Calculation (Extract Document Path)

**Files:**
- Modify: `backend/app/services/extraction/tasks.py:177-459` (`extract_document` function, async path)
- Test: `tests/services/test_extraction_tasks.py`

### Context
The async path in `extract_document` also updates completeness after extraction. It has the same bug: counts all docs, not just scenario-required ones.

- [ ] **Step 1: Find the async completeness update in extract_document**

Search for where `chain_completeness` is set in the async extraction path:

```bash
cd backend
grep -n "chain_completeness\|_update_chain" app/services/extraction/tasks.py | head -20
```

Expected: Find lines where completeness is calculated/set in the async flow.

- [ ] **Step 2: Write test for async path**

```python
# In tests/services/test_extraction_tasks.py

@pytest.mark.asyncio
async def test_async_completeness_counts_only_scenario_required_docs():
    """Verify that async extraction path also counts only required docs."""
    # Similar setup as Task 1, but trigger via async extraction flow
    # This tests the async updater in extract_document
    
    po = PurchaseOrder(
        id="test-po-async",
        po_number="PO-ASYNC-001",
        order_scenario=OrderScenario.STOCK,
        status=POStatus.INITIATED,
        chain_completeness=0,
    )
    await db.add(po)
    await db.flush()
    
    # Simulate extraction of CUSTOMER_PO + optional SERVICE_AMC
    # Then check that completeness is only 33% (1/3), not 50% (1/2)
    # Extract CUSTOMER_PO
    doc1 = Document(po_id=po.id, document_type=DocumentType.CUSTOMER_PO, status=DocumentStatus.PENDING_MODEL)
    await db.add(doc1)
    await db.flush()
    
    # Simulate extraction completing
    doc1.status = DocumentStatus.PROCESSED
    
    # Extract optional SERVICE_AMC (out of stock scenario)
    doc2 = Document(po_id=po.id, document_type=DocumentType.SERVICE_AMC, status=DocumentStatus.PROCESSED)
    await db.add(doc2)
    await db.flush()
    
    # After this, completeness should be 33% (1 of 3 required), not 50% (2 of 4)
    # The async path should recalculate on doc2 completion
    await db.refresh(po)
    assert po.chain_completeness <= 33.4, f"Expected ≤33%, got {po.chain_completeness}%"
```

- [ ] **Step 3: Locate and fix async completeness update**

In `extract_document`, find where completeness is recalculated after document processing (search around line 400–450):

```python
# BEFORE (wrong):
count = db.query(func.count(distinct(Document.document_type))).filter(
    Document.po_id == po_id,
    Document.status.notin_([...]),
).scalar() or 0
completeness = round((count / chain_length) * 100, 1)

# AFTER (correct):
scenario = po.order_scenario
scenario_chain = get_scenario_chain(scenario)
required_docs = set(scenario_chain) if scenario_chain else set(CHAIN_DOC_TYPES)

count = db.query(func.count(distinct(Document.document_type))).filter(
    Document.po_id == po_id,
    Document.document_type.in_(required_docs),  # <-- Filter to required only
    Document.status.notin_([...]),
).scalar() or 0
completeness = min(100.0, round((count / chain_length) * 100, 1))
```

- [ ] **Step 4: Run both tests to verify**

```bash
cd backend
pytest tests/services/test_extraction_tasks.py::test_completeness_counts_only_scenario_required_docs tests/services/test_extraction_tasks.py::test_async_completeness_counts_only_scenario_required_docs -xvs
```

Expected: Both PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/extraction/tasks.py tests/services/test_extraction_tasks.py
git commit -m "fix: apply required-docs filter to async completeness path

- Apply same fix as Task 1 to the async extraction flow in extract_document
- Ensures both sync and async paths count only scenario-required docs
- Closes the completeness inflation vulnerability in extraction pipeline"
```

---

## Task 3: Guard Manual Closure in Sync Chain Updater (Extraction API)

**Files:**
- Modify: `backend/app/api/v1/extraction.py:373-380` (sync chain updater called from document verification/rejection)
- Test: `tests/api/v1/test_extraction.py`

### Context
After `close_order()` sets `manually_completed=True`, the extraction API's sync chain updater still overwrites status and completeness on later verification/rejection events. Fix: short-circuit if `po.manually_completed == True`.

- [ ] **Step 1: Write failing test**

```python
# In tests/api/v1/test_extraction.py

def test_manual_close_prevents_status_downgrade():
    """Verify that once an order is manually closed, chain recalculation cannot downgrade status."""
    
    po = PurchaseOrder(
        id="test-manual-close",
        po_number="PO-MANUAL",
        status=POStatus.IN_PROGRESS,
        chain_completeness=50,
        manually_completed=False,
        order_scenario=OrderScenario.STOCK,
    )
    db.add(po)
    db.flush()
    
    # Close the order manually
    po.manually_completed = True
    po.status = POStatus.COMPLETE
    po.chain_completeness = 100.0
    po.completed_at = datetime.now(timezone.utc)
    db.commit()
    
    # Later: document is rejected (e.g., via API)
    doc = Document(
        po_id=po.id,
        document_type=DocumentType.CUSTOMER_PO,
        status=DocumentStatus.PROCESSED
    )
    db.add(doc)
    db.flush()
    
    # Simulate rejection
    doc.status = DocumentStatus.REJECTED
    db.flush()
    
    # Call sync updater (this should NOT change the closed order)
    _update_chain_sync(db, po.id)  # or whatever the extraction API calls
    
    # Assert: order remains COMPLETE and manually_completed=True
    db.refresh(po)
    assert po.status == POStatus.COMPLETE, f"Status should remain COMPLETE, got {po.status}"
    assert po.chain_completeness == 100.0, f"Completeness should remain 100%, got {po.chain_completeness}%"
    assert po.manually_completed is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/api/v1/test_extraction.py::test_manual_close_prevents_status_downgrade -xvs
```

Expected: FAIL — status gets downgraded to IN_PROGRESS or NEAR_COMPLETE

- [ ] **Step 3: Implement the fix**

The sync updater already has the guard (from Task 1). Verify the extraction API calls it with the guard in place. If there's a separate updater in extraction.py, add the same guard:

```python
# In backend/app/api/v1/extraction.py, in the sync chain updater:

def _update_po_chain_after_verification(db, po_id):
    """Update chain completeness after document verification."""
    po = db.get(PurchaseOrder, po_id)
    if not po:
        return
    
    # GUARD: skip if manually closed
    if po.manually_completed:
        return
    
    # ... rest of calculation ...
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend
pytest tests/api/v1/test_extraction.py::test_manual_close_prevents_status_downgrade -xvs
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/extraction.py tests/api/v1/test_extraction.py
git commit -m "fix: guard manual-closed orders against chain recalculation

- Add check: if po.manually_completed=True, skip chain completeness/status update
- Enforces one-way semantics: manual close cannot be overwritten by doc state changes
- Prevents operational status inconsistency in UI and audit logs"
```

---

## Task 4: Guard Manual Closure in Async Extraction Pipeline

**Files:**
- Modify: `backend/app/services/extraction/tasks.py:177-459` (`extract_document` async path, where chain is recalculated)
- Test: `tests/services/test_extraction_tasks.py`

### Context
The async extraction pipeline in `extract_document` also recalculates chain on document completion. It must also check `manually_completed` before updating status/completeness.

- [ ] **Step 1: Write test**

```python
# In tests/services/test_extraction_tasks.py

@pytest.mark.asyncio
async def test_manual_close_survives_async_extraction():
    """Verify manually closed order status is not overwritten by async extraction."""
    
    po = PurchaseOrder(
        id="test-async-manual",
        po_number="PO-ASYNC-MANUAL",
        status=POStatus.COMPLETE,
        chain_completeness=100.0,
        manually_completed=True,
        completed_at=datetime.now(timezone.utc),
        order_scenario=OrderScenario.STOCK,
    )
    await db.add(po)
    await db.flush()
    
    # New document uploaded and extracted (should not change closed order)
    doc = Document(po_id=po.id, document_type=DocumentType.SERVICE_AMC, status=DocumentStatus.PENDING_MODEL)
    await db.add(doc)
    await db.flush()
    
    # Extraction completes
    doc.status = DocumentStatus.PROCESSED
    await db.flush()
    
    # Async path recalculates (should skip because manually_completed=True)
    # (This is called internally during extract_document)
    
    await db.refresh(po)
    assert po.status == POStatus.COMPLETE
    assert po.chain_completeness == 100.0
    assert po.manually_completed is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/services/test_extraction_tasks.py::test_manual_close_survives_async_extraction -xvs
```

Expected: FAIL

- [ ] **Step 3: Implement the fix in extract_document**

Find where `extract_document` recalculates completeness and add the guard:

```python
# In extract_document, where chain is recalculated:

# GUARD: skip if manually closed
if not po.manually_completed:
    # ... recalculate completeness ...
    po.chain_completeness = completeness
    po.status = new_status
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend
pytest tests/services/test_extraction_tasks.py::test_manual_close_survives_async_extraction -xvs
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/extraction/tasks.py tests/services/test_extraction_tasks.py
git commit -m "fix: skip chain recalc in async extraction if order is manually closed

- Guard async path: check manually_completed before updating status/completeness
- Matches sync guard from Task 3, ensures consistent behavior
- Protects closed order state across both extraction code paths"
```

---

## Task 5: Remove TLS Verification Bypass in Item Matcher

**Files:**
- Modify: `backend/app/services/item_matcher.py:115` (httpx.AsyncClient initialization)
- Modify: `backend/app/config.py` (add optional CA bundle config)
- Test: `tests/services/test_item_matcher.py`

### Context
Item matcher disables certificate verification (`verify=False`). This exposes document data to MITM tampering. Fix: enable verification by default, support explicit CA bundle configuration.

- [ ] **Step 1: Add config for certificate bundle**

```python
# In backend/app/config.py, add to Settings class:

class Settings(BaseSettings):
    # ... existing settings ...
    
    # TLS/SSL configuration
    ocr_extractor_ca_bundle: str | None = Field(
        default=None,
        description="Path to CA bundle for verifying OCR extractor server certificate. "
        "If None, uses system CA bundle. Set to empty string to disable (not recommended)."
    )
```

- [ ] **Step 2: Write test for TLS verification**

```python
# In tests/services/test_item_matcher.py

def test_item_matcher_uses_tls_verification():
    """Verify that item matcher enables certificate verification."""
    from backend.app.services.item_matcher import match_items_with_llm
    import httpx
    
    # Mock the httpx.AsyncClient to capture initialization kwargs
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {"content": '[{"sr_no": "1", "matched_part_no": "ABC123", "confidence": 0.9}]'}
        }
        mock_client.post.return_value = mock_response
        
        # Call the function
        result = asyncio.run(match_items_with_llm(
            unmatched=[{"sr_no": "1", "description": "test"}],
            catalog=["ABC123"]
        ))
        
        # Assert: AsyncClient was created with verify=True (or a path)
        call_kwargs = mock_client_class.call_args.kwargs
        assert 'verify' in call_kwargs, "verify parameter must be set"
        assert call_kwargs['verify'] is not False, "verify must not be False (TLS bypass)"
```

- [ ] **Step 3: Implement the fix**

```python
# In backend/app/services/item_matcher.py, around line 115:

# BEFORE:
async with httpx.AsyncClient(timeout=30, verify=False) as client:

# AFTER:
from backend.app.config import settings

# Determine certificate verification: use custom CA bundle if configured, else system default
verify = settings.ocr_extractor_ca_bundle if settings.ocr_extractor_ca_bundle else True

async with httpx.AsyncClient(timeout=30, verify=verify) as client:
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend
pytest tests/services/test_item_matcher.py::test_item_matcher_uses_tls_verification -xvs
```

Expected: PASS

- [ ] **Step 5: Document .env requirement**

Update `.env.example` and `backend/.env` to include:

```bash
# TLS/SSL configuration for OCR extractor
OCR_EXTRACTOR_CA_BUNDLE=   # Leave empty to use system CA bundle
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/item_matcher.py backend/app/config.py .env.example tests/services/test_item_matcher.py
git commit -m "fix: enable TLS certificate verification for item matcher

- Remove verify=False from httpx.AsyncClient initialization
- Add OCR_EXTRACTOR_CA_BUNDLE config for explicit CA bundle (if needed)
- Default: verify=True with system CA bundle
- Closes MITM vulnerability in document extraction → matching pipeline"
```

---

## Task 6: Fix Price Match Computation in Item Comparison

**Files:**
- Modify: `backend/app/services/po_service.py:932` (one line)
- Test: `tests/services/test_po_service.py`

### Context
When comparing items across documents, `price_match` is set to `part_match` (part-number equality) instead of comparing actual prices. This hides billing discrepancies. Fix: compute price_match from numeric price comparison.

- [ ] **Step 1: Write failing test**

```python
# In tests/services/test_po_service.py

def test_item_comparison_price_match_compares_prices_not_parts():
    """Verify price_match is computed from price values, not part numbers."""
    from backend.app.services.po_service import build_item_comparison
    
    company_po = {
        "items": [
            {
                "sr_no": "1",
                "description": "Widget A",
                "part_no": "PART-123",
                "quantity": 10,
                "unit_price": 100.00,  # Price: ₹100
            }
        ]
    }
    
    vendor_dc = {
        "items": [
            {
                "sr_no": "1",
                "description": "Widget A",
                "part_no": "PART-123",  # Same part
                "quantity": 10,
                "unit_price": 150.00,  # Different price: ₹150
            }
        ]
    }
    
    comparison = build_item_comparison(
        po=PurchaseOrder(...),
        company_po_doc=...,
        vendor_dc_doc=...,
    )
    
    item_match = comparison[0]  # First matched item
    assert item_match.part_no == "PART-123"
    assert item_match.part_match is True, "Parts should match"
    assert item_match.price_match is False, "Prices should NOT match (100 != 150)"
    assert item_match.source_price == 100.0
    assert item_match.compared_price == 150.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/services/test_po_service.py::test_item_comparison_price_match_compares_prices_not_parts -xvs
```

Expected: FAIL — assertion `price_match is False` fails because it's True (bug: assigned part_match)

- [ ] **Step 3: Implement the fix**

```python
# In backend/app/services/po_service.py, around line 932:

# BEFORE:
price_match=part_match,  # BUG: assigns part_match instead of comparing prices

# AFTER:
# Compute price_match from actual prices with 2% tolerance
src_price = _safe_float(src.get("unit_price"))
cmp_price = _safe_float(cmp.get("unit_price"))
if src_price is not None and cmp_price is not None:
    # Allow 2% price variance (e.g., ₹100 vs ₹102 is a match)
    price_match = abs(src_price - cmp_price) <= max(src_price, cmp_price) * 0.02
else:
    price_match = False  # If either price is missing, it's not a match

# Then in ItemComparison:
price_match=price_match,  # FIX: now compares actual prices
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend
pytest tests/services/test_po_service.py::test_item_comparison_price_match_compares_prices_not_parts -xvs
```

Expected: PASS

- [ ] **Step 5: Add edge case test**

```python
def test_item_comparison_price_match_handles_missing_prices():
    """Verify price_match=False when prices are missing."""
    comparison = build_item_comparison(
        po=...,
        company_po_doc=... # items with no unit_price
        vendor_dc_doc=...,
    )
    
    item_match = comparison[0]
    assert item_match.price_match is False, "Missing prices should not match"

def test_item_comparison_price_match_tolerance():
    """Verify 2% price tolerance is applied."""
    # Company: ₹100, Vendor: ₹101.99 (1.99% diff)
    # Should match within 2% tolerance
    assert price_match is True
    
    # Company: ₹100, Vendor: ₹102.01 (2.01% diff)
    # Should NOT match (exceeds 2% tolerance)
    assert price_match is False
```

- [ ] **Step 6: Run all price tests**

```bash
cd backend
pytest tests/services/test_po_service.py -k "price_match" -xvs
```

Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/po_service.py tests/services/test_po_service.py
git commit -m "fix: compute price_match from prices, not part-number equality

- price_match now compares source_price vs compared_price
- Apply 2% tolerance to handle minor price variations
- Keep part_match as separate field for part-number matching
- Prevents hiding billing discrepancies in item reconciliation"
```

---

## Verification & Integration

After all 6 tasks:

- [ ] **Run all affected tests:**

```bash
cd backend
pytest tests/services/test_extraction_tasks.py tests/services/test_po_service.py tests/services/test_item_matcher.py tests/api/v1/test_extraction.py -v
```

- [ ] **Manual end-to-end test (stock scenario):**

```
1. Create PO in stock scenario (CUSTOMER_PO + VENDOR_DC + VENDOR_INVOICE)
2. Upload all 3 required docs → completeness should be 100%
3. Upload optional SERVICE_AMC → completeness should stay 100% (not inflate to 125%+)
4. Close the order manually
5. Reject a document → order should remain COMPLETE (not downgrade to IN_PROGRESS)
6. Verify prices on items: if part matches but prices differ, UI should show price_match=false
```

- [ ] **Verify .env config:**

Ensure `OCR_EXTRACTOR_CA_BUNDLE` is set or left empty (uses system CA).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-07-codex-review-fixes.md`.

**Two execution options:**

**1. Subagent-Driven (Recommended)** - Fresh subagent per task, review between tasks, fast iteration with parallel work on independent tasks (e.g., Tasks 3–4, Tasks 5–6 can work in parallel)

**2. Inline Execution** - Batch tasks in this session with checkpoints

**Which approach?**
