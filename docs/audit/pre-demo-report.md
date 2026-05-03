# DPP 2.2.0 — Pre-Demo Audit Report
**Date:** 2026-04-17
**Tested by:** QA-Backend + QA-Frontend
**Purpose:** Verify readiness for client screen recording (Skylark Information Technologies)

---

## Executive Summary

The platform is mostly demo-ready. All 9 frontend pages load without crashes. Core workflows (PO creation, document upload, review, profile analysis, chain validation UI) are functional. However there are **2 BLOCKERs**, **3 HIGH** issues, and **5 MEDIUM** issues. The two blockers are admin route 404s (low demo risk if admin page is not scripted) and the chat feature returning a 403 error (high demo risk if chat is in the recording). The most visually damaging issue for a client recording is the Document Chain panel showing "Not yet uploaded" for every slot even when documents are verified — this is HIGH and will look broken on screen.

Total issues: 2 BLOCKER, 3 HIGH, 5 MEDIUM, 3 LOW.

---

## Issue List

### BLOCKERS (must fix before recording)

#### B-1: Admin route 404s — `/queue-status` and `/extraction-failures` do not exist
**Where:** `GET /api/v1/admin/queue-status`, `GET /api/v1/admin/extraction-failures`
**What happens:** Both routes return HTTP 404. The real queue endpoint is `/api/v1/admin/queue`. There is no `/extraction-failures` route at all. Any frontend panel or monitoring script calling these documented paths silently fails.
**Fix:** In `backend/app/api/admin.py`, either rename `/queue` to `/queue-status` to match what is documented, or update all frontend callers to use `/queue`. For `/extraction-failures`, either implement the endpoint (query documents with `status=FAILED`) or remove it from documentation and any frontend reference.

#### B-2: Chat assistant completely non-functional — Ollama 403 on localhost
**Where:** `GET /api/v1/chat/stream` / Chat page `/chat`
**What happens:** Every chat message returns `"Chat service unavailable: Client error '403 Forbidden' for url 'http://localhost:11434/api/chat'"`. The SSE transport works; the LLM backend does not. The error is displayed inline in the chat bubble rather than crashing the page, but the feature is entirely unusable.
**Confirmed by:** QA-Backend AND QA-Frontend (duplicate finding, merged).
**Fix:** Check `.env` for the chat model endpoint. The OCR pipeline uses the RunPod remote URL (`OLLAMA_BASE_URL`), but chat is pointing to `localhost:11434` which is not running or is rejecting requests. Either: (a) start local Ollama with `qwen2.5:3b` loaded, or (b) update the chat service config to use the same RunPod endpoint as OCR, or (c) gate the chat feature with a startup health check that disables the UI chip if the endpoint is unreachable.

---

### HIGH (visible quality issues the client will see)

#### H-1: Document Chain panel shows "Not yet uploaded" for all slots — even verified documents
**Where:** PO Detail page `/purchase-orders/{id}` — dark Document Chain panel
**What happens:** Every document slot (Customer PO, Company PO, Vendor Invoice, Company DC, Company Invoice) shows "Not yet uploaded" in a dashed box, regardless of actual upload status. Status badges (Verified/Mismatch/Waiting) are correct, but the reference number box is empty. For SAMPLE-TEST-001 with 5 uploaded/verified documents, the entire chain appears as unloaded.
**Root cause:** `buildSlots()` in `PODetailPage.tsx` (lines 25–55) never sets the `ref` field on the `TimelineSlot` object. `ChainTimeline.tsx` (line 50) shows `slot.ref` if truthy, otherwise falls back to "Not yet uploaded". The `ref` field is never populated from API data.
**Fix:** In `buildSlots()`, extract the reference number from `chainByType[type][0]` (the `dc_number`, `invoice_number`, or `po_number` field as appropriate per type) and pass it as `slot.ref`.

#### H-2: Advanced search `po_no` parameter returns zero results for valid PO numbers
**Where:** `GET /api/v1/search/advanced?po_no=PO-2026-SF003`
**What happens:** Returns `{"results":[],"total":0}` even though the PO exists. The `po_no` filter queries `reference_index` for `ref_type IN ('po_number','po_reference')`, but PO numbers on the `purchase_orders` table are not indexed there. Only document-level extracted `po_reference` fields are indexed.
**Workaround (for demo):** Use `GET /api/v1/search?q=PO-2026-SF003` (global search) which finds POs correctly.
**Fix:** In `advanced_search()`, add a fallback: when `po_no` is provided and `reference_index` returns no results, also query `purchase_orders.po_number ILIKE %po_no%` and join back to documents. Alternatively, index PO numbers into `reference_index` on PO creation.

#### H-3: Header search autocomplete dropdown blocks page interaction on Search page
**Where:** Search page `/search`
**What happens:** Typing in the search page's main input causes the global header search bar to also receive focus and open its autocomplete dropdown. The dropdown overlays the page with a high `z-index`, intercepting all click events. The dropdown cannot be dismissed by clicking elsewhere or pressing Escape. The user must navigate away and back to reset the page.
**Fix:** Isolate the page-level search input from the header global search (they should not share the same focus/event handler). Add an outside-click handler to the header autocomplete dropdown so it closes when focus moves away.

---

### MEDIUM (minor issues, won't block demo)

#### M-1: PO Profile Scenario shows "Unknown" for populated POs
**Where:** PO Profile `/purchase-orders/{id}/profile` — Scenario field
**What happens:** SAMPLE-TEST-001 (5 documents uploaded) shows "Unknown" for scenario instead of PROCUREMENT/STOCK/DROP_SHIP/SERVICE_AMC. The `derive_scenario()` function exists in `po_service.py` but the field is apparently not set in the DB for this PO. None of the scenario selector buttons shows as selected.
**Note:** Likely a data issue (PO created before `derive_scenario` was wired) rather than a code bug. Can be demoed by manually clicking a scenario button to set it, but the auto-detection is not firing.

