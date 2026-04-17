from uuid import UUID
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, distinct, delete as sa_delete, exists, not_
from sqlalchemy.orm import selectinload, joinedload
from fastapi import HTTPException

from app.models.customer import Customer
from app.models.purchase_order import PurchaseOrder, POStatus, FulfillmentType, OrderScenario, GstType
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
    VendorGroup,
    FieldComparison,
    ItemComparison,
    ItemMatch,
    ParsedAddress,
)
from app.services.storage_service import StorageService
from app.config import settings

storage_service = StorageService(settings.nas_base_path)


# Full 6-doc chain — kept for backward compat with any code that imports this
CHAIN_DOC_TYPES = [
    DocumentType.CUSTOMER_PO,
    DocumentType.COMPANY_PO,
    DocumentType.VENDOR_DC,
    DocumentType.VENDOR_INVOICE,
    DocumentType.COMPANY_DC,
    DocumentType.COMPANY_INVOICE,
]

# Required doc chain per scenario — None means indeterminate (unknown scenario)
_SCENARIO_CHAIN: dict[OrderScenario, list[DocumentType] | None] = {
    OrderScenario.UNKNOWN: None,
    OrderScenario.PROCUREMENT: [
        # VENDOR_DC excluded — some vendors don't issue separate DC
        # It's optional (tracked if uploaded, doesn't block completeness)
        DocumentType.CUSTOMER_PO,
        DocumentType.COMPANY_PO,
        DocumentType.VENDOR_INVOICE,
        DocumentType.COMPANY_DC,
        DocumentType.COMPANY_INVOICE,
    ],
    OrderScenario.STOCK: [
        DocumentType.CUSTOMER_PO,
        DocumentType.COMPANY_DC,
        DocumentType.COMPANY_INVOICE,
    ],
    OrderScenario.DROP_SHIP: [
        # COMPANY_DC is optional on drop-ship — not included in required chain
        DocumentType.CUSTOMER_PO,
        DocumentType.COMPANY_PO,
        DocumentType.VENDOR_DC,
        DocumentType.VENDOR_INVOICE,
        DocumentType.COMPANY_INVOICE,
    ],
    OrderScenario.SERVICE_AMC: [
        DocumentType.CUSTOMER_PO,
        DocumentType.COMPANY_INVOICE,
    ],
}


def get_scenario_chain(scenario: OrderScenario | None) -> list[DocumentType] | None:
    """Return required doc list for this scenario. None = indeterminate."""
    if scenario is None:
        return None
    return _SCENARIO_CHAIN.get(scenario)


def derive_scenario(
    vpo_count: int,
    has_vendor_dc: bool,
    has_service_hint: bool,
) -> OrderScenario:
    """Derive scenario from observable facts. Never manually set."""
    if vpo_count == 0:
        if has_vendor_dc:
            return OrderScenario.DROP_SHIP
        if has_service_hint:
            return OrderScenario.SERVICE_AMC
        return OrderScenario.STOCK
    return OrderScenario.PROCUREMENT


# Known Indian states with GST codes for auto-detection
# Company state should be set in config; deliveries to a different state = IGST
_KNOWN_IGST_TRIGGER_STATES = {
    s.lower() for s in [
        "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
        "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
        "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram",
        "nagaland", "odisha", "punjab", "rajasthan", "sikkim", "tamil nadu",
        "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal",
        "delhi", "jammu and kashmir", "ladakh", "chandigarh", "puducherry",
    ]
}


def detect_gst_type(delivery_state: str | None) -> GstType | None:
    """
    Auto-detect GST type from delivery state vs company state (from settings).
    Returns None if detection is not possible.
    """
    if not delivery_state:
        return None
    company_state = getattr(settings, "company_state", "").lower().strip()
    if not company_state:
        return None
    if delivery_state.lower().strip() == company_state:
        return GstType.CGST_SGST
    return GstType.IGST


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

    VENDOR_DOC_TYPES = {DocumentType.COMPANY_PO, DocumentType.VENDOR_DC, DocumentType.VENDOR_INVOICE}

    if po.fulfillment_type == FulfillmentType.STOCK:
        active_chain = [dt for dt in CHAIN_DOC_TYPES if dt not in VENDOR_DOC_TYPES]
    else:
        active_chain = CHAIN_DOC_TYPES

    for doc_type in active_chain:
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

    completeness = round((slots_filled / len(active_chain)) * 100)

    return ChainStatusResponse(
        po_id=po.id,
        po_number=po.po_number,
        completeness_pct=completeness,
        chain=chain,
    )


