from __future__ import annotations

import fitz
from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.serializers import audit_event_to_dict, document_to_dict, metadata_to_dict, reference_to_dict
from app.database import get_db
from app.logging_config import log_event
from app.repositories.documents import DocumentRepository
from app.repositories.reference_index import ReferenceIndexRepository
from app.schemas.audit import AuditEventCreate
from app.schemas.document import ExtractionRequest, ManualExtractedDataPatch
from app.services.audit_service import AuditService
from app.services.extraction_service import extract_document
from app.services.extraction_queue import OcrExtractionQueueFullError, OcrExtractionQueueTimeoutError
from app.services.file_cleanup_service import delete_document_file
from app.services.manual_metadata_service import patch_extracted_data
from app.services.storage_service import resolve_stored_pdf_path
from app.services.verification_summary_service import sync_bundle_status_from_verification


router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{document_id}")
def get_document(document_id: str, db: Session = Depends(get_db)):
    document = DocumentRepository(db).get(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document_to_dict(document)


@router.get("/{document_id}/preview")
def preview_document(document_id: str, db: Session = Depends(get_db)):
    document = DocumentRepository(db).get(document_id)
    if not document or not document.storage_path:
        raise HTTPException(status_code=404, detail="Document preview not found")
    resolved_path = resolve_stored_pdf_path(document.storage_path)
    if not resolved_path or not resolved_path.is_file():
        raise HTTPException(status_code=404, detail="Document preview not found")
    return FileResponse(
        path=resolved_path,
        media_type="application/pdf",
        filename=document.filename,
        content_disposition_type="inline",
    )


@router.get("/{document_id}/preview/pages/{page_number}.png")
def preview_document_page(document_id: str, page_number: int, db: Session = Depends(get_db)):
    document = DocumentRepository(db).get(document_id)
    if not document or not document.storage_path:
        raise HTTPException(status_code=404, detail="Document preview not found")
    resolved_path = resolve_stored_pdf_path(document.storage_path)
    if not resolved_path or not resolved_path.is_file():
        raise HTTPException(status_code=404, detail="Document preview not found")
    try:
        with fitz.open(resolved_path) as pdf:
            if page_number < 1 or page_number > pdf.page_count:
                raise HTTPException(status_code=404, detail="PDF page not found")
            pixmap = pdf[page_number - 1].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            content = pixmap.tobytes("png")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Unable to render PDF page: {exc}") from exc
    return Response(content=content, media_type="image/png")


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, db: Session = Depends(get_db)):
    repo = DocumentRepository(db)
    document = repo.get(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    bundle_id = document.order_bundle_id
    delete_document_file(document)
    AuditService(db).record_event(
        AuditEventCreate(
            event_type="document_deleted",
            actor="system",
            order_bundle_id=bundle_id,
            payload={"document_id": document.id, "document_type": document.document_type, "filename": document.filename},
        )
    )
    repo.delete(document)
    sync_bundle_status_from_verification(db, bundle_id)
    db.commit()
    return None


def _run_extraction(
    db: Session,
    document_id: str,
    *,
    force: bool,
    payload: ExtractionRequest | None = None,
):
    document = DocumentRepository(db).get(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        result = extract_document(
            db,
            document,
            force=force,
            ocr_rotation_degrees=payload.ocr_rotation_degrees if payload else None,
        )
        sync_bundle_status_from_verification(db, document.order_bundle_id)
        _diag = (document.metadata_record.diagnostics if document.metadata_record else {}) or {}
        _failure_code = _diag.get("failure_code")
        AuditService(db).record_event(
            AuditEventCreate(
                event_type="extraction_failed" if _failure_code else "extraction_completed",
                actor="system",
                order_bundle_id=document.order_bundle_id,
                document_id=document.id,
                payload={
                    "document_type": document.document_type,
                    "filename": document.filename,
                    "metadata_status": document.metadata_record.status if document.metadata_record else None,
                    "extraction_route": _diag.get("extraction_route"),
                    "ocr_provider": _diag.get("ocr_provider"),
                    "fallback_used": _diag.get("fallback_used"),
                    "failure_code": _failure_code,
                    "failure_reason": _diag.get("failure_reason"),
                },
            )
        )
        db.commit()
        db.refresh(document)
    except (OcrExtractionQueueFullError, OcrExtractionQueueTimeoutError) as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OperationalError as exc:
        db.rollback()
        if "database is locked" in str(exc).lower():
            raise HTTPException(
                status_code=503,
                detail="Another extraction is in progress. Please wait a moment and try again.",
            ) from exc
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "document": document_to_dict(document),
        "metadata": metadata_to_dict(document.metadata_record),
        "references": [reference_to_dict(reference) for reference in result["references"]],
    }


@router.post("/{document_id}/extract")
def extract_document_route(
    document_id: str,
    payload: ExtractionRequest | None = Body(default=None),
    db: Session = Depends(get_db),
):
    return _run_extraction(db, document_id, force=False, payload=payload)


@router.post("/{document_id}/re-extract")
def reextract_document_route(
    document_id: str,
    payload: ExtractionRequest | None = Body(default=None),
    db: Session = Depends(get_db),
):
    return _run_extraction(db, document_id, force=True, payload=payload)


@router.patch("/{document_id}/extracted-data")
def patch_document_extracted_data(
    document_id: str,
    payload: ManualExtractedDataPatch,
    db: Session = Depends(get_db),
):
    document = DocumentRepository(db).get(document_id)
    if not document or not document.metadata_record:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        result = patch_extracted_data(
            document=document,
            metadata=document.metadata_record,
            fields=payload.fields,
            audit_service=AuditService(db),
            actor=payload.actor,
            reason=payload.reason,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Manual extracted-data patch failed.") from exc
    references = ReferenceIndexRepository(db).replace_for_document(
        document.id,
        result["metadata"].extracted_data,
        document.order_bundle_id,
        document_type=document.document_type,
        diagnostics=result["metadata"].diagnostics,
    )
    log_event(
        "reference_index_rebuilt",
        bundle_id=document.order_bundle_id,
        document_id=document.id,
        document_type=document.document_type,
        reference_count=len(references),
    )
    sync_bundle_status_from_verification(db, document.order_bundle_id)
    db.commit()
    db.refresh(document)
    log_event(
        "manual_metadata_patch",
        bundle_id=document.order_bundle_id,
        document_id=document.id,
        document_type=document.document_type,
        patched_field_count=len(payload.fields),
        missing_required_fields=result["metadata"].diagnostics.get("missing_required_fields", []),
    )
    return {
        "document": document_to_dict(document),
        "metadata": metadata_to_dict(document.metadata_record),
        "references": [reference_to_dict(reference) for reference in references],
        "audit_event": audit_event_to_dict(result["audit_event"]),
    }
