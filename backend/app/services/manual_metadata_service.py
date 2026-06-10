from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.logging_config import current_request_id
from app.models.document import DocumentRecord
from app.models.document_metadata import DocumentMetadataRecord
from app.schemas.audit import AuditEventCreate
from app.services.audit_service import AuditService
from app.services.extraction.structured_text_parser import CUSTOMER_PO_REQUIRED
from app.services.reference_index_service import build_reference_index


def patch_extracted_data(
    *,
    document: DocumentRecord,
    metadata: DocumentMetadataRecord,
    fields: dict[str, Any],
    audit_service: AuditService,
    actor: str = "system",
    reason: str | None = None,
) -> dict[str, Any]:
    unknown_fields = sorted(set(fields) - allowed_manual_fields(str(document.document_type)))
    if unknown_fields:
        raise ValueError("Unsupported manual extracted fields: " + ", ".join(unknown_fields))
    _validate_manual_patch(fields, reason)
    normalized_fields = _normalize_manual_fields(fields)

    previous = dict(metadata.extracted_data or {})
    merged = dict(metadata.extracted_data)
    for key, value in normalized_fields.items():
        if value in (None, ""):
            merged.pop(key, None)
        else:
            merged[key] = value
    merged["extraction_source"] = "manual_entry"

    metadata.extracted_data = merged
    field_metadata = dict((metadata.diagnostics or {}).get("field_metadata") or {})
    field_locations = dict((metadata.diagnostics or {}).get("field_locations") or {})
    for key, value in normalized_fields.items():
        if value not in (None, ""):
            field_metadata[key] = {
                "field": key,
                "value": value,
                "confidence": 1.0,
                "source": "manual_entry",
                "evidence_text": "Manual entry",
            }
            field_locations[key] = {
                "page": None,
                "bbox": None,
                "evidence_text": "Manual entry",
                "source": "manual_entry",
                "confidence": 1.0,
            }
    diagnostics = {**(metadata.diagnostics or {}), "field_metadata": field_metadata, "field_locations": field_locations}
    missing = required_manual_fields_missing(str(document.document_type), merged)
    if missing:
        metadata.status = "MANUAL_ENTRY"
        metadata.last_error = "MANUAL_ENTRY_REQUIRED: missing " + ", ".join(missing)
        document.status = "EXTRACTION_FAILED"
        document.last_error = metadata.last_error
        diagnostics["failure_code"] = "MANUAL_ENTRY_REQUIRED"
        diagnostics["failure_reason"] = metadata.last_error
    else:
        previous_failure_code = diagnostics.get("failure_code")
        previous_failure_reason = diagnostics.get("failure_reason")
        if previous_failure_code:
            diagnostics["previous_failure_code"] = previous_failure_code
        if previous_failure_reason:
            diagnostics["previous_failure_reason"] = previous_failure_reason
        diagnostics["failure_code"] = None
        diagnostics["failure_reason"] = None
        metadata.status = "EXTRACTED"
        metadata.last_error = None
        document.status = "PENDING_REVIEW"
        document.last_error = None
    metadata.diagnostics = diagnostics

    references = build_reference_index(
        document.id,
        merged,
        document.order_bundle_id,
        document_type=document.document_type,
        diagnostics=metadata.diagnostics,
    )
    changed_fields = {
        key: value for key, value in normalized_fields.items() if previous.get(key) != value
    }
    changes = [
        {"field": key, "old_value": previous.get(key), "new_value": value}
        for key, value in sorted(changed_fields.items())
    ]
    audit_event = audit_service.record_event(
        AuditEventCreate(
            event_type="manual_extracted_data_patched",
            actor=actor,
            document_id=document.id,
            order_bundle_id=document.order_bundle_id,
            payload={
                "document_type": document.document_type,
                "bundle_id": document.order_bundle_id,
                "patched_fields": sorted(changed_fields.keys()),
                "changes": changes,
                "reason": reason,
                "source": "manual_entry",
                "request_id": current_request_id(),
            },
        )
    )
    return {"metadata": metadata, "document": document, "references": references, "audit_event": audit_event}


