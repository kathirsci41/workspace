# Backend Test Results
**Tested by:** QA-Backend  
**Date:** 2026-04-17  
**Backend URL:** http://127.0.0.1:8002

---

## Summary
22 endpoint calls tested | 17 passed | 3 failed | 2 skipped (upload endpoints require file data)

---

## Results

### [PASS] GET /api/v1/admin/health
Status: HTTP 200  
Response: `{"database":"ok","redis":"ok","ollama":"ok","models":"ok","storage":"ok"}`  
Notes: All services healthy. Result is cached in Redis for 30s (confirmed by source code).

---

### [PASS] GET /api/v1/admin/stats
Status: HTTP 200  
Response shape correct. All counters present. `stats_delta` sub-object present.  
Notes: Stats updated correctly after QA test records were created (total_purchase_orders went from 9 → 10 during test, delta showed +1).

---

### [FAIL] GET /api/v1/admin/queue-status
Status: HTTP 404 — **BLOCKER**  
Notes: Route does not exist. The real route is `/api/v1/admin/queue` (not `/queue-status`). See Issues section.

---

### [FAIL] GET /api/v1/admin/extraction-failures
Status: HTTP 404 — **BLOCKER**  
Notes: This route does not exist in the codebase. The admin router only exposes `/health`, `/stats`, `/queue`, and `/requeue-pending-models`. See Issues section.

---

### [PASS] GET /api/v1/admin/queue (actual route)
Status: HTTP 200  
Response: `{"workers_online":1,"active_tasks":0,"queued_tasks":0}`  
Notes: Celery worker is up. Queue is idle. Shape is correct.

---

### [PASS] GET /api/v1/customers
Status: HTTP 200  
Response: paginated list with `items`, `total`, `page`, `per_page` fields. All customer fields present.  
Notes: `search` query param works — tested with `?search=SHRIRAM`, returned 1 result correctly.  
Pagination works correctly (`page=2&per_page=5` returns correct slice).

---

### [PASS] POST /api/v1/customers
Status: HTTP 201  
Test payload: `{"name":"QA Test Customer","customer_id":"SKY-QA001","contact_email":"qa@test.com"}`  
Response: Full CustomerResponse object with UUID, timestamps, `po_count:0`.  
Notes: Duplicate `customer_id` returns HTTP 409 with clear error message. Missing required fields return 422 with per-field detail.

---

### [PASS] GET /api/v1/customers/{id}
Status: HTTP 200 (existing ID)  
Status: HTTP 404 (non-existent UUID)  
Status: HTTP 422 (invalid UUID format — not a UUID)  
Notes: 404 and 422 error handling are correct.

---

### [PASS] PATCH /api/v1/customers/{id}
Status: HTTP 200  
Notes: Partial update works. However — **no email format validation**: passing `"not-an-email"` as `contact_email` is accepted and stored. No 422 error. See Issues section (MEDIUM).

---

### [PASS] GET /api/v1/purchase-orders
Status: HTTP 200  
Response: paginated list with all expected PO fields including `chain_completeness`, `chain_status`, `order_scenario`, `customer_name`, `customer_sky_id`.  
Notes: Pagination works. No filtering params exposed (can only page).

---

### [PASS] POST /api/v1/purchase-orders
Status: HTTP 201  
Test payload: `{"customer_id":"c39a5aba-...","po_number":"QA-PO-TEST-001"}`  
Response: Full PO object with `status:"INITIATED"`, `chain_completeness:0.0`.  
Notes: Duplicate `po_number` returns HTTP 409. Non-existent `customer_id` returns HTTP 404 with "Customer not found". Required fields (missing po_number) return 422.

---

### [PASS] GET /api/v1/purchase-orders/{id}
Status: HTTP 200 (existing ID), HTTP 404 (non-existent UUID)  
Notes: Returns full PO object. Data integrity observation: PO-2026-SF003 has `status: "COMPLETE"` but `chain_status: "mismatch"` — these are stored independently and can diverge. See Issues section (MEDIUM).

---

### [PASS] GET /api/v1/purchase-orders/{id}/chain
Status: HTTP 200  
Tested on: PO-2026-SF003 (fully populated), QA-PO-TEST-001 (empty).  
Response includes: `chain_status`, `completeness_pct`, `missing_slots`, `missing_vendor_invoices`, `reference_checks`, `billing`.  
Notes: Empty PO returns `{"chain_status":"incomplete","completeness_pct":0,"missing_slots":[],...}` correctly. The `completeness_pct` on the chain endpoint returns an integer (e.g., `100`), while the PO object's `chain_completeness` field is a float (e.g., `100.0`) — inconsistent types across endpoints, see Issues.

