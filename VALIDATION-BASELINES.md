# Validation Baselines

Records accepted validation runs per OCR provider. Update this file when new baselines are established.

---

## GLM-OCR Baselines (`OCR_PROVIDER=glm_ocr`, default)

| Fixture | Run | Score | Failed docs | XLSX |
|---|---|---|---|---|
| Panimalar | `validation-runs/real-doc-001-tradefix-final8` | 24/24 | 0 | PASS |
| Trade | `validation-runs/real-doc-002-trade-fix7` | — (no expected.json) | 0 | PASS |
| AMC | `validation-runs/real-doc-003-amc-fix1` | 27/27 | 0 | PASS |

---

## PaddleOCR-GPU Baselines (`OCR_PROVIDER=paddleocr_gpu`)

Required env vars:
```powershell
$env:OCR_PROVIDER = "paddleocr_gpu"
$env:OCR_PADDLE_DOCUMENT_TYPES = "VENDOR_INVOICE,CUSTOMER_PO"
```

| Fixture | Run | Score | Failed docs | XLSX | Date |
|---|---|---|---|---|---|
| Panimalar | `validation-runs/paddle-panimalar-001` | 24/24 | 0 | PASS | 2026-06-23 |
| Trade | `validation-runs/paddle-trade-001` | — (no expected.json) | 0 | PASS | 2026-06-23 |
| AMC | `validation-runs/paddle-amc-001` | 27/27 | 0 | PASS | 2026-06-23 |

All fixtures match or exceed GLM baseline. AMC `export_fail` improved 1 → 0.

---

## Sprint 2 Completion Record — 2026-06-23

Tagged: `sprint2-complete`

### Delivered

- PP-OCRv4 → PP-OCRv5 upgrade
- PP-StructureV3 table extraction service (`table_extraction_service.py`)
- PaddleOCR-VL-1.6 HuggingFace fallback (`paddleocr_vl_service.py`)
- `OCR_PROVIDER` / `OCR_PADDLE_DOCUMENT_TYPES` config wiring

### Post-sprint stabilisation fixes

| File | Fix |
|---|---|
| `structured_text_parser.py` | `_DATE_PATTERN` second alternative restricted to real month names only (fixed PP-OCRv5 23→24 regression on Panimalar scanned PO) |
| `structured_text_parser.py` | `customer_po_date`: `_label_value` runs before `_date_near_value` (prevents false date match from product codes in proximity window) |
| `order_bundle_verifier.py` | `_refs_match` G5: vacuous MATCH guard — `len(left_norm) < 3` rejects short placeholders like "N/A" |
| `order_bundle_verifier.py` | G9 multi-DC: check_ids suffixed `_1`, `_2` when >1 DC to eliminate frontend duplicate key confusion (two loop fixes) |
| `tests/unit/test_order_bundle_verifier.py` | Assertions updated for new suffixed check_ids (`INVOICE_DC_SO_MATCH_2`, `CUSTOMER_PO_DC_ORDER_MATCH_2`) |

### Deferred (not worth doing now)

- `table_extraction_service.py` wiring into `_apply_bbox_layer`: needs PDF→image render step + scanned line-item fixture. No scanned invoice fixture with known line items exists yet.
- Celery caller replacement: Redis not running locally. Requires status polling endpoint + frontend changes — multi-sprint scope.
