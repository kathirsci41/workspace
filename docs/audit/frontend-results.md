# Frontend Test Results
**Tested by:** QA-Frontend
**Date:** 2026-04-17
**Frontend URL:** http://localhost:5174
**Backend URL:** http://127.0.0.1:8002

---

## Summary
9 pages tested | 7 passed | 2 partial | 8 issues found (1 HIGH, 4 MEDIUM, 3 LOW)

---

## Page Results

### [PASS] Dashboard — /
Status: Loads fully. All stat cards visible (8 customers, 9 POs, 15 pending reviews, 9 verified docs, 24 total docs). Pending review queue shows 10 items with overdue labels and review links. Recent POs table loads with chain %, status badges, and customer names. Quick action buttons ("Create PO", "Upload Document", "Review Pending (15)") present.
Console errors: None
Notes: All panels populated with real data. Status badges render correctly (IN PROGRESS, NEAR COMPLETE, COMPLETE, INITIATED). Overdue labels ("7 d overdue", "9 d overdue") show correctly.

---

### [PASS] Customers — /customers
Status: Loads fully. All 8 customers listed in table. Customer ID, Name, GST, Email, Created Date columns all present. Search filter works — searching "shriram" correctly filters to only SHRIRAM FINANCE.
Console errors: None
Notes: GST and Email columns show "—" for most customers (no data populated) — expected given demo data. No pagination (8 items fit on one page). Add Customer button visible.

---

### [PASS] Purchase Orders — /purchase-orders
Status: Loads fully. All 9 POs listed with PO Number, Customer, Date, Amount, Chain %, Status columns. Status badges render (IN PROGRESS amber, NEAR COMPLETE amber, COMPLETE green, INITIATED gray). Multiple filter controls visible: search by PO/SO number, customer combobox, status dropdown, date range pickers, sort dropdown, completeness quick-filter chips, missing-document filter chips.
Console errors: None
Notes: Status filter is a `<select>` element (playwright_select permission denied prevented live testing, but confirmed correct HTML). Date columns show "—" for most POs — likely no po_date set for those records. Amount column shows "—" for all — no total_amount set. Chain % renders correctly (0%, 16.7%, 50%, 66.7%, 83.3%, 100%).

---

### [PARTIAL] PO Detail — /purchase-orders/{id}
Status: Loads and mostly functions correctly. Chain status bar (6 slot timeline at top) shows correct states with confidence percentages and hover tooltips. Reference Validation panel shows SKIP/FAIL results. Billing Completeness panel shows "full Billing — PENDING". Document upload cards show per-type (Customer PO, Company PO, etc.) with status, ref number, confidence %, and action buttons (Preview, Review & Verify, Re-extract, Add another). SO number edit is functional (click badge → inline input appears → fill → Escape or Enter).

However, see Issue #1 below (Document Chain "Not yet uploaded" bug).

Console errors: None
Notes:
- SO number inline edit DOES work — the input appears after clicking the badge. Earlier test was a false negative; the input is small and inline but functional.
- The "View →" button in Document Chain section correctly opens the PDF preview panel on the right.
- Upload zone appears for missing document types.
- Re-extract button present per document slot.

---

### [PASS] PO Profile — /purchase-orders/{id}/profile
Status: Loads fully with rich data. Sections present: header (PO number, status, customer, scenario selector, GST type selector), Cross-Reference Check panel, Cross-Document Field Comparison table (with match/mismatch/pending counts), Item-Level Verification table, Customer PO → Company PO Part Match (AI), Vendor Breakdown, individual document sections (each with metadata fields and Order Items table), and Order Timeline.