async def close_order(db: AsyncSession, po_id: UUID, note: str | None = None) -> PurchaseOrder:
    """Manually close a PO — marks order as completed regardless of doc chain state.

    This is a one-way operation. Once closed, the order cannot be re-opened
    through the normal UI (admin API only).
    """
    from datetime import datetime, timezone
    po = await get_po(db, po_id)

    if po.manually_completed:
        raise HTTPException(status_code=400, detail="Order is already closed.")

    po.manually_completed = True
    po.completed_at = datetime.now(timezone.utc)
    po.completion_note = note
    po.status = POStatus.COMPLETE
    po.chain_completeness = 100.0
    # Preserve chain_status so mismatches remain visible after close
    # (do not override to COMPLETE — reviewers should still see unresolved refs)

    await db.commit()
    await db.refresh(po)
    return po


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
    # Fetch PO to determine scenario and manually_completed flag
    po = (await db.execute(
        select(PurchaseOrder).where(PurchaseOrder.id == po_id)
    )).scalar_one_or_none()

    if not po:
        return 0.0

    # Skip recalculation if manually completed — user-set values take precedence
    if po.manually_completed:
        return po.chain_completeness or 0.0

    # Get scenario-specific chain; fall back to full chain if scenario unknown
    scenario = getattr(po, 'order_scenario', None)
    scenario_chain = get_scenario_chain(scenario)
    if scenario_chain is None or scenario == OrderScenario.UNKNOWN:
        chain_length = len(CHAIN_DOC_TYPES)
        required_docs = set(CHAIN_DOC_TYPES)
    else:
        chain_length = len(scenario_chain)
        required_docs = set(scenario_chain)

    # Count only documents in the scenario's required chain
    count_result = await db.execute(
        select(func.count(distinct(Document.document_type))).where(
            Document.po_id == po_id,
            Document.document_type.in_(required_docs),
            Document.status.notin_([
                DocumentStatus.EXTRACTION_FAILED,
                DocumentStatus.PENDING_MODEL,
                DocumentStatus.REJECTED,
            ]),
        )
    )
    count = count_result.scalar() or 0

    # Clamp completeness to [0, 100]
    completeness = min(100.0, round((count / chain_length) * 100, 1))

    # Determine status
    if completeness == 0:
        status = POStatus.INITIATED
    elif completeness < 50:
        status = POStatus.IN_PROGRESS
    elif completeness < 100:
        status = POStatus.NEAR_COMPLETE
    else:
        status = POStatus.COMPLETE

    po.chain_completeness = completeness
    po.status = status

    # Auto-derive scenario from document evidence if still UNKNOWN
    if getattr(po, 'order_scenario', None) == OrderScenario.UNKNOWN:
        docs_result = await db.execute(
            select(Document.document_type).where(Document.po_id == po_id)
        )
        doc_types = [row[0] for row in docs_result.all()]
        vpo_count = sum(1 for dt in doc_types if dt == DocumentType.COMPANY_PO)
        has_vendor_dc = DocumentType.VENDOR_DC in doc_types
        if vpo_count > 0 or has_vendor_dc:
            po.order_scenario = derive_scenario(vpo_count, has_vendor_dc, False)

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

    # Determine active chain based on order_scenario (falls back to fulfillment_type)
    scenario = po.order_scenario if hasattr(po, 'order_scenario') else None
    scenario_chain = get_scenario_chain(scenario)

    if scenario_chain is not None:
        # Scenario is known — use its specific chain
        active_chain = scenario_chain
        if scenario == OrderScenario.DROP_SHIP:
            optional_types = {DocumentType.COMPANY_DC}
        elif scenario == OrderScenario.PROCUREMENT:
            optional_types = {DocumentType.VENDOR_DC}
        else:
            optional_types = set()
    else:
        # Scenario unknown — fall back to legacy fulfillment_type behaviour
        VENDOR_DOC_TYPES = {DocumentType.COMPANY_PO, DocumentType.VENDOR_DC, DocumentType.VENDOR_INVOICE}
        if po.fulfillment_type == FulfillmentType.STOCK:
            active_chain = [dt for dt in CHAIN_DOC_TYPES if dt not in VENDOR_DOC_TYPES]
        else:
            active_chain = CHAIN_DOC_TYPES
        optional_types = set()

    # All 6 doc types — slots not in active_chain show as "not_applicable"
    ALL_DOC_TYPES = [
        DocumentType.CUSTOMER_PO,
        DocumentType.COMPANY_PO,
        DocumentType.VENDOR_DC,
        DocumentType.VENDOR_INVOICE,
        DocumentType.COMPANY_DC,
        DocumentType.COMPANY_INVOICE,
    ]

    # Build slots — required slots show empty/filled, non-required show not_applicable
    slots: list[POProfileDocumentSlot] = []
    for doc_type in ALL_DOC_TYPES:
        doc_list = docs_by_type.get(doc_type, [])
        is_required = doc_type in active_chain
        is_optional = doc_type in optional_types

        if not is_required and not is_optional and doc_list:
            # Doc uploaded but not required by scenario — show it anyway
            slots.append(POProfileDocumentSlot(
                document_type=doc_type.value,
                status=_derive_slot_status(doc_list),
                documents=[_build_profile_document(d) for d in doc_list],
                required=False,
            ))
        elif not is_required and not is_optional:
            slots.append(POProfileDocumentSlot(
                document_type=doc_type.value,
                status="not_applicable",
                documents=[],
                required=False,
            ))
        elif not doc_list:
            slots.append(POProfileDocumentSlot(
                document_type=doc_type.value,
                status="empty",
                documents=[],
                required=is_required,
                optional=is_optional,
            ))
        else:
            slots.append(POProfileDocumentSlot(
                document_type=doc_type.value,
                status=_derive_slot_status(doc_list),
                documents=[_build_profile_document(d) for d in doc_list],
                required=is_required,
                optional=is_optional,
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

    # ── Chain field comparison engine ──────────────────────────────────────────
    def _extracted(doc_type: DocumentType, field: str) -> str | None:
        """Return extracted_data[field] from the primary (most-recent) doc of this type."""
        doc_list = docs_by_type.get(doc_type, [])
        if not doc_list:
            return None
        meta = doc_list[0].doc_metadata
        if not meta or not meta.extracted_data:
            return None
        val = meta.extracted_data.get(field)
        return str(val).strip() if val is not None else None

    def _amount_match(a: str | None, b: str | None, tolerance: float = 0.01) -> bool | None:
        """Compare two amount strings with a relative tolerance."""
        if a is None or b is None:
            return None
        try:
            fa, fb = float(a), float(b)
        except (ValueError, TypeError):
            return None
        if fa == 0 and fb == 0:
            return True
        if fa == 0 or fb == 0:
            return abs(fa - fb) < 1.0
        return abs(fa - fb) / max(abs(fa), abs(fb)) <= tolerance

    def _str_match(a: str | None, b: str | None) -> bool | None:
        """Case-insensitive exact match."""
        if a is None or b is None:
            return None
        return a.lower() == b.lower()

    def _cmp(
        label: str,
        src_type: DocumentType,
        src_field: str,
        cmp_type: DocumentType,
        cmp_field: str,
        is_amount: bool = False,
        note: str | None = None,
    ) -> FieldComparison:
        src_val = _extracted(src_type, src_field)
        cmp_val = _extracted(cmp_type, cmp_field)
        if is_amount:
            matched = _amount_match(src_val, cmp_val)
        else:
            matched = _str_match(src_val, cmp_val)
        return FieldComparison(
            field_label=label,
            source_doc=src_type.value,
            source_value=src_val,
            compared_doc=cmp_type.value,
            compared_value=cmp_val,
            match=matched,
            note=note,
        )

    field_comparisons: list[FieldComparison] = []

    # Amount cross-checks
    field_comparisons.append(_cmp(
        "Grand Total",
        DocumentType.CUSTOMER_PO, "grand_total",
        DocumentType.COMPANY_INVOICE, "total_amount",
        is_amount=True, note="tolerance ±1%",
    ))
    field_comparisons.append(_cmp(
        "Vendor PO Amount",
        DocumentType.COMPANY_PO, "total_amount",
        DocumentType.VENDOR_INVOICE, "total_amount",
        is_amount=True, note="tolerance ±1%",
    ))

    # Delivery address consistency
    field_comparisons.append(_cmp(
        "Delivery Address (Company PO → Vendor DC)",
        DocumentType.COMPANY_PO, "delivery_address",
        DocumentType.VENDOR_DC, "delivery_address",
    ))
    field_comparisons.append(_cmp(
        "Delivery Address (Company PO → Company DC)",
        DocumentType.COMPANY_PO, "delivery_address",
        DocumentType.COMPANY_DC, "delivery_address",
    ))

    # SO number consistency between our outgoing documents
    field_comparisons.append(_cmp(
        "SO Number (Company DC → Company Invoice)",
        DocumentType.COMPANY_DC, "so_number",
        DocumentType.COMPANY_INVOICE, "so_number",
    ))

    # DC reference on invoice matches actual DC number
    field_comparisons.append(_cmp(
        "DC Reference on Invoice",
        DocumentType.COMPANY_DC, "dc_number",
        DocumentType.COMPANY_INVOICE, "dc_reference",
    ))

    # Vendor name consistency
    field_comparisons.append(_cmp(
        "Vendor Name (Company PO → Vendor Invoice)",
        DocumentType.COMPANY_PO, "vendor_name",
        DocumentType.VENDOR_INVOICE, "vendor_name",
    ))
    field_comparisons.append(_cmp(
        "Vendor Name (Company PO → Vendor DC)",
        DocumentType.COMPANY_PO, "vendor_name",
        DocumentType.VENDOR_DC, "vendor_name",
    ))

    # Strip comparisons where both sides are None (no docs uploaded yet — no useful info)
    field_comparisons = [fc for fc in field_comparisons if not (fc.source_value is None and fc.compared_value is None)]

    # ── Item-level comparison engine ───────────────────────────────────────────
    import json as _json

    def _get_items(doc_type: DocumentType) -> list[dict]:
        doc_list = docs_by_type.get(doc_type, [])
        if not doc_list:
            return []
        meta = doc_list[0].doc_metadata
        if not meta or not meta.extracted_data:
            return []
        raw = meta.extracted_data.get("order_items")
        if not raw:
            return []
        try:
            items = raw if isinstance(raw, list) else _json.loads(raw)
            return items if isinstance(items, list) else []
        except Exception:
            return []

    def _safe_float(v) -> float | None:
        if v is None:
            return None
        try:
            return float(str(v).replace(",", ""))
        except (ValueError, TypeError):
            return None

    item_comparisons: list[ItemComparison] = []

    # Qty: CUSTOMER_PO → COMPANY_DC (ordered vs delivered — most critical)
    cpo_items = _get_items(DocumentType.CUSTOMER_PO)
    cdc_items = _get_items(DocumentType.COMPANY_DC)
    if cpo_items or cdc_items:
        len_src, len_cmp = len(cpo_items), len(cdc_items)
        # If count differs by >50%, skip positional matching — show warning row instead
        if len_src and len_cmp and abs(len_src - len_cmp) / max(len_src, len_cmp) > 0.5:
            item_comparisons.append(ItemComparison(
                sr_no=None,
                description="Item count mismatch — manual review required",
                source_doc=DocumentType.CUSTOMER_PO.value,
                source_qty=None,
                compared_doc=DocumentType.COMPANY_DC.value,
                compared_qty=None,
                qty_match=False,
            ))
        else:
            for i in range(max(len_src, len_cmp)):
                src = cpo_items[i] if i < len_src else {}
                cmp = cdc_items[i] if i < len_cmp else {}
                src_qty = _safe_float(src.get("qty"))
                cmp_qty = _safe_float(cmp.get("qty"))
                qty_match = (src_qty == cmp_qty) if src_qty is not None and cmp_qty is not None else None
                item_comparisons.append(ItemComparison(
                    sr_no=str(src.get("sr_no") or cmp.get("sr_no") or (i + 1)),
                    description=src.get("description") or cmp.get("description"),
                    part_no=cmp.get("part_no"),
                    source_doc=DocumentType.CUSTOMER_PO.value,
                    source_qty=src_qty,
                    compared_doc=DocumentType.COMPANY_DC.value,
                    compared_qty=cmp_qty,
                    qty_match=qty_match,
                ))

    # Part no + qty: COMPANY_PO → VENDOR_DC (procurement only — did vendor ship right parts?)
    if po.fulfillment_type != FulfillmentType.STOCK:
        comp_po_items = _get_items(DocumentType.COMPANY_PO)
        vdc_items = _get_items(DocumentType.VENDOR_DC)
        if comp_po_items or vdc_items:
            len_src, len_cmp = len(comp_po_items), len(vdc_items)
            if len_src and len_cmp and abs(len_src - len_cmp) / max(len_src, len_cmp) > 0.5:
                item_comparisons.append(ItemComparison(
                    sr_no=None,
                    description="Item count mismatch — manual review required",
                    source_doc=DocumentType.COMPANY_PO.value,
                    source_qty=None,
                    compared_doc=DocumentType.VENDOR_DC.value,
                    compared_qty=None,
                    qty_match=False,
                ))
            else:
                for i in range(max(len_src, len_cmp)):
                    src = comp_po_items[i] if i < len_src else {}
                    cmp = vdc_items[i] if i < len_cmp else {}
                    src_part = str(src.get("part_no") or "").strip().lower() or None
                    cmp_part = str(cmp.get("part_no") or "").strip().lower() or None
                    src_qty = _safe_float(src.get("qty"))
                    cmp_qty = _safe_float(cmp.get("qty"))
                    qty_match = (src_qty == cmp_qty) if src_qty is not None and cmp_qty is not None else None
                    part_match = (src_part == cmp_part) if src_part and cmp_part else None
                    src_price = _safe_float(src.get("unit_price"))
                    cmp_price = _safe_float(cmp.get("unit_price"))
                    if src_price is not None and cmp_price is not None and max(src_price, cmp_price) > 0:
                        price_match = abs(src_price - cmp_price) <= max(src_price, cmp_price) * 0.02
                    else:
                        price_match = False
                    item_comparisons.append(ItemComparison(
                        sr_no=str(src.get("sr_no") or cmp.get("sr_no") or (i + 1)),
                        description=src.get("description") or cmp.get("description"),
                        part_no=src_part or cmp_part,
                        source_doc=DocumentType.COMPANY_PO.value,
                        source_qty=src_qty,
                        compared_doc=DocumentType.VENDOR_DC.value,
                        compared_qty=cmp_qty,
                        qty_match=qty_match,
                        source_price=src_price,
                        compared_price=cmp_price,
                        price_match=price_match,
                    ))

    # Build per-vendor groups (procurement only — stock has no vendor docs)
    vendor_groups: list[VendorGroup] = []
    if po.fulfillment_type != FulfillmentType.STOCK:
        for company_po_doc in docs_by_type.get(DocumentType.COMPANY_PO, []):
            meta = company_po_doc.doc_metadata
            vendor_po_ref = meta.primary_ref_no if meta else None
            if not vendor_po_ref:
                continue

            vendor_name = (
                meta.extracted_data.get("vendor_name")
                if meta and meta.extracted_data
                else None
            )

            linked_vdc = [
                d for d in docs_by_type.get(DocumentType.VENDOR_DC, [])
                if d.doc_metadata and d.doc_metadata.po_ref_no == vendor_po_ref
            ]
            linked_vinv = [
                d for d in docs_by_type.get(DocumentType.VENDOR_INVOICE, [])
                if d.doc_metadata and d.doc_metadata.po_ref_no == vendor_po_ref
            ]

            def _make_slot(dt: DocumentType, doc_list: list[Document]) -> POProfileDocumentSlot:
                if not doc_list:
                    return POProfileDocumentSlot(document_type=dt.value, status="empty", documents=[])
                return POProfileDocumentSlot(
                    document_type=dt.value,
                    status=_derive_slot_status(doc_list),
                    documents=[_build_profile_document(d) for d in doc_list],
                )

            group_slots = [
                _make_slot(DocumentType.COMPANY_PO, [company_po_doc]),
                _make_slot(DocumentType.VENDOR_DC, linked_vdc),
                _make_slot(DocumentType.VENDOR_INVOICE, linked_vinv),
            ]
            filled = sum(1 for s in group_slots if s.status != "empty")

            vendor_groups.append(VendorGroup(
                vendor_po_ref=vendor_po_ref,
                vendor_name=vendor_name,
                completeness_pct=round(filled / 3 * 100, 1),
                slots=group_slots,
            ))

    # ── AI item description → part_no matching ─────────────────────────────────
    item_matches: list[ItemMatch] = []
    if po.fulfillment_type != FulfillmentType.STOCK:
        _cpo_raw = _get_items(DocumentType.CUSTOMER_PO)
        _comp_po_raw = _get_items(DocumentType.COMPANY_PO)
        if _cpo_raw and _comp_po_raw:
            try:
                from app.services.item_matcher import match_items_by_description
                import redis.asyncio as _aioredis
                _r = _aioredis.from_url(settings.redis_url, decode_responses=True)
                _cpo_docs = docs_by_type.get(DocumentType.CUSTOMER_PO, [])
                _cache_key = f"{po.id}:{_cpo_docs[0].id if _cpo_docs else 'none'}"
                _matches = await match_items_by_description(_cpo_raw, _comp_po_raw, _r, _cache_key)
                await _r.aclose()
                item_matches = [ItemMatch(**m) for m in _matches]
            except Exception as _e:
                import logging as _logging
                _logging.getLogger(__name__).warning(f"Item matching skipped: {_e}")

    # ── Structured delivery address parsing ────────────────────────────────────
    from app.services.address_parser import parse_delivery_address
    _addr_raw = None
    for _dt in [DocumentType.COMPANY_DC, DocumentType.COMPANY_PO, DocumentType.VENDOR_DC]:
        _val = _extracted(_dt, "delivery_address")
        if _val:
            _addr_raw = _val
            break
    delivery_address_parsed = (
        ParsedAddress(**parse_delivery_address(_addr_raw)) if _addr_raw else None
    )

    # ── GST auto-detect (only if user hasn't set it manually) ─────────────────
    resolved_gst_type = po.gst_type.value if hasattr(po, 'gst_type') else "unknown"
    if resolved_gst_type == "unknown" and delivery_address_parsed and delivery_address_parsed.state:
        detected = detect_gst_type(delivery_address_parsed.state)
        if detected:
            resolved_gst_type = detected.value

    # ── Chain completeness display ─────────────────────────────────────────────
    # When scenario is unknown, completeness is indeterminate → show "—"
    if scenario == OrderScenario.UNKNOWN or scenario is None and not hasattr(po, 'order_scenario'):
        chain_completeness_display = "—"
    else:
        _pct = min(po.chain_completeness or 0.0, 100.0)
        chain_completeness_display = f"{_pct:.1f}%"

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
        chain_completeness_display=chain_completeness_display,
        fulfillment_type=po.fulfillment_type.value if po.fulfillment_type else "procurement",
        order_scenario=po.order_scenario.value if hasattr(po, 'order_scenario') and po.order_scenario else "unknown",
        gst_type=resolved_gst_type,
        invoice_split=po.invoice_split if hasattr(po, 'invoice_split') else False,
        manually_completed=po.manually_completed if hasattr(po, 'manually_completed') else False,
        completed_at=po.completed_at if hasattr(po, 'completed_at') else None,
        completion_note=po.completion_note if hasattr(po, 'completion_note') else None,
        created_at=po.created_at,
        slots=slots,
        timeline=timeline,
        discrepancies=discrepancies,
        cross_references=cross_references,
        vendor_groups=vendor_groups,
        field_comparisons=field_comparisons,
        items_verified=po.items_verified,
        item_comparisons=item_comparisons,
        item_matches=item_matches,
        delivery_address_parsed=delivery_address_parsed,
    )
