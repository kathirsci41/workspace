# Remaining Modules — Line-Item Verification, POD, Address
# Implementation Plan + Feasibility + Fallback

> **For agentic workers:** Use superpowers:subagent-driven-development to execute task-by-task.

**Goal:** Complete the "did the right product reach the customer?" verification loop with rules-based item/amount/part matching, POD document type, and structured address parsing.

**Architecture:** All changes extend the existing `get_po_profile()` pipeline and `POProfileResponse` schema. No new tables except POD enum migration. Item comparison runs at profile-load time (same as field_comparisons today).

---

## Pre-Read Checklist (read before touching anything)

- `backend/app/services/po_service.py` — lines 570–760 (entire field comparison + vendor group section)
- `backend/app/schemas/po_profile.py` — full file (FieldComparison, VendorGroup, POProfileResponse)
- `backend/app/models/document.py` — DocumentType enum
- `backend/app/services/extraction/glm_ocr_prompts.py` — EXTRACTION_SCHEMAS keys
- `frontend/src/types/index.ts` — POProfile, FieldComparison interfaces
- `frontend/src/components/ProfileFieldComparison.tsx` — full file
- `frontend/src/pages/POProfilePage.tsx` — how field_comparisons and vendor_groups are rendered

---

## What Already Exists (DO NOT re-implement)

| Already built | Location |
|---|---|
| Grand Total vs COMPANY_INVOICE total match | `po_service.py:636` — `_cmp("Grand Total", ...)` |
| Vendor PO amount match | `po_service.py:642` |
| Delivery address comparison (scalar) | `po_service.py:650-660` |
| SO number + DC reference + vendor name comparison | `po_service.py:662-688` |
| `FieldComparison` schema + frontend component | `po_profile.py:57`, `ProfileFieldComparison.tsx` |
| `field_comparisons` in `POProfile` frontend type | `types/index.ts:277` |

**M20 (amount match) is already done.** Do NOT add it again.

---

## Discovered Risk: POD Was Deliberately Removed

Migration `a1b2c3d4e5f6` is titled **"add COMPANY_PO, remove POD"** — POD was explicitly deleted from the enum. Re-adding it changes `len(CHAIN_DOC_TYPES)` from 6 → 7, which drops every existing PO's chain completeness % (e.g. a PO at 100% drops to 85.7%). This is a **breaking UX change** — users will see all POs regress. See Module 4 fallback.

---

## Module 1 — Item-Level Qty + Part Number Comparison (M19 + M21)

**Approach:** Rules-based. Walk `order_items` arrays from each document, match by `sr_no` or position, compare `qty` and `part_no`.

**Feasibility: HIGH** — all fields present in extraction schemas. No AI needed. Extends existing `_cmp` pattern.

### Files

| Action | File |
|---|---|
| MODIFY | `backend/app/schemas/po_profile.py` |
| MODIFY | `backend/app/services/po_service.py` |
| MODIFY | `frontend/src/types/index.ts` |
| MODIFY | `frontend/src/components/ProfileFieldComparison.tsx` OR create new component |
| MODIFY | `frontend/src/pages/POProfilePage.tsx` |

### Exact Changes

**`backend/app/schemas/po_profile.py`** — add after `FieldComparison` class (line ~66):

```python
class ItemComparison(BaseModel):
    """One row-level comparison between order_items across two documents."""
    sr_no: str | None            # Row identifier (sr_no or position index)
    description: str | None      # Description from source doc
    part_no: str | None          # Part number (from COMPANY_PO side)
    source_doc: str              # Document type with canonical qty
    source_qty: float | None
    compared_doc: str
    compared_qty: float | None
    qty_match: bool | None       # None = one side missing
    source_price: float | None = None
    compared_price: float | None = None
    price_match: bool | None = None
```

**`backend/app/schemas/po_profile.py`** — add to `POProfileResponse`:
```python
item_comparisons: list[ItemComparison] = []
```

**`backend/app/services/po_service.py`** — import `ItemComparison` at top, then add after the `field_comparisons` block (before `vendor_groups`):

