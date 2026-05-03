# Deployment Gate Issue Audit
**Date:** 2026-04-21  
**Purpose:** Current-state audit of known application issues before deployment phase

---

## Summary

This audit classifies previously identified issues into four buckets:

- `Fixed and verified`
- `Fixed and runtime-verified`
- `Still open`
- `Not reproducible / likely stale`

The goal is to separate real deployment blockers from already-resolved items and stale findings.

### Current deployment gate

**Status:** `Nearly clear for deployment`

The application is close enough to continue toward deployment preparation, but a few issues still need to be closed or explicitly accepted:

- date parsing limitation is still open
- broader UX/runtime verification should be repeated once the latest backend/frontend build is running

---

## 1. Fixed And Verified

### 1.1 Billing tab full-billing total fallback

**Previous issue:** `Billed so far` showed `₹0` in full billing mode when invoices existed but `billing.stages` was empty.

**Root cause:** `BillingTab` only summed `billing.stages` and ignored the already-available aggregate `billing.invoiced_total`.

**Status:** `Fixed and verified`

**Evidence:**

- frontend fix in `frontend/src/components/BillingTab.tsx`
- regression test added in `tests/frontend/test_billing_tab_full_fallback.test.ts`
- verified with:
  - `npm test -- ..\tests\frontend\test_billing_tab_full_fallback.test.ts`

**Deployment impact:** closed

---

### 1.2 PO detail `/chain` endpoint runtime failure

**Previous issue:** live UI testing previously saw `500` errors from the PO detail chain endpoint.

**Current status:** `Fixed / not currently reproducing`

**Evidence:**

- `GET /api/v1/purchase-orders/1ededf54-b09d-4316-b097-1f94394ae6ed/chain` returns `200`
- response includes valid `reference_checks` and `billing.invoiced_total`

**Deployment impact:** not currently a blocker

---

### 1.3 PO profile runtime failure

**Previous issue:** live UI testing previously saw the PO profile fail to load for a real PO.

**Current status:** `Fixed / not currently reproducing`

**Evidence:**

- `GET /api/v1/purchase-orders/1ededf54-b09d-4316-b097-1f94394ae6ed/profile` returns `200`
- profile payload is rich and structurally complete

**Deployment impact:** not currently a blocker

---

### 1.4 Header search outside-click dismissal

**Previous issue:** header autocomplete dropdown reportedly trapped page interaction.

**Current code status:** `Likely fixed`

**Evidence:**

- `frontend/src/components/layout/InlineSearch.tsx` now contains an outside-click handler that closes the dropdown
- the dropdown is also intentionally suppressed on `/search`

**Deployment impact:** low, but should be rechecked in a live browser once the newest build is running

---

## 2. Fixed And Runtime-Verified

### 2.1 Address search confidence-dict leak

**Previous issue:** address search displayed raw values like `{'value': '1DNT2526DC2915', 'confidence': 1.0}`.

**Root cause:** the user-facing address search goes through `advanced_search`, and the metadata-only branch was still returning raw `meta.primary_ref_no`.

**Status:** `Fixed and runtime-verified`

**Evidence:**

- backend fix in `backend/app/services/search_service.py`
- regression test added in `backend/tests/test_search_fixes.py`
- verified by test:
  - `pytest tests/test_search_fixes.py -k advanced_search_cleans_primary_ref_no_for_metadata_results`

**Runtime verification:**

- `GET /api/v1/search/advanced?delivery_address=Hyderabad&per_page=10`
- matching records now return clean `ref_number` values in the live backend

**Deployment impact:** closed

---

## 3. Still Open

### 3.1 Date parsing does not support `20 March 2026`

**Issue:** natural-language date strings like `20 March 2026` are still not parsed by the extraction date parser.

**Root cause:** `ResponseParser.parse_date()` and `_parse_date_flexible()` support numeric formats, abbreviated month formats, and `March 20, 2026`, but not `%d %B %Y`.

**Status:** `Still open`

**Evidence:**

- `backend/app/services/extraction/response_parser.py`
- `backend/app/services/extraction/invoice_validator.py`

**Deployment impact:** medium

This is not a deployment blocker if the business accepts occasional manual correction during review, but it is still a known product limitation.

---

### 3.2 End-to-end revalidation of major UI workflows

**Issue:** some previously observed UI/UX findings were tied to an older running build, and not every path has been rechecked against the latest code.

**Status:** `Still open as verification work`

**Deployment impact:** medium to high

Before deployment signoff, the following live flows should be re-run on the current build:

- PO detail
- PO profile
- documents queue to review modal
- reference search
- address search
- billing tab
- chat, if in scope

This is a verification gap rather than a single product bug.

---

## 4. Not Reproducible Or Likely Stale

### 4.1 Chat assistant outage / 403 from local model endpoint

**Previous issue:** chat was observed failing with `403` from `http://localhost:11434/api/chat`.

**Current status:** `Not currently reproducing`

**Evidence:**

- `GET /api/v1/chat/stream?message=hello` returns `200`
- the SSE stream emits normal assistant chunks

**Interpretation:**

The issue was environmental/runtime-state related, not a confirmed current application defect.

**Deployment impact:** verify model endpoint availability in the deployment environment, but this is not currently blocked in local runtime

---

### 4.2 Advanced search document type filter shows customer rows

**Previous issue:** filtering by document type reportedly still showed customer results.

**Current status:** `Not reproducible from backend/API`

**Evidence:**

- direct calls to `/api/v1/search/advanced?document_type=COMPANY_DC` return only document results
- backend `advanced_search()` does not append customer rows in that path

**Interpretation:**

If this still appears in the browser, it is more likely a UI-state mixing problem than a backend filter bug. As of this audit, it is not proven as an active backend defect.

**Deployment impact:** monitor during final live QA

---

### 4.3 PO profile `Unknown` scenario on populated PO

**Previous issue:** some earlier audit output showed `Unknown` scenario on a populated PO.

**Current status:** `Not currently reproducing on checked PO`

**Evidence:**

- current profile response for `PO-2026-SF003` returns:
  - `order_scenario: procurement`

This may have been data-specific or already corrected.

**Deployment impact:** low unless seen again on real rollout data

---

### 4.4 PO detail document-chain `Not yet uploaded` everywhere

**Previous issue:** older audit reported the PO detail timeline always showed `Not yet uploaded`.

**Current status:** `Likely stale`

**Evidence:**

- current `PODetailPage.tsx` uses `LightChainTimeline`
- the old `buildSlots()` pattern described in earlier audit output is not present in the current file
- document cards in the current page render `slot.ref_no`

This looks like an older implementation finding rather than a current one, but it should still be spot-checked in live QA.

**Deployment impact:** low unless reproduced on the current build

---

## 5. Data Quality / Non-Code Notes

These are not product defects by themselves, but they matter during rollout:

- `SKY-QA001` invalid email looks like test/demo data
- many POs still have null `total_amount`
- some scenario/state values may depend on seed data quality

Deployment should use cleaned demo/customer seed data if the environment is client-facing.

---

## 6. Deployment Gate Recommendation

### Must close before deployment signoff

- confirm the current build end to end on PO detail, PO profile, search, and billing

### Can deploy with known limitation if accepted

- `20 March 2026` date parsing gap, provided manual review remains the fallback

### Current verdict

**Recommendation:** `Proceed toward deployment, but do one more live verification pass before final signoff`

This is not blocked by deep architectural issues anymore. It is mainly blocked by final runtime confirmation and acceptance of the remaining date-parsing limitation.
