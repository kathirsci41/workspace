from __future__ import annotations

from dataclasses import dataclass
import difflib
import re
from typing import Any

from app.services.tolerance_config import DEFAULT_TOLERANCE


@dataclass(frozen=True)
class LineItemMatch:
    key: str
    hsn: str
    description: str
    vendor_qty: float | None
    dc_qty: float | None
    invoice_qty: float | None
    vendor_unit_price: float | None
    invoice_unit_price: float | None
    qty_status: str
    price_status: str
    result: str
    issues: list[str]


def reconcile_line_items(
    vendor_items: list[dict[str, Any]],
    dc_items: list[dict[str, Any]],
    invoice_items: list[dict[str, Any]],
    tolerance=None,
) -> list[LineItemMatch]:
    if not vendor_items or not dc_items or not invoice_items:
        return []

    tol = tolerance or DEFAULT_TOLERANCE
    dc_map = _build_lookup(dc_items)
    invoice_map = _build_lookup(invoice_items)
    results: list[LineItemMatch] = []

    for vendor_item in _build_lookup(vendor_items).values():
        key = vendor_item["key"]
        dc_item = dc_map.get(key) or _fuzzy_find(key, dc_map)
        invoice_item = invoice_map.get(key) or _fuzzy_find(key, invoice_map)

        vendor_qty = vendor_item["qty"]
        dc_qty = dc_item["qty"] if dc_item else None
        invoice_qty = invoice_item["qty"] if invoice_item else None
        vendor_unit_price = vendor_item["unit_price"]
        invoice_unit_price = invoice_item["unit_price"] if invoice_item else None

        issues: list[str] = []
        qty_status = "PASS"
        if dc_item is None:
            qty_status = "WARN"
            issues.append(f"Item '{key}' not found in delivery challans")
        elif vendor_qty is not None and dc_qty is not None and not _quantity_matches(vendor_qty, dc_qty):
            qty_status = "FAIL"
            issues.append(f"DC qty {dc_qty:g} does not match Vendor qty {vendor_qty:g}")

        if invoice_item is None:
            if qty_status == "PASS":
                qty_status = "WARN"
            issues.append(f"Item '{key}' not found in customer invoice")
        elif vendor_qty is not None and invoice_qty is not None and not _quantity_matches(vendor_qty, invoice_qty):
            qty_status = "FAIL"
            issues.append(f"Invoice qty {invoice_qty:g} does not match Vendor qty {vendor_qty:g}")

        price_status = "NA"
        if vendor_unit_price is not None and invoice_unit_price is not None:
            price_status = "PASS" if tol.passes(vendor_unit_price, invoice_unit_price, "unit_price") else "FAIL"
            if price_status == "FAIL":
                issues.append(f"Invoice unit price {invoice_unit_price:g} does not match Vendor unit price {vendor_unit_price:g}")

        result = _result(qty_status, price_status)
        results.append(
            LineItemMatch(
                key=key,
                hsn=vendor_item["hsn"],
                description=vendor_item["description"],
                vendor_qty=vendor_qty,
                dc_qty=dc_qty,
                invoice_qty=invoice_qty,
                vendor_unit_price=vendor_unit_price,
                invoice_unit_price=invoice_unit_price,
                qty_status=qty_status,
                price_status=price_status,
                result=result,
                issues=issues,
            )
        )

    return results


def _build_lookup(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for item in items:
        key = _match_key(item)
        if not key:
            continue
        qty = _to_float(_first_value(item, "quantity", "qty", "total_quantity"))
        unit_price = _to_float(_first_value(item, "unit_price", "unit_rate", "rate", "price"))
        existing = lookup.get(key)
        if existing is None:
            lookup[key] = {
                "key": key,
                "hsn": _clean_hsn(_first_value(item, "hsn_sac", "hsn", "sac")) or "",
                "description": str(_first_value(item, "description", "item_description", "particulars") or ""),
                "qty": qty,
                "unit_price": unit_price,
            }
            continue
        if qty is not None:
            existing["qty"] = qty if existing["qty"] is None else existing["qty"] + qty
        if existing["unit_price"] is None and unit_price is not None:
            existing["unit_price"] = unit_price
    return lookup


def _match_key(item: dict[str, Any]) -> str:
    hsn = _clean_hsn(_first_value(item, "hsn_sac", "hsn", "sac"))
    if hsn:
        return hsn
    description = str(_first_value(item, "description", "item_description", "particulars") or "")
    return re.sub(r"[^a-z0-9]+", " ", description.lower()).strip()


def _clean_hsn(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def _first_value(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, int | float):
        return float(value)
    text = (
        str(value)
        .replace(",", "")
        .replace(chr(8377), "")
        .replace("Rs.", "")
        .replace("INR", "")
        .strip()
    )
    try:
        return float(text)
    except ValueError:
        return None


def _fuzzy_find(key: str, lookup: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if not key or re.fullmatch(r"[A-Z0-9]+", key):
        return None
    matches = difflib.get_close_matches(key, lookup.keys(), n=1, cutoff=0.75)
    return lookup[matches[0]] if matches else None


def _result(qty_status: str, price_status: str) -> str:
    if "FAIL" in {qty_status, price_status}:
        return "MISMATCH"
    if "WARN" in {qty_status, price_status}:
        return "REVIEW_REQUIRED"
    return "PASS"


def _quantity_matches(left: float, right: float) -> bool:
    return abs(left - right) <= 0.0001
