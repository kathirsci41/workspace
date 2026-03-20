import os
import re
import uuid
import hashlib
import aiofiles


class NASUnavailableError(Exception):
    """Raised when the NAS storage path is not accessible."""
    pass


class StorageService:
    def __init__(self, nas_base_path: str):
        self.base_path = nas_base_path

    def generate_storage_path(
        self,
        customer_id: str,
        po_number: str,
        document_type: str,
        original_filename: str,
    ) -> tuple[str, str]:
        """Returns (relative_path, uuid_filename)."""
        file_uuid = uuid.uuid4().hex[:8]
        safe_name = self.sanitize_filename(original_filename)
        uuid_filename = f"{file_uuid}_{safe_name}"
        relative_path = f"documents/{customer_id}/{po_number}/{document_type}/{uuid_filename}"
        return relative_path, uuid_filename

    def check_accessible(self) -> None:
        """Raise NASUnavailableError if the base storage path is not writable."""
        if not os.path.isdir(self.base_path):
            raise NASUnavailableError(
                f"Storage path not found: {self.base_path}"
            )
        if not os.access(self.base_path, os.W_OK):
            raise NASUnavailableError(
                f"Storage path is not writable: {self.base_path}"
            )

    async def save_file(self, relative_path: str, file_data: bytes) -> str:
        """Save file to NAS. Returns relative path."""
        self._validate_path(relative_path)
        self.check_accessible()
        full_path = os.path.join(self.base_path, relative_path)
        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            async with aiofiles.open(full_path, "wb") as f:
                await f.write(file_data)
        except OSError as exc:
            raise NASUnavailableError(
                f"Failed to write to storage: {exc}"
            ) from exc
        return relative_path

    async def read_file(self, relative_path: str) -> bytes:
        """Read file from NAS."""
        self._validate_path(relative_path)
        full_path = os.path.join(self.base_path, relative_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {relative_path}")
        async with aiofiles.open(full_path, "rb") as f:
            return await f.read()

    async def delete_file(self, relative_path: str) -> bool:
        """Delete file from NAS."""
        self._validate_path(relative_path)
        full_path = os.path.join(self.base_path, relative_path)
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False

    def get_full_path(self, relative_path: str) -> str:
        """Get absolute path for a relative NAS path."""
        self._validate_path(relative_path)
        return os.path.join(self.base_path, relative_path)

    @staticmethod
    def calculate_checksum(file_data: bytes) -> str:
        """Calculate SHA-256 checksum."""
        return hashlib.sha256(file_data).hexdigest()

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Remove unsafe characters from filename."""
        safe = re.sub(r"[^\w.\-]", "_", name)
        return safe[:100]

    @staticmethod
    def _validate_path(path: str):
        """Reject any path containing '..' to prevent traversal."""
        if ".." in path:
            raise ValueError("Path traversal detected")
