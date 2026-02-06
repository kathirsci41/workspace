from sqlalchemy.orm import Session
from typing import Optional, List
import re

from app.models.sales_order import SalesOrder
from app.models.document import Document
from app.models.case import Case
from app.models.audit_log import AuditLog
from app.schemas.sales_order import SalesOrderCreate


class SalesOrderService:
    """Service for sales order operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_sales_order(self, case_id: int, so_data: SalesOrderCreate) -> SalesOrder:
        """Create a new sales order for a case."""
        # Validate month format
        if not re.match(r'^\d{4}-\d{2}$', so_data.so_month):
            raise ValueError("Invalid month format. Use YYYY-MM")
        
        # Check global uniqueness of SO number
        existing = self.db.query(SalesOrder).filter(
            SalesOrder.so_number == so_data.so_number
        ).first()
        if existing:
            raise ValueError(f"Sales Order {so_data.so_number} already exists")
        
        # Verify case exists
        case = self.db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise ValueError(f"Case with ID {case_id} not found")
        
        # Create sales order
        sales_order = SalesOrder(
            case_id=case_id,
            so_number=so_data.so_number,
            so_month=so_data.so_month
        )
        
        self.db.add(sales_order)
        self.db.commit()
        self.db.refresh(sales_order)
        
        # Log audit
        self._log_audit(case_id, None, sales_order.id, "SO_CREATED", "System", {
            "so_number": sales_order.so_number,
            "so_month": sales_order.so_month
        })
        
        return sales_order
    
    def get_sales_order(self, so_id: int) -> Optional[SalesOrder]:
        """Get sales order by ID."""
        return self.db.query(SalesOrder).filter(SalesOrder.id == so_id).first()
    
    def get_sales_order_by_number(self, so_number: str) -> Optional[SalesOrder]:
        """Get sales order by SO number."""
        return self.db.query(SalesOrder).filter(
            SalesOrder.so_number == so_number
        ).first()
    
    def get_sales_orders_for_case(self, case_id: int, month: Optional[str] = None) -> List[SalesOrder]:
        """Get all sales orders for a case, optionally filtered by month."""
        query = self.db.query(SalesOrder).filter(SalesOrder.case_id == case_id)
        
        if month:
            query = query.filter(SalesOrder.so_month == month)
        
        return query.order_by(SalesOrder.so_month, SalesOrder.so_number).all()
    
    def search_sales_orders(self, query: str, limit: int = 20) -> List[dict]:
        """Search sales orders by SO number."""
        sales_orders = self.db.query(SalesOrder).filter(
            SalesOrder.so_number.ilike(f"%{query}%")
        ).limit(limit).all()
        
        results = []
        for so in sales_orders:
            case = self.db.query(Case).filter(Case.id == so.case_id).first()
            documents = self.db.query(Document).filter(
                Document.sales_order_id == so.id
            ).all()
            
            # Build checklist
            doc_types = {doc.document_type for doc in documents}
            checklist = {
                "CUSTOMER_PO": "CUSTOMER_PO" in doc_types,
                "VENDOR_INVOICE": "VENDOR_INVOICE" in doc_types,
                "VENDOR_DC": "VENDOR_DC" in doc_types,
                "COMPANY_INVOICE": "COMPANY_INVOICE" in doc_types,
                "COMPANY_DC": "COMPANY_DC" in doc_types,
                "POD": "POD" in doc_types
            }
            
            results.append({
                "so_number": so.so_number,
                "so_month": so.so_month,
                "case_id": case.case_id if case else None,
                "opportunity_id": case.opportunity_id if case else None,
                "customer_name": case.customer_name if case else None,
                "document_count": len(documents),
                "checklist": checklist,
                "folder_path": f"/nas/cases/{case.case_id}/{so.so_month}/SO-{so.so_number}" if case else None,
                "documents": documents
            })
        
        return results
    
    def get_sales_order_with_checklist(self, so: SalesOrder) -> dict:
        """Get sales order data with document checklist."""
        documents = self.db.query(Document).filter(
            Document.sales_order_id == so.id
        ).all()
        
        doc_types = {doc.document_type for doc in documents}
        checklist = {
            "VENDOR_INVOICE": "VENDOR_INVOICE" in doc_types,
            "VENDOR_DC": "VENDOR_DC" in doc_types,
            "COMPANY_INVOICE": "COMPANY_INVOICE" in doc_types,
            "COMPANY_DC": "COMPANY_DC" in doc_types,
            "POD": "POD" in doc_types
        }
        
        return {
            "id": so.id,
            "case_id": so.case_id,
            "so_number": so.so_number,
            "so_month": so.so_month,
            "created_at": so.created_at,
            "updated_at": so.updated_at,
            "document_count": len(documents),
            "checklist": checklist
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
