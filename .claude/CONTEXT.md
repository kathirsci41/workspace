# Order Assurance — Domain Context
*Created: June 2026 | Source: Grill-with-docs session + codebase analysis*

---

## What This System Does

Order Assurance is an **Intelligent Document Processing (IDP)** system for Indian logistics procurement. It ingests a 5-document bundle, extracts fields via OCR, and verifies consistency across documents before allowing payment or delivery sign-off.

---

## The 5-Document Bundle

Every order produces exactly this bundle. All 5 documents must be present for a complete verification.

| Internal Name | Document | Direction | Who Issues |
|---|---|---|---|
| `CUSTOMER_PO` | Customer Purchase Order | Customer → Our Company | Customer |
| `COMPANY_INVOICE` | Company Invoice (Tax Invoice) | Our Company → Customer | Our Company (Skylark) |
| `COMPANY_DC` | Delivery Challan | Our Company → Customer | Our Company (Skylark) |
| `COMPANY_PO` | Vendor Purchase Order | Our Company → Vendor | Our Company (Skylark) |
| `VENDOR_INVOICE` | Vendor Bill / Tax Invoice | Vendor → Our Company | Vendor |

**Our company**: Skylark Information Technologies Pvt Ltd (Tamil Nadu, state code 33)

---

## Document Flow

```
Customer ──[CUSTOMER_PO]──► Our Company ──[COMPANY_PO]──► Vendor
                                │                              │
                          [COMPANY_DC]              [VENDOR_INVOICE]
                          [COMPANY_INVOICE]
                                │
                           Customer ◄──────────────────────────┘
```

- Customer sends PO to us
- We raise a PO to the vendor
- Vendor ships goods with their invoice
- We ship to customer with our DC and invoice

---

## Key Reference Numbers (Flow Through All Docs)

| Field | Meaning | Present In |
|---|---|---|
| `customer_po_no` | Customer's order number | CUSTOMER_PO, COMPANY_INVOICE, COMPANY_DC |
| `so_no` | Our internal Sales Order number | COMPANY_INVOICE, COMPANY_DC |
| `po_number` / `vendor_po_no` | Our PO to vendor | COMPANY_PO, VENDOR_INVOICE (`po_reference`) |
| `vendor_invoice_no` | Vendor's invoice number | VENDOR_INVOICE |

---

## GSTIN (Tax Identity)

**Format:** `[state_code_2][PAN_10][entity_1][Z][checksum_1]`
Example: `33AAGCS1406H1ZR` = state 33 (Tamil Nadu) + PAN + suffix

**GST type by transaction:**
- Vendor state == 33 (TN) + Our company state == 33 (TN) → **CGST + SGST** (intrastate)
- Vendor state ≠ 33 → **IGST** (interstate)

