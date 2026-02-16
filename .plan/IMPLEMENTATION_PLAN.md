# Document Platform V3 — Implementation Plan

> **Baseline**: Git commit `v2.1.0` — Multi-doc support, OCR prompt rewrite, customer combobox, inline search, extraction pipeline fixes  
> **Goal**: Fix extraction pipeline, upload & test all 28 real documents, build auto chain linking

---

## Phase 1 — Extraction Pipeline Fixes

Focus: Make the first 2-3 pages yield accurate, reliable data for each document type.

### 1.1 Add Missing Schema Fields

**File**: `backend/app/services/extraction/prompts.py`

| Document Type | New Field | Reason |
|---|---|---|
| COMPANY_DC | `sales_order_no` | Present on every company DC ("Sales Order No."), critical for DC↔Invoice linking |
| COMPANY_DC | `customer_order_date` | Printed on every DC, useful for cross-referencing |
| COMPANY_INVOICE | `customer_order_date` | Present on every invoice ("Customer Order Date"), helps match to customer PO |
| COMPANY_INVOICE | `acct_manager` | Present on every invoice, useful metadata |

Also add `sales_order_no` to COMPANY_DC searchable fields in `get_searchable_fields()`.

**Impact**: Schema-only change — no DB migration needed (fields go into `extracted_data` JSONB).

---

### 1.2 Fix Multi-Page PDF Extraction

**File**: `backend/app/services/extraction/pdf_converter.py`

**Problem**: Current `max_pages` default is 10 with first-half/last-half strategy. For a 5-6 page company DC, all pages are sent. But for very long documents (42-page customer POs), page 1 may crash the model.

**Fix**:
1. Always include **page 1** (header info) and **last page** (totals/signatures)
2. For documents > `max_pages`, select: pages [0, 1, ..., half-1] + [total-half, ..., total-1]
3. Ensure last page is always in the set even if `total_pages <= max_pages` (already true, just verify)

**Current code already handles this correctly** for docs ≤ 10 pages. The main fix is resilience — if page 1 fails (Ollama 500), skip and try page 2.

---

### 1.3 Handle Ollama 500 Errors Gracefully (Per-Page)

**File**: `backend/app/services/extraction/tasks.py`

**Problem**: If Ollama returns HTTP 500 on any page, the entire extraction crashes. This happened with a 42-page customer PO where page 1 was too complex.

**Fix**:
```python
# In the OCR loop (step 6 of extract_document):
for i, img in enumerate(images):
    try:
        result = asyncio.run(ocr.extract_from_image(img, prompt))
        raw_texts.append(result["text"])
        total_time_ms += result["processing_time_ms"]
    except (OCRServiceError, OCRTimeoutError) as e:
        logger.warning(f"Page {i+1} failed, skipping: {e}")
        raw_texts.append("")  # Empty page, parser will skip
        continue

if not any(raw_texts):
    raise Exception("All pages failed OCR extraction")
```

**Impact**: Partial extraction > total failure. Parser already handles merging non-empty pages.

---

### 1.4 Refine Prompts with Exact Label Text

**File**: `backend/app/services/extraction/prompts.py`

Based on analysis of all 28 real documents, use exact field label text from the documents:

#### COMPANY_DC (issued by company — title "NON RETURNABLE DELIVERY CHALLAN")
- Labels found: "DC No.", "DC Date", "Customer Order No.", "Reference" (person name — NOT the PO), "Sales Order No."
- Fix: Clarify that `po_reference` = "Customer Order No." field, NOT "Reference" field

