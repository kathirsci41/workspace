# Real PDF Regression Fixtures

This folder supports optional, skip-safe regression testing with approved redacted documents. Do not commit private client PDFs.

The checked-in JSON files describe approved expectations. The PDFs themselves
must stay local unless they have been explicitly redacted and approved for source
control.

## Expected Layout

```text
real-pdf-regression/
  panimalar/
    customer-po.pdf
    customer-invoice.pdf
    delivery-challan.pdf
    vendor-po.pdf
    vendor-bill.pdf
    expected.json
```

The current regression test requires `customer-invoice.pdf`, `delivery-challan.pdf`, `vendor-po.pdf`, and `vendor-bill.pdf`; it skips clearly when these PDFs are absent. `customer-po.pdf` may be supplied for expanded anchor-document coverage.

Controlled Model Layer 2 validation additionally requires `customer-po.pdf`, `vendor-bill.pdf`, and `expected.json`. Run it only with `MODEL_LAYER2_LIVE_TESTS=true`; the model remains disabled in normal application configuration.

## `expected.json`

The fixture JSON must contain expected verification outcomes and any deliberate manual fallback values, for example:

```json
{
  "bundle_status": "REVIEW_REQUIRED",
  "customer_delivery_status": "PARTIAL_PASS",
  "vendor_procurement_status": "REVIEW_REQUIRED",
  "difference": 141600,
  "manual_vendor_bill": {
    "vendor_invoice_no": "2526PSI25087738",
    "vendor_invoice_date": "12-02-2026",
    "vendor_name": "SUPREME COMPUTERS INDIA P LTD",
    "po_reference": "1PTR2526000467",
    "invoice_total": 554600
  },
  "model_layer2_expected": {
    "CUSTOMER_PO": {
      "customer_po_no": "visible expected reference if approved"
    },
    "VENDOR_INVOICE": {
      "vendor_invoice_no": "2526PSI25087738",
      "po_reference": "1PTR2526000467",
      "invoice_total": 554600
    }
  }
}
```

## Local Private Fixtures

To run without committing PDFs, place redacted files in a local folder and set:

```powershell
$env:ORDER_ASSURANCE_REAL_PDF_FIXTURE_DIR="E:\path\to\redacted\panimalar"
python -m pytest backend/tests -q -k real_pdf
```

`glm-ocr` is used only for OCR text acquisition; the parser extracts fields and the verifier calculates business status.

Run from `order-assurance` when using the relative command above. From the
workspace parent, keep the project prefix:

```powershell
python -m pytest order-assurance/backend/tests -q -k real_pdf
```