**What gets extracted:**
- `VENDOR_INVOICE`: `vendor_gstin` (vendor's own GSTIN) — always present
- Other doc types: `gstin` field attempted via regex — often not present on physical docs
- Decision: SKIP (not fail) when GSTIN not found in a document

---

## Split Delivery (Multi-DC)

A single Customer PO / SO can result in multiple deliveries, each with its own DC.

Example: `Single PO & SO - Multi Vendor PO - Customer Side 2 DC 1 Invoice`

Rules:
- **Amount match**: SUM of all DC amounts vs single invoice total
- **Reference match**: EACH DC must have same SO/PO as the invoice
- Never use only `dcs[0]` — always iterate all DCs

---

## Verification Checks (Current)

| Check ID | Left | Right | Severity |
|---|---|---|---|
| `INVOICE_DC_CUSTOMER_ORDER_MATCH` | Invoice PO ref | DC PO ref | BLOCKER |
| `INVOICE_DC_SO_MATCH` | Invoice SO | DC SO | BLOCKER |
| `CUSTOMER_NAME_MATCH` | Invoice customer | DC customer | WARNING |
| `INVOICE_DC_AMOUNT_MATCH` | Invoice taxable | DC taxable | WARNING |
| `CUSTOMER_PO_INVOICE_ORDER_MATCH` | Customer PO no | Invoice PO ref | BLOCKER |
| `CUSTOMER_PO_DC_ORDER_MATCH` | Customer PO no | DC PO ref | BLOCKER |
| `CUSTOMER_PO_INVOICE_AMOUNT_MATCH` | Customer PO amount | Invoice amount | WARNING |
| `VENDOR_PO_INVOICE_REFERENCE_MATCH` | Vendor PO no | Vendor Invoice PO ref | BLOCKER |
| `VENDOR_NAME_MATCH` | Vendor PO vendor name | Vendor Invoice vendor name | WARNING |
| `VENDOR_BILLING_COVERAGE` | Vendor PO total | Vendor Invoice total | WARNING |

---

## Bundle Status Values

| Status | Meaning |
|---|---|
| `PASS` | All checks passed |
| `PARTIAL_PASS` | Customer side OK, vendor side issues |
| `REVIEW_REQUIRED` | One or more checks need manual review |
| `FAILED` | Blocking check failed |

Two separate status axes:
- `customer_delivery_status` — COMPANY_INVOICE + COMPANY_DC + CUSTOMER_PO checks
- `vendor_procurement_status` — COMPANY_PO + VENDOR_INVOICE checks

---

## Vendor Name Normalization

Legal suffix variants are all the same company:

| Variant | Normalized to |
|---|---|
| `SUPREME COMPUTERS INDIA P LTD` | `SUPREME COMPUTERS INDIA` |
| `Supreme Computers India Pvt Ltd` | `SUPREME COMPUTERS INDIA` |
| `Supreme Computers India Private Limited` | `SUPREME COMPUTERS INDIA` |

Suffixes stripped: `Private Limited`, `Pvt Ltd`, `P Ltd`, `Limited`, `Ltd`, `LLP`, `LLC`

---

## Accepted Validation Baselines

| Fixture | Baseline |
|---|---|
| Panimalar (`real-doc-001-tradefix-final8`) | 24/24 fields, zero failed doc statuses, XLSX passed, vendor partial billing open |
| Trade (`real-doc-002-trade-fix7`) | Zero failed doc statuses, XLSX passed |
| AMC (`real-doc-003-amc-fix1`) | 27/28 fields, Delivery Challan missing only, vendor PASS, XLSX passed |

---

## Tenant Model

- Single tenant today: `tenant_id = "default"` on all records
- `TenantMiddleware` injects `request.state.tenant_id = "default"` on every request
- Future: replace stub with JWT extraction in `get_tenant_id(request)`
- `tenant_id` column present on: `order_bundles`, `documents`, `document_metadata`, `audit_events`, `reference_index`, `vendor_master`

---

## OCR Stack (Sprint 2 target)

```
PDF → PyMuPDF (digital text attempt)
   → PP-OCRv5 (PaddleOCR 3.0, GPU)        ← upgraded from v4
   → [if low confidence] PaddleOCR-VL-1.6  ← HuggingFace, NOT Ollama
       (PaddlePaddle/PaddleOCR-VL-1.6, 0.9B, 96.33 OmniDocBench)
   → regex parser → extracted_data{}
   → [VENDOR_INVOICE / COMPANY_INVOICE] PP-StructureV3 table extraction → line_items[]
```

---

## Sprint 4 Extraction Architecture (LiteParse BBox, June 2026)

### What changed

Benchmark finding: LiteParse extracts 50–111% more text than PyMuPDF for digital PDFs (222–242 bboxes per fixture). However feeding that richer text into the existing regex parser causes FEWER fields extracted — line-item table amounts bleed into header regex patterns. Spatial bbox extraction is the correct path.

### Updated Pipeline (Sprint 4, digital PDFs only)

```
PDF → PyMuPDF text (existing, unchanged)
    → regex parser → flat_dict (existing result)
    → LiteParse bboxes (new, Sprint 4)
    → BBoxFieldExtractor (label-proximity rules) → bbox_dict
    → TableRowExtractor (Y-band grouping) → line_items[]
    → MERGE: {**flat_dict, **bbox_dict}   ← bbox wins on overlap (Option G)
    → extracted_data{}  ← unchanged key name, same DB column

Scanned docs: LiteParse returns empty → skip bbox layer → regex result only
```

### New Files (Sprint 4)

| File | Purpose |
|---|---|
| `backend/app/services/extraction/liteparse_extractor.py` | Wraps LiteParse, returns bboxes + text for digital PDFs |
| `backend/app/services/extraction/bbox_field_extractor.py` | Label-proximity rules → header fields |
| `backend/app/services/extraction/table_row_extractor.py` | Y-band bbox grouping → line_items[] |
| `backend/app/services/extraction/unified_schema.py` | Internal schema S + adapter to flat dict T |

### One Existing File Edited (Sprint 4)

- `backend/app/services/extraction/ocr_extraction_service.py` — adds `_apply_bbox_layer()` call after existing regex parse

### line_items Storage (Option J)

`extracted_data["line_items"] = [{description, product_code, hsn_sac, qty, uom, unit_rate, taxable_value, tax_amount, amount, serial_numbers}]`

Zero DB schema change. Build 2 promotes to relational table when verification needs line-level SQL queries.

### line_items Schema (mirrors LlamaExtract reference)

```json
{
  "description": "EC-10106 SDWAN",
  "product_code": "EC-10106",
  "hsn_sac": "85176990",
  "qty": "2",
  "uom": "NOS",
  "unit_rate": "531000",
  "taxable_value": "1062000",
  "tax_amount": "191160",
  "amount": "1253160",
  "serial_numbers": ["SN001", "SN002"]
}
```

### Unified Schema S (internal only, Sprint 4)

Dataclasses: `InvoiceSchema` → `PartyInfo` (buyer/vendor), `OrderDetails`, `LineItem[]`, `TaxSummary`, `FinancialSummary`. Adapter `to_flat_dict()` maps to existing flat field names. Build 2 exposes S directly to frontend.

### LlamaExtract Schema Finding (June 2026 benchmark)

LlamaExtract uses DIFFERENT top-level field names per batch:
- Panimalar: `buyer_info`, `vendor_info`, `order_details`, `financial_summary`
- Trade (Hindalco): `seller`, `consignee`, `buyer`, `totals`
- AMC (Shriram/Corrohealth): `seller_details`, `customer_details`, `invoice_details`, `totals`

Unified schema only if you define a Pydantic model upfront. Our normalized field names (`customer_name`, `vendor_name`, `po_reference`, etc.) are already more consistent than raw LlamaExtract output. This confirmed Option T (keep our flat dict).

### PaddleOCR HTTP Server (Option E)

- Ships with LiteParse at `liteparse/ocr/paddleocr/server.py`
- Starts on `localhost:8828`
- Backend checks if running; falls back to existing `paddle_provider.py` if not
- PP-StructureV3 PP-TableMagic (also in this server) handles table extraction for SCANNED docs
- For DIGITAL docs: LiteParse Y-band grouping is faster and more accurate (no rendering artifacts)

### Offline Tesseract (air-gapped deployment)

LiteParse bundles Tesseract. For offline environments: pre-download `eng.traineddata`, set `TESSDATA_PREFIX=/path/to/tessdata/`. No internet needed. Production resilience fallback if PaddleOCR HTTP server not running.

### Build 2 Candidates

- Expose unified schema S to frontend (nested buyer_info{}, vendor_info{})
- line_items → relational table (Option K)
- LayoutLMv3 fine-tuned on our fixtures (requires training data + GPU)
- PP-TableMagic PATH B for complex digital tables
- TESSDATA_PREFIX offline Tesseract production config

---

## Key Decisions (ADRs)

- **ADR-001**: PostgreSQL 16 + Alembic replacing SQLite
- **ADR-002**: Celery 5 + Redis 7 replacing in-process `threading.Condition + deque`
- **ADR-003**: `ToleranceConfig` (2% / ₹5 floor), `LineItemRecord`, `VendorMasterRecord` + GSTIN validation
- **Sprint 4**: LiteParse bbox spatial extraction + layer+merge + line_items as nested JSON key (Options A/Y/P/T/E/G/J)