```python
# ── Item-level comparison engine ───────────────────────────────────────────
def _get_items(doc_type: DocumentType) -> list[dict]:
    doc_list = docs_by_type.get(doc_type, [])
    if not doc_list:
        return []
    meta = doc_list[0].doc_metadata
    if not meta or not meta.extracted_data:
        return []
    raw = meta.extracted_data.get("order_items")
    if not raw:
        return []
    try:
        items = raw if isinstance(raw, list) else __import__("json").loads(raw)
        return items if isinstance(items, list) else []
    except Exception:
        return []

def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return None

item_comparisons: list[ItemComparison] = []

# Qty: CUSTOMER_PO → COMPANY_DC (most critical — ordered vs delivered)
cpo_items = _get_items(DocumentType.CUSTOMER_PO)
cdc_items = _get_items(DocumentType.COMPANY_DC)
if cpo_items or cdc_items:
    max_len = max(len(cpo_items), len(cdc_items))
    for i in range(max_len):
        src = cpo_items[i] if i < len(cpo_items) else {}
        cmp = cdc_items[i] if i < len(cdc_items) else {}
        src_qty = _safe_float(src.get("qty"))
        cmp_qty = _safe_float(cmp.get("qty"))
        qty_match = (src_qty == cmp_qty) if src_qty is not None and cmp_qty is not None else None
        item_comparisons.append(ItemComparison(
            sr_no=str(src.get("sr_no") or cmp.get("sr_no") or (i + 1)),
            description=src.get("description") or cmp.get("description"),
            part_no=cmp.get("part_no"),
            source_doc=DocumentType.CUSTOMER_PO.value,
            source_qty=src_qty,
            compared_doc=DocumentType.COMPANY_DC.value,
            compared_qty=cmp_qty,
            qty_match=qty_match,
        ))

# Part no: COMPANY_PO → VENDOR_DC (did vendor ship the right parts?)
if po.fulfillment_type != FulfillmentType.STOCK:
    comp_po_items = _get_items(DocumentType.COMPANY_PO)
    vdc_items = _get_items(DocumentType.VENDOR_DC)
    if comp_po_items or vdc_items:
        max_len = max(len(comp_po_items), len(vdc_items))
        for i in range(max_len):
            src = comp_po_items[i] if i < len(comp_po_items) else {}
            cmp = vdc_items[i] if i < len(vdc_items) else {}
            src_part = str(src.get("part_no") or "").strip().lower() or None
            cmp_part = str(cmp.get("part_no") or "").strip().lower() or None
            src_qty = _safe_float(src.get("qty"))
            cmp_qty = _safe_float(cmp.get("qty"))
            qty_match = (src_qty == cmp_qty) if src_qty is not None and cmp_qty is not None else None
            part_match = (src_part == cmp_part) if src_part and cmp_part else None
            item_comparisons.append(ItemComparison(
                sr_no=str(src.get("sr_no") or cmp.get("sr_no") or (i + 1)),
                description=src.get("description") or cmp.get("description"),
                part_no=src_part or cmp_part,
                source_doc=DocumentType.COMPANY_PO.value,
                source_qty=src_qty,
                compared_doc=DocumentType.VENDOR_DC.value,
                compared_qty=cmp_qty,
                qty_match=qty_match,
                source_price=_safe_float(src.get("unit_price")),
                compared_price=_safe_float(cmp.get("unit_price")),
                price_match=part_match,
            ))
```

**`frontend/src/types/index.ts`** — add interface:
```typescript
export interface ItemComparison {
  sr_no: string | null;
  description: string | null;
  part_no: string | null;
  source_doc: string;
  source_qty: number | null;
  compared_doc: string;
  compared_qty: number | null;
  qty_match: boolean | null;
  source_price?: number | null;
  compared_price?: number | null;
  price_match?: boolean | null;
}
```

Add to `POProfile`:
```typescript
item_comparisons: ItemComparison[];
```

**`frontend/src/components/`** — CREATE `ProfileItemComparison.tsx`:
- Table layout: sr_no | description | part_no | source qty | compared qty | match icon
- Group by source_doc/compared_doc pair (CUSTOMER_PO→COMPANY_DC, COMPANY_PO→VENDOR_DC)
- Show mismatch count badge same style as ProfileFieldComparison

**`frontend/src/pages/POProfilePage.tsx`** — render `<ProfileItemComparison>` below `<ProfileFieldComparison>`

