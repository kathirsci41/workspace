# Chain Validation System — Design Spec

**Date:** 2026-04-11  
**Status:** Approved  
**Approach:** Reference Enrichment (Approach B) — CPO-centric model preserved, documents enriched with cross-reference fields

---

## Problem

DPP currently tracks whether the correct *document types* exist for a CPO (chain presence). It does not verify whether the documents reference the *same order*, whether the *correct items* were delivered, whether the *correct address* was used, or whether *billing is complete*. This spec covers all four dimensions.

---

## Business Context

### Document Prefix Taxonomy
| Prefix | Meaning |
|---|---|
| `1PTR` | Trading VPO — Chennai |
| `9POT` | Trading VPO — Mumbai |
| `1POC` | Contract/AMC VPO |
| `1OTM` | Sales Order — Chennai |
| `9OTM` | Sales Order — Mumbai |
| `SOSC` | Service Sales Order |
| `1DNT` | Delivery Challan — Chennai |
| `MBDNT` | Delivery Challan — Mumbai |
| `1ITR` | Invoice — Chennai |
| `9STG` | Invoice — Mumbai |
| `1IAM` | AMC Invoice |

### Order Scenarios
| Scenario | Document chain |
|---|---|
| STOCK | CPO → Company DC → Company Invoice |
| PROCUREMENT (single vendor) | CPO → VPO → Vendor Invoice → Company DC → Company Invoice |
| PROCUREMENT (multi-vendor) | CPO → N×VPO → N×Vendor Invoice → Company DC → Company Invoice |
| SERVICE_AMC | CPO → Company Invoice (no DC) |
| DROP_SHIP | CPO → VPO → Vendor DC → Vendor Invoice → Company Invoice |

### Billing Types
- **FULL:** Single invoice = 100% of CPO value
- **STAGED:** Multiple invoices tied to milestones (e.g., 40% advance + 60% on delivery)
- **RECURRING:** Periodic invoices (monthly/quarterly/half-yearly/yearly) for AMC/service contracts

### Cross-Document Reference Map
```
CPO ──[customer_order_no on DC/Invoice]──▶ Company DC + Company Invoice
VPO ──[so_number]──▶ Company DC + Company Invoice  (SO is the bridge)
Vendor Invoice ──[vpo_number]──▶ VendorPO record
```
SO number is manually entered by operator (no ERP access). It appears on Company DC and Company Invoice — extracted automatically and validated against the operator-entered value.

---

## Architecture

No new tables. The existing CPO-centric model is preserved. Documents are enriched with cross-reference fields. Validation logic lives in new service files. Scenario detection extends the existing `_SCENARIO_CHAIN` dict in `po_service.py`.

---

## Module 1 — Data Model Enrichment

### `PurchaseOrder` — new fields
```python
billing_type: BillingType          # FULL / STAGED / RECURRING (default FULL)
billing_milestones: list[dict]     # JSONB [{stage, percent, expected_amount, invoice_id}]
requires_install_report: bool      # Customer-specific flag (default False)
chain_status: ChainStatus          # INCOMPLETE / COMPLETE / VERIFIED / MISMATCH
```

`so_number` already exists on `PurchaseOrder`.

### `Document` — new fields
```python
so_number: str | None          # Auto-extracted from Company DC / Company Invoice / VPO
vpo_numbers: list[str]         # JSONB array — handles combined vendor invoices
billing_stage: int | None      # 1, 2... for staged billing documents
extraction_ok: bool            # False = extraction incomplete, validation skipped
```

### New enums
```python
class BillingType(str, enum.Enum):
    FULL = "full"
    STAGED = "staged"
    RECURRING = "recurring"

class ChainStatus(str, enum.Enum):
    INCOMPLETE = "incomplete"       # Missing required documents
    COMPLETE = "complete"           # All docs present, references match
    VERIFIED = "verified"           # Docs + line items + address confirmed
    MISMATCH = "mismatch"           # Reference or content discrepancy found
```

### `DocumentType` — new values
```python
INSTALLATION_REPORT = "INSTALLATION_REPORT"
VENDOR_CREDIT_NOTE = "VENDOR_CREDIT_NOTE"
```

### `UniqueConstraint` change
Remove `document_type` from the unique constraint on `Document` to allow multiple COMPANY_DC / COMPANY_INVOICE per CPO (partial shipments). New constraint: `(po_id, checksum)`.

---

## Module 2 — Scenario Engine

Scenario is **derived**, never manually set. Rules run whenever a VPO is added or removed.

