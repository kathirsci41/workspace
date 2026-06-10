from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class NormalizedDocument:
    document_id: str
    document_type: str
    fields: dict[str, Any] = field(default_factory=dict)
    raw_document_type: str | None = None


DOCUMENT_TYPE_ALIASES = {
    "CUSTOMER_PO": "CUSTOMER_PO",
    "COMPANY_INVOICE": "CUSTOMER_INVOICE",
    "CUSTOMER_INVOICE": "CUSTOMER_INVOICE",
    "COMPANY_DC": "DELIVERY_CHALLAN",
    "DELIVERY_CHALLAN": "DELIVERY_CHALLAN",
    "COMPANY_PO": "VENDOR_PO",
    "VENDOR_PO": "VENDOR_PO",
    "VENDOR_INVOICE": "VENDOR_INVOICE",
    "VENDOR_BILL": "VENDOR_INVOICE",
    "ERP_ORDER_EXPORT": "ERP_ORDER_EXPORT",
}


FIELD_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "CUSTOMER_PO": {
        "customer_po_no": ("customer_po_no", "po_number", "customer_order_no", "primary_ref_no"),
        "customer_po_date": ("customer_po_date", "po_date", "order_date"),
        "customer_name": ("customer_name", "buyer_name"),
        "billing_address": ("billing_address", "bill_to_address"),
        "delivery_address": ("delivery_address", "shipping_address", "ship_to_address"),
        "subtotal_amount": ("subtotal_amount", "taxable_amount", "basic_amount"),
        "tax_amount": ("tax_amount", "gst_amount"),
        "grand_total": ("grand_total", "total_amount", "net_amount"),
        "total_quantity": ("total_quantity", "quantity", "qty"),
    },
    "CUSTOMER_INVOICE": {
        "invoice_no": ("invoice_no", "invoice_number"),
        "invoice_date": ("invoice_date",),
        "customer_order_no": ("customer_order_no", "po_reference", "customer_po_no"),
        "so_no": ("so_no", "so_number", "sales_order_no"),
        "customer_name": ("customer_name",),
        "customer_address": ("customer_address", "billing_address", "delivery_address"),
        "customer_pin": ("customer_pin", "delivery_pin"),
        "customer_city": ("customer_city", "delivery_city"),
        "customer_state": ("customer_state", "delivery_state"),
        "customer_gstin": ("customer_gstin", "gstin"),
        "seller_gstin": ("seller_gstin",),
        "taxable_amount": ("taxable_amount", "subtotal_amount"),
        "tax_amount": ("tax_amount", "gst_amount"),
        "net_amount": ("net_amount", "total_amount"),
        "grand_total": ("grand_total", "total_amount", "net_amount"),
        "line_item_count": ("line_item_count",),
        "total_quantity": ("total_quantity",),
    },
    "DELIVERY_CHALLAN": {
        "dc_no": ("dc_no", "dc_number"),
        "dc_date": ("dc_date",),
        "sales_order_no": ("sales_order_no", "so_number", "so_no"),
        "so_no": ("so_no", "so_number", "sales_order_no"),
        "customer_order_no": ("customer_order_no", "po_reference", "customer_po_no"),
        "customer_name": ("customer_name", "delivery_to_name"),
        "delivery_to_name": ("delivery_to_name", "customer_name"),
        "delivery_address": ("delivery_address", "customer_address"),
        "billing_address": ("billing_address",),
        "total_quantity": ("total_quantity",),
        "estimated_amount": ("estimated_amount", "taxable_amount", "total_amount"),
    },
    "VENDOR_PO": {
        "vendor_po_no": ("vendor_po_no", "po_number", "primary_ref_no"),
        "vendor_po_date": ("vendor_po_date", "po_date"),
        "vendor_name": ("vendor_name",),
        "part_shipment_allowed": ("part_shipment_allowed",),
        "mode_of_bill": ("mode_of_bill",),
        "subtotal_amount": ("subtotal_amount", "taxable_amount"),
        "tax_amount": ("tax_amount", "gst_amount"),
        "net_amount": ("net_amount", "total_amount"),
        "grand_total": ("grand_total", "total_amount", "net_amount"),
        "total_quantity": ("total_quantity",),
    },
    "VENDOR_INVOICE": {
        "vendor_invoice_no": ("vendor_invoice_no", "invoice_number", "invoice_no"),
        "vendor_invoice_date": ("vendor_invoice_date", "invoice_date"),
        "vendor_name": ("vendor_name", "supplier_name"),
        "bill_to_name": ("bill_to_name",),
        "ship_to_name": ("ship_to_name",),
        "po_reference": ("po_reference", "customer_ref_no", "external_doc_no"),
        "customer_ref_no": ("customer_ref_no", "po_reference"),
        "external_doc_no": ("external_doc_no",),
        "subtotal_amount": ("subtotal_amount", "taxable_amount"),
        "tax_amount": ("tax_amount", "gst_amount"),
        "net_amount": ("net_amount",),
        "invoice_total": ("invoice_total", "total_amount", "grand_total", "net_amount"),
        "line_item_count": ("line_item_count",),
        "total_quantity": ("total_quantity",),
    },
}


