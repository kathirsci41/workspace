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
4. sales_order_no starts with "1OTM" — do not confuse with dc_number which starts with "1DNT"
5. dispatch_to is the customer's delivery address or name (labeled "Delivery To")
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
""",

    "VENDOR_DC": """
CRITICAL EXTRACTION RULES:
1. dc_number is the vendor's Delivery Challan number
2. vendor_name is the company that ISSUED this DC (the sender/supplier at the top of the document)
3. po_reference is OUR Purchase Order number the vendor is fulfilling — look for "PO No." or "Order Ref"
4. po_reference is an alphanumeric code, NOT a person name
5. receiver_name is the name or signature of the person who RECEIVED and signed for the goods
""",

    "CUSTOMER_PO": """
CRITICAL EXTRACTION RULES:
1. po_number is the customer's purchase order or work order reference number
   It may be labeled: 'PO No.', 'Ref No.', 'Ref No/', 'Reference No.', 'Work Order No.', 'Order No.'
   Example: "Ref No/323-24/White HO/AI" → po_number = "323-24/White HO/AI"
   Look for an alphanumeric code with slashes or hyphens near the top or date line
2. bsif_name is the company/organization name at the TOP of the document — the entity that issued it
3. po_date is the date the PO or work order was issued — may appear on the same line as po_number
""",

    "COMPANY_PO": """
CRITICAL EXTRACTION RULES:
1. purchase_bill_no is labeled 'Purchase Bill No.' — this is the bill number from the vendor TO us
2. po_number is labeled 'PO No.' — this is OUR company's PO number issued to the vendor
3. bill_no is labeled 'Bill No.' — the vendor's own internal bill/invoice reference
4. All three numbers appear in the document header — look for their exact labels
5. purchase_bill_no and po_number are ALWAYS different values — if they appear the same,
   you may have read the same field twice; carefully distinguish between 'Purchase Bill No.' and 'PO No.'
""",
}


# ── Layer 2: Extraction schemas per document type ────────────────────────────
# Field names MUST match the existing schemas in prompts.py exactly,
# so DocumentMetadata indexed columns and ReferenceIndex continue working.

EXTRACTION_SCHEMAS = {

    "CUSTOMER_PO": {
        "po_number":  "PO No or Ref No — the purchase order / work order reference number. May be labeled 'PO No.', 'Ref No.', 'Ref No/', 'Work Order No.'",
        "po_date":    "PO Date — date exactly as printed on document",
        "bsif_name":  "BSIF Name — business/company name on the document header (the issuing entity)",
    },

    "COMPANY_PO": {
        "purchase_bill_no": "Purchase Bill No — labeled 'Purchase Bill No.' in the document header",
        "po_number":        "PO No — labeled 'PO No.' in the document header (different from purchase_bill_no)",
        "bill_no":          "Bill No — labeled 'Bill No.' — vendor's own bill/invoice reference",
    },

    "VENDOR_DC": {
        "dc_number":         "Delivery Challan number (main reference, e.g. 1DNT2526DC2865)",
        "dc_date":           "DC date exactly as printed",
        "po_reference":      "Purchase Order number this DC fulfills (alphanumeric code, NOT a person name)",
        "vendor_name":       "Name of the vendor/supplier sending goods",
        "items_description": "All items as ONE string separated by semicolons, include part numbers and serial numbers",
        "quantity":          "Total quantity of items shipped",
        "vehicle_number":    "Vehicle or transport number",
        "receiver_name":     "Name of person who physically received the goods (with signature)",
    },

    "VENDOR_INVOICE": {
        "invoice_number":    "Invoice No — vendor's invoice number (labeled 'Invoice No.', 'Invoice', 'Bill No.'). "
                             "Extract ONLY the alphanumeric code — never include label text or colon separators.",
        "customer_order_no": "Vendor's own internal reference (labeled 'Our Order' in Redington invoices, "
                             "or 'Customer Order No.' in Savex/other invoices). This is the VENDOR'S order.",
        "po_reference":      "Our company's PO reference as seen by the vendor. "
                             "Labeled 'Your Ref.' or 'Your Ref' (Redington) or 'PO Ref:' or 'PO Ref' (Savex). "
                             "Extract ONLY the alphanumeric value. "
                             "NEVER use the 'Our Order' value — that is the vendor's own internal order.",
    },

    "COMPANY_DC": {
        "dc_number":      "DC No — Delivery Challan number (labeled 'DC No.', e.g. 1DNT2526DC2871)",
        "dc_date":        "DC Date — date of dispatch exactly as printed (labeled 'DC Date', e.g. 30/01/2026). NEVER put a date into po_reference.",
        "po_reference":   "Customer Order No — customer's PO number (labeled 'Customer Order No.', e.g. IGKPO/106399/2526). NOT a date. NOT a person name.",
        "sales_order_no": "Sales Order No (labeled 'Sales Order No.', starts with '1OTM')",
        "dispatch_to":    "Delivery To — customer address or name (labeled 'Delivery To')",
    },

    "COMPANY_INVOICE": {
        "invoice_number": "Invoice No (labeled 'Invoice No.', starts with '1ITR' or '1ISR')",
        "po_reference":   "Customer Order No — customer's PO number (labeled 'Customer Order No.'). NOT a CIN.",
        "so_number":      "SO No — Sales Order number (labeled 'SO No.', starts with '1OTM')",
        "customer_name":  "Customer Name — name of the customer being billed (the buyer)",
        "total_amount":   "Amount — grand total AFTER tax (the LARGEST amount on the invoice)",
    },

}


def build_extraction_prompt(doc_type: str, markdown_text: str) -> str:
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
- For items_description: return ONE string with all items separated by semicolons. NEVER return an array.
- Do not calculate or infer values — only extract what is explicitly written

Document text:
---
{markdown_text}
---

JSON:"""


def get_ocr_prompt(doc_type: str) -> str:
    """Get the GLM-OCR Layer 1 prompt for a document type."""
    return GLM_OCR_PROMPT.get(doc_type, DEFAULT_OCR_PROMPT)
