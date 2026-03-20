# DPP 2.2.0 — Unit Test Suite

**274 tests total** — 232 backend (pytest) + 42 frontend (vitest)
All tests run in under 4 seconds combined. No database, no network, no running server required.

---

## Quick Start

### Backend (Python / pytest)

```bash
# From project root
cd backend
source venv/Scripts/activate        # Windows
# source venv/bin/activate           # Linux/Mac

cd ..
python -m pytest tests/backend/ -v
```

### Frontend (TypeScript / vitest)

```bash
cd frontend
npx vitest run
```

### Run a single file

```bash
# Backend — one file
python -m pytest tests/backend/test_field_validator.py -v

# Frontend — one file
npx vitest run ../tests/frontend/test_types_constants.test.ts
```

### Run a single test by name

```bash
# Backend — match by keyword
python -m pytest tests/backend/ -v -k "test_11tr_fixed"

# Frontend — match by name
npx vitest run --reporter=verbose -t "CHAIN_ORDER"
```

---

## Test File Index

### Backend (`tests/backend/`)

| File | Source file | Tests | What it guards |
| ---- | ----------- | ----- | -------------- |
| `test_field_validator.py` | `services/extraction/field_validator.py` | 84 | All OCR fix functions + validate_extracted_fields entrypoint |
| `test_invoice_validator.py` | `services/extraction/invoice_validator.py` | 21 | Invoice math, date validation, amount sanity |
| `test_hybrid_router.py` | `services/extraction/hybrid_router.py` | 16 | PDF vs image routing decisions |
| `test_extraction_error_messages.py` | `services/extraction/two_layer_client.py` + `tasks.py` | 8 | Error message strings, fast-fail on 4xx, no-retry guard alignment |
| `test_response_parser.py` | `services/extraction/response_parser.py` | 26 | JSON parsing strategies, multi-page merge, confidence calculation |
| `test_so_validator.py` | `services/extraction/so_validator.py` | 26 | SO number matching, normalization, skip rules |
| `test_chain_completeness.py` | `api/v1/extraction.py` (`_update_chain_async`) | 18 | PO completeness % formula, POStatus mapping |
| `test_pdf_validation.py` | `api/v1/purchase_orders.py` (upload endpoint) | 11 | PDF type, magic bytes, size limit validation |
| `test_ocr_cleaning.py` | `services/extraction/two_layer_client.py` (`_clean_ocr_output`) | 14 | OCR artifact corrections in raw text |

### Frontend (`tests/frontend/`)

| File | Source file | Tests | What it guards |
| ---- | ----------- | ----- | -------------- |
| `test_extraction_error_messages.test.ts` | `utils/extractionErrors.ts` | 14 | Error message mapping — service unavailable, no data, pass-through |
| `test_friendly_extraction_error.test.ts` | `utils/extractionErrors.ts` | 11 | Same function, additional edge cases and legacy message formats |
| `test_types_constants.test.ts` | `types/index.ts` | 17 | CHAIN_ORDER sequence, DOC_TYPE_LABELS, DOC_TYPE_SHORT completeness |

---

## What Each File Covers

### `test_field_validator.py`
Tests every OCR correction function individually, then the `validate_extracted_fields` entrypoint that applies them all.

Key scenarios:
- `fix_invoice_number` — 8 cases: `11TR→1ITR`, `11SR→1ISR`, `IT1R→1ITR`, lowercase-L, label-colon stripping
- `fix_dc_number` — `lDNT→1DNT`, `10TN/10NT/10N7→1DNT` transpositions
- `fix_so_number` — `10TM→1OTM`, spurious `Z` removal
- `fix_po_reference` — date string rejection, person name rejection, label stripping, FY notation restore
- `fix_purchase_bill_no` / `fix_company_po_number` — prefix confusion fixes
- `normalize_amount` — currency symbols, Indian comma format, non-numeric rejection
- `validate_extracted_fields` — verifies that corrections are applied per doc_type and `_validation` key is attached only when something changed

---

### `test_invoice_validator.py`
Tests `ValidationResult` state machine and all three validation passes.

Key scenarios:
- Math check skipped entirely for non-invoice doc types
- Correct math passes, wrong math fails with "mismatch" message
- Future date → error; very old date → warning; unparseable date → warning
- Negative amount → error; >10 crore → warning; <1 → warning; non-numeric → warning

---

### `test_hybrid_router.py`
Tests routing decisions without opening a real PDF — uses `tmp_path` fixtures and mocks `is_digital_pdf`.

Key scenarios:
- All image extensions (`.png`, `.tiff`, `.jpg`, etc.) → always `SCANNED`
- Unknown extensions → `SCANNED` (safe default)
- PDF with text layer → `DIGITAL`; PDF without → `SCANNED`
- Uppercase extensions handled correctly

---

### `test_extraction_error_messages.py`
Two concerns in one file:

**String alignment** — verifies the no-retry guard keyword in `tasks.py` exactly matches the RuntimeError message. If someone edits one without the other, the Celery task will retry unnecessarily on permanent failures.

