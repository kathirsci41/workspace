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
This is our STANDARD COMPANY DELIVERY CHALLAN layout. Prioritize exact label mapping.
1. dc_number = value from "DC No." or "DC Number" and usually starts with "1DNT".
2. dc_date = value from "DC Date" only.
3. po_reference = value from "Customer Order No." only (example: "IGKPO/106399/2526").
    po_reference is NEVER a date, NEVER a person name, and NEVER GST/CIN.
4. so_number = value from "Sales Order No." or "SO No." and usually starts with "1OTM".
    Do not confuse so_number with dc_number.
5. Ignore any field labeled "Reference" when extracting po_reference. "Reference" is usually a person/contact.
6. delivery_address = customer ship-to block (labels like "Delivery To", "Ship To", "Consignee").
7. billing_address = customer billing block (labels like "Customer's Billing Address", "Bill To").
8. order_items MUST be a JSON array with one object per visible row.
    Keep row order exactly as printed. Do not merge adjacent rows.
    If serial numbers are printed inside description text, keep them in description.
9. If the same header field appears multiple times, pick the clearest complete value (no truncation).
10. If a required value is not explicitly printed, return null. Do not infer.
""",

    "COMPANY_INVOICE": """
CRITICAL EXTRACTION RULES:
This is our STANDARD COMPANY INVOICE layout. Use strict label-to-field mapping.
1. invoice_number = value from "Invoice No." only. Usually starts with "1ITR" (product) or "1ISR" (service).
2. If OCR reads "11TR", "IT1R", "11SR", or "IT1SR", treat as "1ITR" or "1ISR".
3. so_number = value from "SO No." only. Usually starts with "1OTM".
    If OCR reads "10TM", treat as "1OTM".
4. po_reference = value from "Customer Order No." only.
    It may contain slashes, hyphens, spaces, and letters. It is NOT a CIN/GSTIN.
5. customer_name = billed customer name (buyer). Do not use our company name as customer_name.
6. invoice_date = value from "Invoice Date" only. invoice_due_date = value from "Invoice Due Date" only.
7. taxable_amount = pre-tax amount (labels like "Nett Amount", "Total Value", "Taxable Amount").
8. tax_amount = total tax paid (IGST, or CGST+SGST combined). Return one combined number.
9. total_amount = final grand total after tax. Prefer the explicit final total field over any computed subtotal.
10. dc_reference = DC number linked on the invoice (labels like "DC No", "DC Ref", "Delivery Challan"). null if missing.
11. coverage_period = service period only for AMC/service invoices; otherwise null.
12. order_items MUST be a JSON array with one object per printed row. Keep order as printed.
13. If header fields appear on one combined line, split by labels and map each label to the correct field.
14. If a value is not explicitly printed, return null. Do not infer.
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
This is our STANDARD COMPANY PURCHASE ORDER layout. Use exact label-driven extraction.
1. po_number = our issued PO number from "Order No." or "PO No." and usually starts with "1PTR".
2. po_date = value from "Order Date" or "PO Date" only.
3. vendor_name = supplier name in the vendor/supplier block (labels like "Supplier", "Vendor", "M/s", "To").
    Do not use customer names, ship-to names, or consignee names as vendor_name.
4. vendor_gstin = 15-character GSTIN from vendor address block only.
5. delivery_due_date = value from "Delivery Due Date" only.
6. delivery_address = shipping location block (labels like "Shipping Location", "Delivery Address", "Ship To").
7. total_amount = pre-tax net amount from footer total (prefer labels "Net Amount" or equivalent pre-tax total).
    Do NOT use per-row totals and do NOT use post-tax grand total when both are present.
8. payment_terms = payment condition text from terms/footer section.
9. order_items MUST be a JSON array with one object per printed row.
    Required keys per object: sr_no, part_no, description, hsn_code, qty, uom, unit_price, total_price, serial_numbers.
    Keep row order exactly as printed. Do not merge or split rows unless clearly separated in the table.
10. If multi-page, extract header fields from the first complete header occurrence and aggregate all item rows across pages.
11. If any value is missing or unclear, return null. Do not infer.
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


# ── Per-vendor invoice extraction templates ───────────────────────────────────
# Keys are case-insensitive substrings of the vendor name.
# Values are vendor-specific layout hints injected into the extraction prompt.
# Auto-detected from the first 500 chars of the document when no hint is given.
# Add a new entry whenever a new vendor template is encountered.

