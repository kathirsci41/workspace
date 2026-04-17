from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response as FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from typing import Optional
from pydantic import BaseModel
from app.schemas.purchase_order import (
    POCreate, POUpdate, POResponse, POListResponse, ChainStatusResponse,
    SONumberUpdate,
)
from app.schemas.po_profile import POProfileResponse
from app.schemas.document import DocumentResponse, DocumentListResponse
from app.models.purchase_order import PurchaseOrder
from app.models.document import Document, DocumentType
from app.services import po_service
from app.services import export_service
from app.services.chain_validator import compute_chain_status

router = APIRouter()


@router.post("", response_model=POResponse, status_code=201)
async def create_po(
    data: POCreate,
    db: AsyncSession = Depends(get_db),
):
    po = await po_service.create_po(db, data)
    resp = POResponse.model_validate(po)
    if po.customer:
        resp.customer_name = po.customer.name
        resp.customer_sky_id = po.customer.customer_id
    return resp


@router.get("", response_model=POListResponse)
async def list_pos(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    customer_id: UUID | None = Query(None),
    status: str | None = Query(None),
    search: str | None = Query(None),
    date_from: date | None = Query(None, description="Filter POs with po_date on or after this date"),
    date_to: date | None = Query(None, description="Filter POs with po_date on or before this date"),
    sort_by: str = Query("created_at", description="Sort field: created_at | po_date | chain_completeness | total_amount"),
    sort_order: str = Query("desc", description="Sort direction: asc | desc"),
    chain_filter: str | None = Query(None, description="incomplete | critical | complete"),
    missing_doc_type: str | None = Query(None, description="Filter POs missing a specific doc type"),
    db: AsyncSession = Depends(get_db),
):
    items, total = await po_service.list_pos(
        db, page=page, per_page=per_page,
        customer_id=customer_id, status=status, search=search,
        date_from=date_from, date_to=date_to,
        sort_by=sort_by, sort_order=sort_order,
        chain_filter=chain_filter, missing_doc_type=missing_doc_type,
    )

    responses = []
    for po in items:
        resp = POResponse.model_validate(po)
        if po.customer:
            resp.customer_name = po.customer.name
            resp.customer_sky_id = po.customer.customer_id
        responses.append(resp)

    return POListResponse(
        items=responses, total=total, page=page, per_page=per_page,
    )


