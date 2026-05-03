# Final Smoke Test Report
**Date:** 2026-04-21  
**Method:** Live browser pass plus direct API validation  
**Target:** Pre-deployment smoke test

---

## Overall Result

**Status:** `Pass with conditions`

Core application workflows are working on the current restarted build.

The application is not showing the previously blocking runtime failures on:

- PO detail
- PO profile
- address search
- billing full-mode totals
- chat availability

The main remaining accepted limitation is date parsing for formats like `20 March 2026`.

---

## What Was Verified

### Core runtime

- frontend root loads at `http://[::1]:5174`
- backend API responds on `http://127.0.0.1:8002`
- PO detail chain endpoint returns `200`
- PO profile endpoint returns `200`
- chat streaming endpoint returns `200`

### Live UI pages checked

- Dashboard
- Customers
- Purchase Orders detail
- Purchase Orders profile
- Documents
- Search
- Admin/System
- Assistant

### Workflow checks passed

- dashboard renders with real metrics and pending queue
- customers page loads correctly
- PO detail renders chain, reference checks, and billing summary without server errors
- PO detail shows non-zero billed amount for a full-billing PO
- PO profile renders fully with discrepancy, item comparison, and timeline sections
- documents queue renders clean reference numbers for tested rows
- review flow opens from documents page and renders extracted fields, warnings, line items, and actions
- address search API now returns clean `ref_number` values after restart
- advanced search by document type returns document results only in the tested API call
- admin page shows healthy service state and queue visibility
- assistant page loads correctly
- chat streaming endpoint is operational

---

## Known Conditions

### 1. Date parsing limitation remains

Observed in live data:

- customer PO warning: `po_date could not be parsed: 20 March 2026`

Impact:

- review flow still works
- operators may need manual correction for this format

Recommendation:

- acceptable for deployment only if explicitly treated as a known limitation

### 2. Data quality is still mixed

Observed in live UI/data:

- `SKY-QA001` still has invalid email `not-an-email`
- many POs still have null `total_amount`

Impact:

- does not block deployment technically
- can reduce confidence in demos or client-facing review environments

Recommendation:

- clean seed/demo data before customer-facing rollout

---

## Deployment Interpretation

### Cleared

- previously observed PO detail runtime failure
- previously observed PO profile runtime failure
- address search confidence-dict leak
- billing full-mode zero-total display bug
- chat outage on local runtime

### Still open but acceptable if signed off

- natural-language date parsing gap for `20 March 2026`
- final seed/demo data cleanup

---

## Recommendation

**Recommendation:** `Go with conditions`

Proceed to deployment preparation if:

- the date parsing limitation is explicitly accepted
- chat scope is confirmed
- rollout/demo data is cleaned where needed

If you want a stricter release standard, do one more optional pass focused only on:

- entering one address search term through the UI
- sending one real message through the Assistant UI
- opening one more review flow for a second document type
