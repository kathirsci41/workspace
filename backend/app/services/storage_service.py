from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app import config


def storage_root() -> Path:
    configured = Path(config.settings.storage_dir)
    if configured.is_absolute():
        return configured
    return Path(__file__).resolve().parents[2] / configured


async def save_upload_file(*, bundle_id: str, file: UploadFile) -> str:
    if not _is_pdf(file):
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported.")
    bundle_dir = storage_root() / bundle_id
    bundle_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "uploaded-document").name
    target = bundle_dir / f"{uuid4()}_{safe_name}"
    bytes_written = 0
    header = b""
    try:
        with target.open("wb") as output:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                if len(header) < 4:
                    header += chunk[: 4 - len(header)]
                bytes_written += len(chunk)
                if bytes_written > config.settings.max_upload_bytes:
                    raise HTTPException(status_code=413, detail="PDF exceeds maximum upload size.")
                output.write(chunk)
        if not header.startswith(b"%PDF"):
            raise HTTPException(status_code=400, detail="Only valid PDF uploads are supported.")
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return str(target)


def _is_pdf(file: UploadFile) -> bool:
    filename = (file.filename or "").lower()
    content_type = (file.content_type or "").lower()
    return filename.endswith(".pdf") and content_type in {"application/pdf", "application/octet-stream"}


def get_pdf_page_count(path: str) -> int | None:
    try:
        import fitz

        with fitz.open(path) as document:
            return document.page_count
    except Exception:
        return None


def resolve_stored_pdf_path(path: str | Path) -> Path | None:
    try:
        resolved = Path(path).resolve()
        root = storage_root().resolve()
    except OSError:
        return None
    try:
        resolved.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=403, detail="Document path is outside configured storage.")
    return resolved