### Fallback
If `order_items` arrays have different lengths (vendor split items differently), position-based matching breaks. Fallback: match by `sr_no` string first, fall back to position. If count differs by >50%, skip comparison and show "Item count mismatch — manual review required" instead of incorrect matches.

---

## Module 2 — AI Description → Part No Linking (M22)

**Approach:** On `get_po_profile()`, if CUSTOMER_PO has items with no `part_no` and COMPANY_PO has items with `part_no`, call the local Layer 2 LLM (qwen2.5:3b) to match them. Result cached in Redis (TTL 1 hour) keyed by `(po_id, customer_po_doc_id, company_po_doc_id)`.

**Feasibility: MEDIUM** — LLM is already wired (`ollama_provider.py`). Risk: adds 3–8s to profile load on first call. Mitigated by Redis cache and async pattern.

**Reliability: ~80–85%** for standard product names. Drops for heavily abbreviated vendor codes. Must show confidence score to user.

### Files

| Action | File |
|---|---|
| CREATE | `backend/app/services/item_matcher.py` |
| MODIFY | `backend/app/schemas/po_profile.py` |
| MODIFY | `backend/app/services/po_service.py` |
| MODIFY | `frontend/src/types/index.ts` |
| MODIFY | `frontend/src/components/ProfileItemComparison.tsx` |

### Exact Changes

**CREATE `backend/app/services/item_matcher.py`**:
```python
"""LLM-assisted item description → part_no linking."""
import json, hashlib, logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

async def match_items_by_description(
    customer_items: list[dict],   # from CUSTOMER_PO — have description, no part_no
    company_items: list[dict],    # from COMPANY_PO — have part_no + description
    redis_client=None,
    cache_key: str | None = None,
) -> list[dict]:
    """
    Returns list of {sr_no, description, matched_part_no, confidence, match_type}.
    match_type: 'exact' | 'ai' | 'unmatched'
    """
    if not customer_items or not company_items:
        return []

    # Check Redis cache
    if redis_client and cache_key:
        cached = await redis_client.get(f"item_match:{cache_key}")
        if cached:
            return json.loads(cached)

    # Step 1: exact description match (case-insensitive)
    company_by_desc = {
        str(it.get("description", "")).lower().strip(): it
        for it in company_items
    }
    results = []
    unmatched = []
    for item in customer_items:
        desc = str(item.get("description", "")).lower().strip()
        if desc in company_by_desc:
            results.append({
                "sr_no": item.get("sr_no"),
                "description": item.get("description"),
                "matched_part_no": company_by_desc[desc].get("part_no"),
                "confidence": 1.0,
                "match_type": "exact",
            })
        else:
            unmatched.append(item)

    # Step 2: LLM match for remainder
    if unmatched:
        try:
            results.extend(await _llm_match(unmatched, company_items))
        except Exception as e:
            logger.warning(f"LLM item matching failed: {e} — marking as unmatched")
            for item in unmatched:
                results.append({
                    "sr_no": item.get("sr_no"),
                    "description": item.get("description"),
                    "matched_part_no": None,
                    "confidence": 0.0,
                    "match_type": "unmatched",
                })

    # Cache result
    if redis_client and cache_key:
        await redis_client.setex(f"item_match:{cache_key}", 3600, json.dumps(results))

    return results


async def _llm_match(unmatched: list[dict], company_items: list[dict]) -> list[dict]:
    catalog = [
        {"part_no": it.get("part_no"), "description": it.get("description")}
        for it in company_items if it.get("part_no")
    ]
    prompt = (
        "Match each customer item description to the best part number from the catalog. "
        "Return a JSON array with objects: {sr_no, matched_part_no, confidence (0-1)}. "
        "If no match, set matched_part_no to null and confidence to 0.\n\n"
        f"Customer items:\n{json.dumps([{'sr_no': i.get('sr_no'), 'description': i.get('description')} for i in unmatched])}\n\n"
        f"Catalog:\n{json.dumps(catalog)}"
    )
    base = settings.ocr_extractor_base_url or settings.ocr_base_url
    model = settings.ocr_extractor_model
    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        resp = await client.post(
            f"{base.rstrip('/')}/api/chat",
            json={"model": model, "stream": False, "messages": [{"role": "user", "content": prompt}]},
        )
        resp.raise_for_status()
        raw = resp.json()["message"]["content"]
        parsed = json.loads(raw[raw.find("["):raw.rfind("]") + 1])

    sr_map = {str(i.get("sr_no")): i for i in unmatched}
    results = []
    for match in parsed:
        original = sr_map.get(str(match.get("sr_no")), {})
        results.append({
            "sr_no": match.get("sr_no"),
            "description": original.get("description"),
            "matched_part_no": match.get("matched_part_no"),
            "confidence": float(match.get("confidence", 0)),
            "match_type": "ai",
        })
    return results
```

