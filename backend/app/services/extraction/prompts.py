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
            "The PO number is the main reference number prominently displayed. "
            "The customer/buyer is the company ISSUING the PO (ordering goods). "
            "BSIF Name is the business/company name shown in the PO header."
        ),
        "schema": {
            "po_number":  "string - PO No — the Purchase Order number (main reference at top of document)",
            "po_date":    "string - PO Date — date exactly as printed on document",
            "bsif_name":  "string - BSIF Name — business/company name on the PO header (the issuing entity name)",
        },
    },
    "COMPANY_PO": {
        "instruction": (
            "Extract details from this Company Purchase Bill document. "
            "Three different reference numbers appear in the header: "
            "Purchase Bill No (issued by the vendor, starts with 1PBTR), "
            "PO No (our company's PO to the vendor, starts with 1PTR), "
            "and Bill No (vendor's internal bill number)."
        ),
        "schema": {
            "purchase_bill_no": "string - Purchase Bill No — issued by vendor to us (starts with '1PBTR')",
            "po_number":        "string - PO No — our company's PO number issued to this vendor (starts with '1PTR')",
            "bill_no":          "string - Bill No — vendor's own internal bill/invoice number",
        },
    },
    "VENDOR_DC": {
        "instruction": (
            "Extract delivery challan details from this vendor DC document. "
            "The DC number is the main reference number on the challan. "
            "The vendor is the company SENDING the goods."
        ),
        "schema": {
            "dc_number":         "string - Delivery Challan number (main reference, e.g. 1DNT2526DC2865)",
            "dc_date":           "string - DC date exactly as printed",
            "po_reference":      "string - Purchase Order number this DC fulfills (alphanumeric code like 1PTR2526000405, NOT a person name)",
            "vendor_name":       "string - Name of the vendor/supplier sending goods",
            "items_description": "string - All items as ONE string separated by semicolons, include part numbers and serial numbers",
            "quantity":          "number - Total quantity of items shipped",
            "vehicle_number":    "string - Vehicle or transport number",
            "receiver_name":     "string - Name of person who physically received the goods (with signature)",
        },
    },
    "VENDOR_INVOICE": {
        "instruction": (
            "Extract invoice/bill details from this vendor or supplier document. "
            "The vendor is the company that ISSUED this invoice or purchase bill (the seller). "
            "Look carefully at the header area for invoice number, bill number, and date."
        ),
        "schema": {
            "invoice_number":    "string - Invoice No — vendor's invoice/bill number "
                                 "(labeled 'Invoice No.', 'Tax Invoice No.', or 'Bill No.')",
            "customer_order_no": "string - Customer Order No — customer's order number referenced by this vendor "
                                 "(look for 'Customer Order No.', 'Your Order No.', 'Customer SO No.'). "
                                 "Different from po_reference.",
            "po_reference":      "string - Customer PO Number — our company's PO number sent to this vendor "
                                 "(look for 'Buyer Order No.', 'Your Ref', 'Customer PO', 'PO No'). NOT a CIN.",
        },
    },
    "COMPANY_DC": {
        "instruction": (
            "Extract delivery challan details from this company dispatch document. "
            "This is a NON RETURNABLE DELIVERY CHALLAN issued by the company to dispatch goods to a customer. "
            "The DC number is the main reference number on the challan. "
            "IMPORTANT: 'Customer Order No.' is the customer's Purchase Order number (po_reference). "
            "'Reference' is a person name — do NOT use it as po_reference."
        ),
        "schema": {
            "dc_number":      "string - DC No — Delivery Challan number (labeled 'DC No.', e.g. 1DNT2526DC2871)",
            "po_reference":   "string - Customer Order No — customer's PO number (labeled 'Customer Order No.', NOT a person name)",
            "sales_order_no": "string - Sales Order No (labeled 'Sales Order No.', starts with '1OTM')",
            "dispatch_to":    "string - Delivery To — customer address or name (labeled 'Delivery To')",
        },
    },
    "COMPANY_INVOICE": {
        "instruction": (
            "Extract invoice details from this company-issued TAX INVOICE. "
            "This company is the SELLER issuing the invoice. "
            "The customer is the BUYER being billed. "
            "IMPORTANT: 'Customer Order No.' is the buyer's Purchase Order number (po_reference). "
            "'SO No.' is the Sales Order number."
        ),
        "schema": {
            "invoice_number": "string - Invoice No (labeled 'Invoice No.', starts with '1ITR' or '1ISR')",
            "po_reference":   "string - Customer Order No — buyer's PO number (labeled 'Customer Order No.'). NOT a CIN.",
            "so_number":      "string - SO No — Sales Order number (labeled 'SO No.', starts with '1OTM')",
            "customer_name":  "string - Customer Name — name of the customer being billed (the buyer)",
            "total_amount":   "number - Amount — grand total AFTER tax (the LARGEST amount on the invoice)",
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
        "COMPANY_PO": "purchase_bill_no",
        "VENDOR_DC": "dc_number",
        "VENDOR_INVOICE": "invoice_number",
        "COMPANY_DC": "dc_number",
        "COMPANY_INVOICE": "invoice_number",
    }
    return mapping.get(doc_type, "")


def get_date_field(doc_type: str) -> str:
    """Get the date field for a document type."""
    mapping = {
        "CUSTOMER_PO": "po_date",
        "COMPANY_PO": "",
        "VENDOR_DC": "dc_date",
        "VENDOR_INVOICE": "",
        "COMPANY_DC": "",
        "COMPANY_INVOICE": "",
    }
    return mapping.get(doc_type, "")


def get_searchable_fields(doc_type: str) -> list[tuple[str, str]]:
    """Returns (ref_type, field_name) pairs for ReferenceIndex."""
    mapping = {
        "CUSTOMER_PO": [
            ("po_number", "po_number"),
        ],
        "COMPANY_PO": [
            ("purchase_bill_no", "purchase_bill_no"),
            ("po_number", "po_number"),
            ("bill_no", "bill_no"),          # bill_no = vendor invoice number (procurement chain link)
        ],
        "VENDOR_DC": [
            ("dc_number", "dc_number"),
            ("po_reference", "po_reference"),
        ],
        "VENDOR_INVOICE": [
            ("invoice_number", "invoice_number"),
            ("customer_order_no", "customer_order_no"),
            ("po_reference", "po_reference"),
        ],
        "COMPANY_DC": [
            ("dc_number", "dc_number"),
            ("po_reference", "po_reference"),
            ("sales_order_no", "sales_order_no"),
        ],
        "COMPANY_INVOICE": [
            ("invoice_number", "invoice_number"),
            ("po_reference", "po_reference"),
            ("so_number", "so_number"),
        ],
    }
    return mapping.get(doc_type, [])
