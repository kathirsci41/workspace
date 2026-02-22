from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, distinct, delete as sa_delete
from sqlalchemy.orm import selectinload, joinedload
from fastapi import HTTPException

from app.models.customer import Customer
from app.models.purchase_order import PurchaseOrder, POStatus
from app.models.document import Document, DocumentType, DocumentStatus
from app.models.document_metadata import DocumentMetadata
from app.models.reference_index import ReferenceIndex
from app.schemas.purchase_order import POCreate, POUpdate, ChainSlot, ChainStatusResponse
from app.services.storage_service import StorageService
from app.config import settings

storage_service = StorageService(settings.nas_base_path)


CHAIN_DOC_TYPES = [
    DocumentType.CUSTOMER_PO,
    DocumentType.COMPANY_PO,
    DocumentType.VENDOR_DC,
    DocumentType.VENDOR_INVOICE,
    DocumentType.COMPANY_DC,
    DocumentType.COMPANY_INVOICE,
]


async def create_po(db: AsyncSession, data: POCreate) -> PurchaseOrder:
    """Create a new purchase order."""
    # Verify customer exists
    customer = (await db.execute(
        select(Customer).where(Customer.id == data.customer_id)
    )).scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=400, detail="Customer not found")

    # Check po_number uniqueness
    existing = (await db.execute(
        select(PurchaseOrder).where(PurchaseOrder.po_number == data.po_number)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"PO number '{data.po_number}' already exists")

    po = PurchaseOrder(
        customer_id=data.customer_id,
        po_number=data.po_number,
        po_date=data.po_date,
        total_amount=data.total_amount,
        notes=data.notes,
        status=POStatus.INITIATED,
        chain_completeness=0.0,
    )
    db.add(po)
    await db.commit()
    await db.refresh(po)
    return po


async def get_po(db: AsyncSession, po_id: UUID) -> PurchaseOrder:
    """Fetch PO with eager-loaded relationships."""
    result = await db.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.customer),
            selectinload(PurchaseOrder.documents).selectinload(Document.doc_metadata),
        )
        .where(PurchaseOrder.id == po_id)
    )
    po = result.scalar_one_or_none()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return po


async def list_pos(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 20,
    customer_id: UUID | None = None,
    status: str | None = None,
    search: str | None = None,
) -> tuple[list[PurchaseOrder], int]:
    """List POs with filters and pagination."""
    query = select(PurchaseOrder).options(selectinload(PurchaseOrder.customer))

    if customer_id:
        query = query.where(PurchaseOrder.customer_id == customer_id)
    if status:
        query = query.where(PurchaseOrder.status == status)
    if search:
        query = query.where(PurchaseOrder.po_number.ilike(f"%{search}%"))

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch page
    query = query.order_by(PurchaseOrder.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return items, total


async def update_po(db: AsyncSession, po_id: UUID, data: POUpdate) -> PurchaseOrder:
    """Update PO fields."""
    po = await get_po(db, po_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(po, key, value)
    await db.commit()
    await db.refresh(po)
    return po


async def get_chain_status(db: AsyncSession, po_id: UUID) -> ChainStatusResponse:
    """Get the 6-document chain status for a PO."""
    po = await get_po(db, po_id)

    chain: dict[str, list[ChainSlot]] = {}
    slots_filled = 0

    for doc_type in CHAIN_DOC_TYPES:
        # Find ALL documents of this type for this PO
        result = await db.execute(
            select(Document)
            .options(selectinload(Document.doc_metadata))
            .where(
                Document.po_id == po_id,
                Document.document_type == doc_type,
            )
            .order_by(Document.created_at.desc())
        )
        docs = list(result.scalars().all())

        if docs:
            slots_filled += 1
            chain[doc_type.value] = [
                ChainSlot(
                    status=doc.status.value,
                    document_id=doc.id,
                    ref_no=doc.doc_metadata.primary_ref_no if doc.doc_metadata else None,
                    uploaded_at=doc.created_at,
                    confidence=doc.doc_metadata.confidence_score if doc.doc_metadata else None,
                )
                for doc in docs
            ]
        else:
            chain[doc_type.value] = []

    completeness = round((slots_filled / 6) * 100, 1)

    return ChainStatusResponse(
        po_id=po.id,
        po_number=po.po_number,
        completeness_pct=completeness,
        chain=chain,
    )


async def delete_po(db: AsyncSession, po_id: UUID) -> None:
    """Delete a PO and all its documents, files, metadata, and reference entries."""
    po = await get_po(db, po_id)
    doc_ids = [doc.id for doc in po.documents]

    # Delete NAS files
    for doc in po.documents:
        try:
            await storage_service.delete_file(doc.file_path)
        except Exception:
            pass

    if doc_ids:
        await db.execute(sa_delete(ReferenceIndex).where(ReferenceIndex.document_id.in_(doc_ids)))
        await db.execute(sa_delete(DocumentMetadata).where(DocumentMetadata.document_id.in_(doc_ids)))
        await db.execute(sa_delete(Document).where(Document.po_id == po_id))

    await db.delete(po)
    await db.commit()


async def update_chain_completeness(db: AsyncSession, po_id: UUID) -> float:
    """Recalculate chain completeness for a PO."""
    count_result = await db.execute(
        select(func.count(distinct(Document.document_type))).where(
            Document.po_id == po_id,
            Document.status != DocumentStatus.EXTRACTION_FAILED,
        )
    )
    count = count_result.scalar() or 0
    completeness = round((count / 6) * 100, 1)

    # Determine status
    if completeness == 0:
        status = POStatus.INITIATED
    elif completeness < 50:
        status = POStatus.IN_PROGRESS
    elif completeness < 100:
        status = POStatus.NEAR_COMPLETE
    else:
        status = POStatus.COMPLETE

    # Update PO
    po = (await db.execute(
        select(PurchaseOrder).where(PurchaseOrder.id == po_id)
    )).scalar_one_or_none()

    if po:
        po.chain_completeness = completeness
        po.status = status
        await db.commit()

    return completeness