```
No VendorPOs on this CPO:
  Any document has type VENDOR_DC → DROP_SHIP
  Any document has type COMPANY_PO → SERVICE_AMC heuristic check
  else if all docs suggest service → SERVICE_AMC
  else → STOCK

VendorPOs exist:
  count ≥ 1 → PROCUREMENT

Upgrade rule:
  STOCK → PROCUREMENT: when first VPO is linked (non-destructive)
  PROCUREMENT → STOCK: when all VPOs are cancelled
```

Location: extend `get_scenario_chain()` in `backend/app/services/po_service.py` and add `derive_scenario()` function.

---

## Module 3 — Chain Presence Tracker

For each CPO, the required document slots are determined by scenario. Each slot has a state.

### Slot states
```
WAITING   → document not yet uploaded
RECEIVED  → document uploaded, extraction in progress or pending review
VERIFIED  → document uploaded + references validated
MISMATCH  → document uploaded but reference check failed
CANCELLED → VPO slot cancelled by operator
```

### VPO slot tracking
Each `VendorPO` record = one slot. Each slot requires exactly one matching `VENDOR_INVOICE` document where `Document.vpo_numbers` contains the VPO number.

**Combined invoice handling:** A single vendor invoice may carry multiple VPO numbers (e.g., Vendor A bills for VPO-1 and VPO-2 in one invoice). `vpo_numbers` is an array to support this.

### Multiple DCs / Invoices
Partial shipment creates multiple `COMPANY_DC` and/or `COMPANY_INVOICE` documents. The chain presence check requires at least one VERIFIED document of each required type — not exactly one.

### Installation report slot
Added to required slots when `PurchaseOrder.requires_install_report = True`. Does not block `COMPLETE` status for billing purposes — tracked separately under `documents_complete`.

### Chain status computation
```
chain_status = INCOMPLETE  if any required slot is WAITING
             = MISMATCH    if any slot is MISMATCH (takes priority over INCOMPLETE)
             = COMPLETE    if all slots are VERIFIED and billing is complete
             = VERIFIED    if COMPLETE + line items + address validated (M7+M8)
```

Location: `backend/app/services/chain_validator.py` (new file)

---

## Module 4 — Reference Validator

Runs automatically when a document finishes extraction and `extraction_ok = True`.
If `extraction_ok = False`, slot shows "Extraction incomplete — review manually" and operator can manually override to VERIFIED.

### SO consistency checks
```
Company DC.so_number        == PurchaseOrder.so_number → ✓ or MISMATCH
Company Invoice.so_number   == PurchaseOrder.so_number → ✓ or MISMATCH
VPO doc.so_number (if extracted) == PurchaseOrder.so_number → ✓ or MISMATCH
```

### CPO reference checks
```
Company DC.customer_order_no    == PurchaseOrder.po_number → ✓ or MISMATCH
Company Invoice.customer_order_no == PurchaseOrder.po_number → ✓ or MISMATCH
```

### VPO reference checks
```
For each VENDOR_INVOICE document:
  Document.vpo_numbers ∩ {VendorPO.vpo_number for this CPO} → each match → slot VERIFIED
  Unmatched vpo_number → MISMATCH (wrong vendor invoice)
```

### Manual override
Operator can mark any slot VERIFIED manually (bypasses reference check). Override is logged with timestamp and user note.

Location: `backend/app/services/reference_validator.py` (new file)

---

## Module 5 — Billing Completeness

### FULL
```
sum(Company Invoice amounts for this CPO) == PurchaseOrder.total_amount
Tolerance: ±1% for rounding
```

### STAGED
```
billing_milestones = [{stage: 1, percent: 40}, {stage: 2, percent: 60}]
expected_amount[stage] = total_amount × percent / 100
For each stage: find Company Invoice with billing_stage == stage
  Check: invoice.amount ≈ expected_amount (±5% tolerance)
  State: PAID / PENDING / EXCESS / MISMATCH
```

Advance invoices (Stage 1) may arrive before Company DC — this is normal and must not be flagged as an error.

### RECURRING
```
billing_milestones = [{period: "2025-Q4"}, {period: "2026-Q1"}, ...]
For each period: find Company Invoice with extracted period matching
  State: INVOICED / MISSING / DUPLICATE
```

### Credit notes
`VENDOR_CREDIT_NOTE` document type. When uploaded, reduces cumulative billed amount and re-evaluates completeness.

### CPO amendment
Operator updates `PurchaseOrder.total_amount` manually. Milestones recalculate proportionally. All previous invoices re-evaluated.

Location: `backend/app/services/billing_tracker.py` (new file)

