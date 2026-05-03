# DPP 2.2.0 — Fix Task Sheet

Created: 2026-03-16 | Last updated: 2026-03-16 17:00

---

## Legend

| Symbol | Meaning |
| ------ | ------- |
| ✅ | Done |
| 🔄 | In progress |
| ⬜ | Pending |

---

## Previously Completed (B1–B6 + Infrastructure)

| ID | File | What was fixed | Date |
| -- | ---- | -------------- | ---- |
| ✅ B1 | `admin.py` | `func.count(X).select()` → `select(func.count(X))` (x8) | 2026-03-11 |
| ✅ B2 | `tasks.py` | `db.query(Model).get(id)` → `db.get(Model, id)` | 2026-03-11 |
| ✅ B3 | `tasks.py` + `extraction.py` | String status literals → `POStatus` enum | 2026-03-11 |
| ✅ B4 | `ReviewModal.tsx` | Later button calls `onVerified()` not `onClose()` | 2026-03-11 |
| ✅ B5 | `extraction.py` | `save_corrections` — no incorrect `MetadataStatus.VERIFIED` | 2026-03-11 |
| ✅ B6 | `DashboardPage.tsx` | Stats fetch has `.catch(() => {})` | 2026-03-11 |
| ✅ ME | `extraction.py` | `create_manual_entry` sets `last_error=None`, `model_version="manual"` | 2026-03-16 |
| ✅ INF-1 | `two_layer_client.py` | Fast-fail on HTTP 4xx — no 60s wait | 2026-03-16 |
| ✅ INF-2 | `two_layer_client.py` | "Extraction service unreachable / offline" error messages | 2026-03-16 |
| ✅ INF-3 | `extractionErrors.ts` | `friendlyExtractionError()` maps raw errors to operator text | 2026-03-16 |
| ✅ INF-4 | `DocumentCard.tsx` | Uses `friendlyExtractionError` for EXTRACTION_FAILED display | 2026-03-16 |
| ✅ INF-5 | `start.ps1` | Kills leftover Celery workers before starting | 2026-03-16 |
| ✅ INF-6 | `start.ps1` | Ollama section trimmed 60 → 10 lines | 2026-03-16 |

---

## Active Fix Plan

### T1 — tasks.py: Clean up digital path error message

| Field | Detail |
| ----- | ------ |
| File | `backend/app/services/extraction/tasks.py` line 334 |
| Problem | Message contained internal dev terms: `debug_markdown/`, `OCR_EXTRACTOR_NUM_CTX` — shown on document card |
| Fix | Replaced with: `"Extraction produced no data for this document. Try re-extracting or use Manual Entry."` |
| Status | ✅ Done |
| Completed | 2026-03-16 17:00 |

---

### T2 — two_layer_client.py: Rename "GLM-OCR" in retry error

| Field | Detail |
| ----- | ------ |
| File | `backend/app/services/extraction/two_layer_client.py` line 447 |
| Problem | `"GLM-OCR failed after X retries"` — internal model name leaked into `last_error` shown on card |
| Fix | Replaced with: `"Extraction failed after {retries} retries: {last_error}"` |
| Status | ✅ Done |
| Completed | 2026-03-16 17:01 |

---

### T3 — extractionErrors.ts: Add missing mappings

| Field | Detail |
| ----- | ------ |
| File | `frontend/src/utils/extractionErrors.ts` |
| Problem | `friendlyExtractionError()` had no mapping for `"produced no fields"` or `"produced no data"` — fell through to raw display |
| Fix | Added `msg.includes('produced no fields')` and `msg.includes('produced no data')` to the no-data branch |
| Status | ✅ Done |
| Completed | 2026-03-16 17:02 |

---

### T4 — Backend unit test suite

| Field | Detail |
| ----- | ------ |
| Location | `tests/backend/` |
| Framework | pytest + pytest-asyncio + unittest.mock |
| Covers | `field_validator.py` (84 tests), `invoice_validator.py` (21 tests), `hybrid_router.py` (16 tests), `two_layer_client.py` (8 tests), `tasks.py` error strings (4 tests), `response_parser.py` (26 tests), `so_validator.py` (26 tests), `chain_completeness` (18 tests), `pdf_validation` (11 tests), `ocr_cleaning` (14 tests) |
| Result | 221 / 221 passed in 1.30s |
| Status | ✅ Done |
| Completed | 2026-03-16 17:15 |

---

### T5 — Frontend unit test suite

| Field | Detail |
| ----- | ------ |
| Location | `tests/frontend/` |
| Framework | vitest 4.1.0 |
| Covers | `extractionErrors.ts` — all mapping cases (25 tests), `types/index.ts` — CHAIN_ORDER, DOC_TYPE_LABELS, DOC_TYPE_SHORT constants (17 tests) |
| Result | 42 / 42 passed in 786ms |
| Status | ✅ Done |
| Completed | 2026-03-16 17:47 |

---

### T6 — Unit test documentation

| Field | Detail |
| ----- | ------ |
| Location | `tests/README.md` |
| Content | How to install, how to run, what each test covers, scenarios |
| Status | ✅ Done |
| Completed | 2026-03-16 18:10 |

---

## Execution Order

```text
T1 (tasks.py message)        ✅ 2026-03-16 17:00
T2 (two_layer_client rename) ✅ 2026-03-16 17:01
T3 (frontend mapping)        ✅ 2026-03-16 17:02
T4 (backend tests)           ✅ 2026-03-16 17:15  — 221/221 passed
T5 (frontend tests)          ✅ 2026-03-16 17:47  — 42/42 passed
T6 (test docs)               ✅ 2026-03-16 18:10
```
