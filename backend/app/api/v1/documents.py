from uuid import UUID
from fastapi import APIRouter, Depends, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io

from app.database import get_db
from app.schemas.document import DocumentResponse, DocumentUploadResponse
from app.schemas.extraction import ExtractionResponse
from app.services import document_service

router = APIRouter()


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
    file_data, mime_type, original_filename = await document_service.get_preview_data(db, id)
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
    file_data, mime_type, original_filename = await document_service.get_preview_data(db, id)
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
        if doc.purchase_order.customer:
            resp.customer_name = doc.purchase_order.customer.name
    if doc.doc_metadata:
        resp.metadata = ExtractionResponse.model_validate(doc.doc_metadata)
    return resp