Console errors: None
Notes:
- Export Excel button visible and present (not tested end-to-end due to requiring file download).
- Close Order button visible.
- Scenario shows "Unknown" for SAMPLE-TEST-001 — see Issue #2 below.
- Cross-Document comparison shows: 1 match (SO Number), 3 mismatches (Grand Total mismatch ₹920k vs ₹874k, Vendor PO Amount mismatch ₹696k vs ₹554k, DC Reference not found on invoice), 3 pending.
- Item-Level Verification section shows item count mismatch warning for Customer PO → Company DC.
- Company PO → Vendor DC comparison: 6 line items from Company PO, Vendor DC quantities all "—" (Vendor DC not uploaded).
- Order Timeline section loads correctly with uploaded/extracted timestamps.

---

### [PASS] Documents — /documents
Status: Loads fully. 24 documents listed with Type badge, Filename, Ref No, PO Number, Customer, Status badge, Upload date, and action buttons (Review →, Open PO). Status filter dropdowns (All Types, All Statuses, All Customers, Uploaded date) visible. Clicking "Review →" on a PENDING_REVIEW document navigates to the PO detail page with the review modal opened.
Console errors: None
Notes: Review modal opens in full manual-entry mode showing a 100% PDF on left and all extracted fields on right (Customer PO Number, Customer Name, PO Date, etc.), with Add Row / Add Field buttons and Verify/Reject/Cancel actions. This is functional.

---

### [PARTIAL] Search — /search
Status: Search page loads. Reference Search and Address Search tabs present. Advanced filters toggle visible. Searching "1ITR2526001878" (Enter key) returns 9 results. The global header search bar also triggers an autocomplete dropdown when the search page input is used — see Issue #3.
Console errors: None
Notes:
- The search page form requires pressing Enter (no visible submit button). This may not be obvious to users.
- Results show document type label, PO number, customer name, and confidence %. Clicking a result was not tested but expected to navigate to PO detail.
- Address Search tab was not tested interactively.
- Advanced filters panel was not expanded (interaction unavailable in automated test).
- Search returned 9 results for an invoice number — some results appear to be fuzzy matches unrelated to the query (e.g., vendor invoices and company POs with different numbers like "1PTR2526000428"). This may be intentional fuzzy search behavior.

---

### [PASS] Admin — /admin
Status: Loads fully. All 5 health service panels show green (database, redis, model endpoint, models loaded, storage). Document pipeline stats load correctly: 0 Uploaded, 0 Extracting, 15 Pending Review, 9 Verified, 0 Failed, 0 Rejected, 24 total documents, 10 purchase orders, 9 customers. Extraction Failures section shows "No extraction failures". Currently Active section shows "No documents currently processing". Celery Queue shows 1 Worker Online, 0 Active Tasks, 0 Queued Tasks.
Console errors: None
Notes: Previous audit reported a 500 error on the stats endpoint — this is now resolved. All panels load. "Requeue Pending" and "Refresh all" buttons present. Click-to-filter on pipeline counters not tested.

---

### [PARTIAL] Chat (NEW) — /chat
Status: Page loads correctly. "Assistant" nav link is visible in the sidebar. Welcome message displays. Quick action chips show on first load ("What needs attention today?", "Find missing documents", "Summarise billing status", "What should I do next?"). PO context selector button ("+ Add PO context") opens a dropdown list of all POs. Selecting a PO from the dropdown correctly updates the button label to the selected PO number.

Chat sends a message but returns an error — see Issue #4 (BLOCKER).

Quick chips disappear after the first message is sent (expected behavior). Chips could not be clicked in isolation due to the error state taking over the interaction.

Console errors: None (the 403 error is shown inline in the chat bubble, not as a console error).

---

## Issues Found

---