def required_manual_fields_missing(document_type: str, extracted_data: dict[str, Any]) -> list[str]:
    doc_type = document_type.upper()
    if doc_type == "CUSTOMER_PO":
        return [field for field in CUSTOMER_PO_REQUIRED if extracted_data.get(field) in (None, "")]
    if doc_type == "VENDOR_INVOICE":
        missing = []
        for field in ["vendor_invoice_no", "vendor_invoice_date", "vendor_name"]:
            if extracted_data.get(field) in (None, ""):
                missing.append(field)
        if not any(extracted_data.get(field) not in (None, "") for field in ("po_reference", "customer_ref_no", "external_doc_no")):
            missing.append("po_reference/customer_ref_no/external_doc_no")
        if not any(extracted_data.get(field) not in (None, "") for field in ("invoice_total", "net_amount")):
            missing.append("invoice_total/net_amount")
        return missing
    return []


def allowed_manual_fields(document_type: str) -> set[str]:
    common = {"extraction_source"}
    by_type = {
        "CUSTOMER_PO": {
            "customer_po_no",
            "customer_po_date",
            "customer_name",
            "billing_address",
            "delivery_address",
            "subtotal_amount",
            "tax_amount",
            "grand_total",
            "total_quantity",
            "po_number",
            "customer_order_no",
            "primary_ref_no",
            "total_amount",
        },
        "COMPANY_INVOICE": {
            "invoice_no",
            "invoice_date",
            "customer_order_no",
            "so_no",
            "so_number",
            "po_reference",
            "customer_ref_no",
            "external_doc_no",
            "customer_name",
            "customer_address",
            "taxable_amount",
            "tax_amount",
            "net_amount",
            "grand_total",
            "total_quantity",
            "invoice_number",
            "total_amount",
        },
        "COMPANY_DC": {
            "dc_no",
            "dc_date",
            "customer_order_no",
            "sales_order_no",
            "so_no",
            "so_number",
            "po_reference",
            "customer_name",
            "delivery_address",
            "total_quantity",
            "estimated_amount",
            "dc_number",
            "total_amount",
        },
        "COMPANY_PO": {
            "po_number",
            "po_date",
            "vendor_po_no",
            "vendor_po_date",
            "vendor_name",
            "part_shipment_allowed",
            "mode_of_bill",
            "taxable_amount",
            "subtotal_amount",
            "tax_amount",
            "net_amount",
            "grand_total",
            "total_amount",
            "vendor_po_number",
        },
        "VENDOR_INVOICE": {
            "vendor_invoice_no",
            "vendor_invoice_date",
            "vendor_name",
            "po_reference",
            "customer_ref_no",
            "external_doc_no",
            "taxable_amount",
            "subtotal_amount",
            "tax_amount",
            "invoice_total",
            "net_amount",
            "total_amount",
            "invoice_number",
            "invoice_date",
            "bill_to_name",
            "ship_to_name",
            "vendor_gstin",
            "gstin",
            "buyer_gstin",
            "eway_bill_no",
            "ack_no",
            "irn",
        },
    }
    return set(by_type.get(document_type.upper(), set())) | common


HIGH_IMPACT_FIELDS = {
    "customer_po_no",
    "customer_order_no",
    "vendor_po_no",
    "po_reference",
    "invoice_total",
    "grand_total",
}
CRITICAL_REFERENCE_FIELDS = {"customer_po_no", "customer_order_no", "vendor_po_no", "po_reference"}
NUMERIC_FIELDS = {
    "subtotal_amount",
    "taxable_amount",
    "tax_amount",
    "grand_total",
    "total_amount",
    "net_amount",
    "invoice_total",
    "estimated_amount",
    "total_quantity",
}


def _validate_manual_patch(fields: dict[str, Any], reason: str | None) -> None:
    high_impact = sorted(field for field in fields if field in HIGH_IMPACT_FIELDS)
    if high_impact and not str(reason or "").strip():
        raise ValueError("Manual correction reason is required for high-impact fields: " + ", ".join(high_impact))
    blank_references = sorted(
        field
        for field in fields
        if field in CRITICAL_REFERENCE_FIELDS and str(fields.get(field) or "").strip() == ""
    )
    if blank_references:
        raise ValueError("Critical reference fields cannot be blank: " + ", ".join(blank_references))


def _normalize_manual_fields(fields: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in fields.items():
        if isinstance(value, str):
            value = value.strip()
        if key in NUMERIC_FIELDS and value not in (None, ""):
            try:
                number = Decimal(str(value).replace(",", ""))
            except InvalidOperation as exc:
                raise ValueError(f"Invalid numeric value for {key}.") from exc
            value = int(number) if number == number.to_integral_value() else float(number)
        normalized[key] = value
    return normalized
