"""Document-type-specific OCR prompts and field mappings."""

SYSTEM_PROMPT = (
    "You are a document OCR extraction system for Indian logistics and IT distribution documents. "
    "Extract the requested fields from the document image. "
    "Return ONLY valid JSON with no markdown, no code blocks, no explanation. "
    "If a field cannot be found, use null.\n\n"
    "RULES:\n"
    "1. For ALL amounts/numbers: NEVER use commas. Write 6087800.00 NOT 6,087,800.00\n"
    "2. For dates: write EXACTLY as printed on document (e.g. 18/12/2025). Do NOT reformat.\n"
    "3. For order_items: ALWAYS return a JSON array of objects. Each object MUST have keys: "
    "sr_no, part_no, description, hsn_code, qty, uom, unit_price, total_price, serial_numbers. "
    "Use null for any key not present. If no items table, return [].\n"
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
            "The PO number is the reference number at the top of the document. "
            "The issuing company (bsif_name) is the customer who sent us this PO — NOT Skylark. "
            "The quotation reference appears in the body text ('As per your quotation no X dated Y'). "
            "order_items MUST be a JSON array of objects with keys: sr_no, description, qty, unit_price, total_price."
        ),
        "schema": {
            "po_number":             "string - PO No — purchase order reference number at top of document",
            "po_date":               "string - PO Date — date exactly as printed on document",
            "bsif_name":             "string - Issuer/Customer Name — company that issued this PO (the buyer)",
            "quotation_no":          "string - Quotation No — from body text 'As per your quotation no [X]'",
            "quotation_date":        "string - Quotation Date — date from the same quotation reference sentence",
            "order_items":           "array - Line items table. JSON array of objects: {sr_no, description, qty, unit_price, total_price}",
            "grand_total":           "number - Grand Total labeled line below the items table, no commas. Use only the Grand Total label — do NOT sum column totals (they are already included in the Grand Total)",
            "terms_and_conditions":  "string - Full Terms and Conditions block (payment, warranty, delivery, invoice requirements)",
            "delivery_details":      "string - Delivery timeframe and invoice instructions from the T&C page",
            "delivery_locations":    "array - Delivery Locations table. JSON array of objects where KEYS come from the actual column headers in the table (lowercased, spaces replaced with underscores). Each row becomes one object. Qty fields must be numbers.",
        },
    },
    "COMPANY_PO": {
        "instruction": (
            "Extract details from this Purchase Order issued by our company (Skylark) to a vendor/supplier. "
            "The Order No is the main reference number (starts with '1PTR'). "
            "The vendor is the supplier receiving this PO. "
            "order_items MUST be a JSON array of objects."
        ),
        "schema": {
            "po_number":         "string - Order No — our company's PO number issued to the vendor (starts with '1PTR')",
            "po_date":           "string - Order Date — date exactly as printed on document",
            "mode_of_bill":      "string - Mode of Bill — billing condition (e.g. ON FULL DELIVERY)",
            "vendor_name":       "string - Vendor Name — name of the supplier/vendor this PO is sent to",
            "order_items":       "array - Line items table. JSON array of objects: {sr_no, part_no, description, hsn_code, qty, uom, unit_price, total_price, serial_numbers}",
            "total_amount":      "number - Net Amount — pre-tax total labeled 'Net Amount' in footer, no commas",
            "vendor_gstin":      "string - Vendor GSTIN — 15-character GST number from vendor's address block",
            "delivery_due_date": "string - Delivery Due Date — date by which vendor must deliver",
            "delivery_address":  "string - Delivery Address — shipping/delivery location",
            "payment_terms":     "string - Payment Terms — from Terms & Conditions block",
        },
    },
    "VENDOR_DC": {
        "instruction": (
            "Extract delivery challan details from this vendor DC document. "
            "The DC number is the main reference number on the challan. "
            "The vendor is the company SENDING the goods. "
            "order_items MUST be a JSON array of objects."
        ),
        "schema": {
            "dc_number":        "string - Delivery Challan number (main reference, e.g. 1DNT2526DC2865)",
            "dc_date":          "string - DC date exactly as printed",
            "po_reference":     "string - Purchase Order number this DC fulfills (alphanumeric code like 1PTR2526000405, NOT a person name)",
            "vendor_name":      "string - Name of the vendor/supplier sending goods",
            "order_items":      "array - Line items table. JSON array of objects: {sr_no, part_no, description, hsn_code, qty, uom, unit_price (null), total_price (null), serial_numbers}",
            "delivery_address": "string - Ship To / Delivery To address printed on this DC",
            "vehicle_number":   "string - Vehicle or transport number",
            "receiver_name":    "string - Name of person who physically received the goods (with signature)",
        },
    },
    "VENDOR_INVOICE": {
        "instruction": (
            "Extract invoice/bill details from this vendor or supplier document. "
            "The vendor is the company that ISSUED this invoice or purchase bill (the seller). "
            "Look carefully at the header area for invoice number, bill number, and date. "
            "order_items MUST be a JSON array of objects."
        ),
        "schema": {
            "invoice_number":    "string - Invoice No — vendor's invoice/bill number (labeled 'Invoice No.', 'Tax Invoice No.', or 'Bill No.')",
            "invoice_date":      "string - Invoice Date — date the invoice was issued, exactly as printed",
            "vendor_name":       "string - Vendor Name — company that issued this invoice (the seller/supplier)",
            "customer_order_no": "string - Vendor's own internal reference (labeled 'Our Order' in Redington, or 'Customer Order No.' in others). Different from po_reference.",
            "po_reference":      "string - Our company's PO reference as seen by the vendor (labeled 'Your Ref.', 'PO Ref:', 'Buyer Order No.'). NOT a CIN.",
            "order_items":       "array - Line items table. JSON array of objects: {sr_no, part_no, description, hsn_code, qty, uom, unit_price, total_price, serial_numbers}",
            "total_amount":      "number - Grand Total — total after all taxes, no commas",
            "taxable_amount":    "number - Taxable Amount — pre-tax total (labeled 'Total Taxable Value', 'Subtotal', or 'Net Amount'), no commas",
            "tax_amount":        "number - Total Tax — IGST alone OR CGST+SGST combined, no commas",
        },
    },
    "COMPANY_DC": {
        "instruction": (
            "Extract delivery challan details from this company dispatch document. "
            "This is a NON RETURNABLE DELIVERY CHALLAN issued by the company to dispatch goods to a customer. "
            "The DC number is the main reference number on the challan. "
            "IMPORTANT: 'Customer Order No.' is the customer's Purchase Order number (po_reference). "
            "'Reference' is a person name — do NOT use it as po_reference. "
            "order_items MUST be a JSON array of objects."
        ),
        "schema": {
            "dc_number":        "string - DC No — Delivery Challan number (labeled 'DC No.', e.g. 1DNT2526DC2871)",
            "dc_date":          "string - DC Date — date of dispatch exactly as printed (labeled 'DC Date')",
            "po_reference":     "string - Customer Order No — customer's PO number (labeled 'Customer Order No.', NOT a date, NOT a person name)",
            "so_number":        "string - Sales Order No (labeled 'Sales Order No.', starts with '1OTM')",
            "delivery_address": "string - Delivery To — customer delivery address or name (labeled 'Delivery To')",
            "billing_address":  "string - Customer's Billing Address block (labeled 'Customer's Billing Address' or 'Bill To')",
            "order_items":      "array - Line items table. JSON array of objects: {sr_no, part_no, description, hsn_code, qty, uom, unit_price, total_price, serial_numbers}",
            "total_amount":     "number - Total — sum of all line amounts in footer, no commas",
        },
    },
    "COMPANY_INVOICE": {
        "instruction": (
            "Extract invoice details from this company-issued TAX INVOICE. "
            "This company is the SELLER issuing the invoice. "
            "The customer is the BUYER being billed. "
            "IMPORTANT: 'Customer Order No.' is the buyer's Purchase Order number (po_reference). "
            "'SO No.' is the Sales Order number. "
            "order_items MUST be a JSON array of objects."
        ),
        "schema": {
            "invoice_number":   "string - Invoice No (labeled 'Invoice No.', starts with '1ITR' or '1ISR')",
            "invoice_date":     "string - Invoice Date — date the invoice was issued, exactly as printed",
            "invoice_due_date": "string - Invoice Due Date — payment due date (labeled 'Invoice Due Date')",
            "po_reference":     "string - Customer Order No — buyer's PO number (labeled 'Customer Order No.'). NOT a CIN.",
            "so_number":        "string - SO No — Sales Order number (labeled 'SO No.', starts with '1OTM')",
            "customer_name":    "string - Customer Name — name of the customer being billed (the buyer)",
            "order_items":      "array - Line items table. JSON array of objects: {sr_no, part_no, description, hsn_code, qty, uom, unit_price, total_price, serial_numbers}",
            "total_amount":     "number - Total Amount — grand total AFTER tax (the LARGEST amount on the invoice), no commas",
            "taxable_amount":   "number - Taxable Amount — pre-tax total (labeled 'Nett Amount', 'Total Value', or 'Taxable Amount'), no commas",
            "tax_amount":       "number - Total Tax — SGST+CGST sum or labeled 'Tax Amount', no commas",
            "dc_reference":     "string - DC Reference — DC number printed on this invoice (e.g. 'DC No: 1DNT2526DC2986'). null if not printed.",
            "coverage_period":  "string - Coverage Period — service/AMC period (e.g. '23/11/2025 to 22/11/2026'). null for trade invoices.",
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
        "COMPANY_PO": "po_number",
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
        "COMPANY_PO": "po_date",
        "VENDOR_DC": "dc_date",
        "VENDOR_INVOICE": "",
        "COMPANY_DC": "dc_date",
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
            ("po_number", "po_number"),
            ("vendor_name", "vendor_name"),
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
            ("so_number", "so_number"),
        ],
        "COMPANY_INVOICE": [
            ("invoice_number", "invoice_number"),
            ("po_reference", "po_reference"),
            ("so_number", "so_number"),
        ],
    }
    return mapping.get(doc_type, [])