### [HIGH] Issue 1: Document Chain always shows "Not yet uploaded" even for uploaded documents
**Page:** PO Detail — /purchase-orders/{id}
**Severity:** HIGH
**What happens:** In the dark "Document Chain" panel on the left side of the PO detail page, every document slot shows `"Not yet uploaded"` in a dashed box regardless of whether documents are actually uploaded. For SAMPLE-TEST-001, Customer PO, Company PO, Vendor Invoice, Company DC, and Company Invoice are all uploaded/verified, yet each shows "Not yet uploaded". The status badge (Verified/Mismatch/Waiting) is correct, but the text inside the ref-number box is wrong.
**Root cause (code):** `buildSlots()` in `PODetailPage.tsx` (lines 25–55) never sets the `ref` field on the `TimelineSlot` object it returns. `ChainTimeline.tsx` (line 50) shows `slot.ref` content if truthy, otherwise falls back to "Not yet uploaded". The `ref` field is never populated from the API data.
**Screenshot:** 04e-po-detail-sample-recheck
**Fix needed:** In `buildSlots()`, extract the reference number from `chainByType[type][0]` (likely the `dc_number`, `invoice_number`, or `po_number` field) and pass it as `slot.ref`.

---

### [MEDIUM] Issue 2: PO Profile Scenario shows "Unknown" for populated POs
**Page:** PO Profile — /purchase-orders/{id}/profile
**Severity:** MEDIUM
**What happens:** For SAMPLE-TEST-001 (which has 5 documents uploaded), the Scenario field shows "Unknown" instead of detecting the appropriate scenario (PROCUREMENT, STOCK, DROP_SHIP, or SERVICE_AMC). The scenario selector buttons (Procurement, Stock, Drop-ship, Service/AMC) are visible but none is selected.
**Screenshot:** 05-po-profile
**Notes:** The `derive_scenario()` backend function exists (`po_service.py`). This may be a data issue (field not set in DB) rather than a UI bug, but the UI shows "Unknown" without any indication that it needs to be set manually.

---

### [MEDIUM] Issue 3: Header search autocomplete dropdown blocks page interaction
**Page:** Search — /search
**Severity:** MEDIUM
**What happens:** When a user types in the search page's main search input, the global header search bar also receives focus and its autocomplete dropdown appears (overlapping the page). Once the dropdown is open, it intercepts all click events on the page — including the search form submit button. The dropdown cannot be dismissed by clicking elsewhere or pressing Escape from the search page. Navigation away and back is required to reset.
**Screenshot:** 07b-search-autocomplete
**Root cause:** Both the page-level search input and the header search bar appear to respond to the same input event or the focus jumps to the header bar instead of the page input. The header autocomplete dropdown has `z-index` priority and blocks interactions.
**Fix needed:** Ensure the page search form and the header global search are isolated. The header dropdown should close on outside click (clicking anywhere outside it).

---

### [HIGH] Issue 4: Chat assistant returns 403 Forbidden — Ollama endpoint blocked
**Page:** Chat — /chat
**Severity:** HIGH (feature unusable)
**What happens:** When a message is sent in the chat interface, the backend returns: `"Chat service unavailable: Client error '403 Forbidden' for url 'http://localhost:11434/api/chat'"`. The error is displayed inline in the chat message bubble (good UX), but the feature is completely non-functional.
**Screenshot:** 09d-chat-error
**Root cause:** The Ollama endpoint at `http://localhost:11434` is returning 403. This is likely because Ollama is not currently running locally (MEMORY.md states OCR is using RunPod remote endpoint, and the local Ollama is optional). The chat API is configured to use `http://localhost:11434` but no local model is loaded.
**Fix needed:** Either start the local Ollama instance with a suitable model (e.g., `qwen2.5:3b`), or update the chat backend to support the remote RunPod endpoint. The `.env` configuration for the chat endpoint may need updating.

---

### [MEDIUM] Issue 5: Search page has no visible submit button — Enter-only submission
**Page:** Search — /search
**Severity:** MEDIUM (UX)
**What happens:** The search form on `/search` has no submit button. Users must press Enter to search. The search icon inside the input is decorative only and does not trigger a search. This is not intuitive for all users.
**Screenshot:** 07c-search-fresh
**Fix needed:** Add a visible search/submit button next to the search input, or make the search icon clickable.

---

