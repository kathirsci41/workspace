from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.schemas.case import CaseCreate, CaseUpdate, CaseResponse, CaseWithDetails
from app.services.case_service import CaseService

router = APIRouter()


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(case_data: CaseCreate, db: Session = Depends(get_db)):
    """Create a new case."""
    service = CaseService(db)
    try:
        case = service.create_case(case_data)
        return case
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db)):
    """Get case with all sales orders and documents."""
    service = CaseService(db)
    result = service.get_case_with_details(case_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case {case_id} not found")
    return result


@router.patch("/{case_id}", response_model=CaseResponse)
def update_case(case_id: str, update_data: CaseUpdate, db: Session = Depends(get_db)):
    """Update an existing case."""
    service = CaseService(db)
    case = service.update_case(case_id, update_data)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case {case_id} not found")
    return case


@router.get("/{case_id}/documents")
def get_case_documents(
    case_id: str,
    sales_order_id: Optional[int] = None,
    document_type: Optional[str] = None,
    month: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get documents for a case with optional filters."""
    from app.services.document_service import DocumentService
    
    # First get the case to get its database ID
    case_service = CaseService(db)
    case = case_service.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case {case_id} not found")
    
    doc_service = DocumentService(db)
    documents = doc_service.get_documents_for_case(
        case_id=case.id,
        sales_order_id=sales_order_id,
        document_type=document_type,
        month=month
    )
    return documents
