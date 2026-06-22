from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_SO_PATTERN = r"\b(?:[0-9][A-Z]{2,3}|[A-Z]{2,4})\d{10}\b"
_SO_FAMILY = r"^(?:[0-9]OTM|SOSC)"
_GSTIN_PATTERN = r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b"


def extract_pdf_text_pages(pdf_path: str, max_pages: int = 10) -> list[str]:
    """Return raw text per page using PyMuPDF when available."""
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("PyMuPDF is required for digital PDF extraction.") from exc

    pages: list[str] = []
    with fitz.open(pdf_path) as doc:
        page_count = min(doc.page_count, max_pages)
        logger.info("Digital PDF text probe: path=%s size_pages=%s pages_read=%s", pdf_path, doc.page_count, page_count)
        for index in range(page_count):
            text = doc.load_page(index).get_text("text") or ""
            logger.info("Digital PDF text page: path=%s page=%s raw_text_len=%s", pdf_path, index + 1, len(text.strip()))
            pages.append(text)
    return pages


def normalize_ocr_text(text: str) -> str:
    """
    Repair common OCR spacing artifacts before parsing.
    Applied ONLY to OCR-routed text, never to clean digital text.
    """
    out = text
    # 1. Join digit groups split by single spaces: "4 63 365.55" -> "463365.55"
    out = re.sub(r"(?<!\.\d{2})(?<=\d) (?=\d)", "", out)
    # 2. Remove spaces around code separators: "PMCH &RI /024" -> "PMCH&RI/024"
    out = re.sub(r"\s*([/&-])\s*", r"\1", out)
    # 3. Rejoin reference codes split after the prefix, but ONLY when the digit run
    #    is long (>=6) so normal text like "GST 18" or "Order 5" is untouched:
    #    "1OTM 2526001611" -> "1OTM2526001611", "SOSC 2526000429" -> "SOSC2526000429"
    out = re.sub(r"\b([0-9][A-Z]{2,4}) (\d{6,})", r"\1\2", out)
    out = re.sub(r"\b([A-Z]{2,4}) (\d{6,})", r"\1\2", out)
    return out


def extract_digital_fields(text: str, doc_type: str) -> dict[str, Any]:
    doc_type = str(doc_type or "").upper()
    lines = _clean_lines(text)
    if doc_type == "COMPANY_INVOICE":
        return _extract_company_invoice(lines)
    if doc_type == "COMPANY_DC":
        return _extract_company_dc(lines)
    if doc_type == "COMPANY_PO":
        return _extract_company_po(lines)
    return {}


def _extract_company_invoice(lines: list[str]) -> dict[str, Any]:
    invoice_number = _invoice_number_from_lines(lines)
    so_number = _so_number_from_lines(lines)
    fields: dict[str, Any] = {
        "invoice_number": invoice_number,
        "so_number": so_number,
        "po_reference": (
            _first_match(lines, r"\b[A-Z]{2,}[^ \n]*\d{3}/\d{4}-\d{4}\b")
            or _first_match(lines, r"\b[A-Z]{2,}[A-Z0-9&/._-]+/\d{2,4}-\d{2,4}/\d{2,}\b")
            or _customer_order_reference_from_lines(lines, excluded={invoice_number, so_number})
        ),
        "invoice_date": _value_after_label(lines, "Invoice Date", date=True),
        "customer_name": _line_after_label(lines, "Customer Name & Detail"),
        "gstin": _gstin_from_lines(lines),
    }
    fields["customer_address"] = _join_after_anchor(lines, fields.get("customer_name"), max_lines=8)
    total, tax, taxable = _invoice_footer_amounts(lines)
    if total is not None:
        fields["total_amount"] = total
        fields["net_amount"] = total
    if taxable is not None:
        fields["taxable_amount"] = taxable
    if tax is not None:
        fields["tax_amount"] = tax
    return _without_empty(fields)


def _extract_company_dc(lines: list[str]) -> dict[str, Any]:
    dc_number = _first_match(lines, r"\b[A-Z0-9]{1,4}DNT\d{4}DC\d+\b")
    so_number = _so_number_from_lines(lines)
    fields: dict[str, Any] = {
        "dc_number": dc_number,
        "so_number": so_number,
        "po_reference": (
            _first_match(lines, r"\b[A-Z]{2,}[^ \n]*\d{3}/\d{4}-\d{4}\b")
            or _first_match(lines, r"\b[A-Z]{2,}[A-Z0-9&/._-]+/\d{2,4}-\d{2,4}/\d{2,}\b")
            or _customer_order_reference_from_lines(lines, excluded={dc_number, so_number})
        ),
        "customer_name": _line_after_label(lines, "Delivery To"),
        "dc_date": _date_before_or_after_label(lines, "DC Date"),
        "gstin": _gstin_from_lines(lines),
    }
    fields["delivery_address"] = _join_after_anchor(lines, fields.get("customer_name"), max_lines=2)
    total_amount, total_quantity = _dc_amount_and_quantity_before_total(lines)
    if total_amount is not None:
        fields["total_amount"] = total_amount
    if total_quantity is not None:
        fields["total_quantity"] = total_quantity
    return _without_empty(fields)