VENDOR_INVOICE_TEMPLATES: dict[str, str] = {

    "REDINGTON": """
VENDOR-SPECIFIC LAYOUT — REDINGTON LIMITED:

HEADER (page 1 of the invoice):
- invoice_number    : value after "Invoice :" label (e.g. "C190224826"). NOT "Our Order :".
- invoice_date      : value after "Invoice date :" label (e.g. "12.01.2026").
                      NOTE: "Date :" (without "Invoice") is the ORDER PLACEMENT date — ignore it.
- vendor_name       : always "REDINGTON LIMITED".
- customer_order_no : value after "Our Order :" — Redington's own numeric order reference.
- po_reference      : value after "Your Ref. :" — our PO reference (starts with "1PTR").

ITEMS TABLE — MERGED CELL FORMAT:
The PDF has multiple rows per item, but the text parser collapses all items into a SINGLE
table row where each column cell contains ALL items concatenated together. You must parse
each cell and align items by their position.

CRITICAL — IGNORE BOILERPLATE TEXT IN CELLS:
The cells also contain fragments of a disclaimer note that appears next to the table.
These fragments start with phrases like "NOTE:", "Interest rate against", "Certified that",
"Please scan the QR code", or contain phone numbers, legal text, or URLs.
COMPLETELY IGNORE any text from "NOTE:" onwards within any cell. It is NOT item data.
Phone number fragments like "480000", "44", "044" appearing in cells are NOT prices or qtys.

HOW TO COUNT ITEMS:
  Count the number of "[decimal] EA" patterns in the UNIT PRICE cell (ignoring NOTE text).
  Each "[decimal] EA" = one product item. One trailing decimal without "EA" = freight line.
  Examples:
    "194400.00 EA 231000.00 EA 388.80 NOTE:..."  → 2 product items + 1 freight
    "4563.22 EA 150.00 se.14 of this..."         → 1 product item  + 1 freight

UNIT PRICE cell (most reliable column — parse this first to count items):
  The only valid prices are decimal numbers (with optional comma thousands separator)
  that are followed immediately by "EA", or the final decimal number before any NOTE text.
  Pattern: "[price1] EA [price2] EA ... [freight_price] [NOTE text to ignore]"
  unit_price for item N = the N-th decimal number before an "EA" in this cell.
  freight unit_price    = the decimal number after the last "EA" and before any NOTE text.
  Example: "194400.00 EA 231000.00 EA 388.80"  → item1=194400.00, item2=231000.00, freight=388.80
  Example: "4,563.22 EA 150.00 se.14..."       → item1=4563.22, freight=150.00
  RULE: Remove commas from prices (4,563.22 → 4563.22). Phone numbers like 480000 are NOT prices.

ITEM CODE/DESCRIPTION cell:
  Product item codes are SHORT (6–10 char) UPPERCASE letter+digit tokens, e.g. FORTSH7047, FOSSHW0427.
  Any short all-uppercase alphanumeric token appearing mid-cell is a NEW ITEM CODE —
  it is NOT part of the previous item's description.
  After each item code: product description, then optional serial numbers (e.g. "NDKDL1U,NDLEFAU").
  Freight lines: labeled "Freight Charge" or "Outstation Freight", no item code (part_no=null).
  Example cell: "FORTSH7047 FG-120G-HW-APP FG-120G FORTSD0935 FC-10-F120G-284-02-60 SUPPORT Freight Charg..."
    → Item1: part_no="FORTSH7047", description="FG-120G-HW-APP FG-120G"
    → Item2: part_no="FORTSD0935", description="FC-10-F120G-284-02-60 SUPPORT FC-10-F120G-284-02-60"
    → Freight: part_no=null, description="Freight Charge"

HSN/SAC cell:
  Contains one HSN code per product item and one SAC code for freight, separated by spaces.
  Example: "851769 998713 996749" → item1_hsn="851769", item2_hsn="998713", freight_hsn="996749"
  Ignore any non-numeric fragments mixed in (e.g. "ht(SAC", "rdue payments").

QUANTITY cell:
  Contains one decimal number per product item (NOT freight), then NOTE text to ignore.
  Example: "1.000 1.000 NOTE:..." → item1_qty=1.0, item2_qty=1.0
  Example: "2.000 entioned in..."  → item1_qty=2.0
  freight qty = null always.

TOTAL cell:
  Each product item contributes TWO consecutive numbers: [pre-tax subtotal] [after-tax subtotal].
  Freight contributes ONE number at the end (after-tax freight total).
  "Vol Wt", "Total Wt" text is from the WEIGHT column — completely ignore it.
  Use the FIRST of the two values for each product as total_price; freight's single value as its total_price.
  Example: "194400.00 229392.00 231000.00 272580.00 Vol Wt 458.78"
    → item1_total=194400.00, item2_total=231000.00, freight_total=458.78
  Example: "9126.44 10769.20 Vol Wt 177.00"
    → item1_total=9126.44, freight_total=177.00

FOOTER (after items table, before "TERMS AND CONDITIONS"):
- taxable_amount : labeled "Total before Tax" — number, no commas (e.g. 425788.80)
- tax_amount     : labeled "Tax Total" — SGST+CGST already combined (e.g. 76641.98)
- total_amount   : labeled "Invoice Total" — number, no commas (e.g. 502430.78)

STOP reading items at the "NOTE:" line. Ignore all "TERMS AND CONDITIONS OF SALE" pages.
""",

}


