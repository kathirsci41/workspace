"""
OCR layer prompts for the two-layer pipeline.

Layer 1 — OCR model converts document image to text.
  Current model: qwen2.5vl:7b (vision-language, /api/chat)
  Fallback:      glm-ocr:latest (specialized OCR, /api/generate)
    GLM-OCR-specific: "<|grounding|>" prefix activates layout-aware mode (tables only).
    "<|grounding|>" is NOT understood by qwen2.5vl — use plain prompts for vision models.

Layer 2 — A separate LLM extracts structured fields from the OCR text.

Do NOT ask Layer 1 to extract JSON or specific fields. That is Layer 2's job.
"""

# ── Layer 1: Per-document-type OCR command ───────────────────────────────────
# Keys match DocumentType enum values used throughout the codebase.
# All prompts use plain text — compatible with both qwen2.5vl and glm-ocr.
# NOTE: "<|grounding|>" was previously used for COMPANY_DC/VENDOR_DC with glm-ocr,
# but it caused header fields to be missed. "Extract the text in the image." is
# correct for all doc types and works with both model families.

GLM_OCR_PROMPT = {
    "COMPANY_DC":      "Extract the text in the image.",
    "VENDOR_DC":       "Extract the text in the image.",
    "COMPANY_INVOICE": "Extract the text in the image.",
    "VENDOR_INVOICE":  "Extract the text in the image.",
    "CUSTOMER_PO":     "Extract the text in the image.",
    "COMPANY_PO":      "Extract the text in the image.",
}

DEFAULT_OCR_PROMPT = "Convert the document to markdown."


# ── Layer 2: Anti-confusion rules per document type ──────────────────────────
# Injected into the extraction prompt to fix known RC issues.

