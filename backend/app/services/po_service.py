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
from app.schemas.po_profile import (
    POProfileDocument,
    POProfileDocumentSlot,
    POProfileDiscrepancy,
    POProfileTimelineEvent,
    POProfileResponse,
)
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

    # If SO number was just set/changed, clear stale SO validation errors on
    # COMPANY_DC and COMPANY_INVOICE that were extracted before the SO was entered.
    if "so_number" in update_data and po.so_number:
        await _clear_stale_so_errors(db, po)

    return po


async def _clear_stale_so_errors(db: AsyncSession, po: PurchaseOrder) -> None:
    """Re-run SO validation on already-extracted COMPANY_DC and COMPANY_INVOICE docs.

    When a document was extracted before the PO had an SO number, the validator
    wrote a blocking error into extracted_data["_validation_errors"]. Now that the
    SO is set, we re-validate and remove the stale error so the doc is unblocked.
    """
    from app.services.extraction.so_validator import validate_so_number

    so_doc_types = [DocumentType.COMPANY_DC, DocumentType.COMPANY_INVOICE]
    stale_phrase = "SO number not set"

    result = await db.execute(
        select(Document)
        .options(selectinload(Document.doc_metadata))
        .where(
            Document.po_id == po.id,
            Document.document_type.in_(so_doc_types),
        )
    )
    docs = list(result.scalars().all())

    changed = False
    for doc in docs:
        meta = doc.doc_metadata
        if not meta or not meta.extracted_data:
            continue
        errors = meta.extracted_data.get("_validation_errors", [])
        if not any(stale_phrase in str(e) for e in errors):
            continue

        # Re-run validator with the now-set SO number
        new_errors = validate_so_number(
            meta.extracted_data, doc.document_type.value, po.so_number
        )
        if new_errors:
            # Still failing (e.g. real mismatch) — leave as-is
            continue

        # Remove the stale SO error(s), keep any other errors
        cleaned = [e for e in errors if stale_phrase not in str(e)]
        updated_data = dict(meta.extracted_data)
        if cleaned:
            updated_data["_validation_errors"] = cleaned
        else:
            updated_data.pop("_validation_errors", None)

        meta.extracted_data = updated_data
        changed = True

    if changed:
        await db.commit()


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


def _build_profile_document(doc: Document) -> POProfileDocument:
    """Convert a Document + its metadata into a POProfileDocument."""
    meta = doc.doc_metadata
    return POProfileDocument(
        document_id=doc.id,
        status=doc.status.value,
        filename=doc.filename,
        original_filename=doc.original_filename,
        primary_ref_no=meta.primary_ref_no if meta else None,
        po_ref_no=meta.po_ref_no if meta else None,
        doc_date=meta.doc_date if meta else None,
        total_amount=float(meta.total_amount) if meta and meta.total_amount else None,
        confidence_score=meta.confidence_score if meta else None,
        field_confidences=meta.field_confidences if meta else None,
        extraction_route=meta.extraction_route if meta else None,
        extracted_data=meta.extracted_data if meta else None,
        verified_at=meta.verified_at if meta else None,
        uploaded_at=doc.created_at,
    )


_STATUS_RANK = {
    "VERIFIED": 6,
    "PENDING_REVIEW": 5,
    "EXTRACTED": 4,
    "EXTRACTING": 3,
    "PENDING_MODEL": 2,
    "UPLOADED": 1,
}


def _derive_slot_status(docs: list[Document]) -> str:
    """Return the most-advanced status across all documents in a slot."""
    return max(
        (doc.status.value for doc in docs),
        key=lambda s: _STATUS_RANK.get(s, 0),
        default="empty",
    )


def _get_extracted_po_number(
    docs_by_type: dict[DocumentType, list[Document]],
    doc_type: DocumentType,
) -> str | None:
    """Return the extracted po_number field from the primary doc of a given type."""
    docs = docs_by_type.get(doc_type, [])
    if not docs:
        return None
    meta = docs[0].doc_metadata
    if not meta or not meta.extracted_data:
        return None
    return meta.extracted_data.get("po_number")


