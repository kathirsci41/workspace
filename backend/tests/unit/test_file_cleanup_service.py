from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.file_cleanup_service import cleanup_orphaned_files, delete_document_file


class DummyDocument:
    def __init__(self, storage_path: str | None):
        self.storage_path = storage_path


def test_document_delete_removes_storage_file(tmp_path: Path):
    file_path = tmp_path / "document.pdf"
    file_path.write_bytes(b"%PDF-1.4")

    result = delete_document_file(DummyDocument(str(file_path)))

    assert result["deleted"] is True
    assert not file_path.exists()


def test_missing_file_does_not_crash_delete(tmp_path: Path):
    missing = tmp_path / "missing.pdf"

    result = delete_document_file(DummyDocument(str(missing)))

    assert result["deleted"] is False
    assert result["reason"] == "missing"


def test_orphan_cleanup_dry_run_reports_files(tmp_path: Path):
    orphan = tmp_path / "orphan.pdf"
    orphan.write_bytes(b"%PDF-1.4")
    old = datetime.now(timezone.utc) - timedelta(days=10)
    timestamp = old.timestamp()
    import os

    os.utime(orphan, (timestamp, timestamp))

    result = cleanup_orphaned_files(storage_root=tmp_path, known_paths=set(), retention_days=1, dry_run=True)

    assert result["candidates"] == [str(orphan)]
    assert result["deleted"] == []
    assert orphan.exists()


def test_orphan_cleanup_actual_removes_files(tmp_path: Path):
    orphan = tmp_path / "orphan.pdf"
    orphan.write_bytes(b"%PDF-1.4")
    old = datetime.now(timezone.utc) - timedelta(days=10)
    timestamp = old.timestamp()
    import os

    os.utime(orphan, (timestamp, timestamp))

    result = cleanup_orphaned_files(storage_root=tmp_path, known_paths=set(), retention_days=1, dry_run=False)

    assert result["deleted"] == [str(orphan)]
    assert not orphan.exists()