def _extract_company_po(lines: list[str]) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "po_number": _first_match(lines, r"\b[0-9][A-Z]{2,3}\d{10}\b"),
        "po_date": _date_before_or_after_label(lines, "Order Date"),
        "mode_of_bill": _find_exact(lines, "ON FULL DELIVERY"),
        "part_shipment_allowed": _find_exact(lines, "NOT ALLOWED"),
        "vendor_name": _vendor_name(lines),
        "gstin": _gstin_from_lines(lines),
    }
    net_idx = _last_index(lines, "Net Amount")
    if net_idx is not None:
        following = [_to_amount(line) for line in lines[net_idx + 1 : net_idx + 8]]
        following = [value for value in following if value is not None]
        if len(following) >= 3:
            fields["taxable_amount"] = following[0]
            fields["tax_amount"] = following[1]
            fields["net_amount"] = following[2]
            fields["total_amount"] = following[2]
        elif following:
            fields["net_amount"] = following[-1]
            fields["total_amount"] = following[-1]
    return _without_empty(fields)


def _clean_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _first_match(lines: list[str], pattern: str) -> str | None:
    regex = re.compile(pattern, flags=re.I)
    for line in lines:
        match = regex.search(line)
        if match:
            return match.group(0).strip()
    return None


def _gstin_from_lines(lines: list[str]) -> str | None:
    return _first_match(lines, _GSTIN_PATTERN)


def _invoice_number_from_lines(lines: list[str]) -> str | None:
    code_re = r"\b[0-9][A-Z]{2,4}\d{10}\b"
    invoice_index = _first_index(lines, "Invoice No")
    if invoice_index is not None:
        match = re.search(code_re, "\n".join(lines[invoice_index : invoice_index + 5]), flags=re.I)
        if match:
            return match.group(0)

    so_number = _so_number_from_lines(lines)
    for code in re.findall(code_re, "\n".join(lines), flags=re.I):
        if code != so_number:
            return code

    match = re.search(code_re, "\n".join(lines), flags=re.I)
    return match.group(0) if match else None


def _so_number_from_lines(lines: list[str]) -> str | None:
    """Choose an SO-family code before falling back to a non-invoice code."""
    codes: list[str] = []
    for code in re.findall(_SO_PATTERN, "\n".join(lines), flags=re.I):
        if code not in codes:
            codes.append(code)
    if not codes:
        return None

    family = [code for code in codes if re.match(_SO_FAMILY, code, flags=re.I)]
    if family:
        return family[0]

    invoice_number = None
    invoice_index = _first_index(lines, "Invoice No")
    if invoice_index is not None:
        match = re.search(r"\b[0-9][A-Z]{2,4}\d{10}\b", "\n".join(lines[invoice_index : invoice_index + 15]), flags=re.I)
        if match:
            invoice_number = match.group(0)
    for code in codes:
        if code != invoice_number:
            return code
    return codes[0]


def _first_distinct_match(lines: list[str], pattern: str, excluded: str | None) -> str | None:
    regex = re.compile(pattern, flags=re.I)
    for line in lines:
        for match in regex.finditer(line):
            value = match.group(0).strip()
            if value != excluded:
                return value
    return None


def _customer_order_reference_from_lines(lines: list[str], excluded: set[str | None] | None = None) -> str | None:
    excluded_values = {str(value).upper() for value in (excluded or set()) if value}
    patterns = (
        r"\b[A-Z]{2,}[^ \n]*\d{3}/\d{4}-\d{4}\b",
        r"\b[A-Z]{2,}[A-Z0-9&/._-]+/\d{2,4}-\d{2,4}/\d{2,}\b",
        r"\b[A-Z]{3,6}\d{6,}\b",
    )
    internal_prefixes = ("1ITR", "1IAM", "9STG", "1OTM", "SOSC", "1DNT", "MBDNT", "1PTR", "1POC", "9POT")
    for pattern in patterns:
        for line in lines:
            for match in re.finditer(pattern, line, flags=re.I):
                value = match.group(0).strip()
                upper = value.upper()
                if upper in excluded_values or upper.startswith(internal_prefixes):
                    continue
                return value
    return None


def _value_after_label(lines: list[str], label: str, *, date: bool = False) -> str | None:
    index = _first_index(lines, label)
    if index is None:
        return None
    pattern = r"\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b" if date else r".+"
    for line in lines[index + 1 : index + 12]:
        match = re.search(pattern, line)
        if match:
            return match.group(0).strip()
    return None


def _line_after_label(lines: list[str], label: str) -> str | None:
    index = _first_index(lines, label)
    if index is None:
        return None
    for line in lines[index + 1 : index + 8]:
        if ":" in line:
            continue
        return line.strip()
    return None