**TwoLayerClient network errors** — mocks `httpx.AsyncClient` to return a 404 or raise `ConnectError`, then verifies:
- 404 → raises with `"unreachable"` in message (fast-fail, no 60s wait)
- DNS failure → raises with `"offline"` in message
- `wait_until_ready` returns `False` on 404 (doesn't raise), `True` on 200

---

### `test_response_parser.py`
Tests the 4 JSON extraction strategies and multi-page merge.

Key scenarios:
- Strategy 1: direct JSON string
- Strategy 2: JSON inside markdown code block
- Strategy 3: JSON embedded in prose text
- Strategy 4: trailing comma cleaned before parse
- Multi-page merge: first non-null value wins per field
- Confidence calculation: null/empty/LOW_CONFIDENCE/AMOUNT_PARSE_FAILED scoring

---

### `test_so_validator.py`
Tests the SO number cross-document validation business rules.

Key scenarios:
- CUSTOMER_PO, COMPANY_PO, VENDOR_DC, VENDOR_INVOICE → always pass (not validated)
- COMPANY_DC / COMPANY_INVOICE with no PO SO set → blocked
- Exact match, case-insensitive, whitespace/dash/slash normalized → passes
- Mismatch → error with both SO numbers in the message
- `so_number` field takes priority over `sales_order_no` fallback

---

### `test_chain_completeness.py`
Tests the pure math formula that drives PO status.

Key scenarios:
- 0 docs → `INITIATED`; 1–2 → `IN_PROGRESS`; 3–5 → `NEAR_COMPLETE`; 6 → `COMPLETE`
- `EXTRACTION_FAILED` and `REJECTED` docs excluded from count
- Duplicate uploads of same doc type count as 1 (distinct types only)

---

### `test_pdf_validation.py`
Tests the upload validation logic as a pure function (no FastAPI request needed).

Key scenarios:
- Valid PDF passes all checks
- Wrong extension, wrong MIME type, wrong magic bytes → rejected
- File named `.pdf` but containing JPEG bytes → rejected
- Exactly 25MB passes; one byte over → rejected

---

### `test_ocr_cleaning.py`
Tests `_clean_ocr_output` which post-processes raw OCR text before extraction.

Key scenarios:
- HTML entity unescaping (`&amp;` → `&`)
- Empty table row removal (3+ repeated empty rows removed, fewer kept)
- Date format fixing
- I/1, O/0, D/N/T confusion corrections
- Excessive blank line reduction

---

### `test_extraction_error_messages.test.ts` + `test_friendly_extraction_error.test.ts`
Both test `friendlyExtractionError` from `utils/extractionErrors.ts`.

Key scenarios:
- `null` / `undefined` / `""` → default message
- `"unreachable"`, `"offline"`, `"getaddrinfo"`, `"connect"` → service unavailable message
- `"no data"`, `"no extractable"`, `"returned empty"`, `"produced no fields"` → no-data message
- Unknown string → returned unchanged (pass-through)

---

### `test_types_constants.test.ts`
Tests the three constants exported from `types/index.ts`.

Key scenarios:
- `CHAIN_ORDER` has exactly 6 entries, no duplicates, correct order
- `DOC_TYPE_LABELS` has one entry per doc type, no extras, all non-empty strings
- `DOC_TYPE_SHORT` has one entry per doc type, all 2–5 chars, no duplicates

---

## Adding a New Test

### Backend

1. Create `tests/backend/test_<module_name>.py`
2. Add the path fix at the top:
   ```python
   import sys, os
   sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))
   ```
3. Import the function you want to test
4. Write a class per function, one method per scenario:
   ```python
   class TestMyFunction:
       def test_normal_input(self):
           assert my_function("input") == "expected"

       def test_none_returns_none(self):
           assert my_function(None) is None
   ```

### Frontend

1. Create `tests/frontend/test_<module>.test.ts`
2. Import from the source using the relative path:
   ```typescript
   import { myFunction } from '../../frontend/src/utils/myModule';
   ```
3. Write describe/it blocks:
   ```typescript
   describe('myFunction', () => {
     it('does the right thing', () => {
       expect(myFunction('input')).toBe('expected');
     });
   });
   ```

---

## What Is NOT Covered (and Why)

| Area | Why not covered here |
| ---- | ------------------- |
| API endpoints (`admin.py`, `extraction.py`, etc.) | Require a live PostgreSQL database — integration tests, not unit tests |
| Celery task flow (`tasks.py` full run) | Requires Celery worker + Redis + DB — end-to-end test |
| React components (`DocumentCard`, `ReviewModal`, etc.) | Require a browser/jsdom environment + `@testing-library/react` setup |
| `two_layer_client.py` full extraction run | Requires Ollama running — tested via mocks for the error paths only |
| Database models | SQLAlchemy ORM models have no logic to test — validation is in the API layer |

These areas are best covered by integration tests or manual testing against a running stack.

---

## Test Results Summary

| Suite | Files | Tests | Time |
| ----- | ----- | ----- | ---- |
| Backend (pytest) | 9 | 221 | 1.30s |
| Frontend (vitest) | 3 | 42 | 0.79s |
| **Total** | **12** | **263** | **~2s** |

Last run: 2026-03-16 — all 263 passed.
