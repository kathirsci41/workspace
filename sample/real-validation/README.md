# Real Document Validation Samples

Keep approved, redacted real-document sets in one folder per order. Do not place
private or unredacted customer documents in the repository.

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
