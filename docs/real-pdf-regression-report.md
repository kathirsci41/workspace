# Real PDF Regression Report

## Phase 10D Scope

This validation is limited to `order-assurance`. It exercises the controlled extraction stack:

- PyMuPDF digital text acquisition
- `glm-ocr:latest` OCR acquisition for scanned or low-text pages
- deterministic structured rules
- opt-in `gemma4:31b-cloud` Model Layer 2 only for test mode
- deterministic Python verification only
- manual correction as the recovery path

Application defaults continue to keep `MODEL_LAYER2_ENABLED=false`.

## Fixture Status

Validation date: 2026-05-23.

The expected fixture manifest exists at `tests/fixtures/real-pdf-regression/panimalar/expected.json`, but the required approved real/redacted PDFs are not present locally:

| Required file | Status |
| --- | --- |
| `customer-po.pdf` | Missing |
| `customer-invoice.pdf` | Missing |
| `delivery-challan.pdf` | Missing |
| `vendor-po.pdf` | Missing |
| `vendor-bill.pdf` | Missing |

The integration test therefore skips cleanly and does not claim real-document extraction accuracy.

## Test Result

The controlled optional command was run on 2026-05-23:

```powershell
$env:OCR_LIVE_TESTS="true"
$env:MODEL_LAYER2_LIVE_TESTS="true"
python -m pytest tests -q -k "real_pdf or live" -rs
```

Result:

- live `glm-ocr` check: passed
- live `gemma4:31b-cloud` structured extraction check: passed
- real Panimalar baseline regression: skipped because PDFs are absent
- real Panimalar Layer 2 comparison: skipped because PDFs are absent
- aggregate result: `2 passed, 2 skipped, 47 deselected`

## Controlled Test Mode

When the five PDFs are supplied, the optional regression test executes with:

```env
OCR_ENABLED=true
OCR_PROVIDER=glm_ocr
OCR_CONTEXT_LENGTH=8192
MODEL_LAYER2_ENABLED=true
MODEL_LAYER2_MODEL=gemma4:31b-cloud
```

These values apply only within the test process. They do not change development or deployment defaults.

## Captured Comparison

The controlled test harness records, per document:

- digital text length and OCR status/text length
- fields extracted by deterministic rules and their missing fields
- whether Model Layer 2 ran
- fields and evidence proposed by Model Layer 2
- final merged fields and remaining missing fields
- confidence summary and manual fallback availability

Until real/redacted inputs are supplied, the corresponding artifacts contain an explicit `SKIPPED` result:

- `tests/artifacts/real-pdf-regression/panimalar/extraction-comparison.json`
- `tests/artifacts/real-pdf-regression/panimalar/customer-po-layer-result.json`
- `tests/artifacts/real-pdf-regression/panimalar/vendor-bill-layer-result.json`
- `tests/artifacts/real-pdf-regression/panimalar/verification-summary.json`
- `tests/artifacts/real-pdf-regression/panimalar/model-layer2-output-redacted.json`
- `tests/artifacts/real-pdf-regression/panimalar/ocr-output-preview-redacted.txt`

## Customer PO Result

Not measured against a real/redacted Customer PO in this workspace because `customer-po.pdf` is absent. The test will capture all required Customer PO fields and any manual-entry requirement once a fixture is supplied.

## Vendor Bill Result

Not measured against a real/redacted Vendor Bill in this workspace because `vendor-bill.pdf` is absent. The verifier safety rule remains mandatory: an extracted invoice amount does not count against Vendor PO coverage unless `po_reference`, `customer_ref_no`, or `external_doc_no` is supported by evidence or manually confirmed.

## Verification Outcome

No real-document verification summary was produced in this run. The expected result after successful or manual Vendor Bill linking remains:

| Status/Value | Expected |
| --- | --- |
| Bundle status | `REVIEW_REQUIRED` |
| Customer delivery status | `PARTIAL_PASS` |
| Vendor procurement status | `REVIEW_REQUIRED` |
| Partial billing difference | `141600` |

## Running The Controlled Regression

After approved redacted documents are placed in the fixture folder, run:

```powershell
$env:OCR_LIVE_TESTS="true"
$env:MODEL_LAYER2_LIVE_TESTS="true"
python -m pytest order-assurance/backend/tests -q -k "real_pdf or live"
```

## Recommendation

Keep Model Layer 2 disabled by default. The current evidence supports controlled testing only: live structured extraction succeeds on synthetic known text, but no approved scanned Customer PO or Vendor Bill regression PDFs are available to validate document-level accuracy. Once those fixtures are provided, evaluate enabling Layer 2 only when deterministic rules leave required fields missing, not as a general default extraction path.