#### COMPANY_INVOICE (issued by company — title "TAX INVOICE")  
- Labels found: "Invoice No.", "Invoice Date", "Customer Order No.", "SO No.", "Customer Order Date", "Acct Manager", "IRN No."
- Fix: `po_reference` = "Customer Order No." (which is actually the customer's PO number on this doc), `so_number` = "SO No."

#### VENDOR_INVOICE (issued by vendors — highly variable format)
- Different vendors use different labels: "Invoice No.", "Bill No.", "Your Ref", "Buyer Order No."
- Current prompt handles this well — no changes needed

#### CUSTOMER_PO (issued by customer — highly variable format)
- Each customer has different PO format
- Current prompt adequate — no changes needed

---

### 1.5 Add SKYLARK_PO Document Type

**Files**: `backend/app/models/document.py`, `prompts.py`

**Problem**: Currently no SKYLARK_PO type. These are "PURCHASE BILL" documents — the company's own purchase orders to vendors. Contains `bill_no` (= vendor invoice number), vendor name, amounts.

**Decision**: **DEFER to Phase 3**. For now, these can be uploaded as VENDOR_INVOICE since they reference the same vendor invoice. The company PO is supplementary.

---

## Phase 2 — Upload & Test All 28 Documents

### 2.1 Create Test Customers & POs

Create 5 customers (using generic names like "Customer A", "Customer B", etc.) and their POs via API or UI.

| Customer | PO Number | Expected Documents |
|---|---|---|
| Customer A | (from customer PO) | 5 docs: Customer PO, Company DC, Company Invoice, Vendor Invoice, Company PO |
| Customer B | (from customer PO) | 8 docs: Customer PO, 2x Company DC, 2x Company Invoice, 2x Vendor Invoice, Company PO |
| Customer C | (from customer PO) | 5 docs: Customer PO, Company DC, Company Invoice, Vendor Invoice, Company PO |
| Customer D | (from customer PO) | 5 docs: Customer PO, Company DC, Company Invoice, Vendor Invoice, Company PO |
| Customer E | (from customer PO) | 5 docs: Customer PO, Company DC, 2x Company Invoice, Vendor Invoice, Company PO |

### 2.2 Upload Documents

Upload all 28 PDFs to their respective POs, one by one via the UI or a script.

### 2.3 Measure Extraction Accuracy

For each document, compare extracted fields against known values from raw OCR analysis:

**Key fields to validate**:
- Primary reference (PO number, DC number, invoice number)
- Date field
- Customer/vendor name
- PO reference (cross-link field — the most important for chain linking)
- Total amount
- Sales order number (new field for company DC)

**Success criteria**:
- Primary reference: ≥ 90% accurate
- PO reference (cross-link): ≥ 80% accurate
- Amounts: ≥ 85% accurate (cleaned of commas)
- Dates: ≥ 90% accurate

### 2.4 Fix Issues Found During Testing

Iterate on prompts and parsing based on results.

---

## Phase 3 — Auto Chain Linking

### 3.1 Chain Model Design

The document chain flows through 3 master keys:

```
CUSTOMER PO NUMBER (★) — The primary chain key
├── Customer PO → po_number = ★
├── Company DC → po_reference = ★ (label: "Customer Order No.")  
├── Company Invoice → po_reference = ★ (label: "Customer Order No.")
└── (Used to group all documents for one transaction)

SALES ORDER NUMBER (●) — Internal link between company DC and company invoice
├── Company DC → sales_order_no = ●
└── Company Invoice → so_number = ●

VENDOR INVOICE NUMBER (◆) — Procurement chain link
├── Vendor Invoice → invoice_number = ◆
└── Company PO → bill_no = ◆
```

### 3.2 Auto-Link Implementation

**New API endpoint**: `GET /api/v1/chain/{po_id}/links`

**Logic**:
1. When a document is extracted, check its `po_reference` against existing `ReferenceIndex`
2. Find all documents with matching `po_reference` → they belong to the same chain
3. Cross-validate using `sales_order_no`/`so_number` match between company DC and company invoice
4. Return chain status showing which documents are linked and which are missing

### 3.3 Chain Visualization in UI

- Show chain diagram on PO detail page
- Color-coded: green (linked), yellow (uploaded but unlinked), gray (missing)
- Click on chain node to jump to that document

### 3.4 Chain Validation Rules

| Rule | Description |
|---|---|
| R1 | Every company DC should have a matching company invoice (via sales_order_no) |
| R2 | Every company invoice should reference an uploaded customer PO (via po_reference) |
| R3 | Total amount on company invoice should approximately match vendor invoice total + margin |
| R4 | DC date should be ≤ invoice date |

---

## Phase 4 — Fetching Related Documents

### 4.1 "Fetch Related" Feature

When viewing any document, show a "Related Documents" panel:
- Find all documents with the same `po_reference` (customer PO number)
- Find all documents with the same `sales_order_no`/`so_number`
- Group and display by document type

### 4.2 API Endpoint

**New**: `GET /api/v1/documents/{document_id}/related`

**Response**:
```json
{
  "chain_key": "CUSTOMER_PO_NUMBER_VALUE",
  "related_documents": [
    {
      "id": "uuid",
      "document_type": "COMPANY_DC",
      "primary_ref": "DC_NUMBER",
      "link_field": "po_reference",
      "link_value": "CUSTOMER_PO_NUMBER_VALUE",
      "confidence": 95
    }
  ]
}
```

### 4.3 Cross-PO Search

Allow searching across ALL POs by any reference number:
- Enter a vendor invoice number → find the company PO and company DC that reference it
- Enter a sales order number → find the company DC and company invoice pair
- This uses the existing `ReferenceIndex` table

---

## Phase 5 — Polish & Production Readiness

### 5.1 Data Quality Dashboard
- Show extraction accuracy stats per document type
- Show documents with low confidence (< 60%)
- Show POs with incomplete chains

### 5.2 Bulk Re-extraction
- Button to re-extract all documents of a type with updated prompts
- Queue all via Celery, track progress

### 5.3 Export & Reporting
- Export chain data as CSV/Excel
- Generate chain completeness report per customer

---

## Priority Order

| Priority | Phase | Effort | Impact |
|---|---|---|---|
| P0 | Phase 1.1 — Add schema fields | 30 min | Enables chain linking |
| P0 | Phase 1.3 — Handle Ollama 500 | 30 min | Prevents total failures |
| P1 | Phase 1.4 — Refine prompts | 1 hr | Better po_reference accuracy |
| P1 | Phase 2 — Upload & test | 2 hrs | Validates everything |
| P2 | Phase 3 — Auto chain linking | 4 hrs | Core feature |
| P2 | Phase 4 — Fetch related | 3 hrs | Core feature |
| P3 | Phase 5 — Polish | 4 hrs | Nice to have |

---

## Known Limitations (OCR Model)

1. **I vs 1 confusion**: "1ITR" reads as "11TR" — font-level issue, model limitation (1.1B parameter model)
2. **Complex page crashes**: Pages with dense tables/graphics may cause Ollama 500 (GGML tensor errors)
3. **Handwritten text**: Receiver signatures/stamps poorly recognized
4. **Scan quality**: Some documents have faded headers or cropped edges
5. **42+ page documents**: Only first few + last few pages processed to stay within model limits

These are inherent to the glm-ocr 1.1B model. A larger model (7B+) would improve accuracy but requires more GPU memory.