def _match_vendor_template(hint: str, markdown_text: str = "") -> str | None:
    """Return vendor-specific extraction hints for VENDOR_INVOICE/VENDOR_DC.

    Tries explicit hint first. Falls back to auto-detecting vendor name from
    the first 500 characters of the document text.
    """
    if hint:
        hint_upper = hint.upper()
        for key, template in VENDOR_INVOICE_TEMPLATES.items():
            if key.upper() in hint_upper:
                return template
    if markdown_text:
        preview = markdown_text[:500].upper()
        for key, template in VENDOR_INVOICE_TEMPLATES.items():
            if key.upper() in preview:
                return template
    return None


# ── Per-customer delivery table schemas ──────────────────────────────────────
# Keys are case-insensitive substrings of the customer name (po.customer.name).
# Values are column names in the EXACT left-to-right order they appear in the
# customer's standard PO template.
# Add a new entry whenever a new customer template is encountered.

CUSTOMER_DELIVERY_SCHEMAS: dict[str, list[str]] = {
    # Column order matches the summary delivery table on page 1 of the Shriram Finance PO.
    # (The detailed table on later pages shows Region first, but GLM-OCR reads the summary first.)
    "SHRIRAM FINANCE": [
        "qty", "unit", "branch", "region", "gstin_no", "contact_no",
        "employee_code", "employee_name", "contact_person",
        "delivery_address", "asset_description",
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

    # Inject vendor-specific layout hints for VENDOR_INVOICE
    # Auto-detects vendor from document text when no explicit hint is given
    if doc_type in ("VENDOR_INVOICE", "VENDOR_DC"):
        vendor_template = _match_vendor_template(customer_hint, markdown_text)
        if vendor_template:
            anti_confusion = anti_confusion + vendor_template

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
                f"    Numeric columns (qty): numbers without commas. If no delivery table found, return [].\n"
                f"    FIELD TYPE HINTS (use these to self-correct if OCR merged adjacent cells):\n"
                f"      gstin_no = 15-character GSTIN code (e.g. '36AAACS7018R1ZU'). NEVER a short number.\n"
                f"      employee_code = short numeric ID (e.g. '13171'). NEVER a person's name.\n"
                f"      employee_name / contact_person = person's full name (e.g. 'PHANIKRISHNA V'). NEVER a phone number.\n"
                f"      contact_no = 10-digit phone number. NEVER a name.\n"
                f"      branch = branch name or region code (e.g. 'HYDERABAD ZONE'). If a GSTIN-looking value appears here, move it to gstin_no instead.",
            )

    return f"""You are a business document data extraction assistant.
Your job is to extract specific fields from the document text provided.

Document Type: {doc_type}

{anti_confusion}

Fields to extract:
{field_lines}

Rules:
- Return ONLY a valid JSON object — no explanation, no markdown fences, no extra text
- For each SCALAR field (string or number), return an object with "value" and "confidence":
    "po_number": {{"value": "PO-2024-123", "confidence": 0.97}}
  confidence is 0.0–1.0: how certain you are the extracted value is correct.
    1.0 = printed clearly and unambiguously
    0.7 = partially obscured or requires interpretation
    0.4 = guessed or inferred from context
    0.1 = very uncertain
- For ARRAY fields (order_items, delivery_locations), return the array directly — NO confidence wrapper
- If a scalar field is not present in the document, set it to null (not a confidence object)
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
