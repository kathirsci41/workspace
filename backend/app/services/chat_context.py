"""
Context builders for the chat assistant.
Each builder returns a plain-text string that is inserted into the LLM system prompt.
"""
from __future__ import annotations

import uuid
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.purchase_order import PurchaseOrder, ChainStatus
from app.models.document import Document, DocumentType, DocumentStatus
from app.models.document_metadata import DocumentMetadata
from app.models.reference_index import ReferenceIndex
from app.services.chain_validator import compute_chain_status


def _fmt_amount(val) -> str:
    if val is None:
        return "N/A"
    try:
        return f"₹{float(val):,.0f}"
    except (TypeError, ValueError):
        return str(val)


async def build_order_context(po_id: str | uuid.UUID, db: AsyncSession) -> str:
    """Return a formatted text block describing a single PO and its chain status."""
    try:
        uid = uuid.UUID(str(po_id))
    except ValueError:
        return "Invalid PO ID."

    po = await db.get(
        PurchaseOrder,
        uid,
        options=[selectinload(PurchaseOrder.documents).selectinload(Document.doc_metadata)],
    )
    if not po:
        return f"Purchase order {po_id} not found."

    customer_name = po.customer.name if po.customer else "Unknown"
    lines: list[str] = [
        f"ORDER CONTEXT: {po.po_number}",
        f"Customer: {customer_name}",
        f"Status: {po.status.value}",
        f"Billing: {po.billing_type.value.upper()} | Scenario: {po.order_scenario.value}",
        f"PO Amount: {_fmt_amount(po.total_amount)}",
        f"SO Number: {po.so_number or 'not set'}",
        f"Chain Status: {po.chain_status.value.upper()} ({int(po.chain_completeness)}% complete)",
    ]

    # Chain validation — reuse the same logic as the API endpoint
    vpo_numbers: list[str] = []
    for doc in po.documents:
        if doc.document_type == DocumentType.COMPANY_PO and doc.vpo_numbers:
            vpo_numbers.extend(doc.vpo_numbers)

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

    chain = compute_chain_status(
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

    if chain["missing_slots"]:
        missing = ", ".join(s.value for s in chain["missing_slots"])
        lines.append(f"Missing documents: {missing}")

    ref_issues = [
        r for r in chain.get("reference_checks", [])
        if r.get("result") == "mismatch"
    ]
    if ref_issues:
        for r in ref_issues:
            lines.append(
                f"Reference mismatch: {r['document_type'].value} — {r['check'].replace('_', ' ')}"
            )

    billing = chain.get("billing", {})
    billing_status = billing.get("overall", "unknown")
    lines.append(f"Billing status: {billing_status}")
    if billing.get("stages"):
        for stage in billing["stages"]:
            lines.append(
                f"  Stage {stage.get('stage')}: {stage.get('status', 'unknown')}"
                f" — {_fmt_amount(stage.get('invoiced_amount'))} / {_fmt_amount(stage.get('expected_amount'))}"
            )

    # Document list
    lines.append("\nDOCUMENTS:")
    if not po.documents:
        lines.append("  No documents uploaded.")
    else:
        for doc in po.documents:
            meta = doc.doc_metadata
            ref = meta.primary_ref_no if meta else None
            amount = _fmt_amount(meta.total_amount) if meta else "N/A"
            conf = f"{int((meta.confidence_score or 0) * 100)}%" if meta and meta.confidence_score else "N/A"
            lines.append(
                f"  {doc.document_type.value}: [{doc.status.value}]"
                f" ref={ref or 'N/A'} amount={amount} confidence={conf}"
            )

    return "\n".join(lines)


async def build_search_context(query: str, db: AsyncSession) -> str:
    """Return a formatted text block for reference-based searches."""
    query_lower = query.lower().strip()
    results: list[str] = []

    # Search reference_index
    ref_rows = await db.execute(
        select(ReferenceIndex)
        .where(func.lower(ReferenceIndex.ref_value).contains(query_lower))
        .limit(5)
    )
    ref_hits = ref_rows.scalars().all()

    for hit in ref_hits:
        results.append(
            f"Reference match: {hit.ref_type}={hit.ref_value}"
            f" in {hit.document_type.value} (PO ID: {hit.po_id})"
        )

    # Search document_metadata primary_ref_no
    meta_rows = await db.execute(
        select(DocumentMetadata)
        .where(func.lower(DocumentMetadata.primary_ref_no).contains(query_lower))
        .limit(5)
    )
    meta_hits = meta_rows.scalars().all()

    for meta in meta_hits:
        results.append(
            f"Document match: {meta.document_type.value} ref={meta.primary_ref_no}"
            f" status={meta.status.value} amount={_fmt_amount(meta.total_amount)}"
        )

    if not results:
        return f"No documents or references found matching '{query}'."

    return "SEARCH RESULTS for '{}':\n{}".format(query, "\n".join(results))


async def build_platform_context(db: AsyncSession) -> str:
    """Return a platform-wide summary: order counts, document counts, critical orders."""
    from app.models.purchase_order import POStatus

    # Order counts by status
    order_counts = await db.execute(
        select(PurchaseOrder.status, func.count().label("cnt"))
        .group_by(PurchaseOrder.status)
    )
    order_lines = ["ORDER COUNTS:"]
    for row in order_counts.all():
        order_lines.append(f"  {row.status.value}: {row.cnt}")

    # Document counts by status
    doc_counts = await db.execute(
        select(Document.status, func.count().label("cnt"))
        .group_by(Document.status)
    )
    doc_lines = ["DOCUMENT COUNTS:"]
    for row in doc_counts.all():
        doc_lines.append(f"  {row.status.value}: {row.cnt}")

    # Critical orders (MISMATCH or INCOMPLETE chain)
    critical = await db.execute(
        select(PurchaseOrder.po_number, PurchaseOrder.chain_status)
        .where(PurchaseOrder.chain_status.in_([ChainStatus.MISMATCH, ChainStatus.INCOMPLETE]))
        .order_by(PurchaseOrder.chain_status)  # MISMATCH first alphabetically
        .limit(10)
    )
    critical_rows = critical.all()
    critical_lines = ["ORDERS NEEDING ATTENTION:"]
    if critical_rows:
        for row in critical_rows:
            critical_lines.append(f"  {row.po_number} — {row.chain_status.value.upper()}")
    else:
        critical_lines.append("  None — all orders are complete.")

    return "\n".join(order_lines + [""] + doc_lines + [""] + critical_lines)
