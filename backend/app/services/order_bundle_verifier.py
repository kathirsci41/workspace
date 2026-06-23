from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from app.services.address_parser import validate_addresses
from app.services.document_normalizer import NormalizedDocument
from app.services.gstin_validator import normalize_gstin, validate_gstin
from app.services.line_item_matcher import reconcile_line_items
from app.services.tolerance_config import DEFAULT_TOLERANCE


def verify_order_bundle(documents: list[NormalizedDocument]) -> dict[str, Any]:
    docs_by_type: dict[str, list[NormalizedDocument]] = {}
    for document in documents:
        if not document.fields:
            continue
        docs_by_type.setdefault(document.document_type, []).append(document)

    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    connections: list[dict[str, Any]] = []

    customer_po = _first(docs_by_type, "CUSTOMER_PO")
    invoice = _first(docs_by_type, "CUSTOMER_INVOICE")
    dcs = docs_by_type.get("DELIVERY_CHALLAN", [])
    primary_dc = dcs[0] if dcs else None
    vendor_pos = docs_by_type.get("VENDOR_PO", [])
    vendor_invoices = docs_by_type.get("VENDOR_INVOICE", [])

    customer_status = _customer_delivery_status(customer_po, invoice, dcs, checks, issues)
    vendor_status = _vendor_procurement_status(vendor_pos, vendor_invoices, checks, issues)
    additional_status = _add_gstin_checks(checks, issues, docs_by_type)
    additional_status = _max_status(additional_status, _add_gst_math_checks(checks, issues, docs_by_type))
    additional_status = _max_status(additional_status, _add_line_item_checks(checks, issues, docs_by_type))
    bundle_status = _max_status(_bundle_status(customer_status, vendor_status, issues), additional_status)
    proven_vendor_invoices = _proven_vendor_invoices(vendor_pos, vendor_invoices)

    extracted_summary = {
        "customer_po_no": _field(customer_po, "customer_po_no"),
        "so_no": _field(invoice, "so_no") or _field(primary_dc, "so_no") or _field(primary_dc, "sales_order_no"),
        "customer_name": _field(invoice, "customer_name") or _field(primary_dc, "customer_name") or _field(customer_po, "customer_name"),
        "customer_invoice_numbers": [_field(doc, "invoice_no") for doc in docs_by_type.get("CUSTOMER_INVOICE", []) if _field(doc, "invoice_no")],
        "dc_numbers": [_field(doc, "dc_no") for doc in docs_by_type.get("DELIVERY_CHALLAN", []) if _field(doc, "dc_no")],
        "vendor_po_numbers": [_field(doc, "vendor_po_no") for doc in vendor_pos if _field(doc, "vendor_po_no")],
        "vendor_invoice_numbers": [_field(doc, "vendor_invoice_no") for doc in vendor_invoices if _field(doc, "vendor_invoice_no")],
        "customer_total": _field(invoice, "grand_total") or _field(invoice, "net_amount"),
        "vendor_total": sum(_amount(doc, "invoice_total", "net_amount", "total_amount") or 0 for doc in proven_vendor_invoices) or None,
    }

    return {
        "bundle_status": bundle_status,
        "customer_delivery_status": customer_status,
        "vendor_procurement_status": vendor_status,
        "extracted_summary": extracted_summary,
        "connections": connections,
        "checks": checks,
        "issues": issues,
        "recommendation": _recommendation(bundle_status, customer_status, vendor_status, issues),
    }