AMOUNT_SUFFIXES = ("_amount", "grand_total", "net_amount", "invoice_total", "total_quantity")


def normalize_document(document: Any, extracted_data: dict[str, Any] | None = None) -> NormalizedDocument:
    raw_type = _document_type(document)
    normalized_type = DOCUMENT_TYPE_ALIASES.get(raw_type, raw_type)
    source = dict(extracted_data or {})
    aliases = FIELD_ALIASES.get(normalized_type, {})
    fields = {target: _first_present(source, candidates) for target, candidates in aliases.items()}
    fields = {key: _normalize_value(key, value) for key, value in fields.items() if value not in (None, "")}
    _add_canonical_aliases(normalized_type, fields)
    return NormalizedDocument(
        document_id=str(getattr(document, "id", getattr(document, "document_id", ""))),
        document_type=normalized_type,
        raw_document_type=raw_type,
        fields=fields,
    )


def _document_type(document: Any) -> str:
    value = getattr(document, "document_type", document)
    if hasattr(value, "value"):
        value = value.value
    return str(value or "").upper()


def _first_present(source: dict[str, Any], candidates: tuple[str, ...]) -> Any:
    for key in candidates:
        if source.get(key) not in (None, ""):
            return source[key]
    return None


def _normalize_value(key: str, value: Any) -> Any:
    if key.endswith(AMOUNT_SUFFIXES) or key in {"total_quantity", "line_item_count"}:
        return _to_number(value)
    if key.endswith("_no") or key.endswith("_ref_no") or key in {"po_reference", "customer_order_no"}:
        return _clean_ref_string(value)
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value.strip())
    return value


def _add_canonical_aliases(document_type: str, fields: dict[str, Any]) -> None:
    if document_type == "CUSTOMER_PO" and fields.get("customer_po_no"):
        fields.setdefault("po_number", fields["customer_po_no"])
        fields.setdefault("customer_order_no", fields["customer_po_no"])
        fields.setdefault("primary_ref_no", fields["customer_po_no"])
        if fields.get("grand_total") is not None:
            fields.setdefault("total_amount", fields["grand_total"])
    if document_type == "VENDOR_INVOICE" and fields.get("vendor_invoice_no"):
        fields.setdefault("invoice_number", fields["vendor_invoice_no"])
        if fields.get("invoice_total") is not None:
            fields.setdefault("total_amount", fields["invoice_total"])
    if document_type == "VENDOR_PO" and fields.get("vendor_po_no"):
        fields.setdefault("po_number", fields["vendor_po_no"])
        if fields.get("grand_total") is not None:
            fields.setdefault("total_amount", fields["grand_total"])


def _clean_ref_string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return re.sub(r"\s+", " ", str(value).strip(" :#-\t\r\n"))


def _to_number(value: Any) -> float | int | Any:
    if isinstance(value, int | float):
        return value
    text = str(value or "").replace(",", "").strip()
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        return value
    number = float(text)
    return int(number) if number.is_integer() else number
