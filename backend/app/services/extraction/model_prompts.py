from __future__ import annotations


OCR_ONLY_PROMPT = """You are an OCR engine.
Extract all visible text from this document image.
Return only the visible text.
Do not summarize.
Do not translate.
Do not infer missing text.
Do not output JSON.
Preserve document numbers, dates, GST numbers, PO numbers, invoice numbers, totals, and table text as accurately as possible.
If text is unreadable, return an empty string.
"""


VENDOR_INVOICE_HEADER_OCR_PROMPT = """You are an OCR engine reading the top/header region of a vendor invoice.
Transcribe only text that is visibly present in the image.
Focus on the invoice number, invoice date, and purchase-order reference.
Preserve each visible label with its value.
When visible, format those lines as:
Invoice No: <visible value>
Invoice Date: <visible value>
PO Reference: <visible value>
Do not infer, guess, or complete missing labels or values.
Do not summarize.
Do not translate.
Do not output JSON or Markdown.
Return an empty string when none of those header fields is readable.
"""


GLOBAL_STRUCTURED_EXTRACTION_PROMPT = """You are a strict business document field extraction engine.

Your job is to convert OCR/raw document text into structured JSON.

Rules:
1. Return only valid JSON.
2. Do not use Markdown.
3. Do not wrap JSON in code fences.
4. Return the JSON object directly.
5. The first character must be "{" and the last character must be "}".
6. Do not include prose before or after the JSON object.
7. Do not guess missing values.
8. If a value is not clearly present, return null.
9. Preserve document values exactly, except normalize numeric amounts by removing commas.
10. Do not invent PO numbers, invoice numbers, dates, GST numbers, names, or amounts.
11. Include evidence_text for every important extracted field when possible.
12. If multiple possible values exist, return the most likely value and add alternatives in diagnostics.alternative_values.
13. If required fields are missing, include them in missing_required_fields.
14. Do not perform business validation.
15. Do not perform line-item description matching.
16. Do not decide OK, REVIEW_REQUIRED, MISMATCH, BLOCKED, or any bundle status.
17. Use the requested document_type schema exactly.
18. Return null for unsupported or invisible fields.

Forbidden output fields:
- bundle_status
- customer_delivery_status
- vendor_procurement_status
- recommendation
- checks
- issues
- business_decision
- validation_status

Required JSON shape:
{
  "document_type": "...",
  "extracted_fields": {},
  "field_evidence": {},
  "missing_required_fields": [],
  "confidence": 0.0,
  "failure_code": null,
  "failure_reason": null,
  "diagnostics": {
    "parser_route": "model_layer2",
    "warnings": [],
    "alternative_values": {}
  }
}
"""


DOCUMENT_PROMPTS: dict[str, str] = {
    "CUSTOMER_PO": """Document type: CUSTOMER_PO
Required fields: customer_po_no, customer_po_date, customer_name, billing_address, delivery_address, subtotal_amount, tax_amount, grand_total, total_quantity.
Label variants:
- customer_po_no: PO No, Purchase Order No, Order No, Customer PO, Customer Order No, Ref No
- customer_po_date: PO Date, Order Date, Date
- customer_name: Customer Name, Buyer, Bill To, Sold To
- billing_address: Billing Address, Bill To
- delivery_address: Delivery Address, Ship To, Consignee, Delivery To
- subtotal_amount: Subtotal, Basic Amount, Taxable Value, Amount Before Tax
- tax_amount: GST, Tax, Tax Amount, CGST, SGST, IGST
- grand_total: Grand Total, Total Amount, Net Amount, Order Value
- total_quantity: Total Qty, Total Quantity, Qty""",
    "COMPANY_INVOICE": """Document type: COMPANY_INVOICE
Required fields: invoice_no, invoice_date, customer_order_no, so_no, customer_name, customer_address, taxable_amount, tax_amount, net_amount.
Label variants:
- invoice_no: Invoice No, Tax Invoice No, Bill No
- invoice_date: Invoice Date, Date
- customer_order_no: Customer Order No, Customer PO No, Buyer Order No, PO Ref
- so_no: SO No, Sales Order No
- customer_name: Customer Name, Buyer, Bill To
- customer_address: Customer Name & Detail, Billing Address, Bill To
- taxable_amount: Taxable Value, Amount, Value
- tax_amount: Tax Amount, GST Amount, Tax Total
- net_amount: Nett Amount, Net Amount, Grand Total, Invoice Total""",
    "COMPANY_DC": """Document type: COMPANY_DC
Required fields: dc_no, dc_date, customer_order_no, so_no, customer_name, delivery_address, total_quantity, estimated_amount.
Label variants:
- dc_no: DC No, Delivery Challan No, Challan No
- dc_date: DC Date, Challan Date, Date
- customer_order_no: Customer Order No, Customer PO No, PO Ref
- so_no: Sales Order No, SO No
- customer_name: Delivery To, Customer Name, Consignee
- delivery_address: Delivery To, Delivery Address, Ship To, Consignee
- total_quantity: Total Qty, Total Quantity, Qty
- estimated_amount: Est. Amount, Estimated Amount, Value, Total""",
    "COMPANY_PO": """Document type: COMPANY_PO
Required fields: vendor_po_no, vendor_po_date, vendor_name, part_shipment_allowed, mode_of_bill, taxable_amount, tax_amount, net_amount.
Label variants:
- vendor_po_no: Order No, PO No, Purchase Order No
- vendor_po_date: Order Date, PO Date, Date
- vendor_name: Vendor Name, Supplier Name, Vendor Name & Address
- part_shipment_allowed: Part Shipment; return false for NOT ALLOWED and true for ALLOWED
- mode_of_bill: Mode of Bill, Billing Mode; preserve visible text exactly
- taxable_amount: Amount, Basic Amount, Taxable Amount
- tax_amount: Tax Amount, Tax Total, GST
- net_amount: Net Amount, Nett Amount, Total Amount, Grand Total""",
    "VENDOR_INVOICE": """Document type: VENDOR_INVOICE
Required fields: vendor_invoice_no, vendor_invoice_date, vendor_name, po_reference, customer_ref_no, external_doc_no, taxable_amount, tax_amount, invoice_total.
Label variants:
- vendor_invoice_no: Invoice No, Tax Invoice No, Bill No
- vendor_invoice_date: Invoice Date, Date
- vendor_name: Supplier, Vendor Name, Seller, From
- po_reference: PO No, Purchase Order No, Customer Ref No, External Doc No, Order Ref
- customer_ref_no: Customer Ref No, Customer Order No, Buyer Ref
- external_doc_no: External Doc No, External Reference
- taxable_amount: Taxable Value, Basic Amount, Subtotal
- tax_amount: GST Amount, Tax Amount, CGST, SGST, IGST
- invoice_total: Grand Total, Invoice Total, Total Invoice Value, Net Amount, Total
Critical rule: If invoice_total is visible but po_reference, customer_ref_no, and external_doc_no are all missing, return invoice_total and include po_reference in missing_required_fields. Never assume the Vendor PO link.""",
}


def prompt_for(document_type: str) -> str:
    return DOCUMENT_PROMPTS.get(str(document_type or "").upper(), "Document type unsupported. Return null fields only.")