ANTI_CONFUSION_RULES = {

    "COMPANY_DC": """
CRITICAL EXTRACTION RULES:
1. po_reference = the value from the field labeled "Customer Order No." ONLY (e.g. "IGKPO/106399/2526")
   po_reference is NEVER a date — dates like "30/01/2026" belong in dc_date, NOT po_reference
2. dc_date = the value from the field labeled "DC Date" (e.g. "30/01/2026")
3. The field labeled "Reference" contains a PERSON'S NAME — never put it in po_reference
4. so_number starts with "1OTM" — do not confuse with dc_number which starts with "1DNT"
5. delivery_address is the customer's delivery address or name (labeled "Delivery To")
6. billing_address is the customer's billing address block (labeled "Customer's Billing Address" or "Bill To")
7. order_items MUST be a JSON array — one object per row in the items table
   Serial numbers printed inside the description cell should be captured in the description field
""",

    "COMPANY_INVOICE": """
CRITICAL EXTRACTION RULES:
1. invoice_number starts with "1ITR" (product invoices) or "1ISR" (service invoices)
2. If you see "11TR", "IT1R", or "11SR", "IT1SR" — that IS "1ITR" or "1ISR" — OCR confusion between I and 1
3. so_number starts with "1OTM" — if you see "10TM", that IS "1OTM" — OCR confusion between O and 0
   so_number appears labeled "SO No. :" on the header line — always extract it
4. po_reference: Look for the field labeled "Customer Order No." in the document header
   These header fields may appear on ONE combined line or on SEPARATE lines — handle both:
   Combined: "Invoice No. : 1ITR2526001748  Customer Order No. : 323-24/Elite HO/AI  SO No. : 1OTM2526001448"
   Separate:
     Invoice No. : 1ITR2526001789
     Customer Order No. : BHAS-PO-IT-2025/26-022
     SO No. : 1OTM2526001544
   po_reference = the value after "Customer Order No. :" — e.g. "323-24/Elite HO/AI" or "BHAS-PO-IT-2025/26-022"
   so_number = the value after "SO No. :" — e.g. "1OTM2526001544"
   Other examples of po_reference: "IGKPO/106399/2526", "BSIF/059.", "4500174759", "BHAS-PO-IT-2025/26-022"
   ALWAYS extract po_reference — even if it contains words, slashes, hyphens, or spaces
   It is NOT a CIN number (CIN looks like U74999TN1997PTC039039)
5. total_amount is the grand total AFTER tax — the largest amount on the invoice
6. taxable_amount: the pre-tax total labeled "Nett Amount", "Total Value", or "Taxable Amount"
7. tax_amount: sum of all tax lines (SGST + CGST combined, or labeled "Tax Amount"). Return total tax paid.
8. dc_reference: look for any "DC No:" label on the invoice. Extract the DC number (e.g. 1DNT2526DC2986). null if not present.
9. coverage_period: for AMC/service invoices only, extract the service period (e.g. "23/11/2025 to 22/11/2026"). null for product invoices.
10. order_items MUST be a JSON array — one object per row in the items table. Some invoices may have just 1 bundled item — still return an array with 1 object.
""",

    "VENDOR_INVOICE": """
CRITICAL EXTRACTION RULES:
1. invoice_number is the vendor's own invoice number — labeled "Invoice No.", "Invoice", "Bill No."
   Extract ONLY the alphanumeric code value — NEVER include the label or the colon separator
2. customer_order_no is the VENDOR'S OWN internal reference for this order
   Redington format: labeled "Our Order" — this is Redington's internal order number → customer_order_no
   Savex/other format: labeled "Customer Order No." — vendor's internal reference → customer_order_no
3. po_reference is OUR company's reference number as seen by the vendor
   Look for these labels (use the FIRST one found):
   - "Your Ref." or "Your Ref" or "Your Reference" → OUR reference → po_reference
   - "PO Ref:" or "PO Ref" or "PO Reference" → OUR PO number → po_reference
   CRITICAL: "Our Order" = THE VENDOR'S OWN internal order → NEVER use this as po_reference
   Extract ONLY the alphanumeric value — never include the label text
4. NEVER include label text in any extracted value
5. tax_amount: if invoice uses IGST, use the IGST total. If it uses CGST+SGST, ADD them together.
   Return the combined total tax amount — NOT individual rate percentages.
6. taxable_amount: the pre-tax total labeled "Total Taxable Value", "Subtotal", or "Net Amount"
7. order_items MUST be a JSON array — one object per row in the items table
""",

    "VENDOR_DC": """
CRITICAL EXTRACTION RULES:
1. dc_number is the vendor's Delivery Challan number
2. vendor_name is the company that ISSUED this DC (the sender/supplier at the top of the document)
3. po_reference is OUR Purchase Order number the vendor is fulfilling — look for "PO No.", "Order Ref", "Your PO"
4. po_reference is an alphanumeric code, NOT a person name
5. receiver_name is the name or signature of the person who RECEIVED and signed for the goods
6. delivery_address is the "Ship To" or "Delivery To" address printed on this DC
7. order_items MUST be a JSON array — one object per row in the items table
   Different vendors use different column layouts — extract whatever columns are present
   unit_price and total_price are ALWAYS null on delivery challans (DCs carry no prices)
   If part numbers or HSN codes are printed, include them in part_no and hsn_code
""",

    "CUSTOMER_PO": """
CRITICAL EXTRACTION RULES:
1. po_number is the customer's purchase order reference number at the top of the document
   It may be labeled: 'PO No.', 'Ref No.', 'Reference No.', 'Work Order No.', 'Order No.'
   Example: "PWFA260320016" or "Ref No/323-24/White HO/AI" → po_number = "323-24/White HO/AI"
2. po_date is the date the PO was issued — often appears near the top-right (e.g. "20 March 2026")
3. bsif_name is the company name that ISSUED this PO (the customer/buyer)
   It is usually in the footer, header logo area, or signatory block (e.g. "SHRIRAM FINANCE LIMITED")
   Do NOT use Skylark Information Technologies — that is us (the vendor receiving the PO)
4. quotation_no appears in the body text: "As per your quotation no [number] dated [date]"
   Extract only the number part (e.g. "SKY2603-20975")
5. quotation_date is the date inside that same quotation reference sentence (e.g. "14.02.2026")
6. order_items MUST be a JSON array of objects — one object per row in the items table
   Each object must have exactly these keys: sr_no, description, qty, unit_price, total_price
   qty, unit_price, total_price must be numbers with NO commas
   If the table has only one item, still return an array with one object
7. grand_total is the single "Grand Total" value printed below the items table — a number, no commas
   Use ONLY the labeled Grand Total line. Do NOT add up column totals — the Grand Total is already the final sum.
   Example: if the items table shows "872550" in the Total column AND "Grand Total 872550.00" below, grand_total = 872550.0 (not 1745100)
8. terms_and_conditions: extract the full Terms and Conditions block as a single string
   Include payment, warranty, delivery, and invoice requirement terms
9. delivery_details: extract delivery timeframe and invoice requirements from the Terms & Conditions page
   (e.g. "1 Week from date of PO. Location wise Separate Invoice required. Scan copy of DC compulsory.")
10. delivery_locations MUST be a JSON array — extract from the "Delivery Details" table (may span multiple pages)
    STEP 1: Read the column header row of the table. Convert each header to lowercase with underscores (e.g. "Employee Name" → "employee_name", "GSTIN No" → "gstin_no").
    STEP 2: Each data row becomes one JSON object. Use the headers from Step 1 as keys.
    STEP 3: Map each cell strictly to its column — do NOT shift values between columns.
    Numeric columns (qty, amounts): numbers without commas. If no delivery locations table exists, return [].
""",

    "COMPANY_PO": """
CRITICAL EXTRACTION RULES:
1. po_number is OUR company's PO number issued to the vendor — labeled 'Order No.' or 'PO No.', starts with '1PTR' (e.g. 1PTR2526000467)
2. po_date is labeled 'Order Date' or 'PO Date'
3. vendor_name is the name of the supplier/vendor this PO is addressed to
4. total_amount is the pre-tax net amount — labeled 'Net Amount' in the footer. Do NOT use the column total.
5. vendor_gstin is in the vendor's address block — 15-character GST identification number
6. delivery_due_date is labeled 'Delivery Due Date'
7. delivery_address is the shipping/delivery location (labeled 'Shipping Location' or 'Delivery Address')
8. order_items MUST be a JSON array — one object per row in the items table
   Each object: sr_no, part_no (product code), description, hsn_code, qty (number), uom, unit_price (number), total_price (number), serial_numbers (null)
   Use null for any key not present in this document
""",
}


