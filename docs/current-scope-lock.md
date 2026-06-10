# Current Scope Lock

Date: 2026-06-05

This document freezes the current review/demo scope for Order Assurance. Until review is complete, work should stay inside this boundary unless a change is required to fix a blocker listed below.

## Product Boundary

Order Assurance is an independent document assurance application. It is not currently scoped as an ODMP frontend integration, ERP integration, or automated approval engine.

The application supports a human-in-the-loop order document review workflow:

- Create and manage order bundles.
- Upload PDF documents into an order bundle.
- Store uploaded files in local or Docker-managed storage.
- Extract key document fields from digital PDF text and OCR text.
- Prefer deterministic extraction rules and confidence metadata over unchecked model output.
- Leave uncertain or missing fields blank for manual review instead of emitting confident-wrong values.
- Review extracted fields against the source document.
- Manually correct extracted fields with a reason.
- Verify bundle consistency across references, totals, and document status.
- Export a verification workbook.
- Keep audit records for material review/correction actions.

## In-Scope Document Types

- `CUSTOMER_PO`
- `COMPANY_INVOICE`
- `COMPANY_DC`
- `COMPANY_PO`
- `VENDOR_INVOICE`

## In-Scope User Flows

- Create an order.
- Open an order detail page.
- Upload one or more PDFs.
- Extract and re-extract documents.
- Review extracted fields with source/document context.
- Edit supported manual fields and save corrections with a reason.
- See missing, low-confidence, and manually confirmed fields clearly in review.
- Run or view bundle verification.
- View verification checks, comparison rows, and audit history.
- Export the bundle verification report.
- Delete uploaded documents.
- Run cleanup for orphaned local files.

## Extraction Policy

Correct-or-blank is the expected behavior. A blank field is acceptable when OCR did not read the value or the parser cannot identify it safely. A confident-wrong value is not acceptable because it can pass through review unnoticed.

The extraction pipeline is scoped as:

- Digital text extraction when the PDF contains usable text.
- OCR text acquisition for scanned PDFs when the OCR backend is healthy.
- Structured parser rules for known business document layouts.
- Manual correction as the safety net for missing, low-confidence, or rejected values.
- Optional model-layer extraction remains experimental and disabled by default.

The application should not persist raw OCR text permanently. Temporary raw OCR capture is allowed only for debugging and must stay out of the database and shared review zip.

## Explicitly Out Of Scope

- Authentication, authorization, RBAC, and multi-user permission design.
- ERP synchronization, posting, or automatic order closure.
- Automatic payment, finance approval, or legal approval decisions.
- Line-item, SKU, serial number, tax-line, or product-description matching.
- Full procurement workflow management outside document assurance.
- PDF editing, annotation persistence, page mutation, or OCR correction tooling.
- Permanent storage or export of raw OCR/model output.
- Replacing human review with AI-only approval.
- Production multi-tenant hardening.
- Background OCR queues, distributed extraction workers, or scaling architecture.
- Email ingestion, notification workflows, or external task assignment.

## Allowed Pre-Review Fixes

Only the following fixes are allowed before calling the current scope demo-ready:

- Fix the manual correction allowlist/UI mismatch that can reject editable extracted fields.
- Add the "Extract all" action to the active order detail page if it is not visible there.
- Update Playwright end-to-end tests to match the active UI and dev-seed behavior.
- Make OCR health reflect real inference health, or clearly mark OCR as degraded when inference fails.
- Add or repair the frontend lint baseline if lint is part of the review gate.

These are blocker fixes because they protect the current scope. They are not permission to broaden the product.

## Known Non-Blocking Limitations

- OCR quality depends on the local OCR runtime and scanned PDF quality.
- Some missing fields are expected and should be manually entered.
- Development seed APIs are disabled in production-safe Docker Compose by default.
- The model layer is not part of the default trusted extraction path.
- Current review/demo is local or Docker Compose based, not a hardened hosted deployment.

## Acceptance Baseline

The current scope is review-ready when:

- Backend tests pass with only expected skips.
- Frontend tests pass.
- Frontend build passes.
- Current UI audit has no application-level failures.
- End-to-end tests are aligned with the active UI and pass in the intended environment.
- The code-only review zip excludes dependencies, build output, database files, real PDFs, uploads, raw OCR output, screenshots, and secrets.

## Change Control

New feature requests go to the post-review backlog unless they are necessary to complete one of the allowed pre-review fixes. Bug fixes should stay narrow, include tests where practical, and preserve the correct-or-blank extraction policy.