@router.get("/{id}", response_model=POResponse)
async def get_po(
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    po = await po_service.get_po(db, id)
    resp = POResponse.model_validate(po)
    if po.customer:
        resp.customer_name = po.customer.name
        resp.customer_sky_id = po.customer.customer_id
    return resp


@router.patch("/{id}", response_model=POResponse)
async def update_po(
    id: UUID,
    data: POUpdate,
    db: AsyncSession = Depends(get_db),
):
    po = await po_service.update_po(db, id, data)
    resp = POResponse.model_validate(po)
    if po.customer:
        resp.customer_name = po.customer.name
        resp.customer_sky_id = po.customer.customer_id
    return resp


@router.patch("/{po_id}/so-number", response_model=POResponse)
async def update_so_number(
    po_id: UUID,
    body: SONumberUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update SO number and return the full updated PO."""
    po = await db.get(
        PurchaseOrder,
        po_id,
        options=[selectinload(PurchaseOrder.documents)],
    )
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    po.so_number = body.so_number.strip() or None
    await db.commit()
    await db.refresh(po)
    resp = POResponse.model_validate(po)
    if po.customer:
        resp.customer_name = po.customer.name
        resp.customer_sky_id = po.customer.customer_id
    return resp


@router.get("/{po_id}/chain")
async def get_chain_status_v2(
    po_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Compute and return current chain validation status for a PO."""
    po = await db.get(
        PurchaseOrder,
        po_id,
        options=[selectinload(PurchaseOrder.documents).selectinload(Document.doc_metadata)],
    )
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    # VPO numbers: from COMPANY_PO documents' extracted vpo_numbers field
    vpo_numbers = []
    for doc in po.documents:
        if doc.document_type == DocumentType.COMPANY_PO and doc.vpo_numbers:
            vpo_numbers.extend(doc.vpo_numbers)

    # Invoiced total: sum of COMPANY_INVOICE metadata total_amount
    invoiced_total = sum(
        float(doc.doc_metadata.total_amount or 0)
        for doc in po.documents
        if doc.document_type == DocumentType.COMPANY_INVOICE and doc.doc_metadata
    )

    docs_payload = [
        {
            "document_type": doc.document_type,
            "so_number": doc.so_number,
            "vpo_numbers": doc.vpo_numbers or [],
            "extraction_ok": doc.extraction_ok,
            "cpo_ref": doc.doc_metadata.po_ref_no if doc.doc_metadata else None,
            "billing_stage": doc.billing_stage,
            "amount": float(doc.doc_metadata.total_amount or 0) if doc.doc_metadata else 0,
        }
        for doc in po.documents
    ]

    result = compute_chain_status(
        scenario=po.order_scenario,
        po_number=po.po_number,
        so_number=po.so_number,
        po_total=float(po.total_amount) if po.total_amount else None,
        billing_type=po.billing_type,
        billing_milestones=po.billing_milestones or [],
        vpo_numbers=vpo_numbers,
        documents=docs_payload,
        requires_install_report=po.requires_install_report,
        invoiced_total=invoiced_total,
    )

    # Fall back to stored chain_completeness when scenario produces no required slots
    if result["completeness_pct"] == 0 and po.chain_completeness:
        result["completeness_pct"] = int(po.chain_completeness)

    # Update chain_status on PO in the background (best-effort, non-blocking)
    try:
        po.chain_status = result["chain_status"]
        await db.commit()
    except Exception:
        await db.rollback()

    return result


class CloseOrderRequest(BaseModel):
    note: Optional[str] = None


@router.post("/{id}/close", response_model=POResponse)
async def close_order(
    id: UUID,
    body: CloseOrderRequest = CloseOrderRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Manually close a PO — marks order as completed. One-way operation."""
    from app.models.purchase_order import ChainStatus
    po = await po_service.close_order(db, id, body.note)
    resp = POResponse.model_validate(po)
    if po.customer:
        resp.customer_name = po.customer.name
        resp.customer_sky_id = po.customer.customer_id
    if po.chain_status == ChainStatus.MISMATCH:
        from fastapi.responses import JSONResponse
        data = resp.model_dump(mode="json")
        data["_warning"] = "Order closed with unresolved reference mismatches. Review chain validation before dispatch."
        return JSONResponse(content=data)
    return resp


@router.delete("/{id}", status_code=204)
async def delete_po(
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    await po_service.delete_po(db, id)


@router.get("/{id}/chain-status", response_model=ChainStatusResponse)
async def get_chain_status(
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    return await po_service.get_chain_status(db, id)


@router.get("/{id}/profile", response_model=POProfileResponse)
async def get_po_profile(
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    return await po_service.get_po_profile(db, id)


@router.get("/{id}/export")
async def export_po_excel(
    id: UUID,
    mode: str = Query("separate"),
    db: AsyncSession = Depends(get_db),
):
    excel_bytes = await export_service.export_po_to_excel(db, id, mode=mode)
    profile = await po_service.get_po_profile(db, id)
    safe_number = profile.po_number.replace("/", "-").replace(" ", "_")
    suffix = "_consolidated" if mode == "single" else ""
    filename = f"PO_{safe_number}{suffix}_{date.today().isoformat()}.xlsx"
    return FileResponse(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# === Document upload nested under PO ===

from fastapi import UploadFile, File, Form
from pathlib import Path
from app.schemas.document import DocumentUploadResponse, DocumentResponse, DocumentListResponse
from app.schemas.extraction import ExtractionResponse
from app.services import document_service


# Format Gate - PDF only (scanned or digital)
ALLOWED_MIME_TYPES = {
    "application/pdf",
}
ALLOWED_EXTENSIONS = {".pdf"}


def validate_upload_file(filename: str, content_type: str) -> None:
    """Raise HTTPException if file is not a PDF.

    The OCR pipeline processes PDFs only (scanned or digital).
    Phone photos must be converted to PDF before uploading.
    """
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS and content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                "Only PDF files are accepted (scanned or digital). "
                "Please convert your document to PDF before uploading."
            )
        )


@router.post("/{po_id}/documents", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    po_id: UUID,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    # Phase 2: Validate file format before processing
    validate_upload_file(file.filename, file.content_type)

    doc = await document_service.upload_document(db, po_id, document_type, file)
    return DocumentUploadResponse.model_validate(doc)


@router.get("/{po_id}/documents", response_model=DocumentListResponse)
async def list_po_documents(
    po_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    docs = await document_service.list_documents_for_po(db, po_id)
    items = []
    for doc in docs:
        resp = _build_doc_response(doc)
        items.append(resp)
    return DocumentListResponse(items=items, total=len(items))


def _build_doc_response(doc) -> DocumentResponse:
    """Build DocumentResponse avoiding SQLAlchemy Base.metadata collision."""
    resp = DocumentResponse(
        id=doc.id,
        po_id=doc.po_id,
        document_type=doc.document_type.value if hasattr(doc.document_type, 'value') else doc.document_type,
        filename=doc.filename,
        original_filename=doc.original_filename,
        file_path=doc.file_path,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
        page_count=doc.page_count,
        checksum=doc.checksum,
        status=doc.status.value if hasattr(doc.status, 'value') else doc.status,
        rotation=getattr(doc, 'rotation', 0),
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )
    if doc.purchase_order:
        resp.po_number = doc.purchase_order.po_number
        resp.po_so_number = doc.purchase_order.so_number
        if doc.purchase_order.customer:
            resp.customer_name = doc.purchase_order.customer.name
    if doc.doc_metadata:
        resp.metadata = ExtractionResponse.model_validate(doc.doc_metadata)
    return resp