def _customer_delivery_status(customer_po, invoice, dcs, checks, issues) -> str:
    dc_list = dcs if isinstance(dcs, list) else ([dcs] if dcs else [])
    primary_dc = dc_list[0] if dc_list else None
    if not invoice or not primary_dc:
        if invoice:
            message = "Delivery challan is missing."
            document_type = "DELIVERY_CHALLAN"
        elif primary_dc:
            message = "Customer invoice is missing."
            document_type = "COMPANY_INVOICE"
        else:
            message = "Customer invoice or delivery challan is missing."
            document_type = "COMPANY_INVOICE"
        issues.append(
            {
                "code": "CUSTOMER_DELIVERY_DOCUMENTS_MISSING",
                "message": message,
                "document_type": document_type,
                "document_id": None,
            }
        )
        return "MISSING_DOCUMENTS"

    for i, dc in enumerate(dc_list):
        dc_suffix = f"_{i+1}" if len(dc_list) > 1 else ""
        _add_compare_check(
            checks,
            f"INVOICE_DC_CUSTOMER_ORDER_MATCH{dc_suffix}",
            "Customer order number matches between invoice and DC",
            invoice,
            "customer_order_no",
            dc,
            "customer_order_no",
        )

        if _field(dc, "so_no") or _field(dc, "sales_order_no"):
            _add_compare_check(
                checks,
                f"INVOICE_DC_SO_MATCH{dc_suffix}",
                "SO number matches between invoice and DC",
                invoice,
                "so_no",
                dc,
                "so_no",
                right_fallback="sales_order_no",
            )
        else:
            checks.append(
                _check(
                    f"INVOICE_DC_SO_MATCH{dc_suffix}",
                    "SO number matches between invoice and DC",
                    "REVIEW_REQUIRED",
                    "BLOCKER",
                    invoice,
                    _field(invoice, "so_no"),
                    dc,
                    None,
                    "SO number absent on DC; manual review is required.",
                )
            )
            issues.append(
                {
                    "code": "DC_SO_NUMBER_MISSING",
                    "message": "SO number is absent on the delivery challan.",
                    "document_type": "COMPANY_DC",
                    "document_id": dc.document_id,
                }
            )
    _add_name_check(checks, invoice, primary_dc)
    _add_dc_amount_check(checks, invoice, dc_list)

    if customer_po:
        _add_compare_check(
            checks,
            "CUSTOMER_PO_INVOICE_ORDER_MATCH",
            "Customer PO number matches customer invoice order number",
            customer_po,
            "customer_po_no",
            invoice,
            "customer_order_no",
        )
        for i, dc in enumerate(dc_list):
            dc_suffix = f"_{i+1}" if len(dc_list) > 1 else ""
            _add_compare_check(
                checks,
                f"CUSTOMER_PO_DC_ORDER_MATCH{dc_suffix}",
                "Customer PO number matches DC order number",
                customer_po,
                "customer_po_no",
                dc,
                "customer_order_no",
            )
        _add_amount_check(checks, customer_po, invoice, "grand_total", "grand_total", "CUSTOMER_PO_INVOICE_AMOUNT_MATCH", fallback_right="net_amount")
    else:
        issues.append(
            {
                "code": "CUSTOMER_PO_MISSING",
                "message": "Customer PO is absent or unreadable; invoice and DC checks were evaluated independently.",
                "document_type": "CUSTOMER_PO",
                "document_id": None,
            }
        )

    if _has_result(checks, "MISMATCH"):
        return "MISMATCH"
    if not customer_po or _has_result(checks, "REVIEW_REQUIRED"):
        return "PARTIAL_PASS"
    return "PASS"


def _add_dc_amount_check(checks, invoice, dc_list) -> None:
    left_value = _amount(invoice, "taxable_amount")
    amounts = [_amount(dc, "estimated_amount", "total_amount") for dc in dc_list]
    dc_total = sum(amount or 0 for amount in amounts) if any(amount is not None for amount in amounts) else None
    if left_value is None or dc_total is None:
        result = "REVIEW_REQUIRED"
        message = "Amount comparison needs review because one amount is missing."
    elif DEFAULT_TOLERANCE.passes(left_value, dc_total, "dc_invoice_amount"):
        result = "PASS"
        message = "Amounts match within rounding tolerance."
    else:
        result = "REVIEW_REQUIRED"
        message = "Amounts differ or tax inclusion is unclear."
    checks.append(
        _amount_check(
            "INVOICE_DC_AMOUNT_MATCH",
            "Amount comparison",
            result,
            "WARNING",
            invoice,
            left_value,
            dc_list[0] if dc_list else None,
            dc_total,
            message,
        )
    )