# ── Layer 2: Extraction schemas per document type ────────────────────────────
# Field names MUST match the existing schemas in prompts.py exactly,
# so DocumentMetadata indexed columns and ReferenceIndex continue working.

EXTRACTION_SCHEMAS = {

    "CUSTOMER_PO": {
        "po_number":             "PO No — the customer's purchase order reference number at top of document (e.g. 'PWFA260320016')",
        "po_date":               "PO Date — date exactly as printed (e.g. '20 March 2026')",
        "bsif_name":             "Customer/Issuer Name — company that issued this PO (e.g. 'SHRIRAM FINANCE LIMITED'). NOT Skylark.",
        "quotation_no":          "Quotation No — from body text 'As per your quotation no [X] dated [Y]' — extract the number only",
        "quotation_date":        "Quotation Date — the date in that same quotation reference sentence",
        "order_items":           "Line items — JSON array of objects, each with: sr_no, description, qty (number), unit_price (number), total_price (number)",
        "grand_total":           "Grand Total — total order amount shown below the items table (number, no commas)",
        "terms_and_conditions":  "Terms and Conditions — full T&C block as a single string (payment, warranty, delivery, invoice requirements)",
        "delivery_details":      "Delivery timeframe and invoice instructions from the T&C page (e.g. '1 Week from date of PO. Location wise separate invoice required.')",
        "delivery_locations":    "Delivery Locations — JSON array from the 'Delivery Details' table. Read the actual column header row and use those headers as keys (lowercased, spaces → underscores). Each data row = one object. Numeric fields (qty, amounts) must be numbers without commas.",
    },

    "COMPANY_PO": {
        "po_number":         "Order No — our company's PO number issued to the vendor (starts with '1PTR', e.g. 1PTR2526000467)",
        "po_date":           "Order Date — date exactly as printed on document",
        "mode_of_bill":      "Mode of Bill — billing condition (e.g. 'ON FULL DELIVERY')",
        "vendor_name":       "Vendor Name — name of the supplier/vendor this PO is sent to",
        "order_items":       "Line items — JSON array of objects, each with: sr_no, part_no (product code or null), description, hsn_code (or null), qty (number), uom (or null), unit_price (number or null), total_price (number or null), serial_numbers (null)",
        "total_amount":      "Net Amount — pre-tax total labeled 'Net Amount' in the footer (number, no commas). NOT the column total.",
        "vendor_gstin":      "Vendor GSTIN — 15-character GST number from the vendor's address block",
        "delivery_due_date": "Delivery Due Date — date by which vendor must deliver (labeled 'Delivery Due Date')",
        "delivery_address":  "Delivery Address — shipping/delivery location (labeled 'Shipping Location' or 'Delivery Address')",
        "payment_terms":     "Payment Terms — payment conditions from the Terms & Conditions block",
    },

    "VENDOR_DC": {
        "dc_number":        "Delivery Challan number — vendor's DC reference number",
        "dc_date":          "DC date exactly as printed",
        "po_reference":     "Our Purchase Order number this DC fulfills (alphanumeric code, NOT a person name). Look for 'PO No.', 'Order Ref', 'Your PO'.",
        "vendor_name":      "Name of the vendor/supplier that issued this DC (sender/supplier at top of document)",
        "order_items":      "Line items — JSON array of objects from the items table. Each object: sr_no (or null), part_no (or null), description, hsn_code (or null), qty (number), uom (or null), unit_price (null — DCs have no prices), total_price (null — DCs have no prices), serial_numbers (string or null)",
        "delivery_address": "Ship To / Delivery To — the delivery address printed on this DC",
        "vehicle_number":   "Vehicle or transport number (truck/courier tracking)",
        "receiver_name":    "Name of person who physically received and signed for the goods",
    },

    "VENDOR_INVOICE": {
        "invoice_number":    "Invoice No — vendor's invoice number (labeled 'Invoice No.', 'Invoice', 'Bill No.'). Extract ONLY the alphanumeric code.",
        "invoice_date":      "Invoice Date — date the invoice was issued, exactly as printed",
        "vendor_name":       "Vendor Name — company that issued this invoice (the seller/supplier in the header)",
        "customer_order_no": "Vendor's own internal reference (labeled 'Our Order' in Redington invoices, or 'Customer Order No.' in Savex/other). This is the VENDOR'S own order reference.",
        "po_reference":      "Our company's PO reference as seen by the vendor. Labeled 'Your Ref.' or 'Your Ref' (Redington) or 'PO Ref:' or 'PO Ref' (Savex). Extract ONLY the alphanumeric value. NEVER use 'Our Order'.",
        "order_items":       "Line items — JSON array of objects from the items table. Each object: sr_no (or null), part_no (or null), description, hsn_code (or null), qty (number), uom (or null), unit_price (number or null), total_price (number or null), serial_numbers (string or null)",
        "total_amount":      "Grand Total — total amount after all taxes (the largest amount in the footer). Number, no commas.",
        "taxable_amount":    "Taxable Amount — pre-tax total (labeled 'Total Taxable Value', 'Subtotal', or 'Net Amount'). Number, no commas.",
        "tax_amount":        "Total Tax — IGST alone OR CGST+SGST combined (add them if both present). Number, no commas.",
    },

    "COMPANY_DC": {
        "dc_number":        "DC No — Delivery Challan number (labeled 'DC No.', e.g. 1DNT2526DC2871)",
        "dc_date":          "DC Date — date of dispatch exactly as printed (labeled 'DC Date'). NEVER put a date into po_reference.",
        "po_reference":     "Customer Order No — customer's PO number (labeled 'Customer Order No.', e.g. IGKPO/106399/2526). NOT a date. NOT a person name.",
        "so_number":        "Sales Order No (labeled 'Sales Order No.', starts with '1OTM')",
        "delivery_address": "Delivery To — customer delivery address or name (labeled 'Delivery To')",
        "billing_address":  "Customer's Billing Address — billing address block (labeled 'Customer\\'s Billing Address' or 'Bill To')",
        "order_items":      "Line items — JSON array from the items table. Each object: sr_no (or null), part_no (or null), description (include serial numbers if printed in this cell), hsn_code (or null), qty (number), uom (or null), unit_price (number or null), total_price (number or null), serial_numbers (null)",
        "total_amount":     "Total — sum of all line amounts in the footer (labeled 'Total' or 'Est. Amount Total'). Number, no commas.",
    },

    "COMPANY_INVOICE": {
        "invoice_number":   "Invoice No (labeled 'Invoice No.', starts with '1ITR' or '1ISR')",
        "invoice_date":     "Invoice Date — date the invoice was issued, exactly as printed",
        "invoice_due_date": "Invoice Due Date — payment due date (labeled 'Invoice Due Date')",
        "po_reference":     "Customer Order No — customer's PO number (labeled 'Customer Order No.'). NOT a CIN.",
        "so_number":        "SO No — Sales Order number (labeled 'SO No.', starts with '1OTM')",
        "customer_name":    "Customer Name — name of the customer being billed (the buyer)",
        "order_items":      "Line items — JSON array from the items table. Each object: sr_no (or null), part_no (or null), description, hsn_code (or null), qty (number), uom (or null), unit_price (number or null), total_price (number or null), serial_numbers (string or null). Some invoices have 1 bundled item — still return an array.",
        "total_amount":     "Total Amount — grand total AFTER tax (the largest amount on the invoice). Number, no commas.",
        "taxable_amount":   "Taxable Amount — pre-tax total (labeled 'Nett Amount', 'Total Value', or 'Taxable Amount'). Number, no commas.",
        "tax_amount":       "Total Tax — SGST+CGST sum or labeled 'Tax Amount'. Number, no commas.",
        "dc_reference":     "DC Reference — DC number printed on this invoice (e.g. 'DC No: 1DNT2526DC2986'). null if not printed.",
        "coverage_period":  "Coverage Period — service/AMC period (e.g. '23/11/2025 to 22/11/2026'). null for trade invoices.",
    },

}


