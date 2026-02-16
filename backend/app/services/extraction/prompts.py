"""Document-type-specific OCR prompts and field mappings."""

SYSTEM_PROMPT = (
    "You are a document OCR extraction system for Indian logistics and IT distribution documents. "
    "Extract the requested fields from the document image. "
    "Return ONLY valid JSON with no markdown, no code blocks, no explanation. "
    "If a field cannot be found, use null.\n\n"
    "RULES:\n"
    "1. For ALL amounts/numbers: NEVER use commas. Write 6087800.00 NOT 6,087,800.00\n"
    "2. For dates: write EXACTLY as printed on document (e.g. 18/12/2025). Do NOT reformat.\n"
    "3. For items_description: return ONE string with all items, separated by semicolons. NEVER return an array.\n"
    "4. For reference numbers: read each character carefully. "
    "Distinguish I vs 1, O vs 0, D vs 0, S vs 5, B vs 8. "
    "Reference numbers like DC/PO/Invoice numbers typically start with digits+letters (e.g. 1DNT2526DC2865, 1PTR2526000405).\n"
    "5. po_reference means a PURCHASE ORDER NUMBER (looks like 1PTR2526000405 or PO-2025-001). "
    "It is NOT a company registration number (CIN starting with U or L), NOT a person's name, NOT a GSTIN."
)

EXTRACTION_PROMPTS = {
    "CUSTOMER_PO": {
        "instruction": (
            "Extract purchase order details from this customer PO document. "
            "The PO number is the main reference number prominently displayed, usually alphanumeric. "
            "The customer/buyer is the company ISSUING the PO (ordering goods)."
        ),
        "schema": {
            "po_number": "string - The Purchase Order number (main reference at top of document)",
            "po_date": "string - PO date exactly as printed on document",
            "customer_name": "string - Name of the company that issued this PO (the buyer)",
            "billing_address": "string - Billing address of the buyer",
            "shipping_address": "string - Physical delivery address (NOT a GSTIN number)",
            "total_amount": "number - Grand total amount including all taxes (the LARGEST amount on the PO)",
            "currency": "string - Currency code (INR, USD, etc.)",
            "payment_terms": "string - Payment terms like 'Net 30 days', '60 days from invoice'. NOT a company name.",
            "gst_number": "string - GSTIN of the buyer (15-character alphanumeric starting with state code)",
        },
    },
    "VENDOR_DC": {
        "instruction": (
            "Extract delivery challan details from this vendor DC document. "
            "The DC number is the main reference number on the challan. "
            "The vendor is the company SENDING the goods."
        ),
        "schema": {
            "dc_number": "string - Delivery Challan number (main reference, e.g. 1DNT2526DC2865)",
            "dc_date": "string - DC date exactly as printed",
            "po_reference": "string - Purchase Order number this DC fulfills (alphanumeric code like 1PTR2526000405, NOT a person name)",
            "vendor_name": "string - Name of the vendor/supplier sending goods",
            "items_description": "string - All items as ONE string separated by semicolons, include part numbers and serial numbers",
            "quantity": "number - Total quantity of items shipped",
            "vehicle_number": "string - Vehicle or transport number",
            "receiver_name": "string - Name of person who physically received the goods (with signature)",
        },
    },
    "VENDOR_INVOICE": {
        "instruction": (
            "Extract invoice details from this vendor/supplier invoice. "
            "The vendor is the company that ISSUED this invoice (the seller). "
            "Look carefully at the TAX INVOICE header area for invoice number and date."
        ),
        "schema": {
            "invoice_number": "string - Invoice number (main reference, usually near 'Tax Invoice' or 'Invoice No')",
            "invoice_date": "string - Invoice date exactly as printed",
            "po_reference": "string - Customer's PO number this invoice is against (look for 'PO No', 'PO Ref', 'Your Ref', 'Buyer Order No'). NOT a CIN or registration number.",
            "vendor_name": "string - Name of the company that issued this invoice (the seller)",
            "subtotal": "number - Taxable value BEFORE tax (smaller than total_amount)",
            "tax_amount": "number - Total tax amount (CGST+SGST or IGST)",
            "total_amount": "number - Grand total AFTER tax (the LARGEST amount, = subtotal + tax). Look for 'Total', 'Grand Total', 'Amount Payable'",
            "payment_terms": "string - Payment terms (e.g. '60 days from invoice date')",
            "gst_number": "string - Vendor's GSTIN (15-character alphanumeric, e.g. 33AAECM8625J1ZB)",
            "irn_number": "string - IRN hash (64-character hexadecimal string from e-invoice portal)",
            "ack_number": "string - IRN acknowledgement number (long numeric code from e-invoice portal, NOT a PAN number)",
            "ack_date": "string - IRN acknowledgement date (from e-invoice portal, NOT the invoice date)",
        },
    },
    "COMPANY_DC": {
        "instruction": (
            "Extract delivery challan details from this company dispatch document. "
            "This is a DC issued by the company to dispatch goods to a customer. "
            "The DC number is the main reference number on the challan."
        ),
        "schema": {
            "dc_number": "string - Delivery Challan number (main reference, e.g. 1DNT2526DC2871)",
            "dc_date": "string - DC date exactly as printed",
            "po_reference": "string - Customer's PO number being fulfilled (alphanumeric code, NOT a person name or contact)",
            "customer_name": "string - Name of the customer receiving the goods",
            "items_description": "string - All items as ONE string separated by semicolons, include part numbers",
            "quantity": "number - Total quantity dispatched",
            "dispatch_to": "string - Delivery destination (customer address or name)",
            "est_amount": "number - Estimated or total amount on the DC",
        },
    },
    "COMPANY_INVOICE": {
        "instruction": (
            "Extract invoice details from this company-issued tax invoice. "
            "This company is the SELLER issuing the invoice. "
            "The customer is the BUYER being billed."
        ),
        "schema": {
            "invoice_number": "string - Invoice number (main reference near 'Tax Invoice' header)",
            "invoice_date": "string - Invoice date exactly as printed",
            "po_reference": "string - Buyer's PO number (look for 'Buyer Order No', 'PO Ref'). NOT a CIN/registration number.",
            "customer_name": "string - Name of the customer being billed (the buyer)",
            "subtotal": "number - Taxable value BEFORE tax (smaller than total_amount)",
            "tax_amount": "number - Total tax amount (CGST+SGST or IGST)",
            "total_amount": "number - Grand total AFTER tax (the LARGEST amount = subtotal + tax)",
            "so_number": "string - Sales Order number",
            "irn_number": "string - IRN hash (64-character hexadecimal string from e-invoice portal)",
        },
    },
    "POD": {
        "instruction": (
            "Extract proof of delivery details from this document. "
            "A POD is typically a delivery challan copy with a receiver's stamp/signature as proof of receipt. "
            "If this looks like a delivery challan with stamps, extract what you can find."
        ),
        "schema": {
            "pod_number": "string - POD or receipt number. If none, use the DC number shown on document",
            "delivery_date": "string - Delivery/receipt date exactly as printed",
            "received_by": "string - Name of person who received the delivery (handwritten or stamped)",
            "dc_reference": "string - Delivery Challan number shown on this document",
            "po_reference": "string - Purchase Order number (alphanumeric, NOT a person name)",
            "delivery_location": "string - Delivery address or location",
            "condition_notes": "string - Any notes about condition of goods received",
            "signature_present": "boolean - true if a signature or stamp is visible, false otherwise",
        },
    },
}


