from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, distinct
from uuid import UUID
from datetime import datetime

from app.database import get_db
from app.models import (
    Document, DocumentMetadata, ReferenceIndex, PurchaseOrder,
    DocumentStatus, MetadataStatus,
)
from app.schemas.extraction import ExtractionResponse, VerifyRequest
from app.services.extraction.prompts import (
    get_primary_field, get_date_field, get_searchable_fields,
    EXTRACTION_PROMPTS,
)
from app.services.extraction.response_parser import ResponseParser

router = APIRouter()


@router.get("/documents/{document_id}/metadata/template")
async def get_field_template(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return the expected extraction field schema for a document's type."""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc_type = doc.document_type.value if hasattr(doc.document_type, "value") else str(doc.document_type)
    config = EXTRACTION_PROMPTS.get(doc_type)
    if not config:
        raise HTTPException(status_code=400, detail=f"Unknown document type: {doc_type}")

    # Return field names with empty values as template
    template = {field: None for field in config["schema"]}
    return {
        "document_type": doc_type,
        "fields": template,
        "field_descriptions": config["schema"],
    }


@router.post("/documents/{document_id}/metadata/manual", response_model=ExtractionResponse)
async def create_manual_entry(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Create an empty metadata stub for manual data entry."""
    # Fetch document
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check if metadata already exists
    meta_result = await db.execute(
        select(DocumentMetadata).where(DocumentMetadata.document_id == document_id)
    )
    existing = meta_result.scalar_one_or_none()

    doc_type = doc.document_type.value if hasattr(doc.document_type, "value") else str(doc.document_type)
    config = EXTRACTION_PROMPTS.get(doc_type)
    template = {field: None for field in config["schema"]} if config else {}

    if existing:
        # If metadata exists but is empty or failed, reset it for manual entry
        if not existing.extracted_data or existing.extracted_data == {}:
            existing.extracted_data = template
        existing.status = MetadataStatus.EXTRACTED
        doc.status = DocumentStatus.PENDING_REVIEW
        await db.commit()
        await db.refresh(existing)
        return existing

    # Create new metadata stub
    meta = DocumentMetadata(
        document_id=document_id,
        document_type=doc.document_type,
        extracted_data=template,
        confidence_score=0,
        status=MetadataStatus.EXTRACTED,
        extraction_attempts=0,
        model_version="manual",
    )
    db.add(meta)
    doc.status = DocumentStatus.PENDING_REVIEW
    await db.commit()
    await db.refresh(meta)
    return meta


@router.post("/documents/{document_id}/re-extract")
async def re_extract_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger re-extraction for a document."""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete existing metadata
    await db.execute(
        delete(DocumentMetadata).where(
            DocumentMetadata.document_id == document_id
        )
    )
    # Delete existing reference index entries
    await db.execute(
        delete(ReferenceIndex).where(
            ReferenceIndex.document_id == document_id
        )
    )

    # Reset document status
    doc.status = DocumentStatus.UPLOADED
    await db.commit()

    # Queue extraction task
    from app.services.extraction.tasks import extract_document
    extract_document.delay(str(document_id))

    return {"message": "Extraction queued", "document_id": str(document_id)}


@router.get("/documents/{document_id}/metadata", response_model=ExtractionResponse)
async def get_document_metadata(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Fetch extraction metadata for a document."""
    result = await db.execute(
        select(DocumentMetadata).where(
            DocumentMetadata.document_id == document_id
        )
    )
    meta = result.scalar_one_or_none()
    if not meta:
        raise HTTPException(
            status_code=404, detail="No metadata found for this document"
        )
    return meta


@router.put("/documents/{document_id}/metadata/verify", response_model=ExtractionResponse)
async def verify_metadata(
    document_id: UUID,
    body: VerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify extraction metadata with user-edited data."""
    # Fetch metadata
    result = await db.execute(
        select(DocumentMetadata).where(
            DocumentMetadata.document_id == document_id
        )
    )
    meta = result.scalar_one_or_none()
    if not meta:
        raise HTTPException(
            status_code=404, detail="No metadata found for this document"
        )

    # Fetch document
    doc_result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Update extracted data
    meta.extracted_data = body.extracted_data

    # Re-derive key fields
    doc_type = meta.document_type.value if hasattr(meta.document_type, "value") else str(meta.document_type)
    primary_field = get_primary_field(doc_type)
    date_field = get_date_field(doc_type)

    meta.primary_ref_no = body.extracted_data.get(primary_field)
    meta.po_ref_no = body.extracted_data.get("po_reference")

    parser = ResponseParser()
    meta.doc_date = parser.parse_date(body.extracted_data.get(date_field))
    meta.total_amount = body.extracted_data.get("total_amount")

    # Set verified
    meta.status = MetadataStatus.VERIFIED
    meta.verified_at = datetime.utcnow()

    # Refresh ReferenceIndex
    await db.execute(
        delete(ReferenceIndex).where(
            ReferenceIndex.document_id == document_id
        )
    )

    searchable = get_searchable_fields(doc_type)
    for ref_type, field_name in searchable:
        value = body.extracted_data.get(field_name)
        if value and str(value).strip():
            ref = ReferenceIndex(
                document_id=doc.id,
                po_id=doc.po_id,
                ref_type=ref_type,
                ref_value=str(value).strip(),
                document_type=doc.document_type,
            )
            db.add(ref)

    # Update document status
    doc.status = DocumentStatus.VERIFIED

    # Update PO chain completeness
    await _update_chain_async(db, doc.po_id)

    await db.commit()
    await db.refresh(meta)
    return meta


@router.put("/documents/{document_id}/metadata/reject", response_model=ExtractionResponse)
async def reject_metadata(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Reject extraction metadata."""
    result = await db.execute(
        select(DocumentMetadata).where(
            DocumentMetadata.document_id == document_id
        )
    )
    meta = result.scalar_one_or_none()
    if not meta:
        raise HTTPException(
            status_code=404, detail="No metadata found for this document"
        )

    # Fetch document
    doc_result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Set status
    meta.status = MetadataStatus.FAILED
    doc.status = DocumentStatus.REJECTED

    # Update PO chain completeness
    await _update_chain_async(db, doc.po_id)

    await db.commit()
    await db.refresh(meta)
    return meta


async def _update_chain_async(db: AsyncSession, po_id: UUID):
    """Update PO chain completeness asynchronously."""
    count_result = await db.execute(
        select(func.count(distinct(Document.document_type))).where(
            Document.po_id == po_id,
            Document.status != DocumentStatus.EXTRACTION_FAILED,
        )
    )
    count = count_result.scalar() or 0
    completeness = round((count / 6) * 100, 1)

    po_result = await db.execute(
        select(PurchaseOrder).where(PurchaseOrder.id == po_id)
    )
    po = po_result.scalar_one_or_none()
    if po:
        po.chain_completeness = completeness
        if completeness == 0:
            po.status = "INITIATED"
        elif completeness < 50:
            po.status = "IN_PROGRESS"
        elif completeness < 100:
            po.status = "NEAR_COMPLETE"
        else:
            po.status = "COMPLETE"
