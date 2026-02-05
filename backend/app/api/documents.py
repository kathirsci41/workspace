from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
import io

from app.database import get_db
from app.schemas.document import DocumentResponse, DocumentUploadResponse, RotateRequest
from app.services.case_service import CaseService
from app.services.document_service import DocumentService

router = APIRouter()


@router.post("/cases/{case_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    case_id: str,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    sales_order_id: Optional[int] = Form(None),
    reference_number: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload a document for a case."""
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed"
        )
    
    # Get case by case_id string
    case_service = CaseService(db)
    case = case_service.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case {case_id} not found")
    
    doc_service = DocumentService(db)
    try:
        document = await doc_service.upload_document(
            case_id=case.id,
            document_type=document_type,
            file=file,
            sales_order_id=sales_order_id,
            reference_number=reference_number
        )
        return DocumentUploadResponse(
            id=document.id,
            message="Document uploaded successfully",
            filename=document.filename,
            storage_path=document.storage_path,
            checksum=document.checksum
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/documents/{document_id}/preview")
def preview_document(document_id: int, db: Session = Depends(get_db)):
    """Get document for preview (PDF streaming)."""
    doc_service = DocumentService(db)
    document = doc_service.get_document(document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    try:
        content = doc_service.get_file_content(document_id)
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename=\"{document.original_filename}\"",
                "X-Document-Rotation": str(document.rotation)
            }
        )
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on storage")


@router.get("/documents/{document_id}/download")
def download_document(document_id: int, db: Session = Depends(get_db)):
    """Download a document."""
    doc_service = DocumentService(db)
    document = doc_service.get_document(document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    try:
        content = doc_service.get_file_content(document_id)
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=\"{document.original_filename}\""
            }
        )
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on storage")


@router.get("/documents/{document_id}")
def get_document(document_id: int, db: Session = Depends(get_db)):
    """Get document metadata."""
    doc_service = DocumentService(db)
    document = doc_service.get_document(document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.post("/documents/{document_id}/rotate")
def rotate_document(document_id: int, rotate_request: RotateRequest, db: Session = Depends(get_db)):
    """Rotate a document."""
    doc_service = DocumentService(db)
    try:
        document = doc_service.rotate_document(document_id, rotate_request.degrees)
        return {
            "message": f"Document rotated by {rotate_request.degrees} degrees",
            "new_rotation": document.rotation
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """Delete a document."""
    doc_service = DocumentService(db)
    if not doc_service.delete_document(document_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return None
