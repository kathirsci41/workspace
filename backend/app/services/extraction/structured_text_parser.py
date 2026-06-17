from __future__ import annotations

import enum
import re
from typing import Any

from app.services.extraction.digital_text_extractor import extract_digital_fields


class FailureCode(str, enum.Enum):
    TEXT_EXTRACTION_FAILED = "TEXT_EXTRACTION_FAILED"
    OCR_EMPTY = "OCR_EMPTY"
    OCR_FAILED = "OCR_FAILED"
    STRUCTURED_PARSE_FAILED = "STRUCTURED_PARSE_FAILED"
    REQUIRED_FIELDS_MISSING = "REQUIRED_FIELDS_MISSING"
    LOW_CONFIDENCE_EXTRACTION = "LOW_CONFIDENCE_EXTRACTION"
    MANUAL_ENTRY_REQUIRED = "MANUAL_ENTRY_REQUIRED"
    MODEL_LAYER2_FAILED = "MODEL_LAYER2_FAILED"


CUSTOMER_PO_REQUIRED = (
    "customer_po_no",
    "customer_po_date",
    "grand_total",
)

VENDOR_INVOICE_REQUIRED = (
    "vendor_invoice_no",
    "vendor_invoice_date",
    "po_reference",
    "invoice_total",
)

PARSER_DOCUMENT_TYPE_ALIASES = {
    "CUSTOMER_INVOICE": "COMPANY_INVOICE",
    "DELIVERY_CHALLAN": "COMPANY_DC",
    "VENDOR_PO": "COMPANY_PO",
    "VENDOR_BILL": "VENDOR_INVOICE",
}


