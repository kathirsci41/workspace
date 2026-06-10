# Status Model

## Source Of Truth

`VerificationSummary` is the computed source of truth for bundle verification outcomes.

The verifier calculates:

- `bundle_status`
- `customer_delivery_status`
- `vendor_procurement_status`
- checks, issues, and recommendation

from the current normalized document metadata at request time.

## Persisted Bundle Status

`OrderBundle.status`, `customer_delivery_status`, and `vendor_procurement_status` are persisted snapshots for list/detail display and operational filtering. They are updated only after explicit mutations:

- extraction
- re-extraction
- manual metadata patch
- document deletion
- demo seed

They are not rewritten by:

- `GET /api/bundles`
- `GET /api/bundles/{bundle_id}`
- `GET /api/bundles/{bundle_id}/verification-summary`
- `GET /api/bundles/{bundle_id}/export.xlsx`

The verification summary and export calculate fresh results without causing a write.

## Evidence Rules

- Vendor invoice amounts count toward vendor PO coverage only when `po_reference`, `customer_ref_no`, or `external_doc_no` proves a match to that Vendor PO.
- A manual correction is tagged `manual_entry`, recorded in the audit trail, and requires a reason for high-impact reference or amount fields.
- Reference index entries store provenance metadata such as source, field name, confidence, and bounded evidence text.

## Operational Meaning

If stored status ever differs from a freshly computed summary due to external database edits or an interrupted mutation, the computed verification summary is authoritative. The next successful mutation refreshes the stored snapshot.

