from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.serializers import audit_event_to_dict, document_to_dict
from app.database import get_db
from app.domain.enums import DocumentType
from app.logging_config import log_event
from app.repositories.audit import AuditRepository
from app.repositories.bundles import BundleRepository
from app.repositories.documents import DocumentRepository
from app.schemas.bundle import BundleCreate, BundleRead
from app.services.storage_service import get_pdf_page_count, save_upload_file
from app.services.export_service import build_bundle_export
from app.services.verification_summary_service import build_verification_summary


router = APIRouter(prefix="/bundles", tags=["bundles"])


@router.post("", response_model=BundleRead, status_code=status.HTTP_201_CREATED)
def create_bundle(payload: BundleCreate, db: Session = Depends(get_db)):
    repo = BundleRepository(db)
    bundle = repo.create(payload)
    db.commit()
    db.refresh(bundle)
    log_event("bundle_created", bundle_id=bundle.id, bundle_number=bundle.bundle_number)
    return bundle


@router.get("", response_model=list[BundleRead])
def list_bundles(db: Session = Depends(get_db)):
    repo = BundleRepository(db)
    bundles = repo.list()
    result = []
    for bundle in bundles:
        summary = build_verification_summary(db, bundle.id)
        result.append(
            {
                "id": bundle.id,
                "bundle_number": bundle.bundle_number,
                "customer_name": bundle.customer_name,
                "customer_po_no": bundle.customer_po_no,
                "so_no": bundle.so_no,
                "status": bundle.status,
                "customer_delivery_status": bundle.customer_delivery_status,
                "vendor_procurement_status": bundle.vendor_procurement_status,
                "computed_status": summary.get("bundle_status"),
                "computed_customer_status": summary.get("customer_delivery_status"),
                "computed_vendor_status": summary.get("vendor_procurement_status"),
                "status_computed_at": bundle.updated_at,
                "created_at": bundle.created_at,
                "updated_at": bundle.updated_at,
            }
        )
    return result


@router.get("/{bundle_id}", response_model=BundleRead)
def get_bundle(bundle_id: str, db: Session = Depends(get_db)):
    bundle = BundleRepository(db).get(bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")
    return bundle


@router.post("/{bundle_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    bundle_id: str,
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not BundleRepository(db).get(bundle_id):
        raise HTTPException(status_code=404, detail="Bundle not found")
    storage_path = await save_upload_file(bundle_id=bundle_id, file=file)
    document = DocumentRepository(db).create(
        bundle_id=bundle_id,
        document_type=document_type.value,
        filename=file.filename or "uploaded-document",
        content_type=file.content_type,
        storage_path=storage_path,
    )
    if document.metadata_record:
        document.metadata_record.diagnostics = {"page_count": get_pdf_page_count(storage_path)}
    db.commit()
    document = DocumentRepository(db).get(document.id)
    storage_file = Path(storage_path)
    log_event(
        "document_uploaded",
        bundle_id=bundle_id,
        document_id=document.id,
        document_type=document.document_type,
        file_size_bytes=storage_file.stat().st_size if storage_file.exists() else None,
    )
    return document_to_dict(document)


@router.get("/{bundle_id}/documents")
def list_bundle_documents(bundle_id: str, db: Session = Depends(get_db)):
    if not BundleRepository(db).get(bundle_id):
        raise HTTPException(status_code=404, detail="Bundle not found")
    return [document_to_dict(document) for document in DocumentRepository(db).list_for_bundle(bundle_id)]


@router.get("/{bundle_id}/verification-summary")
def verification_summary(bundle_id: str, db: Session = Depends(get_db)):
    if not BundleRepository(db).get(bundle_id):
        raise HTTPException(status_code=404, detail="Bundle not found")
    summary = build_verification_summary(db, bundle_id)
    log_event(
        "verification_summary_calculated",
        bundle_id=bundle_id,
        bundle_status=summary.get("bundle_status"),
        customer_delivery_status=summary.get("customer_delivery_status"),
        vendor_procurement_status=summary.get("vendor_procurement_status"),
        issue_count=len(summary.get("issues") or []),
        check_count=len(summary.get("checks") or []),
    )
    return summary


@router.get("/{bundle_id}/audit-events")
def list_audit_events(bundle_id: str, db: Session = Depends(get_db)):
    if not BundleRepository(db).get(bundle_id):
        raise HTTPException(status_code=404, detail="Bundle not found")
    return [audit_event_to_dict(event) for event in AuditRepository(db).list_for_bundle(bundle_id)]


@router.get("/{bundle_id}/export.xlsx")
def export_bundle(bundle_id: str, db: Session = Depends(get_db)):
    bundle = BundleRepository(db).get(bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")
    log_event("export_started", bundle_id=bundle_id)
    try:
        content = build_bundle_export(db, bundle_id)
    except Exception as exc:
        log_event("export_failed", bundle_id=bundle_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Export failed") from exc
    log_event("export_completed", bundle_id=bundle_id, size_bytes=len(content))
    filename = f"{bundle.bundle_number}-verification-report.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
