from __future__ import annotations

from datetime import datetime
from io import BytesIO
import json
from typing import Any

from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.repositories.audit import AuditRepository
from app.repositories.documents import DocumentRepository
from app.repositories.reference_index import ReferenceIndexRepository
from app.services.verification_summary_service import build_verification_summary


def build_bundle_export(db: Session, bundle_id: str) -> bytes:
    summary = build_verification_summary(db, bundle_id)
    documents = DocumentRepository(db).list_for_bundle(bundle_id)
    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "Verification Summary"
    _write_summary(summary_sheet, summary, documents)
    _write_documents(workbook.create_sheet("Documents"), documents)
    _write_checks(workbook.create_sheet("Checks"), summary.get("checks", []))
    _write_fields(workbook.create_sheet("Extracted Fields"), documents)
    _write_references(workbook.create_sheet("References"), ReferenceIndexRepository(db).list_for_bundle(bundle_id))
    _write_audit(workbook.create_sheet("Audit Trail"), AuditRepository(db).list_for_bundle(bundle_id))
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _write_summary(sheet, summary: dict[str, Any], documents=()) -> None:
    extracted = summary.get("extracted_summary", {})
    issues = summary.get("issues", [])
    difference = next((issue.get("difference") for issue in issues if issue.get("difference") is not None), None)
    rows = [
        ("Bundle Status", summary.get("bundle_status")),
        ("Customer Delivery Status", summary.get("customer_delivery_status")),
        ("Vendor Procurement Status", summary.get("vendor_procurement_status")),
        ("Recommendation", summary.get("recommendation")),
        ("Customer PO No", extracted.get("customer_po_no")),
        ("SO No", extracted.get("so_no")),
        ("Customer Invoice No", _join(extracted.get("customer_invoice_numbers"))),
        ("DC No", _join(extracted.get("dc_numbers"))),
        ("Vendor PO No", _join(extracted.get("vendor_po_numbers"))),
        ("Vendor Invoice No", _join(extracted.get("vendor_invoice_numbers"))),
        (
            "Vendor PO Total",
            _issue_value(issues, "vendor_po_total")
            or _document_total(documents, {"COMPANY_PO", "VENDOR_PO"}, ("net_amount", "total_amount", "grand_total")),
        ),
        (
            "Vendor Invoice Total",
            _issue_value(issues, "vendor_invoice_total")
            or extracted.get("vendor_total")
            or _document_total(documents, {"VENDOR_INVOICE", "VENDOR_BILL"}, ("invoice_total", "net_amount", "total_amount", "grand_total")),
        ),
        ("Difference", difference),
        ("Issues", "\n".join(str(issue.get("message") or issue.get("code")) for issue in issues)),
    ]
    for row in rows:
        sheet.append(row)


def _write_documents(sheet, documents) -> None:
    sheet.append(["Document Type", "Filename", "Document Status", "Metadata Status", "Extraction Route", "Failure Code", "Failure Reason"])
    for document in documents:
        metadata = document.metadata_record
        diagnostics = metadata.diagnostics if metadata else {}
        sheet.append(
            [
                document.document_type,
                document.filename,
                document.status,
                metadata.status if metadata else None,
                diagnostics.get("extraction_route"),
                diagnostics.get("failure_code"),
                diagnostics.get("failure_reason"),
            ]
        )


def _write_checks(sheet, checks: list[dict[str, Any]]) -> None:
    sheet.append(["Check ID", "Check Name", "Result", "Severity", "Left Document", "Left Value", "Right Document", "Right Value", "Message"])
    for check in checks:
        sheet.append(
            [
                check.get("check_id"),
                check.get("check_name"),
                check.get("result"),
                check.get("severity"),
                check.get("left_document_type"),
                check.get("left_value"),
                check.get("right_document_type"),
                check.get("right_value"),
                check.get("message"),
            ]
        )


def _write_fields(sheet, documents) -> None:
    sheet.append(["Document Type", "Field", "Value", "Source", "Confidence", "Evidence Text", "Page", "BBox", "Failure Reason"])
    for document in documents:
        metadata = document.metadata_record
        if not metadata:
            continue
        source = metadata.extracted_data.get("extraction_source")
        field_metadata = metadata.diagnostics.get("field_metadata") or {}
        field_locations = metadata.diagnostics.get("field_locations") or {}
        for field, value in metadata.extracted_data.items():
            if str(field).startswith("raw_"):
                continue
            details = field_metadata.get(field, {})
            location = field_locations.get(field, {})
            sheet.append(
                [
                    document.document_type,
                    field,
                    value,
                    details.get("source") or source,
                    details.get("confidence", metadata.diagnostics.get("parser_confidence")),
                    location.get("evidence_text") or details.get("evidence_text"),
                    location.get("page"),
                    json.dumps(location.get("bbox")) if location.get("bbox") else None,
                    metadata.diagnostics.get("failure_reason"),
                ]
            )


def _write_audit(sheet, events) -> None:
    sheet.append(["Timestamp", "Document Type", "Action", "Field", "Old Value", "New Value", "Source/Actor", "Reason", "Request ID"])
    for event in events:
        payload = event.payload or {}
        changes = payload.get("changes") or []
        if not changes:
            sheet.append(
                [
                    _excel_value(event.created_at),
                    payload.get("document_type"),
                    event.event_type,
                    None,
                    None,
                    None,
                    payload.get("source") or event.actor,
                    payload.get("reason"),
                    payload.get("request_id"),
                ]
            )
            continue
        for change in changes:
            sheet.append(
                [
                    _excel_value(event.created_at),
                    payload.get("document_type"),
                    event.event_type,
                    change.get("field"),
                    change.get("old_value"),
                    change.get("new_value"),
                    payload.get("source") or event.actor,
                    payload.get("reason"),
                    payload.get("request_id"),
                ]
            )


def _write_references(sheet, references) -> None:
    sheet.append(["Document Type", "Field Name", "Reference Type", "Reference Value", "Source Type", "Confidence", "Evidence Text", "Created At"])
    for reference in references:
        sheet.append(
            [
                reference.document_type,
                reference.field_name,
                reference.reference_type,
                reference.reference_value,
                reference.source_type,
                reference.confidence,
                reference.evidence_text,
                _excel_value(reference.created_at),
            ]
        )


def _join(value: Any) -> str | None:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value) if value is not None else None


def _issue_value(issues: list[dict[str, Any]], key: str) -> Any:
    return next((issue.get(key) for issue in issues if issue.get(key) is not None), None)


def _document_total(documents, document_types: set[str], fields: tuple[str, ...]) -> float | int | None:
    values: list[float] = []
    for document in documents:
        if str(document.document_type).upper() not in document_types:
            continue
        metadata = document.metadata_record
        extracted_data = metadata.extracted_data if metadata else {}
        for field in fields:
            value = extracted_data.get(field)
            try:
                number = float(str(value).replace(",", ""))
            except (TypeError, ValueError):
                continue
            values.append(number)
            break
    if not values:
        return None
    total = sum(values)
    return int(total) if total.is_integer() else round(total, 2)


def _excel_value(value: Any) -> Any:
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value
