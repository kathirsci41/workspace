from app.models.document_metadata import DocumentType


# =============================================================================
# JSON Schemas (expected structure for each document type)
# =============================================================================

DC_SCHEMA = {
    "dc_no": "",
    "customer_order_no": "",
    "dc_date": "",
    "so_no": ""
}

COMPANY_INVOICE_SCHEMA = {
    "invoice_no": "",
    "customer_order_no": "",
    "so_no": "",
    "invoice_date": "",
    "customer_order_date": "",
    "acct_manager": ""
}

VENDOR_INVOICE_SCHEMA = {
    "invoice_no": "",
    "our_order": "",
    "invoice_date": "",
    "customer": "",
    "def_pmnt": "",
    "ack_no": "",
    "ack_date": "",
    "customer_po_no": ""
}

CUSTOMER_PO_SCHEMA = {
    "ref_no": "",
    "po_no": "",
    "reference_no": "",
    "po_date": ""
}

PURCHASE_BILL_SCHEMA = {
    "purchase_bill_no": "",
    "po_no": "",
    "bill_no": "",
    "date": "",
    "due_date": "",
    "bill_date": ""
}

POD_SCHEMA = {
    "pod_no": "",
    "delivery_date": "",
    "receiver_name": "",
    "dc_ref_no": "",
    "so_no": ""
}


# =============================================================================
# Document-Specific Prompts
# =============================================================================

DC_PROMPT = """Analyze this Delivery Challan document image carefully and extract the following information.
Return ONLY a valid JSON object with the exact structure shown below.
If a field cannot be found in the document, return an empty string for that field.
Do not add any explanation or text outside the JSON.
Dates should be extracted exactly as they appear in the document.

Look for these specific fields:
- dc_no: The Delivery Challan Number (may appear as "DC No", "DC No.", "Challan No", "D.C. No")
- customer_order_no: Customer Order Number (may appear as "Customer Order No", "Cust Order", "Customer PO")
- dc_date: Date of Delivery Challan (may appear as "DC Date", "Date", "Challan Date")
- so_no: Sales Order Number (may appear as "SO No", "Sales Order", "SO Number", "S.O. No")

{
    "dc_no": "",
    "customer_order_no": "",
    "dc_date": "",
    "so_no": ""
}"""

COMPANY_INVOICE_PROMPT = """Analyze this Company Tax Invoice document image carefully and extract the following information.
Return ONLY a valid JSON object with the exact structure shown below.
If a field cannot be found in the document, return an empty string for that field.
Do not add any explanation or text outside the JSON.
Dates should be extracted exactly as they appear in the document.

Look for these specific fields:
- invoice_no: Invoice Number (may appear as "Invoice No", "Invoice #", "Inv No", "Tax Invoice No")
- customer_order_no: Customer Order Number (may appear as "Customer Order No", "Cust PO", "Buyer's Order No")
- so_no: Sales Order Number (may appear as "SO No", "Sales Order", "SO Number")
- invoice_date: Date of Invoice (may appear as "Invoice Date", "Date", "Inv Date", "Dated")
- customer_order_date: Customer Order Date (may appear as "Customer Order Date", "PO Date", "Buyer's Order Date", "Order Date")
- acct_manager: Account Manager name (may appear as "Acct Manager", "Account Manager", "Sales Person", "Sales Rep")

{
    "invoice_no": "",
    "customer_order_no": "",
    "so_no": "",
    "invoice_date": "",
    "customer_order_date": "",
    "acct_manager": ""
}"""

VENDOR_INVOICE_PROMPT = """Analyze this Vendor Invoice document image carefully and extract the following information.
Return ONLY a valid JSON object with the exact structure shown below.
If a field cannot be found in the document, return an empty string for that field.
Do not add any explanation or text outside the JSON.
Dates should be extracted exactly as they appear in the document.

Look for these specific fields:
- invoice_no: Invoice Number (may appear as "Invoice No", "Invoice #", "Inv No", "Tax Invoice No", "Bill No")
- our_order: Our Order reference (may appear as "Our Order", "Your Order", "Order Ref", "PO Ref")
- invoice_date: Date of Invoice (may appear as "Invoice Date", "Date", "Inv Date", "Dated")
- customer: Customer name (may appear as "Customer", "Bill To", "Buyer", "Customer Name", "M/s")
- def_pmnt: Deferred Payment terms (may appear as "Def Pmnt", "Payment Terms", "Credit Period", "Net Days", "Payment")
- ack_no: Acknowledgement Number (may appear as "Ack. No", "Ack No", "Acknowledgement No", "IRN Ack No")
- ack_date: Acknowledgement Date (may appear as "Ack. Date", "Ack Date", "Acknowledgement Date", "IRN Date")
- customer_po_no: Customer PO Number (may appear as "Customer PO No", "PO No", "Purchase Order", "Buyer's Order No")

{
    "invoice_no": "",
    "our_order": "",
    "invoice_date": "",
    "customer": "",
    "def_pmnt": "",
    "ack_no": "",
    "ack_date": "",
    "customer_po_no": ""
}"""

