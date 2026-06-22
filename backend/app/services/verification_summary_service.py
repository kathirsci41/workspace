from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.repositories.bundles import BundleRepository
from app.repositories.documents import DocumentRepository
from app.services.document_normalizer import normalize_document
from app.services.order_bundle_verifier import verify_order_bundle
from app.services.vendor_master_service import apply_vendor_master_checks


VERIFICATION_READY_METADATA_STATUSES = {"EXTRACTED", "MANUAL_ENTRY"}


def build_verification_summary(db: Session, bundle_id: str) -> dict:
    documents = DocumentRepository(db).list_for_bundle(bundle_id)
    normalized = [
        normalize_document(document, document.metadata_record.extracted_data if document.metadata_record else {})
        for document in documents
        if document.metadata_record
        and document.metadata_record.status in VERIFICATION_READY_METADATA_STATUSES
    ]
    summary = verify_order_bundle(normalized)
    return apply_vendor_master_checks(db, normalized, summary)


def sync_bundle_status_from_verification(db: Session, bundle_id: str, summary: dict | None = None) -> dict:
    summary = summary or build_verification_summary(db, bundle_id)
    bundle = BundleRepository(db).get(bundle_id)
    if not bundle:
        return summary

    extracted = summary.get("extracted_summary") or {}
    changed = False
    updates = {
        "status": summary.get("bundle_status"),
        "customer_delivery_status": summary.get("customer_delivery_status"),
        "vendor_procurement_status": summary.get("vendor_procurement_status"),
    }
    for field, value in updates.items():
        if value is not None and getattr(bundle, field) != value:
            setattr(bundle, field, value)
            changed = True

    header_updates = {
        "customer_po_no": extracted.get("customer_po_no"),
        "so_no": extracted.get("so_no"),
        "customer_name": extracted.get("customer_name"),
    }
    for field, value in header_updates.items():
        if value and getattr(bundle, field) != value:
            setattr(bundle, field, str(value))
            changed = True

    bundle.last_verified_at = datetime.now(timezone.utc)
    if changed:
        bundle.updated_at = datetime.now(timezone.utc)
    db.flush()
    return summary
