# Phase 1 Remaining Modules — Implementation Plan
**Date:** 2026-03-31
**Branch:** development
**Estimated total:** ~21 hours across 5 modules

---

## Codebase Facts (verified by exploration)

- `DocumentType` enum: 6 values in `backend/app/models/document.py` — no POD
- `PurchaseOrder` model: no `fulfillment_type` field exists anywhere
- `CHAIN_ORDER` constant in `frontend/src/types/index.ts` — drives chain rendering order
- Chain slots keyed by `dict[str, list[ChainSlot]]` in `ChainStatusResponse`
- Extraction templates: `EXTRACTION_PROMPTS` dict in `backend/app/services/extraction/prompts.py`
- Excel export: `backend/app/services/export_service.py` — 7 builder functions, `_build_discrepancies()` already exists
- No `fulfillment_type`, `flow_type`, or vendor grouping logic anywhere in codebase

---

## Module 1 — Stock vs Procurement Flow Logic (~4h)

**What it does:** Add a `fulfillment_type` flag to PurchaseOrder. When set to `stock`, vendor documents (COMPANY_PO, VENDOR_DC, VENDOR_INVOICE) are excluded from chain completeness. Manual UI toggle lets user set this when no vendor PO is uploaded.

### Phase 0 — Read Before Touching

Before writing any code, read:
- `backend/app/models/purchase_order.py` — PurchaseOrder model, POStatus enum
- `backend/app/api/v1/purchase_orders.py` — `chain-status` endpoint, completeness calc logic
- `backend/app/schemas/purchase_order.py` — POUpdate schema, ChainStatusResponse
- `frontend/src/pages/POProfilePage.tsx` — where to add the UI toggle
- `frontend/src/types/index.ts` — POProfile type, add `fulfillment_type` field

### Backend Changes

**1. `backend/app/models/purchase_order.py`**
- Add Python enum: `class FulfillmentType(str, enum.Enum): PROCUREMENT = "procurement"; STOCK = "stock"`
- Add column to `PurchaseOrder`: `fulfillment_type = Column(Enum(FulfillmentType), default=FulfillmentType.PROCUREMENT, nullable=False)`
- Generate Alembic migration after

**2. `backend/app/schemas/purchase_order.py`**
- Add `fulfillment_type: Optional[str] = "procurement"` to `POUpdate`
- Add `fulfillment_type: str` to `POProfileResponse` and `PurchaseOrderResponse`

**3. `backend/app/api/v1/purchase_orders.py`**
- In the `chain-status` endpoint: read `po.fulfillment_type`
- If `fulfillment_type == "stock"`: filter out `COMPANY_PO`, `VENDOR_DC`, `VENDOR_INVOICE` from the required slots before computing `completeness_pct`
- Pattern to follow: locate existing completeness calculation, wrap the slot filter in a condition

**4. Migration**
```bash
cd backend
alembic revision --autogenerate -m "add fulfillment_type to purchase_orders"
alembic upgrade head
```

### Frontend Changes

**5. `frontend/src/types/index.ts`**
- Add `fulfillment_type: 'procurement' | 'stock'` to `POProfile` and `PurchaseOrder` interfaces

**6. `frontend/src/pages/POProfilePage.tsx`**
- Add a small toggle control below the PO header (near `so_number` display)
- On toggle: call `updatePO(id, { fulfillment_type: 'stock' | 'procurement' })` then refetch profile
- Show a label: "Stock-based order — vendor documents not required" when `fulfillment_type === 'stock'`

**7. `frontend/src/api/purchaseOrders.ts`**
- `updatePO` already accepts `Partial<PurchaseOrder>` — no change needed

### Verification
- Create a PO, set `fulfillment_type = 'stock'`, confirm `completeness_pct` ignores COMPANY_PO/VENDOR_DC/VENDOR_INVOICE
- Confirm PATCH `/purchase-orders/{id}` with `{ fulfillment_type: "stock" }` persists
- Grep: `grep -r "fulfillment_type" backend/app/` — should appear in model, schema, endpoint

---

## Module 2 — POD Document Type (~4h)

**What it does:** Add `POD` (Proof of Delivery) as the 7th document type, positioned after `COMPANY_DC` in the chain. Add extraction template and OCR rules.

### Phase 0 — Read Before Touching

Before writing any code, read:
- `backend/app/models/document.py` — DocumentType enum, full file
- `backend/app/services/extraction/prompts.py` — `EXTRACTION_PROMPTS` dict structure, `get_primary_field()`, `get_date_field()`, `get_searchable_fields()`
- `backend/app/services/extraction/glm_ocr_prompts.py` — anti-confusion rules pattern
- `frontend/src/types/index.ts` — `DocumentType` union, `CHAIN_ORDER`, `DOC_TYPE_LABELS`, `DOC_TYPE_SHORT`

### Backend Changes

**1. `backend/app/models/document.py`**
- Add `POD = "POD"` to `DocumentType` enum