def _vendor_procurement_status(vendor_pos, vendor_invoices, checks, issues) -> str:
    if not vendor_pos:
        issues.append(
            {"code": "VENDOR_PO_MISSING", "message": "Vendor PO is missing.", "document_type": "COMPANY_PO", "document_id": None}
        )
        return "MISSING_DOCUMENTS"
    if not vendor_invoices:
        issues.append(
            {"code": "VENDOR_INVOICE_MISSING", "message": "Vendor invoice is missing.", "document_type": "VENDOR_INVOICE", "document_id": None}
        )
        return "MISSING_DOCUMENTS"

    status = "PASS"
    known_pos = {
        _norm_ref(_field(vendor_po, "vendor_po_no")): vendor_po
        for vendor_po in vendor_pos
        if _field(vendor_po, "vendor_po_no")
    }
    grouped: dict[str, list[NormalizedDocument]] = {key: [] for key in known_pos}
    for invoice in vendor_invoices:
        invoice_ref = _vendor_invoice_ref(invoice)
        invoice_total = _amount(invoice, "invoice_total", "net_amount", "total_amount")
        if not invoice_ref:
            if invoice_total is not None:
                issues.append(
                    {
                        "code": "VENDOR_BILL_REFERENCE_MISSING",
                        "message": "Vendor bill amount extracted but Vendor PO reference missing; not counting vendor bill amount against Vendor PO coverage until the reference is proven or manually confirmed.",
                        "document_type": "VENDOR_INVOICE",
                        "document_id": invoice.document_id,
                        "vendor_invoice_id": invoice.document_id,
                    }
                )
                status = _max_status(status, "REVIEW_REQUIRED")
            continue
        normalized_ref = _norm_ref(invoice_ref)
        matched_po = known_pos.get(normalized_ref)
        if not matched_po:
            issues.append(
                {
                    "code": "VENDOR_BILL_REFERENCE_UNMATCHED",
                    "message": f"Vendor bill reference {invoice_ref} does not match any Vendor PO in the bundle; amount was not counted.",
                    "document_type": "VENDOR_INVOICE",
                    "document_id": invoice.document_id,
                    "vendor_invoice_id": invoice.document_id,
                    "vendor_invoice_reference": invoice_ref,
                }
            )
            status = _max_status(status, "REVIEW_REQUIRED")
            continue
        grouped[normalized_ref].append(invoice)

    for vendor_po in vendor_pos:
        po_no = _field(vendor_po, "vendor_po_no")
        matching = grouped.get(_norm_ref(po_no), [])
        for invoice in matching:
            _add_vendor_ref_check(checks, vendor_po, invoice)
            _add_vendor_name_check(checks, vendor_po, invoice)

        if not matching:
            issues.append(
                {
                    "code": "VENDOR_BILL_MISSING_FOR_PO",
                    "message": "No vendor bill with a proven reference was matched to this Vendor PO.",
                    "document_type": "VENDOR_INVOICE",
                    "document_id": None,
                    "vendor_po_no": po_no,
                }
            )
            status = _max_status(status, "REVIEW_REQUIRED")
            continue

        po_total = _amount(vendor_po, "grand_total", "net_amount", "total_amount")
        invoice_total = sum(_amount(invoice, "invoice_total", "net_amount", "total_amount") or 0 for invoice in matching)
        if po_total is not None and invoice_total:
            difference = round(po_total - invoice_total, 2)
            # ponytail: vendor coverage keeps exact +/-2, not DEFAULT_TOLERANCE's 2%.
            # a percentage band here would mask near-full partial billing, which is
            # an accepted Panimalar open-issue baseline. Widen only if a fixture needs it.
            if abs(difference) <= 2:
                result = "PASS"
            elif invoice_total < po_total and _partial_billing_restricted(vendor_po):
                result = "REVIEW_REQUIRED"
                issues.append(
                    {
                        "code": "VENDOR_PARTIAL_BILLING_REVIEW_REQUIRED",
                        "message": f"Vendor invoice total {invoice_total:g} does not fully cover Vendor PO {po_total:g}.",
                        "document_type": "COMPANY_PO",
                        "document_id": vendor_po.document_id if vendor_po else None,
                        "vendor_po_no": po_no,
                        "vendor_invoice_total": invoice_total,
                        "vendor_po_total": po_total,
                        "difference": int(difference) if float(difference).is_integer() else difference,
                    }
                )
            else:
                result = "REVIEW_REQUIRED"
            checks.append(
                _check(
                    "VENDOR_BILLING_COVERAGE",
                    "Vendor invoice total covers Vendor PO total",
                    result,
                    "BLOCKER",
                    vendor_po,
                    po_total,
                    matching[0] if matching else None,
                    invoice_total,
                    "Vendor billing coverage evaluated against matching invoice references.",
                )
            )
            status = _max_status(status, result)
    if _has_result(checks, "MISMATCH"):
        return "MISMATCH"
    return status


