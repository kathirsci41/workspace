"""Global search service across customers, POs, and document references."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func, cast, Text
from app.models import (
    Customer, PurchaseOrder, Document, DocumentMetadata,
    ReferenceIndex,
)


def _search_sort_key(item: dict, q_lower: str) -> int:
    """Rank: 0=exact, 1=starts-with, 2=contains, 3=fuzzy-only."""
    ref = (item["ref_number"] or "").lower()
    if ref == q_lower:
        return 0
    elif ref.startswith(q_lower):
        return 1
    elif q_lower in ref:
        return 2
    return 3


async def global_search(
    db: AsyncSession,
    query: str,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """
    Search across ReferenceIndex, Customers, and PurchaseOrders.
    Returns a unified, deduplicated, sorted, paginated result set.
    """
    results = []
    seen_ids = set()
    pattern = f"%{query}%"

    # 1. Search ReferenceIndex → document results
    ref_stmt = (
        select(
            ReferenceIndex,
            Document,
            DocumentMetadata,
            PurchaseOrder,
            Customer,
        )
        .join(Document, ReferenceIndex.document_id == Document.id)
        .outerjoin(
            DocumentMetadata,
            DocumentMetadata.document_id == Document.id,
        )
        .join(PurchaseOrder, Document.po_id == PurchaseOrder.id)
        .join(Customer, PurchaseOrder.customer_id == Customer.id)
        .where(
            or_(
                ReferenceIndex.ref_value.ilike(pattern),
                func.similarity(ReferenceIndex.ref_value, query) > 0.3,
            )
        )
    )
    ref_result = await db.execute(ref_stmt)
    for ref, doc, meta, po, cust in ref_result.all():
        if doc.id not in seen_ids:
            seen_ids.add(doc.id)
            doc_type_label = doc.document_type.value.replace("_", " ").title()
            results.append({
                "result_type": "document",
                "id": doc.id,
                "ref_number": ref.ref_value,
                "display_name": f"{doc_type_label} — {ref.ref_value}",
                "document_type": doc.document_type.value,
                "po_number": po.po_number,
                "po_id": str(po.id),
                "customer_name": cust.name,
                "confidence": meta.confidence_score if meta else None,
            })

    # 2. Search Customers
    cust_stmt = select(Customer).where(
        or_(
            Customer.customer_id.ilike(pattern),
            Customer.name.ilike(pattern),
        )
    )
    cust_result = await db.execute(cust_stmt)
    for cust in cust_result.scalars().all():
        if cust.id not in seen_ids:
            seen_ids.add(cust.id)
            results.append({
                "result_type": "customer",
                "id": cust.id,
                "ref_number": cust.customer_id,
                "display_name": cust.name,
                "document_type": None,
                "po_number": None,
                "po_id": None,
                "customer_name": cust.name,
                "confidence": None,
            })

    # 3. Search Purchase Orders
    po_stmt = (
        select(PurchaseOrder, Customer)
        .join(Customer, PurchaseOrder.customer_id == Customer.id)
        .where(PurchaseOrder.po_number.ilike(pattern))
    )
    po_result = await db.execute(po_stmt)
    for po, cust in po_result.all():
        if po.id not in seen_ids:
            seen_ids.add(po.id)
            results.append({
                "result_type": "purchase_order",
                "id": po.id,
                "ref_number": po.po_number,
                "display_name": f"{po.po_number} — {cust.name}",
                "document_type": None,
                "po_number": po.po_number,
                "po_id": str(po.id),
                "customer_name": cust.name,
                "confidence": None,
            })

    # 4. Search DocumentMetadata delivery_address (JSONB text field)
    addr_stmt = (
        select(Document, DocumentMetadata, PurchaseOrder, Customer)
        .join(DocumentMetadata, DocumentMetadata.document_id == Document.id)
        .join(PurchaseOrder, Document.po_id == PurchaseOrder.id)
        .join(Customer, PurchaseOrder.customer_id == Customer.id)
        .where(
            cast(DocumentMetadata.extracted_data["delivery_address"], Text).ilike(pattern)
        )
    )
    addr_result = await db.execute(addr_stmt)
    for doc, meta, po, cust in addr_result.all():
        if doc.id not in seen_ids:
            seen_ids.add(doc.id)
            doc_type_label = doc.document_type.value.replace("_", " ").title()
            delivery_address = (
                meta.extracted_data.get("delivery_address") if meta.extracted_data else None
            )
            results.append({
                "result_type": "document",
                "id": doc.id,
                "ref_number": meta.primary_ref_no or "",
                "display_name": f"{doc_type_label} → {delivery_address or 'Address match'}",
                "document_type": doc.document_type.value,
                "po_number": po.po_number,
                "po_id": str(po.id),
                "customer_name": cust.name,
                "confidence": meta.confidence_score if meta else None,
            })

    # Sort: exact match first, then starts-with, then contains, then fuzzy
    q_lower = query.lower()
    results.sort(key=lambda item: _search_sort_key(item, q_lower))

    # Paginate
    total = len(results)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = results[start:end]

    return {
        "results": paginated,
        "total": total,
        "query": query,
    }


async def search_by_ref(db: AsyncSession, ref_value: str) -> list[dict]:
    """Direct exact lookup in ReferenceIndex."""
    stmt = (
        select(
            ReferenceIndex,
            Document,
            DocumentMetadata,
            PurchaseOrder,
            Customer,
        )
        .join(Document, ReferenceIndex.document_id == Document.id)
        .outerjoin(
            DocumentMetadata,
            DocumentMetadata.document_id == Document.id,
        )
        .join(PurchaseOrder, Document.po_id == PurchaseOrder.id)
        .join(Customer, PurchaseOrder.customer_id == Customer.id)
        .where(ReferenceIndex.ref_value == ref_value)
    )
    result = await db.execute(stmt)
    results = []
    for ref, doc, meta, po, cust in result.all():
        doc_type_label = doc.document_type.value.replace("_", " ").title()
        results.append({
            "result_type": "document",
            "id": doc.id,
            "ref_number": ref.ref_value,
            "display_name": f"{doc_type_label} — {ref.ref_value}",
            "document_type": doc.document_type.value,
            "po_number": po.po_number,
            "po_id": str(po.id),
            "customer_name": cust.name,
            "confidence": meta.confidence_score if meta else None,
        })
    return results


async def advanced_search(
    db: AsyncSession,
    invoice_no: str | None = None,
    dc_no: str | None = None,
    po_no: str | None = None,
    so_no: str | None = None,
    customer_name: str | None = None,
    delivery_address: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    document_type: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Multi-field advanced search across metadata and references."""
    results = []
    seen_ids = set()

    # Build filters for ReferenceIndex
    ref_filters = []
    if invoice_no:
        ref_filters.append(
            (ReferenceIndex.ref_type == "invoice_number")
            & (ReferenceIndex.ref_value.ilike(f"%{invoice_no}%"))
        )
    if dc_no:
        ref_filters.append(
            (ReferenceIndex.ref_type == "dc_number")
            & (ReferenceIndex.ref_value.ilike(f"%{dc_no}%"))
        )
    if po_no:
        ref_filters.append(
            (ReferenceIndex.ref_type.in_(["po_number", "po_reference"]))
            & (ReferenceIndex.ref_value.ilike(f"%{po_no}%"))
        )
    if so_no:
        ref_filters.append(
            (ReferenceIndex.ref_type == "so_number")
            & (ReferenceIndex.ref_value.ilike(f"%{so_no}%"))
        )

    if ref_filters:
        from sqlalchemy import or_ as or_clause

        stmt = (
            select(
                ReferenceIndex,
                Document,
                DocumentMetadata,
                PurchaseOrder,
                Customer,
            )
            .join(Document, ReferenceIndex.document_id == Document.id)
            .outerjoin(
                DocumentMetadata,
                DocumentMetadata.document_id == Document.id,
            )
            .join(PurchaseOrder, Document.po_id == PurchaseOrder.id)
            .join(Customer, PurchaseOrder.customer_id == Customer.id)
            .where(or_clause(*ref_filters))
        )

        if document_type:
            stmt = stmt.where(Document.document_type == document_type)
        if customer_name:
            stmt = stmt.where(Customer.name.ilike(f"%{customer_name}%"))
        if date_from:
            stmt = stmt.where(DocumentMetadata.doc_date >= date_from)
        if date_to:
            stmt = stmt.where(DocumentMetadata.doc_date <= date_to)
        if delivery_address:
            stmt = stmt.where(
                cast(DocumentMetadata.extracted_data["delivery_address"], Text)
                .ilike(f"%{delivery_address}%")
            )

        ref_result = await db.execute(stmt)
        for ref, doc, meta, po, cust in ref_result.all():
            if doc.id not in seen_ids:
                seen_ids.add(doc.id)
                doc_type_label = doc.document_type.value.replace("_", " ").title()
                results.append({
                    "result_type": "document",
                    "id": doc.id,
                    "ref_number": ref.ref_value,
                    "display_name": f"{doc_type_label} — {ref.ref_value}",
                    "document_type": doc.document_type.value,
                    "po_number": po.po_number,
                    "po_id": str(po.id),
                    "customer_name": cust.name,
                    "confidence": meta.confidence_score if meta else None,
                })
    elif customer_name or date_from or date_to or document_type or delivery_address:
        # Search via metadata without ref filters
        stmt = (
            select(
                Document,
                DocumentMetadata,
                PurchaseOrder,
                Customer,
            )
            .outerjoin(
                DocumentMetadata,
                DocumentMetadata.document_id == Document.id,
            )
            .join(PurchaseOrder, Document.po_id == PurchaseOrder.id)
            .join(Customer, PurchaseOrder.customer_id == Customer.id)
        )

        if document_type:
            stmt = stmt.where(Document.document_type == document_type)
        if customer_name:
            stmt = stmt.where(Customer.name.ilike(f"%{customer_name}%"))
        if date_from:
            stmt = stmt.where(DocumentMetadata.doc_date >= date_from)
        if date_to:
            stmt = stmt.where(DocumentMetadata.doc_date <= date_to)
        if delivery_address:
            stmt = stmt.where(
                cast(DocumentMetadata.extracted_data["delivery_address"], Text)
                .ilike(f"%{delivery_address}%")
            )

        doc_result = await db.execute(stmt)
        for doc, meta, po, cust in doc_result.all():
            if doc.id not in seen_ids:
                seen_ids.add(doc.id)
                doc_type_label = doc.document_type.value.replace("_", " ").title()
                ref_no = meta.primary_ref_no if meta else doc.original_filename
                results.append({
                    "result_type": "document",
                    "id": doc.id,
                    "ref_number": ref_no or "",
                    "display_name": f"{doc_type_label} — {ref_no or 'Unknown'}",
                    "document_type": doc.document_type.value,
                    "po_number": po.po_number,
                    "po_id": str(po.id),
                    "customer_name": cust.name,
                    "confidence": meta.confidence_score if meta else None,
                })

    # po_no fallback: also search purchase_orders.po_number directly
    # (reference_index only has document-extracted refs, not the PO number itself)
    if po_no:
        po_stmt = (
            select(PurchaseOrder, Customer)
            .join(Customer, PurchaseOrder.customer_id == Customer.id)
            .where(PurchaseOrder.po_number.ilike(f"%{po_no}%"))
            .limit(10)
        )
        po_rows = await db.execute(po_stmt)
        for po, cust in po_rows.all():
            # Avoid duplicating a PO already surfaced via its documents
            key = f"po-{po.id}"
            if key not in seen_ids:
                seen_ids.add(key)
                results.append({
                    "result_type": "purchase_order",
                    "id": str(po.id),
                    "ref_number": po.po_number,
                    "display_name": f"PO — {po.po_number}",
                    "document_type": None,
                    "po_number": po.po_number,
                    "po_id": str(po.id),
                    "customer_name": cust.name,
                    "confidence": None,
                })

    # Filter out results with blank ref_number (failed extractions with no useful data)
    results = [r for r in results if r.get("ref_number")]

    total = len(results)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = results[start:end]

    return {
        "results": paginated,
        "total": total,
        "query": "|".join(
            filter(
                None,
                [invoice_no, dc_no, po_no, so_no, customer_name, delivery_address],
            )
        ),
    }