**2. Migration**
```bash
alembic revision --autogenerate -m "add POD to document_type enum"
alembic upgrade head
```
Note: PostgreSQL enum additions require `ALTER TYPE ... ADD VALUE` — verify the autogenerate handles this, or write manually:
```sql
ALTER TYPE documenttype ADD VALUE 'POD' AFTER 'COMPANY_DC';
```

**3. `backend/app/services/extraction/prompts.py`**
- Add entry to `EXTRACTION_PROMPTS["POD"]`:
```python
"POD": {
    "instruction": "Extract proof of delivery information from this document...",
    "schema": {
        "pod_number": "string - POD/acknowledgement reference number",
        "pod_date": "string - Date of delivery acknowledgement",
        "dc_reference": "string - Delivery Challan number this POD covers",
        "delivered_to": "string - Name of person who received the delivery",
        "delivery_address": "string - Address where delivery was made",
        "received_by_signature": "string - Signature or name acknowledgement",
        "remarks": "string - Any delivery remarks or condition notes",
    }
}
```
- Add to `get_primary_field()`: `"POD": "pod_number"`
- Add to `get_date_field()`: `"POD": "pod_date"`
- Add to `get_searchable_fields()`: include `dc_reference`

**4. `backend/app/services/extraction/glm_ocr_prompts.py`**
- Add POD-specific anti-confusion rules if needed (dc_reference vs pod_number)

### Frontend Changes

**5. `frontend/src/types/index.ts`**
- Add `'POD'` to `DocumentType` union
- Add `'POD'` to `CHAIN_ORDER` array — position it after `'COMPANY_DC'`
- Add to `DOC_TYPE_LABELS`: `POD: 'Proof of Delivery'`
- Add to `DOC_TYPE_SHORT`: `POD: 'POD'`

### Verification
- Upload a POD document to a test PO — confirm it appears in chain after COMPANY_DC
- Confirm extraction runs and returns `pod_number` as primary ref
- Grep: `grep -r "POD" backend/app/models/` — should appear in enum
- Grep: `grep -r "'POD'" frontend/src/types/` — should appear in union and CHAIN_ORDER

---

## Module 3 — Per-Vendor Completeness Grouping (~4h)

**What it does:** Group vendor document slots by which Vendor PO they belong to. Show a separate completeness indicator per vendor group on the PO Profile page.

### Phase 0 — Read Before Touching

Before writing any code, read:
- `backend/app/api/v1/purchase_orders.py` — `profile` endpoint (`GET /{id}/profile`), `POProfileResponse` construction
- `backend/app/schemas/purchase_order.py` — `POProfileResponse`, `POProfileDocumentSlot`
- `frontend/src/pages/POProfilePage.tsx` — how `profile.slots` is mapped to `ProfileDocumentSection`
- `frontend/src/components/ChainStatusBar.tsx` — reusable for per-vendor mini-bars

### Backend Changes

**1. `backend/app/schemas/purchase_order.py`**
- Add `VendorGroup` schema:
```python
class VendorGroup(BaseModel):
    vendor_po_ref: str           # primary_ref_no of the COMPANY_PO
    vendor_name: Optional[str]   # extracted vendor_name from COMPANY_PO metadata
    completeness_pct: float
    slots: list[POProfileDocumentSlot]  # COMPANY_PO, VENDOR_DC, VENDOR_INVOICE for this vendor
```
- Add `vendor_groups: list[VendorGroup] = []` to `POProfileResponse`

**2. `backend/app/api/v1/purchase_orders.py`** — profile endpoint
- After building `slots`, group by vendor:
  - Find all COMPANY_PO slots
  - For each COMPANY_PO: find VENDOR_DC and VENDOR_INVOICE slots whose `po_ref_no` matches the COMPANY_PO's `primary_ref_no`
  - Compute `completeness_pct` = filled slots / 3 × 100 per group
  - Build `VendorGroup` objects, attach to response

### Frontend Changes

**3. `frontend/src/types/index.ts`**
- Add `VendorGroup` interface matching the backend schema
- Add `vendor_groups: VendorGroup[]` to `POProfile`

**4. `frontend/src/pages/POProfilePage.tsx`**
- After the main `ChainStatusBar`, render a vendor groups section if `profile.vendor_groups.length > 0`
- For each group: show vendor PO ref + vendor name as heading, mini `ChainStatusBar` (pass group.slots as chain), and `{group.completeness_pct}% complete` badge
- `ChainStatusBar` already accepts `chain: Record<string, ChainSlot[]>` — construct from group.slots

### Verification
- Test with Hindalco sample (2 vendor POs: 9POT2526000007 + 9POT2526000008)
- Confirm 2 vendor groups appear, each showing its own 3-slot chain
- Confirm overall completeness is unchanged

---

## Module 4 — Delivery Address Structured Field (~6h)

**What it does:** Extract delivery address as structured columns (not just free text in JSONB), store in dedicated DB columns, expose in search filter.

### Phase 0 — Read Before Touching