def _add_gstin_checks(checks, issues, docs_by_type) -> str:
    status = "PASS"
    for documents in docs_by_type.values():
        for document in documents:
            for field_name, gstin in _document_gstins(document):
                valid, reason = validate_gstin(gstin)
                result = "PASS" if valid else "REVIEW_REQUIRED"
                if not valid:
                    status = _max_status(status, result)
                    issues.append(
                        {
                            "code": "GSTIN_FORMAT_REVIEW_REQUIRED",
                            "message": reason,
                            "document_type": document.document_type,
                            "document_id": document.document_id,
                            "field_name": field_name,
                            "gstin": normalize_gstin(gstin),
                        }
                    )
                checks.append(
                    _check(
                        f"{document.document_type}_{field_name.upper()}_FORMAT",
                        "GSTIN format",
                        result,
                        "WARNING",
                        document,
                        normalize_gstin(gstin),
                        None,
                        None,
                        reason or f"GSTIN {normalize_gstin(gstin)} is valid.",
                    )
                )

    vendor_po_gstins = _gstins_for(docs_by_type.get("VENDOR_PO", []), "vendor_gstin")
    vendor_invoice_gstins = _gstins_for(docs_by_type.get("VENDOR_INVOICE", []), "vendor_gstin", "gstin")
    if vendor_po_gstins and vendor_invoice_gstins:
        po_values = {value for _, _, value in vendor_po_gstins}
        invoice_values = {value for _, _, value in vendor_invoice_gstins}
        left_doc, _, left_value = vendor_invoice_gstins[0]
        right_doc, _, right_value = vendor_po_gstins[0]
        if po_values & invoice_values:
            result = "PASS"
            message = "Vendor GSTIN matches between vendor invoice and Vendor PO."
        else:
            result = "MISMATCH"
            status = _max_status(status, result)
            message = f"Vendor invoice GSTIN {left_value} does not match Vendor PO GSTIN {right_value}."
            issues.append(
                {
                    "code": "VENDOR_GSTIN_MISMATCH",
                    "message": message,
                    "document_type": left_doc.document_type,
                    "document_id": left_doc.document_id,
                    "vendor_invoice_gstin": left_value,
                    "vendor_po_gstin": right_value,
                }
            )
        checks.append(
            _check(
                "VENDOR_GSTIN_MATCH",
                "Vendor GSTIN match",
                result,
                "WARNING",
                left_doc,
                left_value,
                right_doc,
                right_value,
                message,
            )
        )
    return status


def _add_gst_math_checks(checks, issues, docs_by_type) -> str:
    status = "PASS"
    for doc_type in ("VENDOR_INVOICE", "CUSTOMER_INVOICE"):
        for document in docs_by_type.get(doc_type, []):
            taxable = _numeric_field(document, "taxable_amount", "subtotal_amount")
            gst_rate = _numeric_field(document, "gst_rate", "tax_rate")
            if taxable is None or gst_rate is None:
                continue

            actual_tax = _actual_gst_tax(document)
            if actual_tax is None:
                continue

            expected_tax = round(taxable * gst_rate / 100, 2)
            result = "PASS" if DEFAULT_TOLERANCE.passes(expected_tax, actual_tax, "gst_tax") else "MISMATCH"
            if result != "PASS":
                status = _max_status(status, result)
                issues.append(
                    {
                        "code": "GST_MATH_MISMATCH",
                        "message": f"GST math mismatch: {taxable:g} * {gst_rate:g}% = {expected_tax:g}, found {actual_tax:g}.",
                        "document_type": document.document_type,
                        "document_id": document.document_id,
                        "expected_tax": expected_tax,
                        "actual_tax": actual_tax,
                    }
                )
            checks.append(
                _amount_check(
                    f"{doc_type}_GST_MATH",
                    "GST math",
                    result,
                    "WARNING",
                    document,
                    _clean_number(expected_tax),
                    document,
                    _clean_number(actual_tax),
                    f"{taxable:g} * {gst_rate:g}% = {expected_tax:g}; extracted tax is {actual_tax:g}.",
                )
            )
    return status