---

## Module 6 — PO Detail UI (Chain View)

The PO detail page gains a chain validation section.

### Components
- **Chain status banner** — shows current `chain_status`, exact missing slots by name, % complete
- **Document chain timeline** — vertical list of slots with icons, state colours, and "Upload →" / "View →" actions
  - VPO section expands to N rows (one per VendorPO)
  - Installation report slot shown when `requires_install_report = True`
- **Reference validation panel** — per-check pass/fail with extracted vs expected values
- **Billing completeness panel** — per-stage progress bars with amounts
- **SO number field** — editable inline on the PO header; save triggers full re-validation

### Slot state colours
| State | Colour |
|---|---|
| VERIFIED | Green |
| MISMATCH | Red |
| RECEIVED | Orange |
| WAITING | Grey / dashed border |
| CANCELLED | Strikethrough grey |

---

## Module 7 — Line Item Comparison

### Goal
Detect when items in the CPO are missing from or have wrong quantities on the Company DC / Company Invoice.

### Approach
Two-tier (mirrors existing `item_matcher.py` pattern):
1. **Exact part number match** — compare extracted `part_no` fields; zero latency, 100% confidence
2. **AI description match** — use existing `item_matcher.py` / `qwen2.5:7b` for items without matching part numbers

### Comparison logic
```
For each line item in CPO:
  Find matching item in Company DC by part_no (tier 1) or description (tier 2)
  If found: compare qty_ordered vs qty_delivered
    qty match → ✓
    qty short  → flag PARTIAL (qty, shortfall)
    qty missing → flag MISSING
  If not found: flag MISSING
```

### Chain status impact
All items matched and quantities correct → upgrades chain toward VERIFIED.
Any MISSING or PARTIAL item → chain_status = MISMATCH (content level).

### Extraction dependency
Both CPO and Company DC/Invoice must have `extraction_ok = True` and non-empty `order_items` in `extracted_data`. If either is missing, comparison is skipped and slot shows "Item comparison unavailable — check extraction".

Location: extend `backend/app/services/item_matcher.py` with `compare_po_to_delivery()` function.

---

## Module 8 — Address Validation

### Checks
1. **Delivery address:** CPO delivery address ↔ Company DC delivery address
2. **Billing address:** CPO billing address ↔ Company Invoice billing address
3. **SEZ enforcement:** If delivery address is SEZ zone → Company Invoice must show 0% GST (flag if IGST 18% found)
4. **Employee code match:** For NBFC/finance customers — DC must match employee code and location from CPO line item

### Match method
Uses existing `address_parser.py` to extract `{pin_code, city, state}` from both documents.

Match logic:
```
MATCH   if pin_code matches (most reliable)
PARTIAL if city + state match but no pin_code
MISMATCH if state differs or no overlap
SKIP    if extraction_ok = False on either document
```

### SEZ detection
If `PurchaseOrder.gst_type == GstType.UNKNOWN` and delivery address contains "SEZ" or known SEZ pin codes → flag for operator review.

### Employee code match
Extracted from CPO `order_items[].delivery_employee_code` vs DC line item delivery detail. Exact string match.

Location: extend `backend/app/services/address_parser.py` with `validate_addresses()` function.

---

## Edge Cases

| Edge case | Module | Handling |
|---|---|---|
| Wrong SO entered | M4 | MISMATCH flag on DC/Invoice slot |
| Extraction null / failed | M4 | `extraction_ok=False` → manual review prompt |
| Combined vendor invoice (2 VPOs) | M1 | `vpo_numbers` is array |
| Partial shipment (N DCs) | M3 | Multiple slots allowed per type |
| Advance invoice before DC | M5 | Billing validated independently of presence |
| Scenario upgrade STOCK→PROCUREMENT | M2 | Re-derives on VPO add |
| VPO cancelled | M3 | Operator cancels slot, removes from requirements |
| Credit note | M5 | Reduces billed total, re-evaluates |
| CPO amendment | M5 | Manual total update, milestones recalc |
| Install report timing | M3 | Separate flag, doesn't block billing COMPLETE |
| Line item qty short | M7 | PARTIAL flag per item |
| SEZ wrong GST | M8 | Flag for operator review |
| Employee code mismatch | M8 | MISMATCH on delivery address check |

---

## What Does Not Change

- Existing upload flow
- Existing extraction pipeline
- Existing `_SCENARIO_CHAIN` dict (extended, not replaced)
- Existing `address_parser.py` and `item_matcher.py` (extended, not replaced)
- Frontend pages outside PO Detail