def build_prompt(document_type: str) -> str:
    """Build the full extraction prompt for a document type."""
    config = EXTRACTION_PROMPTS.get(document_type)
    if not config:
        raise ValueError(f"Unknown document type: {document_type}")

    fields_text = "\n".join(
        f"  - {field}: {desc}" for field, desc in config["schema"].items()
    )

    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"{config['instruction']}\n\n"
        f"Extract these fields as a JSON object:\n{fields_text}\n\n"
        f"Return ONLY the JSON object."
    )


def get_primary_field(doc_type: str) -> str:
    """Get the primary reference field for a document type."""
    mapping = {
        "CUSTOMER_PO": "po_number",
        "VENDOR_DC": "dc_number",
        "VENDOR_INVOICE": "invoice_number",
        "COMPANY_DC": "dc_number",
        "COMPANY_INVOICE": "invoice_number",
        "POD": "pod_number",
    }
    return mapping.get(doc_type, "")


def get_date_field(doc_type: str) -> str:
    """Get the date field for a document type."""
    mapping = {
        "CUSTOMER_PO": "po_date",
        "VENDOR_DC": "dc_date",
        "VENDOR_INVOICE": "invoice_date",
        "COMPANY_DC": "dc_date",
        "COMPANY_INVOICE": "invoice_date",
        "POD": "delivery_date",
    }
    return mapping.get(doc_type, "")


def get_searchable_fields(doc_type: str) -> list[tuple[str, str]]:
    """Returns (ref_type, field_name) pairs for ReferenceIndex."""
    mapping = {
        "CUSTOMER_PO": [
            ("po_number", "po_number"),
            ("gst_number", "gst_number"),
        ],
        "VENDOR_DC": [
            ("dc_number", "dc_number"),
            ("po_reference", "po_reference"),
        ],
        "VENDOR_INVOICE": [
            ("invoice_number", "invoice_number"),
            ("po_reference", "po_reference"),
            ("ack_number", "ack_number"),
            ("irn_number", "irn_number"),
        ],
        "COMPANY_DC": [
            ("dc_number", "dc_number"),
            ("po_reference", "po_reference"),
            ("dispatch_to", "dispatch_to"),
        ],
        "COMPANY_INVOICE": [
            ("invoice_number", "invoice_number"),
            ("po_reference", "po_reference"),
            ("so_number", "so_number"),
            ("irn_number", "irn_number"),
        ],
        "POD": [
            ("pod_number", "pod_number"),
            ("dc_reference", "dc_reference"),
            ("po_reference", "po_reference"),
        ],
    }
    return mapping.get(doc_type, [])
