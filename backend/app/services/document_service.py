import io
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload
from fastapi import HTTPException, UploadFile
import fitz  # PyMuPDF

from app.models.document import Document, DocumentType, DocumentStatus
from app.models.document_metadata import DocumentMetadata
from app.models.reference_index import ReferenceIndex
from app.models.purchase_order import PurchaseOrder
from app.services.storage_service import StorageService
from app.services.po_service import update_chain_completeness
from app.config import settings

storage_service = StorageService(settings.nas_base_path)

VALID_DOC_TYPES = {dt.value for dt in DocumentType}


async def upload_document(
    db: AsyncSession,
    po_id: UUID,
    document_type: str,
    file: UploadFile,
) -> Document:
    """Upload a PDF document to a PO."""
    # Validate document_type
    if document_type not in VALID_DOC_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid document_type. Must be one of: {', '.join(VALID_DOC_TYPES)}",
        )

    # Fetch PO with customer
    result = await db.execute(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.customer))
        .where(PurchaseOrder.id == po_id)
    )
    po = result.scalar_one_or_none()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    # Read file
    contents = await file.read()

    # Validate PDF
    is_pdf = (
        file.content_type == "application/pdf"
        or contents[:5] == b"%PDF-"
    )
    if not is_pdf:
        raise HTTPException(status_code=400, detail="File must be a valid PDF")

    # Size check (25MB)
    if len(contents) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large. Maximum 25MB.")

    # Checksum
    checksum = StorageService.calculate_checksum(contents)

    # Duplicate check
    existing = (await db.execute(
        select(Document).where(
            Document.po_id == po_id,
            Document.document_type == document_type,
            Document.checksum == checksum,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Duplicate document")

    # Generate path
    customer_sky_id = po.customer.customer_id
    relative_path, uuid_filename = storage_service.generate_storage_path(
        customer_sky_id, po.po_number, document_type, file.filename or "document.pdf",
    )

    # Save file
    await storage_service.save_file(relative_path, contents)

    # Count pages
    page_count = None
    try:
        pdf_doc = fitz.open(stream=contents, filetype="pdf")
        page_count = pdf_doc.page_count
        pdf_doc.close()
    except Exception:
        pass

    # Create Document record
    doc = Document(
        po_id=po_id,
        document_type=document_type,
        filename=uuid_filename,
        original_filename=file.filename or "document.pdf",
        file_path=relative_path,
        file_size=len(contents),
        page_count=page_count,
        checksum=checksum,
        status=DocumentStatus.UPLOADED,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Update chain completeness
    await update_chain_completeness(db, po_id)

    # Queue extraction (import here to avoid circular)
    try:
        from app.services.extraction.tasks import extract_document
        extract_document.delay(str(doc.id))
    except Exception:
        pass  # Celery might not be running in dev

    return doc


async def get_document(db: AsyncSession, document_id: UUID) -> Document:
    """Fetch a document with metadata and PO/customer."""
    result = await db.execute(
        select(Document)
        .options(
            selectinload(Document.doc_metadata),
            selectinload(Document.purchase_order).selectinload(PurchaseOrder.customer),
        )
        .where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


async def list_documents_for_po(db: AsyncSession, po_id: UUID) -> list[Document]:
    """List all documents for a PO."""
    result = await db.execute(
        select(Document)
        .options(
            selectinload(Document.doc_metadata),
            selectinload(Document.purchase_order),
        )
        .where(Document.po_id == po_id)
        .order_by(Document.document_type)
    )
    return list(result.scalars().all())


async def delete_document(db: AsyncSession, document_id: UUID):
    """Delete document, file, metadata, and references."""
    doc = await get_document(db, document_id)
    po_id = doc.po_id

    # Delete from NAS
    try:
        await storage_service.delete_file(doc.file_path)
    except Exception:
        pass

    from sqlalchemy import delete
    from app.models.extraction_correction import ExtractionCorrection

    # Delete child records (order matters — FK constraints)
    await db.execute(
        delete(ExtractionCorrection).where(ExtractionCorrection.document_id == document_id)
    )
    await db.execute(
        delete(ReferenceIndex).where(ReferenceIndex.document_id == document_id)
    )
    await db.execute(
        delete(DocumentMetadata).where(DocumentMetadata.document_id == document_id)
    )

    # Delete document
    await db.delete(doc)
    await db.commit()

    # Update chain
    await update_chain_completeness(db, po_id)


async def get_preview_data(
    db: AsyncSession, document_id: UUID,
) -> tuple[bytes, str, str]:
    """Read file data for preview/download."""
    doc = await get_document(db, document_id)
    file_data = await storage_service.read_file(doc.file_path)
    return file_data, doc.mime_type, doc.original_filename
