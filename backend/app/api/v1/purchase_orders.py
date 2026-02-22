from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.purchase_order import (
    POCreate, POUpdate, POResponse, POListResponse, ChainStatusResponse,
)
from app.schemas.document import DocumentResponse, DocumentListResponse
from app.services import po_service

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
    db: AsyncSession = Depends(get_db),
):
    items, total = await po_service.list_pos(
        db, page=page, per_page=per_page,
        customer_id=customer_id, status=status, search=search,
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


# === Document upload nested under PO ===

from fastapi import UploadFile, File, Form
from app.schemas.document import DocumentUploadResponse, DocumentResponse, DocumentListResponse
from app.schemas.extraction import ExtractionResponse
from app.services import document_service


@router.post("/{po_id}/documents", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    po_id: UUID,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
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
    if doc.doc_metadata:
        resp.metadata = ExtractionResponse.model_validate(doc.doc_metadata)
    return resp
