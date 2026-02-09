"""
Extraction API router — Phase 2 AI metadata extraction endpoints.

Provides endpoints for triggering OCR-based extraction, viewing metadata,
human-in-the-loop verification, and rejection/re-extraction.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.document_metadata import DocumentType, ExtractionStatus
from app.schemas.document_metadata import (
    ExtractionRequest,
    ExtractionResponse,
    MetadataResponse,
    MetadataVerifyRequest,
    MetadataListResponse,
)
from app.services.extraction.extraction_service import ExtractionService

router = APIRouter(tags=["Extraction"])


# ── 1. Trigger extraction ────────────────────────────────────────────

@router.post(
    "/documents/{document_id}/extract",
    response_model=ExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger metadata extraction for a document",
)
async def extract_metadata(
    document_id: int,
    request: ExtractionRequest = ExtractionRequest(),
    db: Session = Depends(get_db),
):
    """
    Triggers AI-powered metadata extraction for the specified document.
    Converts the document PDF to images, sends to GLM-OCR with the
    appropriate prompt for the document type, and stores results.
    """
    service = ExtractionService(db)
    try:
        result = await service.extract(document_id, request.force_re_extract)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}",
        )


# ── 2. Get metadata for a document ───────────────────────────────────

@router.get(
    "/documents/{document_id}/metadata",
    response_model=MetadataResponse,
    summary="Get extraction metadata for a document",
)
def get_metadata(
    document_id: int,
    db: Session = Depends(get_db),
):
    """Retrieve the extracted metadata for a specific document."""
    service = ExtractionService(db)
    metadata = service.get_metadata(document_id)
    if not metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No metadata found for this document",
        )
    return metadata


# ── 3. Verify / edit metadata ────────────────────────────────────────

@router.put(
    "/metadata/{metadata_id}/verify",
    response_model=MetadataResponse,
    summary="Verify or edit extracted metadata",
)
def verify_metadata(
    metadata_id: int,
    request: MetadataVerifyRequest,
    db: Session = Depends(get_db),
):
    """
    Human-in-the-loop verification. Accepts edited fields and marks
    the metadata as VERIFIED.
    """
    service = ExtractionService(db)
    try:
        result = service.verify(metadata_id, request)
        return result
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metadata record not found",
        )


# ── 4. Reject extraction ─────────────────────────────────────────────

@router.put(
    "/metadata/{metadata_id}/reject",
    response_model=MetadataResponse,
    summary="Reject extraction and reset to PENDING",
)
def reject_metadata(
    metadata_id: int,
    db: Session = Depends(get_db),
):
    """Reject the extraction result and allow re-extraction."""
    service = ExtractionService(db)
    try:
        result = service.reject(metadata_id)
        return result
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metadata record not found",
        )


# ── 5. Search by document reference ───────────────────────────────────

@router.get(
    "/metadata/search",
    summary="Search documents by any extracted reference (invoice no, PO no, DC no, etc.)",
)
def search_by_ref(
    q: str = Query(..., min_length=2, description="Search query (invoice no, PO no, DC no, etc.)"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    db: Session = Depends(get_db),
):
    """Search across primary_ref_no and all extracted_data JSONB fields."""
    service = ExtractionService(db)
    results = service.search_by_ref(q, limit)
    return {"results": results}


# ── 6. List metadata with filters ────────────────────────────────────

@router.get(
    "/metadata",
    response_model=MetadataListResponse,
    summary="List all metadata records with filters",
)
def list_metadata(
    doc_type: Optional[DocumentType] = Query(None, description="Filter by document type"),
    extraction_status: Optional[ExtractionStatus] = Query(
        None, alias="status", description="Filter by extraction status"
    ),
    primary_ref_no: Optional[str] = Query(None, description="Filter by primary reference number"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
):
    """List metadata records with optional filters for doc_type, status, and reference number."""
    service = ExtractionService(db)
    items, total = service.list_metadata(
        doc_type=doc_type,
        status=extraction_status,
        primary_ref_no=primary_ref_no,
        limit=limit,
        offset=offset,
    )
    return MetadataListResponse(items=items, total=total)