**`backend/app/schemas/po_profile.py`** — add:
```python
class ItemMatch(BaseModel):
    sr_no: str | None
    description: str | None
    matched_part_no: str | None
    confidence: float
    match_type: str   # 'exact' | 'ai' | 'unmatched'
```
Add to `POProfileResponse`:
```python
item_matches: list[ItemMatch] = []
```

**`backend/app/services/po_service.py`** — after item_comparisons block:
```python
# AI item matching (CUSTOMER_PO descriptions → COMPANY_PO part numbers)
item_matches: list[ItemMatch] = []
cpo_raw = _get_items(DocumentType.CUSTOMER_PO)
comp_po_raw = _get_items(DocumentType.COMPANY_PO)
if cpo_raw and comp_po_raw and po.fulfillment_type != FulfillmentType.STOCK:
    try:
        from app.services.item_matcher import match_items_by_description
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        cache_key = f"{po.id}:{docs_by_type.get(DocumentType.CUSTOMER_PO, [{}])[0].id if docs_by_type.get(DocumentType.CUSTOMER_PO) else 'none'}"
        matches = await match_items_by_description(cpo_raw, comp_po_raw, r, cache_key)
        await r.aclose()
        item_matches = [ItemMatch(**m) for m in matches]
    except Exception as e:
        logger.warning(f"Item matching skipped: {e}")
```

### Fallback
If LLM is unreachable or returns malformed JSON → all items marked `match_type: "unmatched"`, confidence 0. UI shows "AI matching unavailable — manual review" badge. No crash, no partial data.

---

## Module 3 — Structured Delivery Address Parsing (M24)

**Approach:** Parse `delivery_address` text at profile-load time using regex. Indian addresses always have 6-digit PIN codes. State names are a known finite set. No DB migration — parse on the fly and include in API response.

**Feasibility: HIGH** — pure Python regex, no external dependencies, no schema change needed.

### Files

| Action | File |
|---|---|
| CREATE | `backend/app/services/address_parser.py` |
| MODIFY | `backend/app/schemas/po_profile.py` |
| MODIFY | `backend/app/services/po_service.py` |
| MODIFY | `frontend/src/types/index.ts` |

### Exact Changes

**CREATE `backend/app/services/address_parser.py`**:
```python
"""Parse Indian delivery addresses into structured components."""
import re

INDIAN_STATES = {
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
    "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram",
    "nagaland", "odisha", "punjab", "rajasthan", "sikkim", "tamil nadu",
    "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal",
    "delhi", "jammu and kashmir", "ladakh", "chandigarh", "puducherry",
}

def parse_delivery_address(raw: str | None) -> dict:
    """Returns {pin_code, city, state, full_address}. All fields may be None."""
    if not raw:
        return {"pin_code": None, "city": None, "state": None, "full_address": None}

    raw = str(raw).strip()
    pin_match = re.search(r'\b(\d{6})\b', raw)
    pin_code = pin_match.group(1) if pin_match else None

    state = None
    raw_lower = raw.lower()
    for s in INDIAN_STATES:
        if s in raw_lower:
            state = s.title()
            break

    # City: word before PIN code if found
    city = None
    if pin_match:
        before_pin = raw[:pin_match.start()].strip().rstrip(",- ")
        city_match = re.search(r'[\w\s]+$', before_pin)
        if city_match:
            candidate = city_match.group().strip().split(",")[-1].strip()
            if 2 < len(candidate) < 40:
                city = candidate

    return {"pin_code": pin_code, "city": city, "state": state, "full_address": raw}
```

**`backend/app/schemas/po_profile.py`** — add:
```python
class ParsedAddress(BaseModel):
    pin_code: str | None
    city: str | None
    state: str | None
    full_address: str | None
```
Add to `POProfileResponse`:
```python
delivery_address_parsed: ParsedAddress | None = None
```

