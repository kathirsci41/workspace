# Phase 1xI — Extraction Review Explainability & Quality Report

**Date:** 2026-06-14  
**Phase:** 1xI  
**Focus:** Review UI explainability improvements and targeted extraction quality fixes

---

## 1. Objectives

This phase had two tracks:

**Track A — Review UI explainability**
- Step 1: Audit existing review UI files (completed in prior phase)
- Step 2: Doc-type-aware field grouping (Critical / Supporting / Needs Review)
- Step 3: Field source/route/"used in comparison" badges
- Step 4: PDF highlight overlay for digital PDFs using `field_locations[field].page`/`bbox`
- Step 5: Scanned-OCR "highlight unavailable" message
- Step 6: PaddleOCR model/runtime diagnostics in extraction result
- Step 7: PaddleOCR OCR text-block capture for future scanned highlight wiring

**Track B — Targeted extraction quality**
- Step 8.1: COMPANY_PO `vendor_po_date` alias from `po_date`
- Step 8.2: VENDOR_INVOICE suspicious party-name fields marked `needs_review`
- Step 8.3: CUSTOMER_PO `tax_amount` rate-vs-amount plausibility check

---

## 2. Test Gate Results

### Backend

```
702 passed, 5 skipped
```

Includes:
- `tests/unit/test_structured_text_parser.py` — 65 passed
- `tests/unit/test_real_document_fix1.py` — 6 passed
- `tests/unit/test_paddle_ocr_provider.py` — 84 passed
- `tests/unit/test_extraction_service.py` — 16 passed

### Frontend

```
55 passed (10 test files)
```

New test files added this phase:
- `src/components/extraction/extractedFieldsPanel.test.ts` — 14 tests (grouping logic, source labels, critical field lists)
- `src/components/documents/pdfHighlight.test.ts` — 7 tests (bbox-to-percent, canHighlight, isScannedNoHighlight)

---

## 3. Step 2 — Doc-type-aware field grouping

**File:** `frontend/src/components/extraction/ExtractedFieldsPanel.tsx`

**Change:** Replaced flat Critical/Amounts/References/Other groups with three doc-type-aware groups:

| Group | Condition |
|---|---|
| **Needs Review** | `field_metadata[field].source` equals `needs_review` or starts with `suspicious_` |
| **Critical Fields** | Field appears in `CRITICAL_FIELDS_BY_DOC_TYPE[docType]` and is not flagged |
| **Supporting Fields** | All remaining fields |

Critical field lists per doc type:

| Doc Type | Critical Fields |
|---|---|
| CUSTOMER_PO | `customer_po_no`, `po_number`, `customer_po_date`, `customer_name`, `grand_total`, `subtotal_amount`, `tax_amount` |
| COMPANY_INVOICE | `invoice_no`, `invoice_number`, `invoice_date`, `customer_order_no`, `so_no`, `so_number`, `net_amount`, `taxable_amount`, `tax_amount` |
| COMPANY_DC | `dc_no`, `dc_number`, `dc_date`, `customer_order_no`, `so_no`, `so_number`, `total_quantity` |
| COMPANY_PO | `vendor_po_no`, `vendor_po_date`, `vendor_name`, `net_amount`, `subtotal_amount`, `tax_amount` |
| VENDOR_INVOICE | `vendor_invoice_no`, `vendor_invoice_date`, `vendor_name`, `po_reference`, `invoice_total`, `subtotal_amount`, `tax_amount` |

Source data: `metadata.diagnostics.field_metadata[field].source` (preserves raw parser source: `rules`, `needs_review`, `suspicious_tax_amount`, `fallback_largest`, etc.)

---

## 4. Step 3 — Field source/route/"used in comparison" badges

**File:** `frontend/src/components/extraction/ExtractedFieldsPanel.tsx`

Two badge types per field:

1. **"Used in Review Results"** (blue, existing): shown for fields in the doc-type critical list (now doc-type-aware via `isVerificationField(field, docType)`)

2. **Source badge** (new): shown for non-obvious extraction sources:

| Source value | Badge label | Style |
|---|---|---|
| `needs_review` | Needs Review | amber |
| `suspicious_*` | Suspicious | amber |
| `fallback_largest` | Estimated | gray/info |
| `filename_fallback` | From Filename | gray/info |
| `model_layer2` | AI Extracted | gray/info |
| `rules` / `digital_text` / `ocr` | *(no badge)* | — |

CSS classes: `.source-badge--warning` (amber), `.source-badge--info` (gray).

---

## 5. Step 4 — PDF highlight overlay for digital PDFs

