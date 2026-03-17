from uuid import UUID
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, distinct, delete as sa_delete, exists, not_
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
    date_from: date | None = None,
    date_to: date | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    chain_filter: str | None = None,
    missing_doc_type: str | None = None,
) -> tuple[list[PurchaseOrder], int]:
    """List POs with filters and pagination."""
    query = select(PurchaseOrder).options(selectinload(PurchaseOrder.customer))

    # Existing filters — unchanged
    if customer_id:
        query = query.where(PurchaseOrder.customer_id == customer_id)
    if status:
        query = query.where(PurchaseOrder.status == status)
    if search:
        # Extended: also search by so_number
        query = query.where(
            or_(
                PurchaseOrder.po_number.ilike(f"%{search}%"),
                PurchaseOrder.so_number.ilike(f"%{search}%"),
            )
        )

    # New: date range on po_date
    if date_from:
        query = query.where(PurchaseOrder.po_date >= date_from)
    if date_to:
        query = query.where(PurchaseOrder.po_date <= date_to)

    # New: chain completeness filter — chain_completeness is stored as 0–100 (percentage)
    if chain_filter == "incomplete":
        query = query.where(PurchaseOrder.chain_completeness < 100.0)
    elif chain_filter == "critical":
        query = query.where(PurchaseOrder.chain_completeness < 25.0)
    elif chain_filter == "complete":
        query = query.where(PurchaseOrder.chain_completeness >= 100.0)

    # New: missing doc type filter (POs that don't have a non-rejected doc of that type)
    if missing_doc_type:
        try:
            doc_type_enum = DocumentType[missing_doc_type.upper()]
            sub = (
                select(Document.id)
                .where(Document.po_id == PurchaseOrder.id)
                .where(Document.document_type == doc_type_enum)
                .where(Document.status != DocumentStatus.REJECTED)
                .correlate(PurchaseOrder)
            )
            query = query.where(not_(exists(sub)))
        except KeyError:
            pass  # Unknown doc type — ignore filter

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # New: sort
    sort_col_map = {
        "created_at": PurchaseOrder.created_at,
        "po_date": PurchaseOrder.po_date,
        "chain_completeness": PurchaseOrder.chain_completeness,
        "total_amount": PurchaseOrder.total_amount,
    }
    sort_col = sort_col_map.get(sort_by, PurchaseOrder.created_at)
    order_expr = sort_col.asc() if sort_order == "asc" else sort_col.desc()
    query = query.order_by(order_expr)
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


def _slot_message(doc) -> str | None:
    """Return a human-readable reason why a document slot is not verified."""
    status = doc.status.value if hasattr(doc.status, "value") else doc.status
    meta = doc.doc_metadata
    if status == "EXTRACTION_FAILED":
        return meta.last_error if meta and meta.last_error else "Extraction failed — try re-extracting."
    if status == "PENDING_REVIEW":
        if meta and meta.extracted_data:
            errors = meta.extracted_data.get("_validation_errors", [])
            if errors:
                return errors[0]
            if meta.extracted_data.get("_so_pending"):
                return "Waiting for SO number to be set on this PO."
        return "Ready to review."
    if status == "REJECTED":
        return "Rejected — please re-upload the correct document."
    return None


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
            # Count slot as filled only when at least one non-failed document exists.
            # Mirrors the same rule used by the stored chain_completeness field so both
            # values stay in sync (EXTRACTION_FAILED docs display but don't count).
            if any(d.status not in (DocumentStatus.EXTRACTION_FAILED, DocumentStatus.REJECTED) for d in docs):
                slots_filled += 1
            chain[doc_type.value] = [
                ChainSlot(
                    status=doc.status.value,
                    document_id=doc.id,
                    ref_no=doc.doc_metadata.primary_ref_no if doc.doc_metadata else None,
                    uploaded_at=doc.created_at,
                    confidence=doc.doc_metadata.confidence_score if doc.doc_metadata else None,
                    extraction_route=(
                        doc.doc_metadata.extraction_route if doc.doc_metadata else None
                    ),
                    has_validation_errors=bool(
                        doc.doc_metadata
                        and doc.doc_metadata.extracted_data
                        and doc.doc_metadata.extracted_data.get("_validation_errors")
                    ),
                    slot_message=_slot_message(doc),
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
        from app.models.extraction_correction import ExtractionCorrection
        await db.execute(sa_delete(ExtractionCorrection).where(ExtractionCorrection.document_id.in_(doc_ids)))
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
            Document.status.notin_([DocumentStatus.EXTRACTION_FAILED, DocumentStatus.REJECTED]),
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
