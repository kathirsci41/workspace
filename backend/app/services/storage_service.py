import os
import uuid
from typing import Tuple

from app.config import get_settings


class StorageService:
    """Service for file storage operations."""
    
    def __init__(self):
        self.settings = get_settings()
        self.base_path = self.settings.nas_base_path
    
    def generate_storage_path(
        self,
        case_id: str,
        document_type: str,
        original_filename: str,
        sales_order_number: str = None,
        so_month: str = None
    ) -> Tuple[str, str]:
        """
        Generate storage path for a document.
        
        Returns:
            Tuple of (full_path, unique_filename)
        
        Path structure:
            Customer PO: /nas/cases/{CASE_ID}/CUSTOMER_PO/{filename}
            Other docs:  /nas/cases/{CASE_ID}/{SO_MONTH}/SO-{SO_NUMBER}/{DOC_TYPE}/{filename}
        """
        # Generate unique filename
        file_uuid = uuid.uuid4().hex[:8]
        safe_filename = original_filename.replace(" ", "_")
        unique_filename = f"{file_uuid}_{safe_filename}"
        
        if document_type == "CUSTOMER_PO":
            # Customer PO is case-level — stored directly under the case folder
            folder_path = os.path.join(
                self.base_path, 
                case_id, 
                "CUSTOMER_PO"
            )
        else:
            if not sales_order_number or not so_month:
                raise ValueError("Sales order number and month are required for SO-level documents")
            folder_path = os.path.join(
                self.base_path, 
                case_id, 
                so_month, 
                f"SO-{sales_order_number}", 
                document_type
            )
        
        # Create directory if it doesn't exist
        os.makedirs(folder_path, exist_ok=True)
        
        full_path = os.path.join(folder_path, unique_filename)
        # Normalize path separators to forward slashes for cross-platform compatibility
        # Windows backslashes don't work in Linux containers
        full_path = full_path.replace('\\', '/')

        return full_path, unique_filename
    
    def save_file(self, file_content: bytes, storage_path: str) -> None:
        """Save file content to storage path."""
        # Ensure directory exists
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        
        with open(storage_path, 'wb') as f:
            f.write(file_content)
    
    def read_file(self, storage_path: str) -> bytes:
        """Read file content from storage path."""
        if not os.path.exists(storage_path):
            raise FileNotFoundError(f"File not found: {storage_path}")
        
        with open(storage_path, 'rb') as f:
            return f.read()
    
    def delete_file(self, storage_path: str) -> bool:
        """Delete file from storage."""
        if os.path.exists(storage_path):
            os.remove(storage_path)
            return True
        return False
    
    def file_exists(self, storage_path: str) -> bool:
        """Check if file exists."""
        return os.path.exists(storage_path)
    
    def get_file_size(self, storage_path: str) -> int:
        """Get file size in bytes."""
        if os.path.exists(storage_path):
            return os.path.getsize(storage_path)
        return 0
