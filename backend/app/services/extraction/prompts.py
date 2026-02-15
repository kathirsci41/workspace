"""Document-type-specific OCR prompts and field mappings."""

SYSTEM_PROMPT = (
    "You are a document OCR extraction system. "
    "Extract the requested fields from the document image. "
    "Return ONLY valid JSON with no markdown, no code blocks, no explanation. "
    "If a field cannot be found, use null."
)

EXTRACTION_PROMPTS = {
    "CUSTOMER_PO": {
        "instruction": "Extract purchase order details from this document.",
        "schema": {
            "po_number": "string - Purchase Order number",
            "po_date": "string - Date in YYYY-MM-DD format",
            "customer_name": "string - Customer/buyer name",
            "billing_address": "string - Billing address",
            "shipping_address": "string - Shipping/delivery address",
            "total_amount": "number - Total order amount",
            "currency": "string - Currency code (INR, USD, etc.)",
            "payment_terms": "string - Payment terms",
            "line_items_count": "number - Number of line items",
            "gst_number": "string - GST/Tax identification number",
        },
    },
    "VENDOR_DC": {
        "instruction": "Extract delivery challan details from this vendor document.",
        "schema": {
            "dc_number": "string - Delivery Challan number",
            "dc_date": "string - Date in YYYY-MM-DD format",
            "po_reference": "string - Reference PO number",
            "vendor_name": "string - Vendor/supplier name",
            "items_description": "string - Description of items shipped",
            "quantity": "string - Total quantity shipped",
            "vehicle_number": "string - Vehicle/transport number",
            "receiver_name": "string - Name of person who received",
        },
    },
    "VENDOR_INVOICE": {
        "instruction": "Extract invoice details from this vendor/supplier invoice.",
        "schema": {
            "invoice_number": "string - Invoice number",
            "invoice_date": "string - Date in YYYY-MM-DD format",
            "po_reference": "string - Reference PO number",
            "vendor_name": "string - Vendor/supplier name",
            "subtotal": "number - Subtotal before tax",
            "tax_amount": "number - Tax/GST amount",
            "total_amount": "number - Total invoice amount",
            "payment_terms": "string - Payment terms",
            "gst_number": "string - Vendor GST number",
            "irn_number": "string - IRN (Invoice Reference Number)",
            "ack_number": "string - Acknowledgement number",
            "ack_date": "string - Acknowledgement date",
        },
    },
    "COMPANY_DC": {
        "instruction": "Extract delivery challan details from this dispatch document.",
        "schema": {
            "dc_number": "string - Delivery Challan number",
            "dc_date": "string - Date in YYYY-MM-DD format",
            "po_reference": "string - Reference PO number",
            "customer_name": "string - Customer name",
            "items_description": "string - Description of items dispatched",
            "quantity": "string - Total quantity dispatched",
            "dispatch_from": "string - Dispatch origin/warehouse",
        },
    },
    "COMPANY_INVOICE": {
        "instruction": "Extract invoice details from this company-issued invoice.",
        "schema": {
            "invoice_number": "string - Invoice number",
            "invoice_date": "string - Date in YYYY-MM-DD format",
            "po_reference": "string - Reference PO number",
            "customer_name": "string - Customer name",
            "subtotal": "number - Subtotal before tax",
            "tax_amount": "number - Tax/GST amount",
            "total_amount": "number - Total invoice amount",
            "so_number": "string - Sales Order number",
            "account_manager": "string - Account manager name",
            "irn_number": "string - IRN (Invoice Reference Number)",
        },
    },
    "POD": {
        "instruction": "Extract proof of delivery details from this document.",
        "schema": {
            "pod_number": "string - POD/receipt number",
            "delivery_date": "string - Date in YYYY-MM-DD format",
            "received_by": "string - Name of person who received delivery",
            "dc_reference": "string - Reference Delivery Challan number",
            "po_reference": "string - Reference PO number",
            "delivery_location": "string - Delivery location/address",
            "condition_notes": "string - Notes about condition of goods",
            "signature_present": "boolean - Whether a signature is present",
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