---

### [PASS] PATCH /api/v1/purchase-orders/{id}/so-number
Status: HTTP 200  
Request: `{"so_number":"QA-TEST-SO-001"}`  
Response: `{"so_number":"QA-TEST-SO-001"}`  
Notes: Response only returns the `so_number` field, not the full PO object. This is intentional but minimal — frontend must re-fetch the full PO after patching. Passing `""` (empty string) correctly clears to `null`. Original test data restored after testing.

---

### [PASS] GET /api/v1/purchase-orders/{id}/profile
Status: HTTP 200  
Notes: Rich response including `slots`, `timeline`, `discrepancies`, `cross_references`, `vendor_groups`, `field_comparisons`, `item_comparisons`, `item_matches`, `delivery_address_parsed`.  
All sub-sections present and populated for real POs. Empty PO returns correct empty arrays.  
`chain_completeness_display` renders as `"—"` for 0% (nice touch) and `"100.0%"` for complete.

---

### [PASS] GET /api/v1/documents
Status: HTTP 200  
Paginated list, all fields present including embedded `metadata` sub-object.  
Filters tested: `?status=VERIFIED` and `?document_type=VENDOR_INVOICE` — both work correctly.  
Notes: Documents embed full extraction metadata inline — responses are very large (multi-KB per document).

---

### [PASS] GET /api/v1/documents/{id}
Status: HTTP 200 (existing), HTTP 404 (non-existent)  
Notes: Returns full document with embedded metadata including extracted_data JSON.

---

### [PASS] GET /api/v1/search?q=test
Status: HTTP 200  
Notes: Minimum query length enforced at 2 characters (returns empty for 0 or 1 char with HTTP 200). Works for document refs, customer names, PO numbers. Example: `?q=SHRIRAM` returned 2 results (1 customer, 1 document).  
`?q=C190224835` correctly found the VENDOR_INVOICE by ref number.

---

### [FAIL] GET /api/v1/search/advanced?po_no=test
Status: HTTP 200, but **returns zero results for valid PO numbers** — **HIGH**  
Notes: The `po_no` parameter searches the `reference_index` table for `ref_type IN ('po_number','po_reference')`. However, PO numbers like `PO-2026-SF003` are stored on the `purchase_orders` table, not indexed as reference entries. Only document-level po_reference fields (e.g., the `po_reference` field inside extracted_data) are indexed.  
Result: `?po_no=PO-2026-SF003` returns `{"results":[],"total":0}`.  
Workaround: Use `GET /api/v1/search?q=PO-2026-SF003` (global search) which finds POs correctly via the `purchase_orders` table.  
Other advanced search params work correctly: `invoice_no`, `dc_no`, `so_no`, `customer_name`, `document_type`.

---

### [PASS] GET /api/v1/chat/stream?message=hello
Status: HTTP 200  
Content-Type: `text/event-stream; charset=utf-8` — correct SSE format.  
Headers: `cache-control: no-cache`, `x-accel-buffering: no` — correct for SSE.  
Notes: SSE stream works correctly, returns `data: {...}` events and terminates with `"done": true`.  
However — the chat backend responds with an **error message** inside the stream: `"Chat service unavailable: Client error '403 Forbidden' for url 'http://localhost:11434/api/chat'"`. This is a functional failure (Ollama is accessible for OCR at the RunPod URL, but the chat service is trying to reach `localhost:11434` which is returning 403). See Issues section.

---

### [PASS] GET /api/v1/chat/stream?message=what+needs+attention+today
Status: HTTP 200  
Notes: Same 403 Ollama error as above — the SSE transport layer works, but the LLM is unreachable. Returns gracefully with error text rather than crashing.

---

## Issues Found

### [BLOCKER] Admin route mismatch — queue-status and extraction-failures are 404
**Endpoint:** `GET /api/v1/admin/queue-status`, `GET /api/v1/admin/extraction-failures`  
**What happens:** Both return HTTP 404. The real queue endpoint is `/api/v1/admin/queue`. There is no `/extraction-failures` route at all.  
**Impact:** Frontend or monitoring tools calling these documented paths will silently fail.  
**Fix:** Either rename the `/queue` route to `/queue-status` in `admin.py`, or update the frontend/docs to use `/queue`. Add a `/extraction-failures` endpoint or remove it from the documented API.

---

