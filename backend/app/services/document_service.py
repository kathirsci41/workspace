from sqlalchemy.orm import Session
from typing import Optional, List, BinaryIO
from fastapi import UploadFile

from app.models.document import Document
from app.models.sales_order import SalesOrder
from app.models.case import Case
from app.models.audit_log import AuditLog
from app.schemas.document import DocumentType
from app.services.storage_service import StorageService
from app.utils.checksum import calculate_checksum


class DocumentService:
    """Service for document operations."""
    
    def __init__(self, db: Session):
        self.db = db
        self.storage = StorageService()
    
    async def upload_document(
        self,
        case_id: int,
        document_type: str,
        file: UploadFile,
        sales_order_id: Optional[int] = None,
        reference_number: Optional[str] = None,
        uploaded_by: str = "Anonymous"
    ) -> Document:
        """Upload a new document."""
        # Get case
        case = self.db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise ValueError(f"Case with ID {case_id} not found")
        
        # Validate document type and SO requirement
        if document_type == "CUSTOMER_PO":
            if sales_order_id is not None:
                raise ValueError("Customer PO cannot be linked to a Sales Order")
            so_number = None
            so_month = None
        else:
            if sales_order_id is None:
                raise ValueError(f"{document_type} requires a Sales Order")
            
            # Get sales order info
            sales_order = self.db.query(SalesOrder).filter(
                SalesOrder.id == sales_order_id
            ).first()
            if not sales_order:
                raise ValueError(f"Sales Order with ID {sales_order_id} not found")
            if sales_order.case_id != case_id:
                raise ValueError("Sales Order does not belong to this case")
            
            so_number = sales_order.so_number
            so_month = sales_order.so_month
        
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Calculate checksum
        import io
        checksum = calculate_checksum(io.BytesIO(file_content))
        
        # Check for duplicate
        existing = self.db.query(Document).filter(
            Document.case_id == case_id,
            Document.checksum == checksum
        ).first()
        if existing:
            raise ValueError(f"File already exists as {existing.original_filename}")
        
        # Generate storage path
        storage_path, unique_filename = self.storage.generate_storage_path(
            case_id=case.case_id,
            document_type=document_type,
            original_filename=file.filename,
            sales_order_number=so_number,
            so_month=so_month
        )
        
        # Save file
        self.storage.save_file(file_content, storage_path)
        
        # Create document record
        document = Document(
            case_id=case_id,
            sales_order_id=sales_order_id,
            document_type=document_type,
            filename=unique_filename,
            original_filename=file.filename,
            reference_number=reference_number,
            storage_path=storage_path,
            checksum=checksum,
            file_size=file_size,
            uploaded_by=uploaded_by
        )
        
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        
        # Log audit
        self._log_audit(case_id, document.id, sales_order_id, "DOCUMENT_UPLOADED", uploaded_by, {
            "document_type": document_type,
            "original_filename": file.filename,
            "file_size": file_size
        })
        
        return document
    
    def get_document(self, document_id: int) -> Optional[Document]:
        """Get document by ID."""
        return self.db.query(Document).filter(Document.id == document_id).first()
    
    def get_documents_for_case(
        self,
        case_id: int,
        sales_order_id: Optional[int] = None,
        document_type: Optional[str] = None,
        month: Optional[str] = None
    ) -> List[Document]:
        """Get documents for a case with optional filters."""
        query = self.db.query(Document).filter(Document.case_id == case_id)
        
        if sales_order_id is not None:
            query = query.filter(Document.sales_order_id == sales_order_id)
        
        if document_type:
            query = query.filter(Document.document_type == document_type)
        
        if month:
            # Filter by SO month
            so_ids = self.db.query(SalesOrder.id).filter(
                SalesOrder.case_id == case_id,
                SalesOrder.so_month == month
            ).all()
            so_ids = [id[0] for id in so_ids]
            query = query.filter(
                (Document.sales_order_id.in_(so_ids)) | 
                (Document.document_type == "CUSTOMER_PO")
            )
        
        return query.order_by(Document.uploaded_at.desc()).all()
    
    def get_file_content(self, document_id: int) -> bytes:
        """Get file content for preview/download."""
        document = self.get_document(document_id)
        if not document:
            raise ValueError(f"Document with ID {document_id} not found")
        
        return self.storage.read_file(document.storage_path)
    
    def rotate_document(self, document_id: int, degrees: int) -> Document:
        """Rotate document by specified degrees."""
        document = self.get_document(document_id)
        if not document:
            raise ValueError(f"Document with ID {document_id} not found")
        
        if degrees not in [0, 90, 180, 270]:
            raise ValueError("Rotation must be 0, 90, 180, or 270 degrees")
        
        # Update rotation (cumulative)
        new_rotation = (document.rotation + degrees) % 360
        document.rotation = new_rotation
        
        self.db.commit()
        self.db.refresh(document)
        
        # Log audit
        self._log_audit(
            document.case_id, document_id, document.sales_order_id,
            "DOCUMENT_ROTATED", "System", {"degrees": degrees, "new_rotation": new_rotation}
        )
        
        return document
    
    def delete_document(self, document_id: int, deleted_by: str = "System") -> bool:
        """Delete a document."""
        document = self.get_document(document_id)
        if not document:
            return False
        
        # Store info for audit before deletion
        case_id = document.case_id
        so_id = document.sales_order_id
        doc_info = {
            "document_type": document.document_type,
            "original_filename": document.original_filename
        }
        
        # Delete file from storage
        self.storage.delete_file(document.storage_path)
        
        # Delete database record
        self.db.delete(document)
        self.db.commit()
        
        # Log audit
        self._log_audit(case_id, None, so_id, "DOCUMENT_DELETED", deleted_by, doc_info)
        
        return True
    
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
