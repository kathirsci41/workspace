# Real Document Validation Samples

Keep approved, redacted real-document sets in one folder per order. Do not place
private or unredacted customer documents in the repository.

These samples are for human-reviewed validation runs and release checks. They are
not loaded by the app during normal startup.

Expected layout:

```text
real-validation/
  sample_set_01/
    customer_po.pdf
    company_invoice.pdf
    delivery_challan.pdf
    company_po_to_vendor.pdf
    vendor_invoice.pdf
    expected.json
```

PDF files under this folder are ignored by Git. The committed `expected.json`
template is not consumed by the application; it is the human-reviewed oracle
for extraction, verification, and export validation.

Run a validation set from the project root after placing the redacted PDFs in
the sample folder. The script requires each document path to be passed
explicitly:

```powershell
cd order-assurance
python scripts\run-real-doc-validation.py `
  --run-root validation-runs\sample-set-01-smoke `
  --bundle-name sample-set-01-smoke `
  --expected sample\real-validation\sample_set_01\expected.json `
  --doc CUSTOMER_PO=sample\real-validation\sample_set_01\customer_po.pdf `
  --doc COMPANY_INVOICE=sample\real-validation\sample_set_01\company_invoice.pdf `
  --doc COMPANY_DC=sample\real-validation\sample_set_01\delivery_challan.pdf `
  --doc COMPANY_PO=sample\real-validation\sample_set_01\company_po_to_vendor.pdf `
  --doc VENDOR_INVOICE=sample\real-validation\sample_set_01\vendor_invoice.pdf `
  --start-backend
```

Create a timestamped validation run directory when comparing results across
parser, OCR, verification, or export changes:

```powershell
.\scripts\new-validation-run.ps1 -RunName real-doc-smoke
```

Keep generated screenshots, workbooks, OCR output, and run logs under
`validation-runs/` or `output/`; do not commit private source PDFs.
