from __future__ import annotations

from typing import Any

from app.models.reference_index import ReferenceIndexRecord


REFERENCE_FIELDS = (
    "customer_po_no",
    "customer_order_no",
    "primary_ref_no",
    "invoice_no",
    "invoice_number",
    "dc_no",
    "dc_number",
    "so_no",
    "so_number",
    "vendor_po_no",
    "vendor_invoice_no",
    "po_reference",
    "customer_ref_no",
    "external_doc_no",
    "po_ref_no",
)


def build_reference_index(
    document_id: str,
    extracted_data: dict[str, Any],
    order_bundle_id: str | None = None,
    *,
    document_type: str | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> list[ReferenceIndexRecord]:
    diagnostics = diagnostics or {}
    field_metadata = diagnostics.get("field_metadata") or {}
    records: list[ReferenceIndexRecord] = []
    seen: set[tuple[str, str]] = set()
    for field in REFERENCE_FIELDS:
        value = extracted_data.get(field)
        if value in (None, ""):
            continue
        normalized_value = str(value).strip()
        key = (field, normalized_value)
        if key in seen:
            continue
        seen.add(key)
        details = field_metadata.get(field) or {}
        source = details.get("source") or "extracted"
        records.append(
            ReferenceIndexRecord(
                document_id=document_id,
                order_bundle_id=order_bundle_id,
                reference_type=field,
                reference_value=normalized_value,
                source_type=str(source),
                document_type=document_type,
                field_name=field,
                confidence=details.get("confidence"),
                evidence_text=_safe_evidence(details.get("evidence_text")),
            )
        )
    return records


def _safe_evidence(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)[:500]