**`backend/app/services/po_service.py`** — after vendor_groups block:
```python
from app.services.address_parser import parse_delivery_address
_addr_raw = None
for dt in [DocumentType.COMPANY_DC, DocumentType.COMPANY_PO, DocumentType.VENDOR_DC]:
    val = _extracted(dt, "delivery_address")
    if val:
        _addr_raw = val
        break
delivery_address_parsed = ParsedAddress(**parse_delivery_address(_addr_raw)) if _addr_raw else None
```

### Fallback
If address doesn't match any known pattern → all fields return `None`, `full_address` returns the raw string. UI shows raw address only. No error.

---

## Module 4 — POD Document Type (M23)

**⚠️ HIGH IMPACT — READ THIS FIRST**

POD was **deliberately removed** via migration `a1b2c3d4e5f6`. Re-adding it to `CHAIN_DOC_TYPES` (making it 7) will drop every existing PO's completeness %. A PO currently at 100% drops to 85.7% immediately after migration. This will alarm users.

**Decision required before implementing:**
- Option A: Add POD to enum + `CHAIN_DOC_TYPES` → all completeness scores reset downward. Existing "complete" POs become "near complete". Must inform Skylark before deploying.
- Option B: Add POD to enum but NOT to `CHAIN_DOC_TYPES` → POD can be uploaded and extracted but doesn't count toward completeness. Safer. Completeness scores unchanged.
- Option C: Make POD optional in chain — add a `requires_pod: bool` flag on PurchaseOrder, only count it when set. Most correct but most work.

**Recommended: Option B first, upgrade to Option C later.**

### Files (Option B)

| Action | File |
|---|---|
| CREATE | `backend/alembic/versions/e5f6a7b8c9d0_add_pod_document_type.py` |
| MODIFY | `backend/app/models/document.py` |
| MODIFY | `backend/app/services/extraction/glm_ocr_prompts.py` |
| MODIFY | `backend/app/services/extraction/prompts.py` |
| MODIFY | `frontend/src/types/index.ts` |
| MODIFY | `frontend/src/components/ChainStatusBar.tsx` |
| MODIFY | `frontend/src/components/ProfileDocumentSection.tsx` |
| DO NOT TOUCH | `CHAIN_DOC_TYPES` in `po_service.py` |

### Exact Changes

**Migration** `e5f6a7b8c9d0_add_pod_document_type.py`:
```python
def upgrade():
    op.execute("""
        CREATE TYPE documenttype_new AS ENUM (
            'CUSTOMER_PO','COMPANY_PO','VENDOR_DC','VENDOR_INVOICE',
            'COMPANY_DC','COMPANY_INVOICE','POD'
        )
    """)
    op.execute("ALTER TABLE documents ALTER COLUMN document_type TYPE documenttype_new USING document_type::text::documenttype_new")
    op.execute("ALTER TABLE document_metadata ALTER COLUMN document_type TYPE documenttype_new USING document_type::text::documenttype_new")
    op.execute("ALTER TABLE reference_index ALTER COLUMN document_type TYPE documenttype_new USING document_type::text::documenttype_new")
    op.execute("DROP TYPE documenttype")
    op.execute("ALTER TYPE documenttype_new RENAME TO documenttype")

def downgrade():
    # Remove any POD documents first
    op.execute("DELETE FROM reference_index WHERE document_type = 'POD'")
    op.execute("DELETE FROM document_metadata WHERE document_type = 'POD'")
    op.execute("DELETE FROM documents WHERE document_type = 'POD'")
    # Reverse enum
    op.execute("""CREATE TYPE documenttype_new AS ENUM (
        'CUSTOMER_PO','COMPANY_PO','VENDOR_DC','VENDOR_INVOICE','COMPANY_DC','COMPANY_INVOICE'
    )""")
    op.execute("ALTER TABLE documents ALTER COLUMN document_type TYPE documenttype_new USING document_type::text::documenttype_new")
    op.execute("ALTER TABLE document_metadata ALTER COLUMN document_type TYPE documenttype_new USING document_type::text::documenttype_new")
    op.execute("ALTER TABLE reference_index ALTER COLUMN document_type TYPE documenttype_new USING document_type::text::documenttype_new")
    op.execute("DROP TYPE documenttype")
    op.execute("ALTER TYPE documenttype_new RENAME TO documenttype")
```

