"""
Invoice math and business rule validation.

Runs after field extraction, before persistence.
Catches financial errors before they reach the ERP.
"""
import logging
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# If computed total differs from extracted total by more than this, flag it
MATH_TOLERANCE_PERCENT = 0.5
# Maximum age of a valid invoice date (in years)
MAX_INVOICE_AGE_YEARS = 2


class ValidationResult:
    def __init__(self):
        self.passed = True
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.route = "AUTO_APPROVED"  # AUTO_APPROVED | PENDING_REVIEW | DUPLICATE_FLAGGED

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.passed = False
        self.route = "PENDING_REVIEW"

    def add_warning(self, msg: str):
        self.warnings.append(msg)
        if self.route == "AUTO_APPROVED":
            self.route = "PENDING_REVIEW"

    def __repr__(self):
        return f"ValidationResult(passed={self.passed}, route={self.route}, errors={self.errors})"


def validate_invoice_math(extracted: dict, doc_type: str) -> ValidationResult:
    """
    Validate invoice math and business rules.

    Args:
        extracted: Extracted fields dict from LayoutLMv3 or qwen2.5:7b
        doc_type: Document type string

    Returns:
        ValidationResult with pass/fail and error details
    """
    result = ValidationResult()

    # Math validation only for invoice types with line items
    if doc_type in ("VENDOR_INVOICE", "COMPANY_INVOICE"):
        _validate_math(extracted, result)

    # Date validation for all types
    _validate_date(extracted, result)

    # Amount sanity for all types with total_amount
    _validate_amount_sanity(extracted, result)

    return result


def _validate_math(extracted: dict, result: ValidationResult):
    """Check invoice math: sum(line_items) + tax == total."""
    total_amount = extracted.get("total_amount")
    if total_amount is None:
        result.add_warning("total_amount not extracted - cannot validate math")
        return

    # Look for line items
    line_items = extracted.get("line_items", [])
    if not line_items:
        # No line items extracted yet - skip math check
        # (line items not in current schema, will be added later)
        return

    try:
        total_extracted = float(total_amount)
        computed = 0.0

        for item in line_items:
            qty = float(item.get("quantity", 0) or 0)
            unit_price = float(item.get("unit_price", 0) or 0)
            discount = float(item.get("discount", 0) or 0)
            computed += (qty * unit_price) - discount

        tax = float(extracted.get("tax_amount", 0) or 0)
        computed_total = computed + tax

        if total_extracted == 0:
            result.add_warning("total_amount is 0 - possible extraction error")
            return

        discrepancy_pct = abs(computed_total - total_extracted) / total_extracted * 100

        if discrepancy_pct > MATH_TOLERANCE_PERCENT:
            result.add_error(
                f"Invoice math mismatch: "
                f"computed={computed_total:.2f}, "
                f"extracted={total_extracted:.2f}, "
                f"discrepancy={discrepancy_pct:.1f}%"
            )
        else:
            logger.debug(f"Math validation passed: discrepancy={discrepancy_pct:.2f}%")

    except (ValueError, TypeError) as e:
        result.add_warning(f"Could not validate math: {e}")


def _validate_date(extracted: dict, result: ValidationResult):
    """Validate document date is reasonable."""
    date_fields = ["po_date", "dc_date", "invoice_date", "doc_date"]
    for field in date_fields:
        raw = extracted.get(field)
        if not raw:
            continue

        # Try to parse the date
        parsed = _parse_date_flexible(str(raw))
        if parsed is None:
            result.add_warning(f"{field} could not be parsed: '{raw}'")
            continue

        today = date.today()
        max_age = today - timedelta(days=MAX_INVOICE_AGE_YEARS * 365)

        if parsed > today:
            result.add_error(f"{field} is in the future: {parsed} > {today}")
        elif parsed < max_age:
            result.add_warning(
                f"{field} is very old ({parsed}) - "
                f"more than {MAX_INVOICE_AGE_YEARS} years ago"
            )


def _validate_amount_sanity(extracted: dict, result: ValidationResult):
    """Sanity check for obviously wrong amounts (e.g., OCR comma/period confusion)."""
    total = extracted.get("total_amount")
    if total is None:
        return

    try:
        amount = float(total)
        if amount < 0:
            result.add_error(f"total_amount is negative: {amount}")
        elif amount > 100_000_000:  # 10 crore — likely a parsing error
            result.add_warning(f"total_amount seems very large: {amount} - verify")
        elif amount > 0 and amount < 1:
            result.add_warning(f"total_amount is less than 1: {amount} - possible decimal error")
    except (ValueError, TypeError):
        result.add_warning(f"total_amount is not numeric: {total}")


def _parse_date_flexible(date_str: str) -> Optional[date]:
    """Try multiple date formats."""
    from datetime import datetime
    formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
        "%Y-%m-%d", "%d-%b-%Y", "%d %b %Y",
        "%B %d, %Y", "%d/%m/%y", "%d-%m-%y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None