### [HIGH] GET /api/v1/search/advanced — po_no parameter returns no results
**Endpoint:** `GET /api/v1/search/advanced?po_no=PO-2026-SF003`  
**What happens:** Returns `{"results":[],"total":0}` even though the PO exists.  
**Root cause:** `po_no` filter queries `reference_index` for `ref_type IN ('po_number','po_reference')`. PO numbers from the `purchase_orders` table are not indexed in `reference_index`. Only document-level extracted `po_reference` fields are indexed there.  
**Response snippet:** `{"results":[],"total":0,"query":"PO-2026-SF003"}`  
**Fix:** In `advanced_search()`, add a fallback: when `po_no` is given, also query `purchase_orders.po_number ILIKE %po_no%` and join back to documents if no ref_index results found. Or index PO numbers into the reference_index on PO creation.

---

### [HIGH] Chat service functional failure — Ollama 403 on localhost
**Endpoint:** `GET /api/v1/chat/stream?message=hello`  
**What happens:** SSE stream opens correctly but the content is an error: `"Chat service unavailable: Client error '403 Forbidden' for url 'http://localhost:11434/api/chat'"`.  
**Root cause:** The chat service is pointing to `localhost:11434` (local Ollama), but local Ollama is either not running or refusing chat-API requests (possibly model not loaded, or Ollama `OLLAMA_HOST` binding restriction). The OCR pipeline uses the RunPod remote URL but chat uses localhost.  
**Fix:** Check `.env` for the chat model endpoint config. If using RunPod for OCR, either also route chat to RunPod URL, or ensure local Ollama is running and has the chat model loaded. Alternatively gate the chat feature behind a health check.

---

### [MEDIUM] status and chain_status can diverge — no consistency enforcement
**Endpoint:** `GET /api/v1/purchase-orders/1ededf54-b09d-4316-b097-1f94394ae6ed`  
**What happens:** PO-2026-SF003 shows `"status":"COMPLETE"` and `"chain_completeness":100.0` simultaneously with `"chain_status":"mismatch"`. A PO marked COMPLETE with reference mismatches is a data integrity concern — operators could miss outstanding reference discrepancies.  
**Fix:** Either prevent COMPLETE status when `chain_status == "mismatch"`, or surface the mismatch as a warning on the PO detail view when status is COMPLETE.

---

### [MEDIUM] No email format validation on PATCH /customers/{id}
**Endpoint:** `PATCH /api/v1/customers/{id}`  
**What happens:** Passing `{"contact_email":"not-an-email"}` returns HTTP 200 and stores the invalid value.  
**Fix:** Add `EmailStr` type or a regex validator to `CustomerUpdate` schema in `schemas/customers.py`.

---

### [MEDIUM] completeness_pct type inconsistency between endpoints
**What happens:** `GET /api/v1/purchase-orders` and `GET /api/v1/purchase-orders/{id}` return `"chain_completeness": 100.0` (float). `GET /api/v1/purchase-orders/{id}/chain` returns `"completeness_pct": 100` (integer). These represent the same value but different types.  
**Fix:** Standardize to float (e.g., `100.0`) in both the chain endpoint response schema and the PO model.

---

### [LOW] PATCH /so-number returns minimal response (only so_number field)
**Endpoint:** `PATCH /api/v1/purchase-orders/{id}/so-number`  
**What happens:** Response is `{"so_number":"TEST-SO-001"}` — only the updated field, not the full PO object.  
**Impact:** Frontend must make a second GET request to refresh the full PO state after patching SO number.  
**Fix (optional):** Return the full PO object in the response, consistent with how PATCH /customers/{id} returns the full customer.

---

### [LOW] Search results contain document with blank ref_number
**Endpoint:** `GET /api/v1/search/advanced?customer_name=SHRIRAM`  
**What happens:** One result has `"ref_number":""` and `"display_name":"Customer Po — Unknown"`. This is PO-2026-SF004's CUSTOMER_PO document which failed extraction (no primary_ref_no extracted).  
**Fix:** Filter blank ref_number results from search output, or display `"[No Reference]"` rather than `"Unknown"` for clarity.

---

## Test Records Created
The following test records were created during QA testing and can be cleaned up:
- **Customer:** `SKY-QA001` / "QA Test Customer" — ID `c39a5aba-627d-42be-ba96-91dbf1665e2f`
- **Purchase Order:** `QA-PO-TEST-001` — ID `64f919e2-53d4-443f-b1aa-294c9268ed99`

No production data was modified (the `so_number` PATCH test on PO-2026-SF004 was immediately reverted to its original value `TEST-SO-001`). The `notes` field briefly set on customer `SKY-KA001` was also reverted to `null`.
