from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List

from app.models.case import Case
from app.models.sales_order import SalesOrder
from app.models.document import Document
from app.models.audit_log import AuditLog
from app.schemas.case import CaseCreate, CaseUpdate
from app.utils.id_generator import generate_case_id
from app.utils.normalizer import normalize_opportunity_id


class CaseService:
    """Service for case operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_case(self, case_data: CaseCreate) -> Case:
        """Create a new case."""
        # Normalize opportunity ID
        normalized_opp_id = normalize_opportunity_id(case_data.opportunity_id)
        
        # Check for duplicate opportunity ID
        existing = self.db.query(Case).filter(
            Case.opportunity_id == normalized_opp_id
        ).first()
        if existing:
            raise ValueError(f"Case with Opportunity ID {normalized_opp_id} already exists")
        
        # Generate case ID
        case_id = generate_case_id(self.db)
        
        # Create case
        case = Case(
            case_id=case_id,
            opportunity_id=normalized_opp_id,
            customer_name=case_data.customer_name,
            case_type=case_data.case_type,
            notes=case_data.notes
        )
        
        self.db.add(case)
        self.db.commit()
        self.db.refresh(case)
        
        # Log audit
        self._log_audit(case.id, None, None, "CASE_CREATED", "System", {
            "case_id": case.case_id,
            "opportunity_id": case.opportunity_id
        })
        
        return case
    
    def get_case_by_id(self, case_id: str) -> Optional[Case]:
        """Get case by case_id (CASE-YYYY-XXXX format)."""
        return self.db.query(Case).filter(Case.case_id == case_id).first()
    
    def get_case_by_db_id(self, id: int) -> Optional[Case]:
        """Get case by database ID."""
        return self.db.query(Case).filter(Case.id == id).first()
    
    def get_case_by_opportunity(self, opportunity_id: str) -> Optional[Case]:
        """Get case by opportunity ID."""
        normalized = normalize_opportunity_id(opportunity_id)
        return self.db.query(Case).filter(Case.opportunity_id == normalized).first()
    
    def search_cases(self, query: str, limit: int = 20) -> List[Case]:
        """Search cases by opportunity ID or customer name."""
        return self.db.query(Case).filter(
            or_(
                Case.opportunity_id.ilike(f"%{query}%"),
                Case.customer_name.ilike(f"%{query}%"),
                Case.case_id.ilike(f"%{query}%")
            )
        ).limit(limit).all()
    
    def update_case(self, case_id: str, update_data: CaseUpdate) -> Optional[Case]:
        """Update an existing case."""
        case = self.get_case_by_id(case_id)
        if not case:
            return None
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(case, field, value)
        
        self.db.commit()
        self.db.refresh(case)
        
        # Log audit
        self._log_audit(case.id, None, None, "CASE_UPDATED", "System", update_dict)
        
        return case
    
    def get_case_with_details(self, case_id: str) -> Optional[dict]:
        """Get case with all sales orders and documents."""
        case = self.get_case_by_id(case_id)
        if not case:
            return None
        
        # Get customer PO (document without sales_order_id)
        customer_po = self.db.query(Document).filter(
            Document.case_id == case.id,
            Document.document_type == "CUSTOMER_PO"
        ).first()
        
        # Get all sales orders with their documents
        sales_orders = self.db.query(SalesOrder).filter(
            SalesOrder.case_id == case.id
        ).order_by(SalesOrder.so_month, SalesOrder.so_number).all()
        
        sales_orders_with_docs = []
        for so in sales_orders:
            documents = self.db.query(Document).filter(
                Document.sales_order_id == so.id
            ).all()
            
            # Build checklist
            doc_types = {doc.document_type for doc in documents}
            checklist = {
                "VENDOR_INVOICE": "VENDOR_INVOICE" in doc_types,
                "VENDOR_DC": "VENDOR_DC" in doc_types,
                "COMPANY_INVOICE": "COMPANY_INVOICE" in doc_types,
                "COMPANY_DC": "COMPANY_DC" in doc_types,
                "POD": "POD" in doc_types
            }
            
            sales_orders_with_docs.append({
                "id": so.id,
                "so_number": so.so_number,
                "so_month": so.so_month,
                "created_at": so.created_at,
                "updated_at": so.updated_at,
                "document_count": len(documents),
                "checklist": checklist,
                "documents": documents
            })
        
        return {
            "id": case.id,
            "case_id": case.case_id,
            "opportunity_id": case.opportunity_id,
            "customer_name": case.customer_name,
            "case_type": case.case_type,
            "status": case.status,
            "notes": case.notes,
            "created_at": case.created_at,
            "updated_at": case.updated_at,
            "customer_po": customer_po,
            "sales_orders": sales_orders_with_docs
        }
    
    def _log_audit(self, case_id: int, document_id: Optional[int], 
                   sales_order_id: Optional[int], action: str, 
                   actor: str, details: dict):
        """Log an audit entry."""
        audit = AuditLog(
            case_id=case_id,
            document_id=document_id,
            sales_order_id=sales_order_id,
            action=action,
            actor=actor,
            details=details
        )
        self.db.add(audit)
        self.db.commit()