def _add_line_item_checks(checks, issues, docs_by_type) -> str:
    vendor_docs = docs_by_type.get("VENDOR_INVOICE", [])
    dc_docs = docs_by_type.get("DELIVERY_CHALLAN", [])
    invoice_docs = docs_by_type.get("CUSTOMER_INVOICE", [])
    vendor_items = _line_items_from(vendor_docs)
    dc_items = _line_items_from(dc_docs)
    invoice_items = _line_items_from(invoice_docs)
    if not vendor_items or not dc_items or not invoice_items:
        return "PASS"

    status = "PASS"
    left_doc = _first_with_line_items(vendor_docs)
    right_doc = _first_with_line_items(invoice_docs) or _first_with_line_items(dc_docs)
    for match in reconcile_line_items(vendor_items, dc_items, invoice_items):
        status = _max_status(status, match.result)
        check = _check(
            f"LINE_ITEM_{_check_suffix(match.key)}",
            "Line item reconciliation",
            match.result,
            "WARNING",
            left_doc,
            match.vendor_qty,
            right_doc,
            {"dc_qty": _clean_optional_number(match.dc_qty), "invoice_qty": _clean_optional_number(match.invoice_qty)},
            "Line item quantities and unit prices compared across vendor invoice, delivery challans, and customer invoice.",
        )
        check.update(
            {
                "line_item_key": match.key,
                "hsn_sac": match.hsn,
                "description": match.description,
                "qty_status": match.qty_status,
                "price_status": match.price_status,
                "vendor_unit_price": _clean_optional_number(match.vendor_unit_price),
                "invoice_unit_price": _clean_optional_number(match.invoice_unit_price),
                "line_item_issues": match.issues,
            }
        )
        checks.append(check)
        for issue in match.issues:
            issues.append(
                {
                    "code": "LINE_ITEM_RECONCILIATION_REVIEW",
                    "message": issue,
                    "document_type": left_doc.document_type if left_doc else "VENDOR_INVOICE",
                    "document_id": left_doc.document_id if left_doc else None,
                    "line_item_key": match.key,
                }
            )
    return status


def _proven_vendor_invoices(vendor_pos, vendor_invoices) -> list[NormalizedDocument]:
    po_numbers = {_norm_ref(_field(vendor_po, "vendor_po_no")) for vendor_po in vendor_pos if _field(vendor_po, "vendor_po_no")}
    return [
        invoice
        for invoice in vendor_invoices
        if _vendor_invoice_ref(invoice) and _norm_ref(_vendor_invoice_ref(invoice)) in po_numbers
    ]


def _add_compare_check(checks, check_id, name, left, left_key, right, right_key, right_fallback=None):
    left_value = _field(left, left_key)
    right_value = _field(right, right_key) or (right_fallback and _field(right, right_fallback))
    if not left_value or not right_value:
        result = "REVIEW_REQUIRED"
        message = f"{name}: one side is missing."
    elif _refs_match(left_value, right_value):
        result = "PASS"
        message = f"{name}."
    else:
        result = "MISMATCH"
        message = f"{name}: values differ."
    checks.append(_check(check_id, name, result, "BLOCKER", left, left_value, right, right_value, message))


def _add_amount_check(checks, left, right, left_key, right_key, check_id, fallback_right=None):
    left_value = _amount(left, left_key)
    right_value = _amount(right, right_key) if right else None
    if right_value is None and fallback_right:
        right_value = _amount(right, fallback_right)
    if left_value is None or right_value is None:
        result = "REVIEW_REQUIRED"
        message = "Amount comparison needs review because one amount is missing."
    elif DEFAULT_TOLERANCE.passes(left_value, right_value, check_id):
        result = "PASS"
        message = "Amounts match within rounding tolerance."
    else:
        result = "REVIEW_REQUIRED"
        message = "Amounts differ or tax inclusion is unclear."
    checks.append(_amount_check(check_id, "Amount comparison", result, "WARNING", left, left_value, right, right_value, message))


