from uuid import UUID
from datetime import date, datetime, time, timezone
from fastapi import APIRouter, Depends, Body, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import io

from app.database import get_db
from app.models.document import Document, DocumentStatus, DocumentType
from app.models.purchase_order import PurchaseOrder
from app.schemas.document import DocumentResponse, DocumentUploadResponse, DocumentListResponse
from app.schemas.extraction import ExtractionResponse
from app.services import document_service
from app.services.storage_service import NASUnavailableError

router = APIRouter()


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    status: str | None = Query(None, description="Filter by document status"),
    document_type: str | None = Query(None, description="Filter by document type"),
    customer_id: UUID | None = Query(None, description="Filter by customer (via PO)"),
    date_from: date | None = Query(None, description="Uploaded on or after this date"),
    date_to: date | None = Query(None, description="Uploaded on or before this date"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List documents across all POs with optional filters."""
    query = (
        select(Document)
        .options(
            selectinload(Document.purchase_order).selectinload(PurchaseOrder.customer),
            selectinload(Document.doc_metadata),
        )
        .order_by(Document.updated_at.desc())
    )

    # Existing status filter — unchanged
    if status:
        try:
            status_enum = DocumentStatus[status.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Unknown status: {status}")
        query = query.where(Document.status == status_enum)

    # New: document type filter
    if document_type:
        try:
            doc_type_enum = DocumentType[document_type.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Unknown document_type: {document_type}")
        query = query.where(Document.document_type == doc_type_enum)

    # New: customer filter — join through PO
    if customer_id:
        query = query.join(Document.purchase_order).where(PurchaseOrder.customer_id == customer_id)

    # New: date range filter on created_at
    if date_from:
        query = query.where(Document.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        query = query.where(Document.created_at <= datetime.combine(date_to, time.max))

    offset = (page - 1) * per_page
    result = await db.execute(query.offset(offset).limit(per_page))
    docs = list(result.scalars().all())

    # Count with same filters
    count_query = select(func.count()).select_from(Document)
    if status:
        count_query = count_query.where(Document.status == DocumentStatus[status.upper()])
    if document_type:
        count_query = count_query.where(Document.document_type == DocumentType[document_type.upper()])
    if customer_id:
        count_query = count_query.join(Document.purchase_order).where(PurchaseOrder.customer_id == customer_id)
    if date_from:
        count_query = count_query.where(Document.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        count_query = count_query.where(Document.created_at <= datetime.combine(date_to, time.max))
    total = (await db.execute(count_query)).scalar_one()

    items = []
    for doc in docs:
        resp = DocumentResponse(
            id=doc.id,
            po_id=doc.po_id,
            document_type=doc.document_type.value if hasattr(doc.document_type, "value") else doc.document_type,
            filename=doc.filename,
            original_filename=doc.original_filename,
            file_path=doc.file_path,
            file_size=doc.file_size,
            mime_type=doc.mime_type,
            page_count=doc.page_count,
            checksum=doc.checksum,
            status=doc.status.value if hasattr(doc.status, "value") else doc.status,
            rotation=getattr(doc, "rotation", 0),
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
        if doc.status == DocumentStatus.PENDING_REVIEW and doc.updated_at:
            delta = datetime.now(timezone.utc) - doc.updated_at.replace(tzinfo=timezone.utc)
            resp.days_pending = delta.days
        items.append(resp)

    return DocumentListResponse(items=items, total=total)


@router.get("/{id}", response_model=DocumentResponse)
async def get_document(
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    doc = await document_service.get_document(db, id)
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


@router.delete("/{id}", status_code=204)
async def delete_document(
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    await document_service.delete_document(db, id)


@router.get("/{id}/preview")
async def preview_document(
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    try:
        file_data, mime_type, original_filename = await document_service.get_preview_data(db, id)
    except NASUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return StreamingResponse(
        io.BytesIO(file_data),
        media_type=mime_type,
        headers={"Content-Disposition": f'inline; filename="{original_filename}"'},
    )


@router.get("/{id}/download")
async def download_document(
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    try:
        file_data, mime_type, original_filename = await document_service.get_preview_data(db, id)
    except NASUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return StreamingResponse(
        io.BytesIO(file_data),
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{original_filename}"'},
    )


@router.post("/{id}/rotate", response_model=DocumentResponse)
async def rotate_document(
    id: UUID,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
):
    angle = body.get("angle", 90)
    if angle not in (90, 180, 270):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Angle must be 90, 180, or 270")

    doc = await document_service.get_document(db, id)
    doc.rotation = (doc.rotation + angle) % 360
    await db.commit()
    await db.refresh(doc)

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
