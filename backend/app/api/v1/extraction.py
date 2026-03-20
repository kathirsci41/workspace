from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, distinct
from sqlalchemy.orm.attributes import flag_modified
from uuid import UUID
from datetime import datetime

from app.database import get_db
from app.models import (
    Document, DocumentMetadata, ReferenceIndex, PurchaseOrder,
    DocumentStatus, MetadataStatus, ExtractionCorrection, POStatus,
)
from app.schemas.extraction import ExtractionResponse, VerifyRequest
from app.services.extraction.prompts import (
    get_primary_field, get_date_field, get_searchable_fields,
    EXTRACTION_PROMPTS,
)
from app.services.extraction.response_parser import ResponseParser
from app.services.extraction.so_validator import validate_so_number
import logging

logger = logging.getLogger(__name__)

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
        existing.last_error = None
        existing.model_version = "manual"
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
    """Manually trigger re-extraction for a document.

    Phase 7: Version-safe re-extract.
    - Increments extraction_version instead of deleting
    - Preserves human corrections in ExtractionCorrection table
    - Clears extraction fields but keeps metadata record
    """
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check for existing metadata
    meta_result = await db.execute(
        select(DocumentMetadata).where(
            DocumentMetadata.document_id == document_id
        )
    )
    existing_meta = meta_result.scalar_one_or_none()

    if existing_meta:
        # Phase 7: INCREMENT version - do NOT delete
        # This preserves audit trail and human corrections
        new_version = (existing_meta.extraction_version or 1) + 1
        existing_meta.extraction_version = new_version
        existing_meta.status = MetadataStatus.PENDING

        # Reset only extraction fields, NOT human corrections
        existing_meta.extracted_data = None
        existing_meta.confidence_score = None
        existing_meta.field_confidences = None
        existing_meta.last_error = None
        existing_meta.extracted_at = None

    # Delete existing reference index entries (will be rebuilt on extraction)
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

    return {
        "message": "Extraction queued",
        "document_id": str(document_id),
        "extraction_version": existing_meta.extraction_version if existing_meta else 1
    }


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

    # Always rebuild ReferenceIndex with current edits
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

    # Fetch PO for SO checks
    po_result = await db.execute(
        select(PurchaseOrder).where(PurchaseOrder.id == doc.po_id)
    )
    po = po_result.scalar_one_or_none()

    # Rule 1: CUSTOMER_PO — SO number must be set before verification completes.
    # Keep document in PENDING_REVIEW and prompt operator to enter SO first.
    # Once SO is entered the frontend re-calls verify and this block is skipped.
    if doc_type == "CUSTOMER_PO" and (not po or not po.so_number):
        doc.status = DocumentStatus.PENDING_REVIEW
        meta.status = MetadataStatus.EXTRACTED
        await db.commit()
        await db.refresh(meta)
        response = ExtractionResponse.model_validate(meta)
        response.requires_so_entry = True
        response.verification_pending = True
        response.po_id = po.id if po else None
        response.po_so_number = None
        return response

    # Rule 2: COMPANY_DC / COMPANY_INVOICE — SO in document must match PO SO
    so_errors = validate_so_number(body.extracted_data, doc_type, po.so_number if po else None)
    if so_errors:
        doc.status = DocumentStatus.PENDING_REVIEW
        meta.status = MetadataStatus.EXTRACTED
        await db.commit()
        await db.refresh(meta)
        response = ExtractionResponse.model_validate(meta)
        response.so_mismatch_message = so_errors[0]
        response.po_id = po.id if po else None
        response.po_so_number = po.so_number if po else None
        return response

    # All checks passed → VERIFIED
    meta.status = MetadataStatus.VERIFIED
    meta.verified_at = datetime.utcnow()
    doc.status = DocumentStatus.VERIFIED
    await _update_chain_async(db, doc.po_id)
    await db.commit()
    await db.refresh(meta)
    response = ExtractionResponse.model_validate(meta)
    response.requires_so_entry = False
    response.po_id = po.id if po else None
    response.po_so_number = po.so_number if po else None
    return response


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
            Document.status.notin_([DocumentStatus.EXTRACTION_FAILED, DocumentStatus.REJECTED]),
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
            po.status = POStatus.INITIATED
        elif completeness < 50:
            po.status = POStatus.IN_PROGRESS
        elif completeness < 100:
            po.status = POStatus.NEAR_COMPLETE
        else:
            po.status = POStatus.COMPLETE


# Phase 8: Corrections Capture + Active Learning
from typing import List, Optional
from pydantic import BaseModel, Field


class CorrectionItem(BaseModel):
    """A single field correction from the user."""
    field: str = Field(..., description="Field name being corrected")
    corrected_value: Optional[str] = Field(None, description="New value entered by user (None = field cleared)")


@router.post("/documents/{document_id}/corrections")
async def save_corrections(
    document_id: UUID,
    corrections: List[CorrectionItem],
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 8: Save human corrections for a document.

    Captures original vs corrected values for LayoutLMv3 fine-tuning.
    When a human reviews and corrects extraction results, we save:
    - The field name being corrected
    - The original (model-extracted) value
    - The corrected (human-entered) value
    - Who made the correction and when

    This data feeds active learning - corrections can be used for
    incremental LayoutLMv3 fine-tuning.
    """
    # Fetch metadata
    meta_result = await db.execute(
        select(DocumentMetadata).where(
            DocumentMetadata.document_id == document_id
        )
    )
    meta = meta_result.scalar_one_or_none()
    if not meta:
        raise HTTPException(
            status_code=404, detail="Document metadata not found"
        )

    saved_fields = []

    for correction in corrections:
        field = correction.field
        new_value = correction.corrected_value

        # Get the original value from extracted_data
        original_value = None
        if meta.extracted_data:
            original_value = meta.extracted_data.get(field)
            # Convert to string for storage
            if original_value is not None:
                original_value = str(original_value)

        # Only save if value actually changed
        if str(original_value or "") == str(new_value or ""):
            continue

        # Create correction record
        corr = ExtractionCorrection(
            document_id=document_id,
            field_name=field,
            original_value=original_value,
            corrected_value=new_value,
            operator_id="system",
            extraction_version=meta.extraction_version or 1,
        )
        db.add(corr)

        # Also update the current extracted_data
        if meta.extracted_data is None:
            meta.extracted_data = {}
        meta.extracted_data[field] = new_value

        saved_fields.append(field)

    if saved_fields:
        flag_modified(meta, 'extracted_data')
        await db.commit()

        logger.info(
            f"Saved {len(saved_fields)} corrections for document {document_id}: "
            f"{saved_fields}"
        )

    return {
        "saved_fields": saved_fields,
        "document_id": str(document_id),
        "corrections_count": len(saved_fields)
    }
