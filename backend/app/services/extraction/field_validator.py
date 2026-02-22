"""
Field-level validation and post-processing for extracted document data.

Fixes known RC issues identified in the 28-document analysis:
  RC2 — I vs 1 confusion in invoice/DC numbers
  RC4 — person name incorrectly placed in po_reference
  Amount normalization (currency symbols, Indian comma format)
  Pattern-based confidence scoring
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ── Known number format patterns ─────────────────────────────────────────────

PATTERNS = {
    "dc_number":        re.compile(r"1DNT\d{4}DC\d{4,}"),
    "sales_order_no":   re.compile(r"1OTM\d{4}\d{6,}"),
    "invoice_number":   re.compile(r"1[I1][T][R]\d{4}\d{6,}|1[I1][S][R]\d{4}\d{6,}"),
    "purchase_bill_no": re.compile(r"1PBTR\d{9,}"),
}


# ── RC2 fix: I vs 1 confusion in invoice numbers ────────────────────────────

def fix_invoice_number(value: Optional[str]) -> Optional[str]:
    """Fix OCR confusion between the letter I and the digit 1.

    Examples:
        "11TR2526001841"  → "1ITR2526001841"
        "11SR2526000166"  → "1ISR2526000166"
        "IT12526001748"   → "1ITR2526001748"  (R dropped by OCR)
        "C: 240847449"    → "C240847449"      (label colon included)
    """
    if not value:
        return value

    value = str(value).strip()

    # Pattern: starts with "11TR" or "11SR" — OCR read 'I' as '1'
    value = re.sub(r"^11TR", "1ITR", value)
    value = re.sub(r"^11SR", "1ISR", value)

    # Pattern: starts with "IT1R" or "IT1SR" — OCR swapped '1' and 'I'
    value = re.sub(r"^IT1R", "1ITR", value)
    value = re.sub(r"^IT1SR", "1ISR", value)

    # Pattern: starts with "IT1" followed by a digit — OCR dropped the 'R'
    # "IT12526001748" → "1ITR2526001748"
    value = re.sub(r"^IT1(\d)", r"1ITR\1", value)

    # Lowercase L confusion
    value = re.sub(r"^lITR", "1ITR", value)
    value = re.sub(r"^lISR", "1ISR", value)

    # Strip label-colon prefix: "C: 240847449" → "C240847449"
    # LLM includes label separator when the label is a short uppercase prefix
    value = re.sub(r"^([A-Za-z]{1,5}):\s+(\w)", r"\1\2", value)

    return value


# ── RC2 fix: I vs 1 confusion in DC numbers ─────────────────────────────────

def fix_dc_number(value: Optional[str]) -> Optional[str]:
    """Fix OCR confusion in DC numbers (1DNT prefix).

    Examples:
        "lDNT2526DC2865"  → "1DNT2526DC2865"  (lowercase L)
        "10TN2528DC2865"  → "1DNT2528DC2865"  (D→0, N↔T transposition)
        "10NT2526DC2626"  → "1DNT2526DC2626"  (D→0, N and T stay in place)
        "10N72526DC2626"  → "1DNT2526DC2626"  (D→0, T→7)
    """
    if not value:
        return value

    value = str(value).strip()

    # Common OCR misread: lDNT → 1DNT (lowercase L)
    value = re.sub(r"^lDNT", "1DNT", value)

    # Pattern: "10TN" — OCR read 'D' as '0' and transposed N/T: 1DNT → 10TN
    value = re.sub(r"^10TN", "1DNT", value)

    # Pattern: "10NT" — OCR read 'D' as '0': 1DNT → 10NT (N and T stay in place)
    value = re.sub(r"^10NT", "1DNT", value)

    # Pattern: "10N7" — OCR read 'D' as '0' and 'T' as '7': 1DNT → 10N7
    value = re.sub(r"^10N7", "1DNT", value)

    return value


# ── RC2 fix: O vs 0 confusion in SO numbers ─────────────────────────────────

def fix_so_number(value: Optional[str]) -> Optional[str]:
    """Fix OCR confusion between letter O and digit 0 in SO numbers.

    Examples:
        "10TM2526001596" → "1OTM2526001596"
    """
    if not value:
        return value

    value = str(value).strip()

    # Pattern: starts with "10TM" — OCR read 'O' as '0'
    value = re.sub(r"^10TM", "1OTM", value)

    # Pattern: "1OTMZ" — OCR inserts spurious 'Z' after OTM: 1OTM → 1OTMZ
    value = re.sub(r"^1OTMZ", "1OTM", value)

    return value


# ── RC4 fix: person name in po_reference ─────────────────────────────────────

def fix_po_reference(value: Optional[str]) -> Optional[str]:
    """Fix and validate po_reference field.

    - Strips label-colon prefix: "Our Order: 502812554" → "502812554"
    - Restores Indian FY notation: "BHAS-PO-IT-2025-06-022" → "BHAS-PO-IT-2025/26-022"
    - Rejects person names (has spaces but no digits)
    """
    if not value:
        return value

    clean: str = str(value).strip()

    # Strip "Label: value" if the part before the colon contains only letters/spaces
    # e.g. "Our Order: 502812554" → "502812554", "Your Ref: PO-123" → "PO-123"
    colon_match = re.match(r"^([A-Za-z][A-Za-z\s]*?):\s*(.+)$", clean)
    if colon_match:
        before: str = str(colon_match.group(1))
        after: str = str(colon_match.group(2)).strip()
        if not any(c.isdigit() for c in before):
            logger.info(f"Stripped label prefix from po_reference: '{clean}' → '{after}'")
            clean = after

    # Restore Indian FY notation mangled by OCR:
    # OCR reads "2025/26" as "2025-06" (slash→hyphen, leading "2" of "26" → "0")
    # Only restore if the 2-digit component "0Y" is consistent with a FY suffix:
    #   year YYYY → next year last digit must equal Y
    # Example: "BHAS-PO-IT-2025-06-022" → "2025-06" where 2025+1=2026 last digit=6 ✓
    fy_match = re.search(r"(\d{4})-0(\d)-", clean)
    if fy_match:
        year = int(fy_match.group(1))
        digit = fy_match.group(2)
        if str(year + 1)[-1] == digit:
            next_2 = str(year + 1)[-2:]
            restored = clean[: fy_match.start()] + f"{year}/{next_2}-" + clean[fy_match.end() :]
            logger.info(f"Restored FY notation in po_reference: '{clean}' → '{restored}'")
            clean = restored

    # If it still contains spaces but NO digits → likely a person name
    if " " in clean and not any(char.isdigit() for char in clean):
        logger.info(
            f"Rejected po_reference as likely person name: '{clean}'"
        )
        return None

    return clean


# ── COMPANY_PO fixes: 1PBTR + 1PTR prefix confusion ─────────────────────────

def fix_purchase_bill_no(value: Optional[str]) -> Optional[str]:
    """Fix OCR confusion in purchase bill numbers (1PBTR prefix).

    Examples:
        "1PBT2R252600529"  → "1PBTR252600529"   (spurious 2 inserted before R)
        "1PTR2526000483"   → "1PBTR2526000483"   (OCR drops 'B' entirely)
    """
    if not value:
        return value

    value = str(value).strip()

    # Pattern: spurious digit '2' between 'T' and 'R': 1PBT2R → 1PBTR
    value = re.sub(r"^1PBT2R", "1PBTR", value)

    # Pattern: OCR drops 'B' from prefix: 1PTR → 1PBTR
    # Only match 1PTR followed by a digit (purchase_bill_no has digits after prefix)
    # This won't affect 1PBTR... (next char after PTR is 'B', not a digit)
    value = re.sub(r"^1PTR(\d)", r"1PBTR\1", value)

    return value


def fix_company_po_number(value: Optional[str]) -> Optional[str]:
    """Fix OCR confusion in COMPANY_PO po_number (1PTR prefix).

    Examples:
        "1PFR2526000405"  → "1PTR2526000405"   (OCR reads T as F)
    """
    if not value:
        return value

    value = str(value).strip()

    # Pattern: OCR reads 'T' as 'F': 1PTR → 1PFR
    value = re.sub(r"^1PFR", "1PTR", value)

    return value


# ── Amount normalization ─────────────────────────────────────────────────────

def normalize_amount(value) -> Optional[float]:
    """Normalize amount values for consistent storage.

    Strips currency symbols, commas (Indian and international format),
    and validates the result as a number.

    Examples:
        "₹ 97,500.00" → 97500.0
        "1,77,000"     → 177000.0   (Indian format)
        86678.5        → 86678.5    (already numeric)
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    value = str(value).strip()

    # Remove currency symbols and whitespace
    value = re.sub(r"[₹$€£\s]", "", value)

    # Remove commas (Indian and international format)
    value = value.replace(",", "")

    # Validate it is a number
    try:
        return float(value)
    except ValueError:
        return None