CUSTOMER_PO_PROMPT = """Analyze this Purchase Order (PO) document image carefully and extract the following information.
Return ONLY a valid JSON object with the exact structure shown below.
If a field cannot be found in the document, return an empty string for that field.
Do not add any explanation or text outside the JSON.
Dates should be extracted exactly as they appear in the document.

Look for these specific fields:
- ref_no: Reference Number (may appear as "Ref No", "Ref.", "Ref No/", "Our Ref")
- po_no: Purchase Order Number (may appear as "PO No", "PO #", "Purchase Order No", "Order No", "P.O. No")
- reference_no: Additional Reference Number (may appear as "Reference No", "Your Ref", "Quotation Ref", "Quote No")
- po_date: PO Date (may appear as "PO Date", "Date", "Order Date", "Dated")

{
    "ref_no": "",
    "po_no": "",
    "reference_no": "",
    "po_date": ""
}"""

PURCHASE_BILL_PROMPT = """Analyze this Purchase Bill document image carefully and extract the following information.
Return ONLY a valid JSON object with the exact structure shown below.
If a field cannot be found in the document, return an empty string for that field.
Do not add any explanation or text outside the JSON.
Dates should be extracted exactly as they appear in the document.

Look for these specific fields:
- purchase_bill_no: Purchase Bill Number (may appear as "Purchase Bill No", "Bill Number", "PB No")
- po_no: Purchase Order Number (may appear as "PO No", "PO #", "Purchase Order", "Order No")
- bill_no: Bill Number (may appear as "Bill No", "Bill #", "Invoice No", "Vendor Bill No")
- date: General date on the document (may appear as "Date", "Dated")
- due_date: Payment Due Date (may appear as "Due Date", "Payment Due", "Due On", "Pay By")
- bill_date: Bill Date (may appear as "Bill Date", "Invoice Date", "Billing Date")

{
    "purchase_bill_no": "",
    "po_no": "",
    "bill_no": "",
    "date": "",
    "due_date": "",
    "bill_date": ""
}"""

POD_PROMPT = """Analyze this Proof of Delivery (POD) document image carefully and extract the following information.
Return ONLY a valid JSON object with the exact structure shown below.
If a field cannot be found in the document, return an empty string for that field.
Do not add any explanation or text outside the JSON.
Dates should be extracted exactly as they appear in the document.

Look for these specific fields:
- pod_no: POD Number or Receipt Number (may appear as "POD No", "Receipt No", "Delivery Receipt", "LR No", "Docket No")
- delivery_date: Date of Delivery (may appear as "Delivery Date", "Date", "Received Date", "Date of Receipt")
- receiver_name: Name of person who received (may appear as "Received By", "Receiver", "Accepted By", "Signed By")
- dc_ref_no: Delivery Challan Reference (may appear as "DC No", "DC Ref", "Challan Ref", "Reference")
- so_no: Sales Order Number (may appear as "SO No", "Sales Order", "SO Number", "Order No")

{
    "pod_no": "",
    "delivery_date": "",
    "receiver_name": "",
    "dc_ref_no": "",
    "so_no": ""
}"""


# =============================================================================
# Prompt Registry
# =============================================================================

PROMPT_REGISTRY = {
    DocumentType.CUSTOMER_PO: {
        "prompt": CUSTOMER_PO_PROMPT,
        "schema": CUSTOMER_PO_SCHEMA,
        "primary_ref_field": "po_no",
        "date_field": "po_date",
    },
    DocumentType.VENDOR_INVOICE: {
        "prompt": VENDOR_INVOICE_PROMPT,
        "schema": VENDOR_INVOICE_SCHEMA,
        "primary_ref_field": "invoice_no",
        "date_field": "invoice_date",
    },
    DocumentType.VENDOR_DC: {
        "prompt": DC_PROMPT,
        "schema": DC_SCHEMA,
        "primary_ref_field": "dc_no",
        "date_field": "dc_date",
    },
    DocumentType.COMPANY_INVOICE: {
        "prompt": COMPANY_INVOICE_PROMPT,
        "schema": COMPANY_INVOICE_SCHEMA,
        "primary_ref_field": "invoice_no",
        "date_field": "invoice_date",
    },
    DocumentType.COMPANY_DC: {
        "prompt": DC_PROMPT,           # Same prompt as VENDOR_DC
        "schema": DC_SCHEMA,
        "primary_ref_field": "dc_no",
        "date_field": "dc_date",
    },
    DocumentType.POD: {
        "prompt": POD_PROMPT,
        "schema": POD_SCHEMA,
        "primary_ref_field": "pod_no",
        "date_field": "delivery_date",
    },
    DocumentType.PURCHASE_BILL: {
        "prompt": PURCHASE_BILL_PROMPT,
        "schema": PURCHASE_BILL_SCHEMA,
        "primary_ref_field": "bill_no",
        "date_field": "bill_date",
    },
}


def get_prompt_config(doc_type: DocumentType) -> dict:
    """Get the prompt configuration for a document type."""
    config = PROMPT_REGISTRY.get(doc_type)
    if not config:
        raise ValueError(f"No prompt configured for document type: {doc_type}")
    return config