def _add_name_check(checks, left, right):
    left_value = _field(left, "customer_name")
    right_value = _field(right, "customer_name")
    result = "PASS" if _name_match(left_value, right_value) else "REVIEW_REQUIRED"
    checks.append(_check("CUSTOMER_NAME_MATCH", "Customer name match", result, "WARNING", left, left_value, right, right_value, "Customer names compared with normalized matching."))


def _add_vendor_ref_check(checks, vendor_po, invoice):
    _add_compare_check(checks, "VENDOR_PO_INVOICE_REFERENCE_MATCH", "Vendor PO reference matches vendor invoice", vendor_po, "vendor_po_no", invoice, "po_reference")


def _add_vendor_name_check(checks, vendor_po, invoice):
    left_value = _field(vendor_po, "vendor_name")
    right_value = _field(invoice, "vendor_name")
    result = "PASS" if _name_match(left_value, right_value) else "REVIEW_REQUIRED"
    checks.append(_check("VENDOR_NAME_MATCH", "Vendor name match", result, "WARNING", vendor_po, left_value, invoice, right_value, "Vendor names compared with normalized matching."))


def _check(check_id, name, result, severity, left_doc, left_value, right_doc, right_value, message) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "check_name": name,
        "result": result,
        "severity": severity,
        "left_document_type": left_doc.document_type if left_doc else None,
        "left_document_id": left_doc.document_id if left_doc else None,
        "left_value": left_value,
        "right_document_type": right_doc.document_type if right_doc else None,
        "right_document_id": right_doc.document_id if right_doc else None,
        "right_value": right_value,
        "message": message,
    }


def _amount_check(check_id, name, result, severity, left_doc, left_value, right_doc, right_value, message) -> dict[str, Any]:
    check = _check(check_id, name, result, severity, left_doc, left_value, right_doc, right_value, message)
    if left_value is not None and right_value is not None:
        check["diff"] = round(abs(float(left_value) - float(right_value)), 2)
        check["diff_pct"] = round(DEFAULT_TOLERANCE.diff_pct(float(left_value), float(right_value)), 2)
    return check


def _first(docs_by_type, doc_type):
    values = docs_by_type.get(doc_type, [])
    return values[0] if values else None


def _field(document, key):
    return document.fields.get(key) if document else None


def _line_items_from(documents) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for document in documents:
        line_items = document.fields.get("line_items") if document else None
        if isinstance(line_items, list):
            items.extend(item for item in line_items if isinstance(item, dict))
    return items


def _first_with_line_items(documents):
    for document in documents:
        line_items = document.fields.get("line_items") if document else None
        if isinstance(line_items, list) and line_items:
            return document
    return None


def _check_suffix(value: str) -> str:
    suffix = re.sub(r"[^A-Z0-9]+", "_", str(value or "").upper()).strip("_")
    return suffix[:40] or "UNKNOWN"


def _document_gstins(document) -> list[tuple[str, str]]:
    if not document:
        return []
    values: list[tuple[str, str]] = []
    seen: set[str] = set()
    for field_name in ("vendor_gstin", "seller_gstin", "customer_gstin", "buyer_gstin", "gstin"):
        value = normalize_gstin(document.fields.get(field_name))
        if not value or value in seen:
            continue
        values.append((field_name, value))
        seen.add(value)
    return values