# ── Per-customer delivery table schemas ──────────────────────────────────────
# Keys are case-insensitive substrings of the customer name (po.customer.name).
# Values are column names in the EXACT left-to-right order they appear in the
# customer's standard PO template.
# Add a new entry whenever a new customer template is encountered.

CUSTOMER_DELIVERY_SCHEMAS: dict[str, list[str]] = {
    "SHRIRAM FINANCE": [
        "region", "unit", "branch", "gstin_no", "asset_description",
        "qty", "employee_code", "employee_name", "contact_person",
        "contact_no", "delivery_address",
    ],
}


def _match_customer_schema(customer_hint: str) -> list[str] | None:
    """Return the delivery column list for a known customer, or None."""
    hint_upper = customer_hint.upper()
    for key, cols in CUSTOMER_DELIVERY_SCHEMAS.items():
        if key.upper() in hint_upper:
            return cols
    return None


def build_extraction_prompt(doc_type: str, markdown_text: str, customer_hint: str = "") -> str:
    """Build the Layer 2 prompt that the extraction LLM receives.

    Takes the markdown from GLM-OCR Layer 1 and returns a structured
    field extraction prompt for the LLM.
    """
    schema = EXTRACTION_SCHEMAS.get(doc_type, {})
    if not schema:
        return ""

    field_lines = "\n".join(
        f'  "{field}": {description}'
        for field, description in schema.items()
    )

    anti_confusion = ANTI_CONFUSION_RULES.get(doc_type, "")

    # Override delivery_locations rule 10 when we know the customer's exact column layout
    if doc_type == "CUSTOMER_PO" and customer_hint:
        customer_cols = _match_customer_schema(customer_hint)
        if customer_cols:
            col_display = " | ".join(customer_cols)
            anti_confusion = anti_confusion.replace(
                "10. delivery_locations MUST be a JSON array — extract from the \"Delivery Details\" table (may span multiple pages)\n"
                "    STEP 1: Read the column header row of the table. Convert each header to lowercase with underscores (e.g. \"Employee Name\" → \"employee_name\", \"GSTIN No\" → \"gstin_no\").\n"
                "    STEP 2: Each data row becomes one JSON object. Use the headers from Step 1 as keys.\n"
                "    STEP 3: Map each cell strictly to its column — do NOT shift values between columns.\n"
                "    Numeric columns (qty, amounts): numbers without commas. If no delivery locations table exists, return [].",
                f"10. delivery_locations MUST be a JSON array — extract from the \"Delivery Details\" table (may span multiple pages)\n"
                f"    This customer's table has EXACTLY these {len(customer_cols)} columns in this left-to-right order: {col_display}\n"
                f"    Each data row becomes one object with exactly those keys in that order.\n"
                f"    Map each cell strictly to its column — do NOT shift or merge values between columns.\n"
                f"    Numeric columns (qty): numbers without commas. If no delivery table found, return [].",
            )

    return f"""You are a business document data extraction assistant.
Your job is to extract specific fields from the document text provided.

Document Type: {doc_type}

{anti_confusion}

Fields to extract:
{field_lines}

Rules:
- Return ONLY a valid JSON object — no explanation, no markdown fences, no extra text
- If a field is not present in the document, set it to null
- For ALL amounts/numbers: NEVER use commas. Write 6087800.00 NOT 6,087,800.00
- Dates should stay EXACTLY as printed on the document (e.g. 18/12/2025). Do NOT reformat.
- For order_items: ALWAYS return a JSON array of objects. Each object MUST have exactly these keys: sr_no, part_no, description, hsn_code, qty, uom, unit_price, total_price, serial_numbers. Use null for any key not present in the document. Numbers must have NO commas. If no items table found, return [].
- For delivery_locations: return a JSON array of objects. Keys come from the actual column headers in the table (lowercased, spaces → underscores). Map each cell strictly to its column — never shift values. Numeric cells: no commas. If no delivery table found, return [].
- Do not calculate or infer values — only extract what is explicitly written

Document text:
---
{markdown_text}
---

JSON:"""


def get_ocr_prompt(doc_type: str) -> str:
    """Get the GLM-OCR Layer 1 prompt for a document type."""
    return GLM_OCR_PROMPT.get(doc_type, DEFAULT_OCR_PROMPT)