async def get_po_profile(db: AsyncSession, po_id: UUID) -> POProfileResponse:
    """Return consolidated profile data for a PO — all 6 document slots, timeline, discrepancies."""
    po = await get_po(db, po_id)

    # Group ALL non-rejected documents by type, most-recent first
    docs_by_type: dict[DocumentType, list[Document]] = {}
    for doc in po.documents:
        if doc.status == DocumentStatus.REJECTED:
            continue
        docs_by_type.setdefault(doc.document_type, []).append(doc)
    for doc_list in docs_by_type.values():
        doc_list.sort(key=lambda d: d.created_at, reverse=True)

    # Build 6 slots in chain order — each slot may hold multiple documents
    slots: list[POProfileDocumentSlot] = []
    for doc_type in CHAIN_DOC_TYPES:
        doc_list = docs_by_type.get(doc_type, [])
        if not doc_list:
            slots.append(POProfileDocumentSlot(
                document_type=doc_type.value,
                status="empty",
                documents=[],
            ))
        else:
            slots.append(POProfileDocumentSlot(
                document_type=doc_type.value,
                status=_derive_slot_status(doc_list),
                documents=[_build_profile_document(d) for d in doc_list],
            ))

    # Build timeline
    timeline_events: list[tuple] = []
    for doc in po.documents:
        meta = doc.doc_metadata
        label = doc.document_type.value
        timeline_events.append((doc.created_at, "uploaded", label, None))
        if meta:
            if meta.extracted_at:
                timeline_events.append((meta.extracted_at, "extracted", label, None))
            if meta.verified_at:
                timeline_events.append((meta.verified_at, "verified", label, None))
        if doc.status == DocumentStatus.REJECTED:
            timeline_events.append((doc.updated_at, "rejected", label, None))

    timeline_events.sort(key=lambda e: e[0])
    timeline = [
        POProfileTimelineEvent(timestamp=ts, event_type=etype, doc_type=dtype, detail=detail)
        for ts, etype, dtype, detail in timeline_events
    ]

    # Build discrepancies
    discrepancies: list[POProfileDiscrepancy] = []

    # SO mismatch — check COMPANY_DC and COMPANY_INVOICE against PO's SO number
    SO_FIELDS = {
        DocumentType.COMPANY_DC: ["sales_order_no", "so_number"],
        DocumentType.COMPANY_INVOICE: ["so_number", "sales_order_no"],
    }
    for doc_type, so_field_names in SO_FIELDS.items():
        primary_docs = docs_by_type.get(doc_type, [])
        if not primary_docs:
            continue
        doc = primary_docs[0]
        if doc.doc_metadata and doc.doc_metadata.extracted_data and po.so_number:
            data = doc.doc_metadata.extracted_data
            so_val = None
            for field in so_field_names:
                so_val = data.get(field)
                if so_val:
                    break
            if so_val and so_val != po.so_number:
                discrepancies.append(POProfileDiscrepancy(
                    type="SO_MISMATCH",
                    doc_type=doc_type.value,
                    message=f"SO number mismatch — document has '{so_val}', PO has '{po.so_number}'",
                    severity="error",
                ))

    # PO reference check — compare against the correct upstream PO number,
    # NOT the platform-internal po_number (which never appears in any document).
    # VENDOR_DC / VENDOR_INVOICE reference the COMPANY_PO number (our PO to vendor).
    # COMPANY_DC / COMPANY_INVOICE reference the CUSTOMER_PO number (customer's PO to us).
    company_po_ref = _get_extracted_po_number(docs_by_type, DocumentType.COMPANY_PO)
    customer_po_ref = _get_extracted_po_number(docs_by_type, DocumentType.CUSTOMER_PO)

    EXPECTED_PO_REFS: dict[DocumentType, str | None] = {
        DocumentType.VENDOR_DC:       company_po_ref,
        DocumentType.VENDOR_INVOICE:  company_po_ref,
        DocumentType.COMPANY_DC:      customer_po_ref,
        DocumentType.COMPANY_INVOICE: customer_po_ref,
    }

    for doc_type, expected_ref in EXPECTED_PO_REFS.items():
        primary_docs = docs_by_type.get(doc_type, [])
        if not primary_docs:
            continue
        doc = primary_docs[0]
        if not doc.doc_metadata:
            continue
        meta = doc.doc_metadata
        if not meta.po_ref_no:
            discrepancies.append(POProfileDiscrepancy(
                type="MISSING_PO_REF",
                doc_type=doc_type.value,
                message=f"No PO reference found in {doc_type.value.replace('_', ' ').title()}",
                severity="warning",
            ))
        elif expected_ref and meta.po_ref_no != expected_ref:
            discrepancies.append(POProfileDiscrepancy(
                type="PO_REF_MISMATCH",
                doc_type=doc_type.value,
                message=f"PO reference mismatch — document has '{meta.po_ref_no}', expected '{expected_ref}'",
                severity="warning",
            ))

    # Build cross-references map — collect all unique po_ref_no values per type
    cross_references: dict[str, list[str]] = {}
    for slot in slots:
        for profile_doc in slot.documents:
            if profile_doc.po_ref_no:
                refs = cross_references.setdefault(slot.document_type, [])
                if profile_doc.po_ref_no not in refs:
                    refs.append(profile_doc.po_ref_no)

    return POProfileResponse(
        po_id=po.id,
        po_number=po.po_number,
        customer_name=po.customer.name,
        customer_sky_id=po.customer.customer_id,
        so_number=po.so_number,
        po_date=po.po_date,
        total_amount=float(po.total_amount) if po.total_amount else None,
        status=po.status.value,
        chain_completeness=po.chain_completeness or 0.0,
        created_at=po.created_at,
        slots=slots,
        timeline=timeline,
        discrepancies=discrepancies,
        cross_references=cross_references,
    )
