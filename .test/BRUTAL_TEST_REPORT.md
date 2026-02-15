# BRUTAL END-TO-END TEST REPORT
**Date:** 2026-02-15  
**Tester:** Automated (GitHub Copilot via API + Browser MCP)  
**Verdict:** PASS — but with caveats

---

## PART 1: API TEST SUITE (45 tests)

### Result: 45/45 PASS | 0 FAIL | 0 WARN

| Section | Tests | Result |
|---------|-------|--------|
| Health & Connectivity | T01–T06 | 6/6 ✅ |
| Customer CRUD | T07–T13 | 7/7 ✅ |
| Purchase Order CRUD | T14–T19 | 6/6 ✅ |
| Document Upload | T20–T25 | 6/6 ✅ |
| Extraction Pipeline | T26–T29 | 4/4 ✅ |
| Verify/Reject/Re-extract | T30–T34 | 5/5 ✅ |
| Search | T35–T37 | 3/3 ✅ |
| Edge Cases | T38–T42 | 5/5 ✅ |
| Data Integrity | T43–T45 | 3/3 ✅ |

### Key Extraction Metrics
- **Extraction time:** 45 seconds (first), 40 seconds (re-extract)
- **Confidence:** 90%
- **Fields filled:** 11 out of 12 (Payment Terms was blank — correct, not on the doc)
- **Critical fields (PO number, customer name, total amount):** All present

### What Actually Works
1. Full CRUD lifecycle for customers and POs — create, read, update, list, search
2. Document upload stores PDF on disk and triggers Celery extraction
3. Celery→Ollama OCR pipeline completes without crashing
4. Metadata extraction returns structured JSON with confidence scores
5. Verify with edits saves modified data and sets status to VERIFIED
6. Re-extract correctly re-queues to Celery and overwrites previous extraction
7. Reject endpoint correctly marks metadata as REJECTED
8. Chain completeness auto-calculates (0% → 16.7% → 33.3% as docs are added)
9. Search finds results by PO number, customer name, and reference number
10. Edge cases handled: invalid UUIDs → 422, page=0 → 422, 10KB name → blocked, duplicate slot upload → 409

---

## PART 2: BROWSER UI TEST (Manual via MCP)

### Result: ALL 8 FLOWS PASS ✅

| Flow | Status | Notes |
|------|--------|-------|
| Dashboard loads | ✅ | Shows stats: 5 customers, 1 PO, pending/verified counts |
| Customers list page | ✅ | All 5 customers render with ID, name, GST, email, date |
| Add Customer modal | ✅ | Form opens, validates, submits, customer appears in list |
| PO list page | ✅ | Both filter dropdowns (customer, status) populated correctly |
| Create PO modal | ✅ | Customer dropdown, PO number, date picker, amount field all work |
| PO detail / chain view | ✅ | 6-slot chain renders with confidence %, status, Preview/Review/Re-extract buttons |
| Review modal | ✅ | PDF preview with zoom/rotate, all extracted fields editable, Verify/Reject buttons |
| Search | ✅ | Both header search bar and dedicated search page work, results link back to entities |

---

## PART 3: THE HONEST CAVEATS (No Sugarcoating)

### Things That Are Genuinely Solid
- The extraction pipeline is stable. Ran it twice (extract + re-extract) with no crashes.
- 90% confidence on a real 2-page PO is respectable for a 1.1B param model.
- The 6-doc chain concept is well-implemented and works end-to-end.
- Error handling is good — invalid inputs get 422, missing resources get 404.

### Things That Are Meh
1. **Extraction speed:** 40-45 seconds per document. For batch processing of 100+ POs, this is painfully slow. The 5-second inter-page delay (`time.sleep(5)`) is a crude hack to prevent Ollama GPU memory pressure.
2. **V.DC and POD confidence = 0%.** These are 222-byte placeholder PDFs, so this is correct behavior — but it means the app doesn't validate whether a document is actually a real scan vs a placeholder.
3. **No authentication.** Anyone with network access can CRUD everything. Fine for internal tooling, not fine if exposed.
4. **Customer ID pattern** `^[A-Z]{2,5}-[A-Z0-9]+$` is strict. Real-world IDs like "TEST-BRUTAL-001" would fail. The pattern should be documented in the UI (placeholder says "SKY-XXXXX" which helps, but doesn't explain the regex).
5. **No file type validation beyond extension.** A .txt file renamed to .pdf would be accepted.

### Things That Could Break Under Pressure
1. **Concurrent extractions.** The Celery solo pool processes one task at a time. Uploading 10 documents simultaneously = 10×45s = 7.5 minutes queue time. Need `--pool=prefork` or multiple workers.
2. **Large PDFs.** The 768px resize cap prevents crashes but degrades OCR quality on detailed documents. A 50-page PDF would take ~4 minutes with inter-page delays.
3. **No retry logic.** If Ollama returns a 500 mid-extraction, the document is marked EXTRACTION_FAILED with no automatic retry.
4. **Database connection pooling.** AsyncSession with default pool size could exhaust connections under high load.

### Known Data Issues
- "ABC Corpuration" is a typo (should be "Corporation") — exists in the actual data
- The chain shows "!" symbols next to slots that have documents with issues — the icon choice is confusing (looks like a warning, means "has document")

---

## FILES GENERATED
- `api_test_report.md` — Detailed per-test results table
- `api_test_results.json` — Machine-readable test data
- `ui_review_modal.png` — Screenshot of the Review Modal with PDF preview
- `brutal_api_test.py` — The 45-test script (reusable)
- `BRUTAL_TEST_REPORT.md` — This file

---

## BOTTOM LINE

The platform works. The full flow — Customer → PO → Upload → Extract → Review → Verify/Reject — is functional end-to-end via both API and UI. The extraction pipeline produces usable 90% confidence results. Chain tracking, search, and CRUD operations are solid.

The main risks are performance at scale (serial Celery, 45s per doc) and the lack of auth. For a v3.0 prototype/internal tool, it's production-viable. For a customer-facing SaaS, it needs work on concurrency, auth, and file validation.

**Score: 8/10** — Functional and reliable, limited by throughput and missing auth.