# ── Main validation entrypoint ───────────────────────────────────────────────

def validate_extracted_fields(fields: dict, doc_type: str) -> dict:
    """Apply all validation and fixes to extracted fields.

    Returns the cleaned fields dict with a ``_validation`` key
    containing a report of any corrections or flags.
    """
    if not fields:
        return {}

    result = dict(fields)
    confidence = {}

    # ── RC2: Fix invoice numbers ─────────────────────────────────────────
    if "invoice_number" in result:
        original = result["invoice_number"]
        result["invoice_number"] = fix_invoice_number(result["invoice_number"])
        if result["invoice_number"] != original:
            confidence["invoice_number"] = "CORRECTED"

    # ── RC2: Fix DC numbers ──────────────────────────────────────────────
    if "dc_number" in result:
        original = result["dc_number"]
        result["dc_number"] = fix_dc_number(result["dc_number"])
        if result["dc_number"] != original:
            confidence["dc_number"] = "CORRECTED"

    # ── RC2: Fix SO/Sales Order numbers ─────────────────────────────────
    for so_field in ("so_number", "sales_order_no"):
        if so_field in result:
            original = result[so_field]
            result[so_field] = fix_so_number(result[so_field])
            if result[so_field] != original:
                confidence[so_field] = "CORRECTED"

    # ── COMPANY_PO: Fix purchase bill number ─────────────────────────────
    if doc_type == "COMPANY_PO" and "purchase_bill_no" in result:
        original = result["purchase_bill_no"]
        result["purchase_bill_no"] = fix_purchase_bill_no(result["purchase_bill_no"])
        if result["purchase_bill_no"] != original:
            confidence["purchase_bill_no"] = "CORRECTED"

    # ── COMPANY_PO: Fix PO number prefix ─────────────────────────────────
    if doc_type == "COMPANY_PO" and "po_number" in result:
        original = result["po_number"]
        result["po_number"] = fix_company_po_number(result["po_number"])
        if result["po_number"] != original:
            confidence["po_number"] = "CORRECTED"

    # ── RC4: Fix PO references ───────────────────────────────────────────
    if "po_reference" in result:
        original = result["po_reference"]
        result["po_reference"] = fix_po_reference(result["po_reference"])
        if result["po_reference"] is None and original is not None:
            confidence["po_reference"] = "REJECTED_PERSON_NAME"
            result["_po_reference_rejected"] = original

    # ── Normalize amounts ────────────────────────────────────────────────
    amount_fields = (
        "total_amount", "subtotal", "tax_amount", "est_amount",
        "grand_total", "unit_rate",
    )
    for field in amount_fields:
        if field in result and result[field] is not None:
            original = result[field]
            normalized = normalize_amount(result[field])
            if normalized is not None:
                result[field] = normalized
            else:
                confidence[field] = "AMOUNT_PARSE_FAILED"
                result[f"_{field}_raw"] = original

    # ── Pattern-based confidence scoring ─────────────────────────────────
    for field, pattern in PATTERNS.items():
        if field in result and result[field]:
            value = str(result[field])
            if not pattern.search(value):
                if field not in confidence:
                    confidence[field] = "LOW_CONFIDENCE"

    # ── Attach validation report ─────────────────────────────────────────
    if confidence:
        result["_validation"] = confidence

    return result