**Files:** `frontend/src/components/documents/PdfPreviewPane.tsx`, `frontend/src/pages/ExtractionReviewPage.tsx`

**Mechanism:**
- Clicking a field name in `ExtractedFieldsPanel` calls `onFieldClick(field)`
- `ExtractionReviewPage` tracks `highlightedField`, reads `field_locations[field]` from `activeDocument.metadata.field_locations`
- If `location.page !== selectedPage`, the page is jumped to automatically via `setPage(location.page)`
- `highlightLocation` is passed to `PdfPreviewPane`
- If `canHighlight(location)` and page matches, a `div.pdf-highlight-overlay` is rendered absolutely inside `.pdf-highlight-container` using `bboxToPercent(bbox, page_width, page_height)` for coordinate scaling

**Highlight rendering:** Semi-transparent amber border (`rgba(251, 191, 36, 0.18)` fill, `#f59e0b` 2px border), positioned using `position: absolute` with percentage coordinates relative to the page image.

**Available for:** Digital PDFs where extraction used `digital_text` route and `pdf_field_locator.py` successfully located the field (bbox is non-null).

---

## 6. Step 5 — Scanned-OCR highlight unavailable message

**File:** `frontend/src/components/documents/PdfPreviewPane.tsx`

When a field is selected but `field_locations[field].bbox` is null (typical for scanned/OCR documents), a status message is shown above the PDF viewport:

> _Highlight unavailable — field was extracted from scanned OCR text without position data._

Triggered by `isScannedNoHighlight(location)`: returns `true` when `location` exists but `location.bbox` is null.

---

## 7. Step 6 — PaddleOCR model/runtime diagnostics

**Files:** `backend/app/services/extraction/ocr_providers/paddle_provider.py`, `backend/app/services/extraction_service.py`, `backend/app/services/extraction/ocr_providers/base.py`

New diagnostics keys recorded when PaddleOCR route runs:

| Key | Description |
|---|---|
| `paddleocr_available` | True/False based on import check |
| `paddleocr_version` | Version from `importlib.metadata`, or `"unknown"` |
| `paddlepaddle_version` | Version of the paddlepaddle backend, or `"unknown"` |
| `paddle_init_args` | Dict of args passed to `PaddleOCR(...)` constructor (e.g. `{"lang": "en"}`) |
| `paddle_device` | Device setting from `settings.ocr_paddle_device` |
| `ocr_paddle_duration_ms` | Wall time of PaddleOCR run |
| `ocr_paddle_text_length` | Character count of extracted raw text |

When PaddleOCR is unavailable, all of the above are still recorded (version fields default to `"unknown"`).

---

## 8. Step 7 — PaddleOCR text-block capture

**Files:** `backend/app/services/extraction/ocr_providers/paddle_provider.py`, `backend/app/services/extraction_service.py`, `backend/app/services/extraction/ocr_providers/base.py`

New optional field on `OcrProviderResult`: `text_blocks: list[dict] | None`

Each text block:
```json
{
  "text": "TAX INVOICE",
  "page": 1,
  "confidence": 0.99,
  "bbox": [[x0,y0],[x1,y1],[x2,y2],[x3,y3]]
}
```

When present, stored in diagnostics as `ocr_paddle_text_blocks`. Not wired to the review UI in this phase — reserved for future scanned-PDF position-data highlighting.

---

## 9. Step 8 — Targeted extraction quality fixes

### 8.1 — COMPANY_PO `vendor_po_date` alias

**File:** `backend/app/services/extraction/structured_text_parser.py` (`_with_aliases`)

Previously, `vendor_po_date` was only aliased from `po_date` if `po_number` was also present. Changed to unconditionally alias `po_date → vendor_po_date` for COMPANY_PO, so the review UI shows the date even when the PO number extraction fails.

**Test:** `test_company_po_vendor_po_date_alias_from_po_date` in `test_real_document_fix1.py`.

### 8.2 — VENDOR_INVOICE suspicious party-name fields

**File:** `backend/app/services/extraction/structured_text_parser.py` (`_parse_vendor_invoice`)

Real-world Panimalar VENDOR_INVOICE extraction produced:
- `ship_to_name = "Invoice No."` (field label captured instead of party name)
- `bill_to_name = "C000691"` (customer reference code)
- `vendor_name = "SUPREME"` (truncated, no company suffix)

New heuristics applied at `field_metadata_overrides` level (values unchanged):