def _gstins_for(documents, *field_names: str) -> list[tuple[NormalizedDocument, str, str]]:
    values: list[tuple[NormalizedDocument, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for document in documents:
        for field_name in field_names:
            value = normalize_gstin(document.fields.get(field_name))
            if not value:
                continue
            dedupe_key = (document.document_id, value)
            if dedupe_key in seen:
                continue
            values.append((document, field_name, value))
            seen.add(dedupe_key)
    return values


def _amount(document, *keys):
    if not document:
        return None
    for key in keys:
        value = document.fields.get(key)
        if value in (None, ""):
            continue
        try:
            number = float(str(value).replace(",", ""))
        except ValueError:
            continue
        return int(number) if number.is_integer() else number
    return None


def _actual_gst_tax(document) -> float | int | None:
    igst = _numeric_field(document, "igst_amount", "igst")
    if igst is not None:
        return _clean_number(igst)

    cgst = _numeric_field(document, "cgst_amount", "cgst")
    sgst = _numeric_field(document, "sgst_amount", "sgst")
    if cgst is not None and sgst is not None:
        return _clean_number(cgst + sgst)

    return _numeric_field(document, "tax_amount", "gst_amount")


def _numeric_field(document, *keys: str) -> float | int | None:
    if not document:
        return None
    for key in keys:
        value = document.fields.get(key)
        if value in (None, ""):
            continue
        if isinstance(value, int | float):
            return _clean_number(float(value))
        text = str(value).replace(",", "").replace(chr(8377), "").replace("Rs.", "").replace("INR", "").replace("%", "").strip()
        try:
            return _clean_number(float(text))
        except ValueError:
            continue
    return None


def _clean_number(value: float | int) -> float | int:
    number = float(value)
    return int(number) if number.is_integer() else round(number, 2)


def _clean_optional_number(value: float | int | None) -> float | int | None:
    return _clean_number(value) if value is not None else None


def _refs_match(left, right) -> bool:
    left_norm = _norm_ref(left)
    right_norm = _norm_ref(right)
    if not left_norm or not right_norm or len(left_norm) < 3:
        return False
    return left_norm == right_norm


def _norm_ref(value) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def _name_match(left, right) -> bool:
    left_norm = _norm_name(left)
    right_norm = _norm_name(right)
    if not left_norm or not right_norm:
        return False
    return left_norm == right_norm or SequenceMatcher(None, left_norm, right_norm).ratio() >= 0.82


def _norm_name(value) -> str:
    text = re.sub(r"[^A-Z0-9 ]+", " ", str(value or "").upper())
    text = re.sub(r"\b(PVT|PRIVATE|LIMITED|LTD|P|P LTD|INDIA)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _vendor_invoice_ref(invoice):
    return _field(invoice, "po_reference") or _field(invoice, "customer_ref_no") or _field(invoice, "external_doc_no")


def _partial_billing_restricted(vendor_po) -> bool:
    text = f"{_field(vendor_po, 'part_shipment_allowed') or ''} {_field(vendor_po, 'mode_of_bill') or ''}".upper()
    return "NOT ALLOWED" in text or "ON FULL DELIVERY" in text


def _has_result(checks, result) -> bool:
    return any(check["result"] == result for check in checks)


def _max_status(current: str, candidate: str) -> str:
    order = {"PASS": 0, "PARTIAL_PASS": 1, "REVIEW_REQUIRED": 2, "MISSING_DOCUMENTS": 3, "BLOCKED": 4, "MISMATCH": 5}
    return candidate if order.get(candidate, 0) > order.get(current, 0) else current


def _bundle_status(customer_status: str, vendor_status: str, issues: list[dict[str, Any]]) -> str:
    statuses = {customer_status, vendor_status}
    if "MISMATCH" in statuses:
        return "MISMATCH"
    if "BLOCKED" in statuses:
        return "BLOCKED"
    if "MISSING_DOCUMENTS" in statuses:
        return "MISSING_DOCUMENTS"
    if statuses <= {"PASS"}:
        return "OK"
    return "REVIEW_REQUIRED"


def _recommendation(bundle_status: str, customer_status: str, vendor_status: str, issues: list[dict[str, Any]]) -> str:
    if any(issue.get("code") == "VENDOR_PARTIAL_BILLING_REVIEW_REQUIRED" for issue in issues):
        return "Review vendor-side partial billing before closure."
    if bundle_status == "OK":
        return "Order bundle references and totals are consistent."
    if bundle_status == "MISSING_DOCUMENTS":
        return "Upload the missing documents before closing the order."
    if customer_status in {"PARTIAL_PASS", "REVIEW_REQUIRED"} or vendor_status in {"REVIEW_REQUIRED", "PARTIAL_PASS"}:
        return "Review the flagged checks and confirm the document bundle before closure."
    return "Resolve blocking or mismatched document evidence before closure."