**`backend/app/models/document.py`** — add to `DocumentType`:
```python
POD = "POD"
```

**`backend/app/services/extraction/glm_ocr_prompts.py`** — add extraction schema for POD:
```python
"POD": {
    "document_type":    "Always 'POD'",
    "dc_reference":     "Delivery Challan number this POD acknowledges",
    "po_reference":     "Purchase Order number",
    "delivery_date":    "Date of delivery (DD/MM/YYYY)",
    "receiver_name":    "Name of person who received the goods",
    "receiver_sign":    "Whether signature is present (yes/no)",
    "delivery_address": "Full delivery address",
    "remarks":          "Any remarks or conditions noted",
}
```

### Fallback
If migration fails on existing data → `downgrade()` safely removes POD records and reverts enum. Zero data loss since POD had no records.

---

## Module 5 — Manual Line-Item Verification UI (M25)

**Approach:** Add a "Mark items verified" toggle on the PO Profile page. Stores a `items_verified: bool` flag on `PurchaseOrder`. Simple — no complex logic.

**Feasibility: HIGH** — UI-only change + one DB field.

### Files

| Action | File |
|---|---|
| CREATE | `backend/alembic/versions/f6a7b8c9d0e1_add_items_verified_to_po.py` |
| MODIFY | `backend/app/models/purchase_order.py` |
| MODIFY | `backend/app/schemas/purchase_order.py` |
| MODIFY | `frontend/src/types/index.ts` |
| MODIFY | `frontend/src/pages/POProfilePage.tsx` |

### Exact Changes

**Migration**: `ALTER TABLE purchase_orders ADD COLUMN items_verified BOOLEAN NOT NULL DEFAULT FALSE`

**`backend/app/models/purchase_order.py`**:
```python
items_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

**`backend/app/schemas/purchase_order.py`** — add to `POUpdate`:
```python
items_verified: Optional[bool] = None
```
Add to `POResponse` / `POProfileResponse`:
```python
items_verified: bool = False
```

**Frontend** — add a toggle button on POProfilePage near the fulfillment_type toggle. Calls `PATCH /purchase-orders/{id}` with `{items_verified: true/false}`.

---

## Execution Order

```
Module 3 (Address parser)   → No migration, safest, ~3h
Module 1 (Item comparison)  → No migration, extends existing pattern, ~5h
Module 5 (Items verified)   → Simple migration + UI toggle, ~3h
Module 4 (POD)              → Migration risk, do last of backend, ~4h
Module 2 (AI matching)      → Depends on Module 1 data, do last, ~5h
```

---

## Final Deliverable — What You Get

After all 5 modules, the PO Profile page answers:

| Business Question | Answered by |
|---|---|
| Was the right qty delivered? | Module 1 — CUSTOMER_PO qty vs COMPANY_DC qty, row by row |
| Did the vendor ship the right parts? | Module 1 — COMPANY_PO part_no vs VENDOR_DC part_no |
| Does the customer PO item match the vendor part? | Module 2 — AI description→part_no link |
| Was the delivery confirmed? | Module 4 — POD document slot |
| Were items manually confirmed by reviewer? | Module 5 — items_verified toggle |
| Where was it delivered (structured)? | Module 3 — parsed pin/city/state |
| Amount billed = amount ordered? | Already live — grand_total vs total_amount |

---

## Impact on Application Workflow

| Module | Impact level | What changes for users |
|---|---|---|
| M1 — Item comparison | **Medium** | New section on PO Profile: "Item Verification" table. No existing screens change. |
| M2 — AI matching | **Medium** | Profile page loads 3–8s slower on first open (cached after). New "AI Matched" badges on items. |
| M3 — Address parser | **Low** | Delivery address shown as pin/city/state instead of raw text. Search behavior unchanged. |
| M4 — POD | **High (Option B)** | New upload slot visible but doesn't affect completeness %. Upload + extraction works immediately. |
| M5 — Items verified | **Low** | New toggle on profile page. PATCH endpoint. No existing behavior changes. |

**No breaking changes to existing API contracts.** All new fields are additive with defaults (`= []`, `= None`, `= False`). Existing clients continue to work.
