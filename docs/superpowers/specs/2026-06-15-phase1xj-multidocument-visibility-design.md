# Phase 1xJ Multi-Document Visibility Hotfix Design

## Scope

Phase 1xJ fixes the Build 1 Documents page so every uploaded backend document is visible and actionable. It keeps the existing five required document categories, upload API, extraction routes, parser behavior, OCR routing, and storage model.

## Root Cause

`DocumentsPage` renders `buildDocumentSlots(documents)`. That helper creates five required slots and uses `Array.find()` to retain only the first exact document-type match for each slot. Additional records of the same type and records using backend aliases such as `CUSTOMER_INVOICE` or `VENDOR_BILL` are omitted from the rendered inventory even though the list API returns them.

## Selected Approach

Keep one required document-type group per Build 1 category and render every matching record inside the group. Canonical UI groups will recognize the backend aliases:

- `COMPANY_INVOICE`: `COMPANY_INVOICE`, `CUSTOMER_INVOICE`
- `COMPANY_DC`: `COMPANY_DC`, `DELIVERY_CHALLAN`
- `COMPANY_PO`: `COMPANY_PO`, `VENDOR_PO`
- `VENDOR_INVOICE`: `VENDOR_INVOICE`, `VENDOR_BILL`

Each record remains independent. No records are deleted, merged, replaced, or rewritten.

## UI Behavior

Each required group remains visible when empty. Empty groups show `Upload`; populated groups show every document and an `Add another` button. Every document row shows filename, raw/display type, document status, extraction status, extraction route when present, upload date, and per-document Extract/Re-extract, Review, Preview, and Delete actions.

When company/customer invoice aliases coexist, the group heading becomes `Company Invoice / Customer Invoice`, and alias rows are explicitly marked. The same canonical grouping logic prevents alias records from creating false frontend missing-document cards or issues.

## Verification Behavior

Backend storage and APIs already support duplicate types and return all records. Backend normalization already maps aliases consistently, and vendor coverage already sums all extracted invoices sharing a proven Vendor PO reference.

`build_verification_summary` will exclude metadata that is not `EXTRACTED` or `MANUAL_ENTRY`, so uploaded/pending/failed records are visible but are not treated as comparable verification evidence.

## Testing

Frontend tests cover multiple vendor invoices, pending visibility, add-another/upload controls, per-document actions, and alias labeling. A focused backend test covers exclusion of pending records from verification. Full backend tests, frontend tests, build, and live browser validation remain required.