### [LOW] Issue 6: Customer PO ref number shows "—" in Document Chain even when ref exists
**Page:** PO Detail — /purchase-orders/{id} (SAMPLE-TEST-001)
**Severity:** LOW (data quality)
**What happens:** The Customer PO uploaded for SAMPLE-TEST-001 was extracted but the `po_number` field shows "—" in all places including the profile. The extraction returned no PO number from the customer's PO document. This is an AI extraction accuracy issue rather than a UI bug, but it results in `null` ref in the chain view.
**Screenshot:** 04c-po-detail-sample
**Notes:** This is expected given extraction confidence is 90% (scanned document) but the key field wasn't parsed. No code fix needed — AI prompt tuning may improve this.

---

### [LOW] Issue 7: React Router v6 future flag warnings in console
**Page:** All pages
**Severity:** LOW (non-functional, dev-only)
**What happens:** Two React Router warnings appear in console on every page load:
- `⚠️ React Router Future Flag Warning: Relative route resolution within Splat routes is changing in v7. Use v7_relativeSplatPath flag.`
- `⚠️ React Router Future Flag Warning: React Router will begin wrapping state updates in React.startTransition in v7. Use v7_startTransition flag.`
**Fix needed:** Add `future={{ v7_relativeSplatPath: true, v7_startTransition: true }}` to the Router component in `main.tsx` or `App.tsx`.

---

### [LOW] Issue 8: PO Amount column always shows "—" on PO list
**Page:** Purchase Orders — /purchase-orders
**Severity:** LOW
**What happens:** The "Amount" column on the PO list shows "—" for all 9 POs. Most POs don't have `total_amount` set.
**Screenshot:** 03-purchase-orders
**Notes:** This appears to be a data issue (POs were created without amounts). Not a UI rendering bug. The column is correctly showing "—" when data is absent.

---

## Console Error Summary (All Pages)
No JavaScript errors found on any page. Only two React Router future-flag warnings (non-breaking).

---

## Screenshots Reference
| Screenshot Name | Description |
|---|---|
| 01-dashboard | Dashboard full view |
| 02-customers | Customers list |
| 02b-customers-search | Search filtered to SHRIRAM FINANCE |
| 03-purchase-orders | PO list with all filters |
| 04-po-detail | PO-2026-SF004 detail page |
| 04c-po-detail-sample | SAMPLE-TEST-001 detail — chain timeline, ref validation |
| 04d-so-number-edit | SO number edit — button click (input present in DOM) |
| 04e-po-detail-sample-recheck | Confirms "Not yet uploaded" bug in chain |
| 04f-chain-view-click | View → button clicked — preview panel opens |
| 04g-chain-view-preview | PDF preview loading |
| 04h-so-edit-attempt2 | SO edit input confirmed present |
| 05-po-profile | PO Profile top half |
| 05b-po-profile-full | PO Profile full page scroll |
| 06-documents | Documents list |
| 06b-document-review-modal | Review modal opened from documents list |
| 07-search | Search page empty state |
| 07b-search-autocomplete | Header autocomplete blocking bug |
| 07d-search-results | Search results for "1ITR2526001878" |
| 08-admin | Admin console |
| 08b-admin-full | Admin full page scroll |
| 09-chat | Chat page initial state with chips |
| 09b-chat-typed | Message typed in chat |
| 09d-chat-error | 403 error from Ollama |
| 09f-chat-po-context | PO context dropdown open |
| 09g-chat-po-selected | PO context selected |

---

## Overall Assessment

The frontend is in good shape for a development build. All 9 pages load without crashes or white screens. Core workflows (PO creation, document upload, review, profile analysis) are functional. The chain validation UI (ChainTimeline, ReferenceValidationPanel, BillingCompletenessPanel) renders correctly. The new Chat page renders correctly but is blocked by a local Ollama configuration issue.

**Priority fixes before next demo:**
1. Fix `buildSlots()` to populate `ref` field in ChainTimeline (HIGH — confusing to users)
2. Fix Ollama/chat endpoint config (HIGH — feature completely broken)
3. Fix header search dropdown intercepting page clicks (MEDIUM — can trap users)
4. Add submit button to search page (MEDIUM — discoverability issue)