| Heuristic | Helper | Threshold |
|---|---|---|
| `_looks_like_label_or_code(v)` | `_LABEL_LIKE_VALUE_RE` + `_PARTY_CODE_RE` | Marks `ship_to_name`/`bill_to_name` `needs_review`, confidence 0.3 |
| `_looks_like_incomplete_company_name(v)` | len < 10, no spaces, no company suffix | Marks `vendor_name` `needs_review`, confidence 0.3 |

**Tests:** 4 tests in `test_structured_text_parser.py` (3 positive, 1 negative control).

### 8.3 — CUSTOMER_PO suspicious tax_amount (rate vs. amount)

**File:** `backend/app/services/extraction/structured_text_parser.py` (`_customer_po_field_metadata_overrides`)

When `tax_amount ≤ 100` AND `(grand_total − subtotal_amount) > tax_amount × 5`, the extracted `tax_amount` is likely a tax rate (e.g. 18 for 18%) rather than the actual tax amount.

Override applied to `field_metadata["tax_amount"]`:
```python
{
  "source": "suspicious_tax_amount",
  "confidence": 0.4,
  "evidence_text": "value (18) looks like a tax rate, not an amount; grand_total - subtotal_amount = 18000"
}
```

The `value` itself (`fields["tax_amount"]`) is preserved unchanged — only the metadata is overridden.

**Tests:** 2 tests in `test_structured_text_parser.py` — positive (rate case) and negative (plausible amount case).

---

## 10. Critical extraction values — unchanged verification

The following values from the Panimalar VENDOR_INVOICE were verified as unchanged by Step 8.2:

| Field | Value |
|---|---|
| `vendor_invoice_no` | `2526PSI25087738` |
| `vendor_gstin` | `33AAGCS1406H1ZR` |
| `po_reference` | `1PTR2526000467` |
| `invoice_total` | `554600` |
| `taxable_amount` | `470000` |
| `tax_amount` | `84600` |

Only `field_metadata` confidence/source changed for `vendor_name`, `bill_to_name`, `ship_to_name`. Verification logic in `document_normalizer.py` is unaffected.

---

## 11. Acceptance criteria check

| Criterion | Status |
|---|---|
| Digital PDF highlight works (bbox→overlay) | ✅ Implemented via `bboxToPercent` + `pdf-highlight-overlay` |
| Scanned OCR shows clear "highlight unavailable" message | ✅ `isScannedNoHighlight` → `pdf-highlight-unavailable` message |
| Review window makes critical data easy to understand | ✅ Needs Review / Critical / Supporting groups with badges |
| PaddleOCR runtime/model details logged | ✅ paddleocr_available, versions, init_args, device all recorded |
| Critical extraction values remain unchanged | ✅ Only field_metadata overridden, values unchanged |
| All tests pass | ✅ Backend: 702 passed, Frontend: 55 passed |

---

## 12. Files modified

### Backend
| File | Change |
|---|---|
| `app/services/extraction/ocr_providers/base.py` | Added `model_info`, `text_blocks` to `OcrProviderResult` |
| `app/services/extraction/ocr_providers/paddle_provider.py` | Added `paddle_runtime_info()`, `_extract_paddle_text_blocks()`, `PADDLE_INIT_ARGS` |
| `app/services/extraction_service.py` | Wire `model_info`/`text_blocks` into diagnostics from paddle route |
| `app/services/extraction/structured_text_parser.py` | Steps 8.1/8.2/8.3 fixes; `_customer_po_field_metadata_overrides` helper |

### Frontend
| File | Change |
|---|---|
| `src/components/extraction/ExtractedFieldsPanel.tsx` | Group A/B/C grouping, source badges, `onFieldClick` prop |
| `src/components/documents/PdfPreviewPane.tsx` | Highlight overlay, scanned unavailable message |
| `src/pages/ExtractionReviewPage.tsx` | `highlightedField` state, `handleFieldClick`, wire to both child components |
| `src/index.css` | `.field-group--warning`, `.source-badge`, `.pdf-highlight-overlay`, `.pdf-highlight-unavailable` |

### Tests added
| File | Tests |
|---|---|
| `tests/unit/test_paddle_ocr_provider.py` | 12 new tests (TestPaddleRuntimeInfo, TestExtractPaddleTextBlocks, TestRunFullPageDiagnostics) |
| `tests/unit/test_extraction_service.py` | 3 new tests (runtime diagnostics, text_blocks, no-crash) |
| `tests/unit/test_structured_text_parser.py` | 7 new tests (8.1/8.2/8.3 fixes) |
| `tests/unit/test_real_document_fix1.py` | 1 new test (vendor_po_date alias) |
| `src/components/extraction/extractedFieldsPanel.test.ts` | 14 new tests |
| `src/components/documents/pdfHighlight.test.ts` | 7 new tests |