def _join_after_anchor(lines: list[str], anchor: str | None, max_lines: int = 2) -> str | None:
    if not anchor:
        return None
    index = _first_index(lines, anchor)
    if index is None:
        return None
    parts = []
    stop_labels = {"GST NO.", "QTY", "SL", "AMOUNT", "E-MAIL", "PHONE NO."}
    for line in lines[index + 1 : index + 1 + max_lines]:
        if parts and line.upper() in stop_labels:
            break
        if line == ":" or line.endswith(":") or line.upper() in {"PAN NO.", "GST NO.", "E-MAIL", "PHONE NO."}:
            continue
        parts.append(line)
    return " ".join(parts) if parts else None


def _date_before_or_after_label(lines: list[str], label: str) -> str | None:
    index = _first_index(lines, label)
    if index is None:
        return None
    date_re = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b")
    for line in lines[max(0, index - 8) : index + 8]:
        match = date_re.search(line)
        if match:
            return match.group(0)
    return None


def _invoice_footer_amounts(lines: list[str]) -> tuple[float | None, float | None, float | None]:
    nett_idx = _last_index(lines, "Nett Amount")
    if nett_idx is not None:
        values = [_to_amount(line) for line in lines[nett_idx : nett_idx + 12]]
        values = [value for value in values if value is not None and value >= 1000]
        if len(values) >= 3:
            return values[0], values[1], values[2]
        if len(values) >= 2 and abs(values[0] - values[1]) <= 0.01 and _has_zero_tax_basis(lines):
            return values[0], 0.0, values[1]
    total_idx = _last_index(lines, "Total")
    if total_idx is None:
        return None, None, None
    values = [_to_amount(line) for line in lines[max(0, total_idx - 4) : total_idx + 12]]
    values = [value for value in values if value is not None and value >= 1000]
    if len(values) >= 3:
        return values[0], values[2], values[1]
    return None, None, None


def _has_zero_tax_basis(lines: list[str]) -> bool:
    text = "\n".join(lines)
    return bool(
        re.search(r"\b(?:IGST|CGST|SGST|GST)\s*0(?:\.0+)?\s*%", text, flags=re.I)
        or re.search(r"\bWITHOUT PAYMENT OF (?:INTEGRATED )?TAX\b", text, flags=re.I)
        or re.search(r"\bGST\s+EXEMPT(?:ED)?\b", text, flags=re.I)
    )


def _numbers_before_label(lines: list[str], label: str, limit: int) -> list[float]:
    index = _last_index(lines, label)
    if index is None:
        return []
    values = []
    for line in reversed(lines[max(0, index - 8) : index]):
        amount = _to_amount(line)
        if amount is not None:
            values.append(amount)
        if len(values) >= limit:
            break
    return list(reversed(values))


def _dc_amount_and_quantity_before_total(lines: list[str]) -> tuple[float | int | None, float | int | None]:
    index = _last_index(lines, "Total")
    if index is None:
        return None, None
    window = lines[max(0, index - 12) : index]
    numeric_entries: list[tuple[int, float | int]] = []
    money_values: list[float | int] = []
    quantity: float | int | None = None
    quantity_index: int | None = None
    for line_index, line in enumerate(window):
        amount = _to_amount(line)
        if amount is None:
            continue
        numeric_entries.append((line_index, amount))
        if _is_money_text(line) and amount >= 1000:
            money_values.append(amount)
        elif 0 < amount < 1000:
            quantity = int(amount) if float(amount).is_integer() else amount
            quantity_index = line_index
    total_amount = money_values[-1] if money_values else None
    table_context = lines[max(0, index - 80) : index]
    has_hsn_context = any(re.search(r"\b(?:HSN|SAC)\b", line, flags=re.I) for line in table_context)
    if total_amount is None and quantity_index is not None and not has_hsn_context:
        for line_index, amount in reversed(numeric_entries):
            if line_index < quantity_index and amount >= 1000:
                total_amount = amount
                break
    return total_amount, quantity


def _is_money_text(value: str) -> bool:
    return bool(re.fullmatch(r"-?\d[\d,]*\.\d{2}", str(value or "").replace(",", "").strip()))


def _vendor_name(lines: list[str]) -> str | None:
    index = _first_index(lines, "Vendor Name & Address")
    if index is None:
        return None
    for line in reversed(lines[max(0, index - 8) : index]):
        if re.search(r"[A-Za-z]", line) and not re.match(r"^\d", line) and line != ":":
            return re.sub(r"\([^)]*\)", "", line).replace(".,", "").replace(".", "").strip()
    return None


def _find_exact(lines: list[str], value: str) -> str | None:
    wanted = value.upper()
    return value if any(wanted in line.upper() for line in lines) else None


def _first_index(lines: list[str], label: str) -> int | None:
    needle = label.upper()
    for index, line in enumerate(lines):
        if needle in line.upper():
            return index
    return None


def _last_index(lines: list[str], label: str) -> int | None:
    needle = label.upper()
    for index in range(len(lines) - 1, -1, -1):
        if needle == lines[index].upper() or needle in lines[index].upper():
            return index
    return None


def _to_amount(value: str) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        return None
    number = float(text)
    return int(number) if number.is_integer() else number


def _without_empty(fields: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in fields.items() if value not in (None, "")}
