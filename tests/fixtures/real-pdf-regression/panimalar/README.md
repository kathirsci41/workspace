# Panimalar Real PDF Regression Fixtures

Place redacted real PDFs in this folder with these names:

- `customer-po.pdf`
- `customer-invoice.pdf`
- `delivery-challan.pdf`
- `vendor-po.pdf`
- `vendor-bill.pdf`

The regression test skips gracefully when the PDFs are not present. You can also point the test at a local-only folder by setting:

```powershell
$env:ORDER_ASSURANCE_REAL_PDF_FIXTURE_DIR="E:\path\to\redacted\panimalar"
```

Run the default skip-safe regression check from `order-assurance`:

```powershell
python -m pytest backend/tests -q -k real_pdf
```

Run the controlled OCR plus Model Layer 2 comparison with:

```powershell
$env:OCR_LIVE_TESTS="true"
$env:MODEL_LAYER2_LIVE_TESTS="true"
python -m pytest backend/tests -q -k "real_pdf or live"
```

This test mode enables `glm_ocr` and `gemma4:31b-cloud` only inside the test process. Normal application configuration keeps Model Layer 2 disabled.

The accepted Panimalar baseline is documented in `CLAUDE.md`: 24/24 fields,
zero failed document statuses, XLSX export passed, with vendor partial billing
as the only open issue.