#### M-2: Search page has no visible submit button — Enter-only submission
**Where:** Search page `/search`
**What happens:** No submit button is present. Users must press Enter to trigger a search. The search icon inside the input is decorative only. Non-obvious to new users watching a demo.
**Fix:** Make the search icon clickable (button type), or add an explicit "Search" button next to the input.

#### M-3: PO `status` and `chain_status` can diverge with no warning
**Where:** `GET /api/v1/purchase-orders/{id}` (e.g., PO-2026-SF003)
**What happens:** PO-2026-SF003 shows `"status":"COMPLETE"` and `"chain_completeness":100.0` simultaneously with `"chain_status":"mismatch"`. A PO marked COMPLETE with reference mismatches is a data integrity concern — operators could miss outstanding discrepancies.
**Fix:** Either prevent COMPLETE status when `chain_status == "mismatch"`, or surface the mismatch as a visible warning on the PO detail header when the PO is COMPLETE.

#### M-4: No email format validation on `PATCH /customers/{id}`
**Where:** `PATCH /api/v1/customers/{id}`
**What happens:** Passing `{"contact_email":"not-an-email"}` returns HTTP 200 and stores the invalid value. No 422 validation error.
**Fix:** Add `EmailStr` type (Pydantic v2) or a regex validator to the `CustomerUpdate` schema in `backend/app/schemas/customers.py`.

#### M-5: `completeness_pct` type inconsistency between endpoints
**Where:** `GET /purchase-orders/{id}` returns `"chain_completeness": 100.0` (float); `GET /purchase-orders/{id}/chain` returns `"completeness_pct": 100` (integer).
**What happens:** Same value, different types. Can cause unexpected frontend type-checks or display differences.
**Fix:** Standardize both to `float` (e.g., `100.0`) in the chain endpoint response schema.

---

### LOW (code quality / dev-only, not visible to client)

- **L-1: React Router v6 future-flag warnings** — Two console warnings on every page load about `v7_relativeSplatPath` and `v7_startTransition`. Fix: add `future={{ v7_relativeSplatPath: true, v7_startTransition: true }}` to the Router component in `main.tsx` or `App.tsx`.
- **L-2: `PATCH /so-number` returns minimal response** — Returns only `{"so_number":"..."}` instead of the full PO object; frontend must make a second GET to refresh state. Low priority but inconsistent with other PATCH endpoints.
- **L-3: Search results include blank `ref_number` entries** — Advanced search returns a result with `"ref_number":""` and `"display_name":"Customer Po — Unknown"` for a document that failed extraction. Consider filtering blank ref_number results or rendering `"[No Reference]"` instead of `"Unknown"`.

---

## What's Working Well

- Dashboard loads fully with real data — stat cards, pending review queue, recent POs table, quick action buttons all render correctly.
- Customers list, search filter, and create/update flows work correctly (including 409 on duplicate, 404 on missing FK).
- Purchase Orders list with all filter controls (search, customer combobox, status, date range, completeness chips) renders correctly.
- PO Detail chain timeline slot states with confidence percentages and hover tooltips render correctly. SO number inline edit is functional.
- PO Profile page renders all sections: Cross-Reference Check, Cross-Document Field Comparison, Item-Level Verification, Vendor Breakdown, Order Timeline.
- Document list with type badges, status filter, and Review modal (manual entry + PDF side-by-side) is fully functional.
- Admin console shows all 5 health panels green, pipeline stats, Celery queue status — all correct.
- `GET /api/v1/admin/health` — all services healthy (DB, Redis, Ollama, models, storage).
- `GET /api/v1/admin/stats` — all counters correct including `stats_delta` sub-object.
- Global search (`/api/v1/search?q=...`) finds customers, documents, and POs correctly.
- Chain validation endpoint (`/purchase-orders/{id}/chain`) returns correct structure for both populated and empty POs.
- All API error handling is correct: 409 on duplicate, 404 on missing resource, 422 on invalid input.
- No JavaScript errors on any page. No white screens.

---

## Fix Priority Order

Fix in this exact order before the client recording:

1. **B-2: Fix Chat Ollama 403** — Update `.env` chat endpoint to point to RunPod URL or start local Ollama with model loaded. Chat is visible in the demo flow.
2. **H-1: Fix `buildSlots()` ref field** in `PODetailPage.tsx` — "Not yet uploaded" on all verified documents is the most visually broken thing the client will see in any PO detail view.
3. **B-1: Fix admin route mismatch** — If admin page is in the demo script, `/queue-status` and `/extraction-failures` 404s need resolving. If admin page is skipped in the recording, defer to post-demo.
4. **H-3: Fix header search autocomplete z-index / focus isolation** — Typing on the search page can trap the user. Add outside-click dismiss to the header dropdown.
5. **H-2: Fix advanced search `po_no` fallback** — If the demo walks through search, `po_no` returning empty is confusing. Add the `purchase_orders` table fallback.
6. **M-2: Add submit button to search page** — Small UX fix, low effort, improves demo narration.
7. **L-1: Add React Router future flags** — Silences console warnings, 2-line fix.
8. **M-1 / M-3 / M-4 / M-5** — Post-demo cleanup; none of these will be visible in a standard client recording.

---

## Test Artifacts

- `docs/audit/backend-results.md` — Full backend findings: 22 endpoint calls, 17 passed, 3 failed, 2 skipped.
- `docs/audit/frontend-results.md` — Full frontend findings: 9 pages tested, 7 passed, 2 partial, 8 issues found.
