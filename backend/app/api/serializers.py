from __future__ import annotations

from app.models.audit_event import AuditEventRecord
from app.models.document import DocumentRecord
from app.models.document_metadata import DocumentMetadataRecord
from app.models.reference_index import ReferenceIndexRecord


def metadata_to_dict(metadata: DocumentMetadataRecord | None) -> dict | None:
    if metadata is None:
        return None
    diagnostics = metadata.diagnostics or {}
    extracted_data = _public_extracted_data(metadata.extracted_data or {})
    field_metadata = diagnostics.get("field_metadata") or {}
    field_locations = diagnostics.get("field_locations") or {}
    field_confidences = {field: details.get("confidence") for field, details in field_metadata.items()}
    field_evidence = {
        field: (field_locations.get(field) or {}).get("evidence_text") or details.get("evidence_text")
        for field, details in field_metadata.items()
    }
    return {
        "id": metadata.id,
        "document_id": metadata.document_id,
        "status": metadata.status,
        "extracted_data": extracted_data,
        "diagnostics": diagnostics,
        "field_confidences": field_confidences,
        "field_evidence": field_evidence,
        "field_locations": field_locations,
        "primary_ref_no": metadata.primary_ref_no,
        "po_ref_no": metadata.po_ref_no,
        "last_error": metadata.last_error,
    }


def document_to_dict(document: DocumentRecord) -> dict:
    return {
        "id": document.id,
        "order_bundle_id": document.order_bundle_id,
        "document_type": document.document_type,
        "filename": document.filename,
        "content_type": document.content_type,
        "status": document.status,
        "last_error": document.last_error,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
        "metadata": metadata_to_dict(document.metadata_record),
    }


def _public_extracted_data(extracted_data: dict) -> dict:
    return {key: value for key, value in extracted_data.items() if key not in {"raw_text", "raw_ocr_text"}}


def reference_to_dict(reference: ReferenceIndexRecord) -> dict:
    return {
        "id": reference.id,
        "document_id": reference.document_id,
        "order_bundle_id": reference.order_bundle_id,
        "reference_type": reference.reference_type,
        "reference_value": reference.reference_value,
        "source_type": reference.source_type,
        "document_type": reference.document_type,
        "field_name": reference.field_name,
        "confidence": reference.confidence,
        "evidence_text": reference.evidence_text,
        "created_at": reference.created_at,
    }


def audit_event_to_dict(event: AuditEventRecord) -> dict:
    return {
        "id": event.id,
        "event_type": event.event_type,
        "actor": event.actor,
        "document_id": event.document_id,
        "order_bundle_id": event.order_bundle_id,
        "payload": event.payload or {},
        "created_at": event.created_at,
    }