def parse_structured_text(
    document_type: str,
    raw_text: str | None,
    extraction_route: str,
    filename: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doc_type = str(document_type or "").upper()
    parser_doc_type = _parser_document_type(doc_type)
    text = raw_text or ""
    text_length = len(text.strip())
    route = str(extraction_route or "").lower()
    parser_diagnostics: dict[str, Any] = _parser_document_type_diagnostics(doc_type, parser_doc_type)
    field_metadata_overrides: dict[str, dict[str, Any]] = {}

    if text_length == 0:
        code = FailureCode.OCR_EMPTY if route in {"scanned", "ocr_glm"} else FailureCode.TEXT_EXTRACTION_FAILED
        return _result(
            fields={},
            required=(),
            parser_route="ocr_rules" if route in {"scanned", "ocr_glm"} else "digital_rules",
            failure_code=code,
            failure_reason="No text was acquired from the document.",
            text_length=text_length,
            filename=filename,
            context=context,
            extra_diagnostics=parser_diagnostics,
        )

    if route == "digital":
        if parser_doc_type == "CUSTOMER_PO":
            fields = _parse_customer_po(text)
            field_metadata_overrides = _customer_po_field_metadata_overrides(fields)
        elif parser_doc_type == "VENDOR_INVOICE":
            fields, extra_diagnostics, field_metadata_overrides = _parse_vendor_invoice(text, filename=filename)
            parser_diagnostics.update(extra_diagnostics)
        else:
            fields = extract_digital_fields(text, parser_doc_type)
        return _result(
            fields=_with_aliases(parser_doc_type, fields),
            required=_required_fields(parser_doc_type),
            parser_route="digital_rules",
            text_length=text_length,
            filename=filename,
            context=context,
            extra_diagnostics=parser_diagnostics,
            field_metadata_overrides=field_metadata_overrides,
        )

    if parser_doc_type == "CUSTOMER_PO":
        fields = _parse_customer_po(text)
        field_metadata_overrides = _customer_po_field_metadata_overrides(fields)
    elif parser_doc_type == "VENDOR_INVOICE":
        fields, extra_diagnostics, field_metadata_overrides = _parse_vendor_invoice(text, filename=filename)
        parser_diagnostics.update(extra_diagnostics)
    elif parser_doc_type == "COMPANY_INVOICE":
        fields = _parse_customer_invoice_ocr(text, filename=filename)
    else:
        fields = extract_digital_fields(text, parser_doc_type)

    return _result(
        fields=_with_aliases(parser_doc_type, fields),
        required=_required_fields(parser_doc_type),
        parser_route="ocr_rules" if parser_doc_type in {"CUSTOMER_PO", "VENDOR_INVOICE"} else "regex_rules",
        text_length=text_length,
        filename=filename,
        context=context,
        extra_diagnostics=parser_diagnostics,
        field_metadata_overrides=field_metadata_overrides,
    )


def _parser_document_type(document_type: str) -> str:
    return PARSER_DOCUMENT_TYPE_ALIASES.get(document_type, document_type)


def _parser_document_type_diagnostics(document_type: str, parser_document_type: str) -> dict[str, Any]:
    if parser_document_type == document_type:
        return {}
    return {
        "raw_document_type": document_type,
        "parser_document_type": parser_document_type,
    }


def _result(
    *,
    fields: dict[str, Any],
    required: tuple[str, ...],
    parser_route: str,
    text_length: int,
    filename: str | None = None,
    context: dict[str, Any] | None = None,
    failure_code: FailureCode | None = None,
    failure_reason: str | None = None,
    extra_diagnostics: dict[str, Any] | None = None,
    field_metadata_overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    clean_fields = {key: value for key, value in fields.items() if value not in (None, "")}
    missing = [key for key in required if clean_fields.get(key) in (None, "")]

    if failure_code is None:
        if not clean_fields and required:
            failure_code = FailureCode.STRUCTURED_PARSE_FAILED
            failure_reason = f"{_acquisition_label(parser_route)} but required fields could not be parsed."
        elif missing:
            failure_code = FailureCode.REQUIRED_FIELDS_MISSING
            failure_reason = f"{_acquisition_label(parser_route)} but required fields are missing: " + ", ".join(missing)

    confidence = round(((len(required) - len(missing)) / len(required)) * 100, 1) if required else (100.0 if clean_fields else 0.0)
    diagnostics = {
        "parser_route": parser_route,
        "extracted_field_keys": sorted(clean_fields.keys()),
        "missing_required_fields": missing,
        "failure_code": failure_code,
        "failure_reason": failure_reason,
        "text_length": text_length,
    }
    if filename:
        diagnostics["filename"] = filename
    if context:
        diagnostics["context"] = context
    diagnostics.update(extra_diagnostics or {})
    field_metadata = _field_metadata(clean_fields, parser_route, text_length)
    for field, field_metadata_override in (field_metadata_overrides or {}).items():
        if field in field_metadata:
            field_metadata[field] = field_metadata_override
    return {
        "fields": clean_fields,
        "missing_required_fields": missing,
        "confidence": confidence,
        "parser_route": parser_route,
        "diagnostics": diagnostics,
        "field_metadata": field_metadata,
    }


def _field_metadata(fields: dict[str, Any], parser_route: str, text_length: int) -> dict[str, dict[str, Any]]:
    source = "rules"
    confidence = 0.9 if parser_route in {"digital_rules", "ocr_rules"} else 0.75
    return {
        field: {
            "field": field,
            "value": value,
            "confidence": confidence,
            "source": source,
            "evidence_text": f"{parser_route}; text_length={text_length}",
        }
        for field, value in fields.items()
    }


def _acquisition_label(parser_route: str) -> str:
    return "OCR text was acquired" if parser_route == "ocr_rules" else "Document text was acquired"


def _required_fields(doc_type: str) -> tuple[str, ...]:
    if doc_type == "CUSTOMER_PO":
        return CUSTOMER_PO_REQUIRED
    if doc_type == "VENDOR_INVOICE":
        return VENDOR_INVOICE_REQUIRED
    return ()


def _parse_customer_po(text: str) -> dict[str, Any]:
    customer_po_no = _first_code(
        _label_value(
            text,
            ("Purchase Order No", "Customer Order No", "Customer PO No", "Buyer Order No", "PO Ref", "Order No", "Ref No", "Reference No"),
            value_pattern=r"[A-Z0-9&/._-]{4,}",
        ),
        _ref_label_po(text),
        _customer_po_code(text),
    )
    return {
        "customer_po_no": customer_po_no,
        "customer_po_date": _date_near_value(text, customer_po_no) or _label_value(text, ("PO Date", "Order Date", "Date"), value_pattern=_DATE_PATTERN),
        "customer_name": _customer_po_customer_name(text) or _label_value(text, ("Customer Name", "Buyer Name", "Bill To", "Invoice To"), value_pattern=r"[A-Z][A-Z0-9 &().,'/-]{4,}"),
        "billing_address": _address_after_label(text, ("Billing Address", "Bill To", "Buyer Address")),
        "delivery_address": _address_after_label(text, ("Delivery Address", "Ship To", "Consignee", "Shipping Address")),
        "subtotal_amount": _amount_after_label(text, ("Subtotal", "Sub Total", "Taxable Value", "Basic Amount", "Taxable Amount")),
        "tax_amount": _amount_after_label(text, ("Tax Amount", "GST Amount", "GST Exempted", "GST", "Tax")),
        "grand_total": _last_amount_after_label(text, ("Grand Total", "Total Amount", "Net Amount", "Total"), min_value=1000),
        "total_quantity": _amount_after_label(text, ("Total Quantity", "Total Qty", "Qty", "Quantity"), integer=True),
    }


def _customer_po_field_metadata_overrides(fields: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Phase 1xI Step 8.3: flag tax_amount that looks like a rate (e.g. 18) rather than an amount."""
    field_metadata_overrides: dict[str, dict[str, Any]] = {}
    tax_amount = fields.get("tax_amount")
    subtotal = fields.get("subtotal_amount")
    grand_total = fields.get("grand_total")
    if tax_amount is not None and subtotal is not None and grand_total is not None:
        implied_tax = grand_total - subtotal
        if tax_amount <= 100 and implied_tax > tax_amount * 5:
            field_metadata_overrides["tax_amount"] = {
                "field": "tax_amount",
                "value": tax_amount,
                "confidence": 0.4,
                "source": "suspicious_tax_amount",
                "evidence_text": f"value ({tax_amount}) looks like a tax rate, not an amount; grand_total - subtotal_amount = {implied_tax}",
            }
    return field_metadata_overrides


def _parse_vendor_invoice(text: str, *, filename: str | None = None) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    explicit_invoice_total = _explicit_invoice_total_from_labels(text)
    generic_invoice_total = None if explicit_invoice_total is not None else _last_amount_after_label(text, ("Total",), min_value=1000, window_chars=80)
    largest_invoice_total = _largest_amount(text)
    invoice_total_source = None
    if explicit_invoice_total is not None:
        invoice_total = explicit_invoice_total
    elif largest_invoice_total is not None and (
        generic_invoice_total is None or generic_invoice_total < largest_invoice_total
    ):
        invoice_total = largest_invoice_total
        invoice_total_source = "fallback_largest"
    else:
        invoice_total = generic_invoice_total
    bill_to_name = _label_value(text, ("Bill To", "Bill-To", "Billed To", "Billing Address", "Buyer Name"), value_pattern=r"[A-Z][A-Z0-9 &().,'/-]{4,}")
    ship_to_name = _label_value(text, ("Ship To", "Ship-To", "Consignee", "Delivery Address"), value_pattern=r"[A-Z][A-Z0-9 &().,'/-]{4,}")
    buyer_name = bill_to_name or ship_to_name
    vendor_name = (
        _clean_vendor_name(
            _label_value(text, ("Vendor Name", "Supplier Name", "Seller Name"), value_pattern=r"[A-Z][A-Z0-9 &().,'/-]{4,}"),
            buyer_name=buyer_name,
        )
        or _extract_header_company(text, buyer_name=buyer_name)
    )
    taxable_amount = _amount_after_label(text, ("Subtotal", "Taxable Value", "Taxable Amount", "Basic Amount", "Total before Tax"), min_value=1000)
    taxable_amount_source = None
    if taxable_amount is None:
        taxable_amount = _sum_taxable_values_from_gst_rows(text)
        if taxable_amount is not None:
            taxable_amount_source = "gst_table_sum"
    split_gst_taxable = _derive_taxable_from_split_gst_total(text, invoice_total)
    if split_gst_taxable is not None and (
        taxable_amount is None or abs(float(taxable_amount) - float(split_gst_taxable)) > 2
    ):
        taxable_amount = split_gst_taxable
        taxable_amount_source = "invoice_total_split_gst_9_9"
    component_gst_taxable = _derive_taxable_from_gst_total_components(text, invoice_total)
    if component_gst_taxable is not None and (
        taxable_amount is None or abs(float(taxable_amount) - float(component_gst_taxable)) > 2
    ):
        taxable_amount = component_gst_taxable
        taxable_amount_source = "invoice_total_minus_split_gst_components"
    vendor_invoice_no_source = None
    vendor_invoice_no = _label_code_value(text, ("Tax Invoice No", "Tax Invoice Number", "Invoice No", "Inv No", "Invoice", "Bill No", "Bill Number", "Invoice Number", "Voucher No"), value_pattern=r"[A-Z0-9/-]{5,80}", reject_dates=True)
    if vendor_invoice_no is None:
        vendor_invoice_no = _vendor_invoice_no_from_filename(filename)
        if vendor_invoice_no is not None:
            vendor_invoice_no_source = "filename_fallback"
    tax_amount = _vendor_invoice_tax_amount(text)
    tax_amount_source = None
    if tax_amount is None:
        tax_amount = _derive_vendor_invoice_tax_from_split_gst(text, invoice_total, taxable_amount)
        if tax_amount is not None:
            tax_amount_source = "invoice_total_minus_taxable_with_split_gst_components"

    fields = {
        "vendor_invoice_no": vendor_invoice_no,
        "vendor_invoice_date": _label_value(text, ("Invoice Date", "Tax Invoice Date", "Invoice Dt", "Inv Date", "Bill Date", "Bill Dt", "Date of Invoice", "Date"), value_pattern=_DATE_PATTERN),
        "vendor_name": vendor_name,
        "po_reference": _looks_like_code(
            _extract_po_from_other_references(text)
            or _label_code_value(
                text,
                ("Your Ref.", "Your Ref", "Your Order", "Buyer's Order No", "Buyer Order No", "Buyer PO No", "Customer Order No", "Customer PO No", "Customer Ref No", "External Doc No", "Order Ref", "Purchase Order", "PO No", "PO Number", "PO Reference"),
                value_pattern=r"[A-Z0-9&/._-]{4,80}",
            )
        ),
        "external_doc_no": _label_code_value(text, ("External Doc No", "External Reference"), value_pattern=r"[A-Z0-9&/._-]{4,80}"),
        "subtotal_amount": taxable_amount,
        "tax_amount": tax_amount,
        "invoice_total": invoice_total,
        "bill_to_name": bill_to_name,
        "ship_to_name": ship_to_name,
        "vendor_gstin": _first_match(text, r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b"),
        "irn": _label_value(text, ("IRN",), value_pattern=r"[A-Z0-9]{8,}"),
        "ack_no": _label_value(text, ("Ack No", "Acknowledgement No"), value_pattern=r"\d{6,}"),
    }
    fields["gstin"] = fields.get("vendor_gstin")
    parser_diagnostics: dict[str, Any] = {}
    field_metadata_overrides: dict[str, dict[str, Any]] = {}
    if invoice_total_source == "fallback_largest":
        parser_diagnostics["invoice_total_source"] = "fallback_largest"
        field_metadata_overrides["invoice_total"] = {
            "field": "invoice_total",
            "value": invoice_total,
            "confidence": 0.5,
            "source": "fallback_largest",
            "evidence_text": "largest money figure on the bill (label extraction unreliable)",
        }
    if vendor_invoice_no_source == "filename_fallback":
        parser_diagnostics["vendor_invoice_no_source"] = "filename_fallback"
        field_metadata_overrides["vendor_invoice_no"] = {
            "field": "vendor_invoice_no",
            "value": vendor_invoice_no,
            "confidence": 0.45,
            "source": "filename_fallback",
            "evidence_text": f"filename={filename}",
        }
    if taxable_amount_source:
        parser_diagnostics["taxable_amount_source"] = taxable_amount_source
        for field in ("subtotal_amount", "taxable_amount"):
            field_metadata_overrides[field] = {
                "field": field,
                "value": taxable_amount,
                "confidence": 0.8,
                "source": taxable_amount_source,
                "evidence_text": "derived from invoice total with explicit CGST/SGST basis",
            }
    if tax_amount_source:
        parser_diagnostics["tax_amount_source"] = tax_amount_source
        field_metadata_overrides["tax_amount"] = {
            "field": "tax_amount",
            "value": tax_amount,
            "confidence": 0.8,
            "source": tax_amount_source,
            "evidence_text": "invoice total minus taxable amount, confirmed by split GST component values",
        }
    for party_field in ("bill_to_name", "ship_to_name"):
        value = fields.get(party_field)
        if value and _looks_like_label_or_code(value):
            field_metadata_overrides[party_field] = {
                "field": party_field,
                "value": value,
                "confidence": 0.3,
                "source": "needs_review",
                "evidence_text": "value looks like a field label or reference code, not a party name",
            }
    if vendor_name and _looks_like_incomplete_company_name(vendor_name):
        field_metadata_overrides["vendor_name"] = {
            "field": "vendor_name",
            "value": vendor_name,
            "confidence": 0.3,
            "source": "needs_review",
            "evidence_text": "value is short and generic; may be an incomplete vendor name",
        }
    return fields, parser_diagnostics, field_metadata_overrides


def _with_aliases(doc_type: str, fields: dict[str, Any]) -> dict[str, Any]:
    result = dict(fields)
    if doc_type == "CUSTOMER_PO":
        po_no = result.get("customer_po_no") or result.get("po_number")
        if po_no:
            result.setdefault("customer_po_no", po_no)
            result.setdefault("po_number", po_no)
            result.setdefault("customer_order_no", po_no)
            result.setdefault("primary_ref_no", po_no)
        if result.get("grand_total") is not None:
            result.setdefault("total_amount", result["grand_total"])
    elif doc_type == "VENDOR_INVOICE":
        inv_no = result.get("vendor_invoice_no") or result.get("invoice_number")
        if inv_no:
            result.setdefault("vendor_invoice_no", inv_no)
            result.setdefault("invoice_number", inv_no)
        if result.get("vendor_invoice_date"):
            result.setdefault("invoice_date", result["vendor_invoice_date"])
        if result.get("invoice_total") is not None:
            result.setdefault("total_amount", result["invoice_total"])
        if result.get("subtotal_amount") is not None:
            result.setdefault("taxable_amount", result["subtotal_amount"])
        if result.get("po_reference"):
            result.setdefault("customer_ref_no", result["po_reference"])
    elif doc_type == "COMPANY_INVOICE":
        if result.get("invoice_number"):
            result.setdefault("invoice_no", result["invoice_number"])
        if result.get("po_reference"):
            result.setdefault("customer_order_no", result["po_reference"])
        if result.get("so_number"):
            result.setdefault("so_no", result["so_number"])
        if result.get("total_amount") is not None:
            result.setdefault("net_amount", result["total_amount"])
    elif doc_type == "COMPANY_DC":
        if result.get("dc_number"):
            result.setdefault("dc_no", result["dc_number"])
        if result.get("po_reference"):
            result.setdefault("customer_order_no", result["po_reference"])
        if result.get("so_number"):
            result.setdefault("so_no", result["so_number"])
        if result.get("total_amount") is not None:
            result.setdefault("estimated_amount", result["total_amount"])
    elif doc_type == "COMPANY_PO":
        if result.get("po_number"):
            result.setdefault("vendor_po_no", result["po_number"])
            if result.get("total_amount") is not None:
                result.setdefault("net_amount", result["total_amount"])
        if result.get("po_date"):
            result.setdefault("vendor_po_date", result["po_date"])
    return result


_DATE_PATTERN = r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}"


def _looks_like_code(value: str | None) -> str | None:
    """A reference/PO/invoice code must contain a digit and not be a plain word."""
    if not value:
        return None
    v = value.strip(" .,:")
    if re.fullmatch(r"(?=.*[a-f])[0-9a-f]{32,}", v, flags=re.I):
        return None
    if not re.search(r"\d", v):
        return None
    if re.fullmatch(r"[&A-Za-z]+", v):
        return None
    return v


_DATE_VALUE_RE = re.compile(
    r"^\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}$|^\d{4}[/.\-]\d{1,2}[/.\-]\d{1,2}$",
    re.I,
)


def _looks_like_date(value: str) -> bool:
    return bool(_DATE_VALUE_RE.match(value.strip()))


def _first_code(*values: str | None) -> str | None:
    for value in values:
        code = _looks_like_code(value)
        if code:
            return code
    return None


_LABEL_LIKE_VALUE_RE = re.compile(
    r"^(invoice|bill|tax\s*invoice|ship\s*to|bill\s*to|purchase\s*order|order|reference|ref|customer|po)"
    r"\s*(no\.?|number|date)?\.?$",
    re.I,
)

_PARTY_CODE_RE = re.compile(r"^[A-Z]\d{4,}$")

_COMPANY_SUFFIX_RE = re.compile(
    r"\b(ltd|limited|pvt|private|inc|incorporated|corp|corporation|co|company|industries|"
    r"enterprises|traders|llp|llc|technologies|systems|solutions|group)\b",
    re.I,
)


def _looks_like_label_or_code(value: str) -> bool:
    """True if value is a field label (e.g. 'Invoice No.') or a short reference code (e.g. 'C000691')."""
    v = value.strip()
    return bool(_LABEL_LIKE_VALUE_RE.match(v) or _PARTY_CODE_RE.match(v))


def _looks_like_incomplete_company_name(value: str) -> bool:
    """True if value is a single short word with no recognized company suffix (e.g. 'SUPREME')."""
    v = value.strip()
    if len(v) >= 10 or " " in v:
        return False
    return not _COMPANY_SUFFIX_RE.search(v)


def _clean_vendor_name(value: str | None, buyer_name: str | None = None) -> str | None:
    if not value:
        return None
    v = value.strip(" .,:")
    label_prefix = re.match(r"^(?:vendor name|supplier name|seller|bill to|ship to)\s*[:#-]\s*(.+)$", v, flags=re.I)
    if label_prefix:
        v = label_prefix.group(1).strip(" .,")
    labels = {
        "our order",
        "customer",
        "bill to",
        "billing address",
        "ship to",
        "delivery address",
        "vendor name",
        "supplier",
        "supplier name",
        "seller",
        "date",
        "invoice date",
        "due date",
        "ref",
        "reference",
        "gst no",
        "currency",
        "place of supply",
        "irn number",
    }
    if v.lower() in labels:
        return None
    if re.match(r"^(?:due date|invoice date|bill date)\b", v, flags=re.I):
        return None
    if re.match(r"^(and|or|the)\b", v, flags=re.I):
        return None
    if re.search(r"\b(governed by|terms and conditions|abide by)\b", v, flags=re.I):
        return None
    party_key = re.sub(r"[^a-z0-9]+", " ", v.lower()).strip()
    known_buyers = {
        "skylark information technologies private limited",
        "skylark information technologies pvt ltd",
    }
    if party_key in known_buyers:
        return None
    if buyer_name and v.strip().lower() == buyer_name.strip().lower():
        return None
    if not re.search(r"[A-Za-z]{3,}", v):
        return None
    return v


def _label_value(text: str, labels: tuple[str, ...], *, value_pattern: str) -> str | None:
    for label in labels:
        escaped = re.escape(label)
        for pattern in (
            rf"{escaped}\.?\s*[:#-]?\s*({value_pattern})",
            rf"{escaped}\.?\s*(?:\n|\r\n)\s*[:#-]?\s*({value_pattern})",
        ):
            match = re.search(pattern, text, flags=re.I)
            if match:
                return _clean_scalar(match.group(1))
    return None


def _label_code_value(
    text: str,
    labels: tuple[str, ...],
    *,
    value_pattern: str,
    reject_dates: bool = False,
) -> str | None:
    lines = [line.strip() for line in text.splitlines()]
    for label in labels:
        escaped = re.escape(label)
        line_label = re.compile(rf"^{escaped}\.?\s*[:#-]?\s*$", flags=re.I)
        for index, line in enumerate(lines):
            if not line_label.match(line):
                continue
            for candidate_line in lines[index + 1 : index + 4]:
                match = re.search(rf"[:#-]?\s*({value_pattern})", candidate_line, flags=re.I)
                if not match:
                    continue
                value = _looks_like_code(_clean_scalar(match.group(1)))
                if value:
                    if reject_dates and _looks_like_date(value):
                        continue
                    return value
        for pattern in (
            rf"{escaped}\.?\s*[:#-]?\s*({value_pattern})",
            rf"{escaped}\.?\s*(?:\n|\r\n)\s*[:#-]?\s*({value_pattern})",
            rf"{escaped}\.?[ \t]+\S[^\n]*\n({value_pattern})",
        ):
            for match in re.finditer(pattern, text, flags=re.I):
                value = _looks_like_code(_clean_scalar(match.group(1)))
                if value:
                    if reject_dates and _looks_like_date(value):
                        continue
                    return value
    return None


def _vendor_invoice_no_from_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    stem = re.sub(r"\.[A-Za-z0-9]{1,8}$", "", filename)
    stem = re.sub(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}[_\s]*", "", stem, flags=re.I)
    ignored = {
        "VENDOR",
        "BILL",
        "INVOICE",
        "TAX",
        "CUSTOMER",
        "COMPANY",
        "TRADE",
        "PDF",
    }
    excluded_prefixes = ("1PTR", "1POC", "1OTM", "1DNT", "1ITR", "PMCH")
    for token in re.findall(r"[A-Z0-9][A-Z0-9/-]{4,31}", stem.upper()):
        token = token.strip(" -_.,")
        if token in ignored or token.startswith(excluded_prefixes):
            continue
        if _looks_like_code(token):
            return token
    return None


def _customer_po_code(text: str) -> str | None:
    excluded_prefixes = ("GST", "PAN", "CIN", "IRN", "LEI", "1ITR", "1OTM", "1DNT", "1PTR", "1POC")
    for match in re.finditer(r"\b[A-Z]{3,6}\d{6,}\b", text, flags=re.I):
        value = match.group(0).upper()
        if value.startswith(excluded_prefixes):
            continue
        return value
    return None


def _date_near_value(text: str, value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(re.escape(value), text, flags=re.I)
    if not match:
        return None
    window = text[match.end() : match.end() + 160]
    date_match = re.search(_DATE_PATTERN, window, flags=re.I)
    return _clean_scalar(date_match.group(0)) if date_match else None


def _customer_po_customer_name(text: str) -> str | None:
    lines = [line.strip(" :\t") for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if re.search(r"tax\s+invoice\s+to\s+be\s+raised\s+as\s+under", line, flags=re.I):
            for candidate in lines[index + 1 : index + 7]:
                company = _clean_customer_company_line(candidate)
                if company:
                    return company

    for index, line in enumerate(lines):
        if _customer_po_code(line):
            for candidate in reversed(lines[max(0, index - 8) : index]):
                company = _clean_customer_company_line(candidate)
                if company:
                    return company
    return None


def _clean_customer_company_line(value: str) -> str | None:
    line = re.sub(r"\s+", " ", value.strip(" .,:"))
    if not line:
        return None
    own_company = {
        "skylark information technologies private limited",
        "skylark information technologies pvt ltd",
    }
    key = re.sub(r"[^a-z0-9]+", " ", line.lower()).strip()
    if key in own_company:
        return None
    if re.search(r"(:|@|www\.|invoice|office|address|website|registered|corporate identity|valid till|submitted|undersigned)", line, flags=re.I):
        return None
    if not re.search(r"\b(LIMITED|LTD|PRIVATE|PVT|FINANCE|HOSPITAL|INSTITUTE)\b", line, flags=re.I):
        return None
    if len(line) > 90:
        return None
    return line


def _ref_label_po(text: str) -> str | None:
    """
    Extract a customer PO number from a bare 'REF:' label (common on scanned POs).
    Strict: REF must be a whole word, and the value must look like a real reference
    code - not arbitrary prose. This avoids false matches like 'REFERENCE' or
    'REF: customer signature'.
    """
    match = re.search(r"\bREF\b\.?\s*:?\s*([A-Z0-9][A-Z0-9&/._-]{3,})", text, flags=re.I)
    if not match:
        return None
    value = match.group(1).strip(" .")
    if re.search(r"\d", value) and re.search(r"[/&\-]", value):
        return value
    if re.match(r"^[0-9A-Z]{8,}$", value) and re.search(r"\d", value):
        return value
    return None


def _address_after_label(text: str, labels: tuple[str, ...]) -> str | None:
    stop = re.compile(r"^(ship to|delivery address|billing address|bill to|subtotal|tax|gst|grand total|total amount|net amount|po date|order date)\b", flags=re.I)
    lines = [line.strip(" :\t") for line in text.splitlines()]
    for idx, line in enumerate(lines):
        for label in labels:
            if re.search(rf"\b{re.escape(label)}\b", line, flags=re.I):
                remainder = re.sub(rf".*?\b{re.escape(label)}\b\s*[:#-]?", "", line, flags=re.I).strip()
                parts = [remainder] if remainder else []
                for next_line in lines[idx + 1 : idx + 5]:
                    if not next_line or stop.search(next_line):
                        break
                    parts.append(next_line)
                value = " ".join(part for part in parts if part).strip()
                return value or None
    return None


def _amount_after_label(text: str, labels: tuple[str, ...], *, integer: bool = False, min_value: float | None = None) -> float | int | None:
    for label in labels:
        match = re.search(rf"{re.escape(label)}\.?\s*[:#-]?\s*(?:INR|Rs\.?|₹)?\s*([0-9][0-9,]*(?:\.\d+)?)", text, flags=re.I)
        if match:
            value = _to_number(match.group(1))
            if value is None or (min_value is not None and value < min_value):
                continue
            return int(value) if integer and float(value).is_integer() else value
    return None


def _last_amount_after_label(
    text: str,
    labels: tuple[str, ...],
    *,
    min_value: float | None = None,
    window_chars: int = 80,
) -> float | int | None:
    """Return the first plausible amount near the last matching label."""
    best_pos = -1
    best_val: float | int | None = None
    for label in labels:
        for label_match in re.finditer(rf"\b{re.escape(label)}\.?\b", text, flags=re.I):
            window = text[label_match.end() : label_match.end() + window_chars]
            for amount_match in re.finditer(r"(?:INR|Rs\.?|₹)?\s*([0-9][0-9,]*(?:\.\d+)?)", window, flags=re.I):
                value = _to_number(amount_match.group(1))
                if value is None or (min_value is not None and value < min_value):
                    continue
                if label_match.start() > best_pos:
                    best_pos = label_match.start()
                    best_val = value
                break
    return best_val


def _explicit_invoice_total_from_labels(text: str) -> float | int | None:
    return _last_amount_after_label(
        text,
        ("Total Invoice Value", "Invoice Total", "Grand Total", "Net Amount"),
        min_value=1000,
        window_chars=120,
    )

def _largest_amount(text: str) -> float | int | None:
    """Largest decimal money figure in the document (e.g. 4,63,365.55)."""
    best: float | int | None = None
    for match in re.finditer(r"\b(\d[\d,]*\.\d{2})\b", text):
        value = _to_number(match.group(1))
        if value is not None and value > 100_000_000:
            continue
        if value is not None and (best is None or value > best):
            best = value
    return best


def _extract_po_from_other_references(text: str) -> str | None:
    """Extract a PO number from a vendor-invoice Other References block."""
    labeled_match = re.search(
        r"(?:External\s+doc(?:ument)?\.?\s*No\.?|Credit\s+Card\s+No\.?)\s*:?\s*PO\s*[:#-]?\s*([A-Z0-9&/._-]{6,})",
        text,
        flags=re.I,
    )
    if labeled_match:
        return labeled_match.group(1).strip()
    match = re.search(
        r"Other References?\s*(?:\n|\r\n)\s*PO\s*NO\s*[:\s]+([A-Z0-9]{6,})",
        text,
        flags=re.I,
    )
    if match:
        return match.group(1).strip()
    inline_match = re.search(r"\bPO\s*NO\s*[:\s]+([A-Z0-9]{6,})", text, flags=re.I)
    return inline_match.group(1).strip() if inline_match else None


def _sum_taxable_values_from_gst_rows(text: str) -> float | int | None:
    """
    Sum item taxable values only when an explicit Taxable Value/CGST/SGST table
    is present. The taxable value is the last amount before the final two tax
    rate columns on each item row.
    """
    if not re.search(r"Taxable\s+Value[^\n]*(?:CGST[^\n]*SGST|SGST[^\n]*CGST)", text, flags=re.I):
        return None

    values: list[float | int] = []
    for line in text.splitlines():
        rate_matches = list(re.finditer(r"\b\d+(?:\.\d+)?\s*%", line))
        if len(rate_matches) < 2:
            continue
        before_tax_rates = line[: rate_matches[-2].start()]
        amount_matches = list(re.finditer(r"\b\d[\d,]*\.\d{2}\b", before_tax_rates))
        if not amount_matches:
            continue
        value = _to_number(amount_matches[-1].group(0))
        if value is not None and value > 0:
            values.append(value)

    if not values:
        return None
    total = sum(float(value) for value in values)
    return int(total) if total.is_integer() else round(total, 2)


def _derive_taxable_from_split_gst_total(text: str, invoice_total: float | int | None) -> float | int | None:
    if invoice_total is None:
        return None
    if not re.search(r"\bCGST\b", text, flags=re.I) or not re.search(r"\bSGST\b", text, flags=re.I):
        return None
    if not re.search(r"Taxable\s+Value", text, flags=re.I):
        return None
    if len(re.findall(r"\b9(?:\.0+)?\s*%", text, flags=re.I)) < 2:
        return None
    taxable = float(invoice_total) / 1.18
    rounded = round(taxable)
    if abs(taxable - rounded) <= 0.05:
        return int(rounded)
    return round(taxable, 2)


def _derive_taxable_from_gst_total_components(text: str, invoice_total: float | int | None) -> float | int | None:
    if invoice_total is None:
        return None
    if not re.search(r"\bCGST\b", text, flags=re.I) or not re.search(r"\bSGST\b", text, flags=re.I):
        return None

    values = _money_values(text)
    total = float(invoice_total)
    for index, value in enumerate(values):
        if abs(float(value) - total) > 1:
            continue
        previous = [float(candidate) for candidate in values[max(0, index - 8) : index] if float(candidate) > 0]
        for left_index, left in enumerate(previous):
            for right in previous[left_index + 1 :]:
                if abs(left - right) > 1:
                    continue
                taxable = total - left - right
                if taxable <= 0:
                    continue
                if any(abs(candidate - taxable) <= 1 for candidate in previous):
                    rounded = round(taxable)
                    return int(rounded) if abs(taxable - rounded) <= 0.05 else round(taxable, 2)
    return None


def _vendor_invoice_tax_amount(text: str) -> float | int | None:
    tax_total = _last_amount_after_label(text, ("Tax Total",), min_value=1, window_chars=80)
    if tax_total is not None:
        return tax_total
    return _amount_after_label(text, ("GST Amount", "Tax Amount"), min_value=1)


def _derive_vendor_invoice_tax_from_split_gst(
    text: str,
    invoice_total: float | int | None,
    taxable_amount: float | int | None,
) -> float | int | None:
    if invoice_total is None or taxable_amount is None:
        return None
    if not re.search(r"\bCGST\b", text, flags=re.I) or not re.search(r"\bSGST\b", text, flags=re.I):
        return None

    tax_amount = float(invoice_total) - float(taxable_amount)
    if tax_amount <= 0:
        return None

    component_amount = tax_amount / 2
    matching_components = sum(
        1
        for value in _money_values(text)
        if abs(float(value) - component_amount) <= 1
    )
    if matching_components < 2:
        return None

    rounded = round(tax_amount)
    return int(rounded) if abs(tax_amount - rounded) <= 0.05 else round(tax_amount, 2)


def _money_values(text: str) -> list[float | int]:
    values: list[float | int] = []
    for match in re.finditer(r"\b\d[\d,]*\.\d{2}\b", text):
        value = _to_number(match.group(0))
        if value is not None and value <= 100_000_000:
            values.append(value)
    return values


# ---------------------------------------------------------------------------
# OCR-aware CUSTOMER_INVOICE (COMPANY_INVOICE) parsing.
#
# The digital-path ``_extract_company_invoice`` is tuned for Skylark's own
# digitally-generated invoices. Third-party scanned invoices (vendor->Skylark
# tax invoices captured by PaddleOCR) use different labels and columnar OCR
# layouts. These helpers extract the shared invoice fields generically by
# anchoring on labels rather than Skylark-specific code patterns, taking the
# FIRST label occurrence so multi-invoice PDFs resolve to the primary invoice,
# and only emitting amounts that appear verbatim in the OCR text.
# ---------------------------------------------------------------------------

_CI_DATE_RE = re.compile(r"\b(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\b")
_CI_GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2}\b", re.I)
_CI_PAN_RE = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$", re.I)
_CI_CODE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9/\-]{4,}")
_CI_AMOUNT_RE = re.compile(r"[0-9][0-9,]*(?:\.\d+)?")

_CI_INVOICE_NO_LABELS = ("invoice number", "invoice no", "tax invoice no", "bill no")
_CI_INVOICE_NO_FALLBACK_LABELS = ("invoice",)
_CI_INVOICE_NO_REJECT = ("invoice date", "invoice due", "invoice total", "invoice value", "tax invoice")
_CI_ORDER_NO_LABELS = (
    "customer order no",
    "customer po",
    "buyer order",
    "your ref",
    "customer ref no",
    "customer reference",
    "po no",
    "p.o. no",
)
_CI_DATE_LABELS = ("invoice date", "date of invoice", "inv date", "bill date")
_CI_NAME_LABELS_PRIMARY = ("bill to", "bill-to", "billed to", "billing address", "sold to", "buyer")
_CI_NAME_LABELS_FALLBACK = ("customer name",)
_CI_TOTAL_LABELS = ("nett amount", "invoice total", "grand total", "total invoice value", "net amount")
_CI_TAXABLE_LABELS = (
    "total before tax",
    "taxable value",
    "taxable amount",
    "otal amount [inr]",
    "total amount [inr]",
)
_CI_TAX_LABELS = ("tax total", "tax amount", "total tax", "igst", "cgst")


def _ci_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _ci_label_segments(
    lines: list[str],
    labels: tuple[str, ...],
    *,
    reject: tuple[str, ...] = (),
    window: int = 8,
) -> list[str] | None:
    """Return text segments starting at the first line matching a label.

    The first element is the remainder of the label line after the label text
    (for same-line values); the rest are the following ``window`` lines (for
    columnar layouts where values trail the labels).
    """
    for index, line in enumerate(lines):
        low = line.lower()
        if any(token in low for token in reject):
            continue
        for label in labels:
            pos = low.find(label)
            if pos == -1:
                continue
            remainder = line[pos + len(label):]
            return [remainder, *lines[index + 1 : index + 1 + window]]
    return None


def _ci_order_no(lines: list[str]) -> str | None:
    segments = _ci_label_segments(lines, _CI_ORDER_NO_LABELS, window=8)
    if segments is None:
        return None
    return _ci_pick_code(segments, mode="order")


def _ci_invoice_no(lines: list[str], *, exclude: set[str]) -> str | None:
    for labels, reject in (
        (_CI_INVOICE_NO_LABELS, ()),
        (_CI_INVOICE_NO_FALLBACK_LABELS, _CI_INVOICE_NO_REJECT),
    ):
        segments = _ci_label_segments(lines, labels, reject=reject, window=8)
        if segments is None:
            continue
        value = _ci_pick_code(segments, mode="invoice", exclude=exclude)
        if value is not None:
            return value
    return None


def _ci_pick_code(segments: list[str], *, mode: str, exclude: set[str] | None = None) -> str | None:
    excluded = {str(value).upper() for value in (exclude or set()) if value}
    for segment in segments:
        for raw in _CI_CODE_RE.findall(segment):
            value = raw.strip(" :#-").strip()
            if len(value) < 6:
                continue
            if value.upper() in excluded:
                continue
            if _CI_DATE_RE.search(value) or _CI_GSTIN_RE.search(value) or _CI_PAN_RE.match(value):
                continue
            has_alpha = any(char.isalpha() for char in value)
            has_digit = any(char.isdigit() for char in value)
            if not has_digit:
                continue
            if mode == "order":
                # Customer order/reference numbers always mix letters and digits.
                if not (has_alpha and has_digit):
                    continue
            else:  # invoice
                # Invoice numbers may be alphanumeric or purely numeric.
                if not has_alpha and len(value) < 7:
                    continue
            return value
    return None


def _ci_invoice_date(lines: list[str]) -> str | None:
    segments = _ci_label_segments(lines, _CI_DATE_LABELS, window=8)
    if segments is None:
        return None
    for segment in segments:
        match = _CI_DATE_RE.search(segment)
        if match:
            return match.group(1)
    return None


def _ci_customer_name(lines: list[str]) -> str | None:
    for labels in (_CI_NAME_LABELS_PRIMARY, _CI_NAME_LABELS_FALLBACK):
        segments = _ci_label_segments(lines, labels, window=6)
        if segments is None:
            continue
        for segment in segments:
            candidate = segment.strip(" :.-")
            if _ci_looks_like_party_name(candidate):
                return _clean_scalar(candidate)
    return None


def _ci_looks_like_party_name(value: str) -> bool:
    value = value.strip()
    if len(value) < 6 or ":" in value:
        return False
    if re.search(r"\d", value):  # addresses / codes carry digits
        return False
    words = [word for word in re.split(r"\s+", value) if len(word) >= 2]
    if len(words) < 2:
        return False
    letters = [char for char in value if char.isalpha()]
    if not letters:
        return False
    uppercase = [char for char in letters if char.isupper()]
    return len(uppercase) / len(letters) >= 0.7


def _ci_amount_after(lines: list[str], labels: tuple[str, ...], *, min_value: float = 1000.0) -> float | int | None:
    segments = _ci_label_segments(lines, labels, window=6)
    if segments is None:
        return None
    for segment in segments:
        for match in _CI_AMOUNT_RE.finditer(segment):
            value = _to_number(match.group(0))
            if value is not None and value >= min_value:
                return value
    return None


def _ci_amount_verbatim(value: float | int, text: str) -> bool:
    flat = text.replace(",", "")
    decimal_form = f"{float(value):.2f}"
    if decimal_form in flat:
        return True
    if float(value).is_integer():
        return re.search(rf"(?<!\d){re.escape(str(int(value)))}(?!\d)", flat) is not None
    return False


def _ci_amounts(lines: list[str]) -> tuple[float | int | None, float | int | None, float | int | None]:
    blob = "\n".join(lines)
    total = _ci_amount_after(lines, _CI_TOTAL_LABELS)
    taxable = _ci_amount_after(lines, _CI_TAXABLE_LABELS)
    tax: float | int | None = None
    if total is not None and taxable is not None:
        candidate = round(float(total) - float(taxable), 2)
        if candidate == 0:
            # total == taxable is an arithmetic identity for zero tax (LUT/export),
            # not a fabricated sum, so it needs no verbatim guard.
            tax = 0
        elif candidate > 0 and _ci_amount_verbatim(candidate, blob):
            tax = _to_number(f"{candidate}")
    elif total is not None and taxable is None:
        tax_label = _ci_amount_after(lines, _CI_TAX_LABELS)
        if tax_label is not None:
            candidate = round(float(total) - float(tax_label), 2)
            if candidate > 0 and _ci_amount_verbatim(candidate, blob):
                taxable = _to_number(f"{candidate}")
                tax = tax_label
    return total, taxable, tax


def _parse_customer_invoice_ocr(text: str, filename: str | None = None) -> dict[str, Any]:
    """OCR-aware extraction for scanned third-party customer/tax invoices.

    Starts from the digital-path extraction (preserving its behavior for any
    field the OCR-aware rules do not resolve) and applies generic
    label-anchored overrides for the shared invoice fields.
    """
    fields = dict(extract_digital_fields(text, "COMPANY_INVOICE"))
    lines = _ci_lines(text)

    order_no = _ci_order_no(lines)
    invoice_no = _ci_invoice_no(lines, exclude={order_no} if order_no else set())
    invoice_date = _ci_invoice_date(lines)
    customer_name = _ci_customer_name(lines)
    total, taxable, tax = _ci_amounts(lines)

    if invoice_no:
        fields["invoice_number"] = invoice_no
    if order_no:
        fields["po_reference"] = order_no
    if invoice_date:
        fields["invoice_date"] = invoice_date
    if customer_name:
        fields["customer_name"] = customer_name
    if total is not None:
        fields["total_amount"] = total
        fields["net_amount"] = total
    if taxable is not None:
        fields["taxable_amount"] = taxable
    if tax is not None:
        fields["tax_amount"] = tax
    elif total is not None and taxable is not None:
        # Amount block resolved confidently but the tax figure is not present
        # verbatim in the OCR text -> do not fabricate it.
        fields.pop("tax_amount", None)

    return _without_empty_ci(fields)


def _without_empty_ci(fields: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in fields.items() if value not in (None, "")}


def _extract_header_company(text: str, buyer_name: str | None = None) -> str | None:
    label_noise = re.compile(
        r"^(tax invoice|invoice|bill|purchase order|delivery challan|gst|pan|cin|gstin|irn|ack no|state name|page \d)$",
        re.I,
    )
    pure_label = re.compile(
        r"^(from|to|the|and|for|with|date|no\.|number|ref|reference|total|subtotal|amount|qty|quantity|description|sir|madam|dear)[\s:.,]*$",
        re.I,
    )
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    first_qualifying: str | None = None
    for line in lines[:12]:
        if len(line) < 5 or re.match(r"^[\d:.,/\-\s]+$", line):
            continue
        if re.match(r"^C/O[\.\s]", line, re.I):
            continue
        if re.match(r"^:?\s*[0-9a-f]{32,}\s*$", line, re.I):
            continue
        if re.match(r"^(IRN|Ack No\.?|Ack Date|e-?Invoice|UDYAM|CIN|GSTIN)\s*:?\s*$", line, re.I):
            continue
        if re.search(r"\d{5,}", line):
            continue
        if label_noise.search(line) or pure_label.match(line):
            continue
        if not re.search(r"\b[A-Z]{3,}\b", line) and not re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", line):
            continue
        cleaned = re.sub(r"\([^)]*\)", "", line).strip(" .,")
        if len(cleaned) < 5:
            continue
        # Prefer a line carrying a recognized company suffix (e.g. "... Pvt Ltd")
        # over an earlier single-word header fragment (e.g. a stylized logo line
        # like "SUPREME"). Fall back to the first qualifying line otherwise.
        if _COMPANY_SUFFIX_RE.search(cleaned):
            return _clean_vendor_name(cleaned, buyer_name=buyer_name)
        if first_qualifying is None:
            first_qualifying = cleaned
    if first_qualifying is not None:
        return _clean_vendor_name(first_qualifying, buyer_name=buyer_name)
    return None


def _first_match(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.I)
    return _clean_scalar(match.group(0)) if match else None


def _to_number(value: str) -> float | int | None:
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _clean_scalar(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"\s+", " ", str(value).strip(" :#-\t\r\n"))