Before writing any code, read:
- `backend/app/models/document_metadata.py` — all existing columns, confirm no address columns
- `backend/app/services/extraction/prompts.py` — existing `delivery_address` field definitions per doc type
- `backend/app/api/v1/search.py` — advanced search endpoint, existing filters
- `backend/app/schemas/extraction.py` — `ExtractionResponse`
- `frontend/src/pages/SearchPage.tsx` — how search filters are rendered

### Backend Changes

**1. `backend/app/models/document_metadata.py`**
- Add structured address columns:
```python
delivery_address_raw   = Column(Text, nullable=True)       # full text as extracted
delivery_address_city  = Column(String(100), nullable=True)
delivery_address_state = Column(String(100), nullable=True)
delivery_address_pin   = Column(String(10), nullable=True)
```

**2. Migration**
```bash
alembic revision --autogenerate -m "add structured delivery address to document_metadata"
alembic upgrade head
```

**3. `backend/app/services/extraction/field_validator.py`** (or pipeline.py)
- After extraction, if `extracted_data["delivery_address"]` is present: parse into city/state/PIN
- Simple regex for PIN code: `r'\b\d{6}\b'`
- Populate new columns when saving DocumentMetadata

**4. `backend/app/schemas/extraction.py`**
- Add `delivery_address_raw`, `delivery_address_city`, `delivery_address_state`, `delivery_address_pin` to `ExtractionResponse`

**5. `backend/app/api/v1/search.py`** — advanced search endpoint
- Add optional `delivery_city: str` and `delivery_pin: str` query params
- Filter `DocumentMetadata.delivery_address_city.ilike(f"%{delivery_city}%")` if provided

### Frontend Changes

**6. `frontend/src/types/index.ts`**
- Add address fields to `DocumentMetadata` interface

**7. `frontend/src/pages/SearchPage.tsx`** (or wherever advanced search filters live)
- Add city and PIN input fields to the advanced search filter panel

### Verification
- Re-extract a COMPANY_PO — confirm `delivery_address_city` and `delivery_address_pin` populated
- Search by city — confirm filtered results
- Grep: `grep -r "delivery_address_city" backend/app/` — appears in model, schema, endpoint

---

## Module 5 — Enriched Excel Dispute Pack (~3h)

**What it does:** Enhance the existing 7-sheet Excel export with cross-reference comparison and extracted amounts comparison. Builds directly on existing builder functions in `export_service.py`.

### Phase 0 — Read Before Touching

Before writing any code, read:
- `backend/app/services/export_service.py` — ALL builder functions, especially `_build_discrepancies()`, `_build_extracted_fields()`, `_build_document_chain()`. Read the full file.
- `backend/app/schemas/purchase_order.py` — `POProfileResponse` — what fields are available to the exporters

### Backend Changes — `backend/app/services/export_service.py`

The existing export already has `_build_discrepancies()`. Two new sheets to add:

**1. Add `_build_cross_reference_table(wb, profile)` builder**
- Sheet name: `"Cross-References"`
- Columns: `Doc Type | Primary Ref | PO Ref | Doc Date | Total Amount`
- Rows: one per slot in `profile.slots` — fill from slot fields
- Highlight rows where `po_ref_no` does not match `profile.po_number` (amber fill)
- Pattern: copy structure from `_build_document_chain()` — same column/header approach

**2. Add `_build_amounts_comparison(wb, profile)` builder**
- Sheet name: `"Amounts Comparison"`
- Columns: `Doc Type | Primary Ref | Extracted Amount | Matches PO Total?`
- Rows: one per slot that has `total_amount`
- Flag where amount differs from `profile.total_amount` by more than 1%
- Pattern: copy structure from `_build_summary()` — same cell styling

**3. Wire into `export_po_to_excel()`**
- In the `mode="separate"` branch, call both new builders after the existing 7
- No change needed to single-sheet mode

### Verification
- Export a PO with known discrepancies (e.g. Hindalco sample)
- Confirm 9 sheets present in separate mode: existing 7 + Cross-References + Amounts Comparison
- Confirm highlighted rows appear where amounts differ

---

## Execution Order

| # | Module | Hours | Dependency |
|---|--------|-------|------------|
| 1 | Stock vs procurement flow | 4h | None — start here |
| 2 | POD document type | 4h | None — can run in parallel with 1 |
| 3 | Per-vendor completeness grouping | 4h | None — independent |
| 4 | Delivery address structured field | 6h | None — independent |
| 5 | Enriched Excel dispute pack | 3h | Easiest — do last |

Modules 1–4 are fully independent. Each can be built in its own session.

## Anti-Patterns to Avoid

- Do NOT invent fields — `fulfillment_type` does not exist yet, add it explicitly with migration
- Do NOT edit `CHAIN_ORDER` in ChainStatusBar — it lives in `frontend/src/types/index.ts`
- Do NOT use `chain_completeness` float directly — it is computed, not stored manually
- Do NOT skip migrations — both enum additions and column additions require Alembic
- PostgreSQL enum `ADD VALUE` cannot be inside a transaction — write migration manually if autogenerate wraps it in `op.execute` inside `BEGIN`
