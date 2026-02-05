import hashlib
from typing import BinaryIO


def calculate_checksum(file: BinaryIO) -> str:
    """
    Calculate SHA256 checksum of a file.
    
    Args:
        file: File-like object opened in binary mode
        
    Returns:
        Hexadecimal SHA256 hash string
    """
    sha256_hash = hashlib.sha256()
    
    # Read file in chunks to handle large files
    for chunk in iter(lambda: file.read(8192), b""):
        sha256_hash.update(chunk)
    
    # Reset file pointer to beginning
    file.seek(0)
    
    return sha256_hash.hexdigest()


def calculate_checksum_from_bytes(data: bytes) -> str:
    """
    Calculate SHA256 checksum from bytes.
    
    Args:
        data: Bytes to hash
        
    Returns:
        Hexadecimal SHA256 hash string
    """
    return hashlib.sha256(data).hexdigest()
