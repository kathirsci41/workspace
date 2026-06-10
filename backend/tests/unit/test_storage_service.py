from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import app.services.storage_service as storage_service
from app.config import Settings


class FakeUploadFile:
    filename = "test.pdf"
    content_type = "application/pdf"

    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)
        self.read_sizes: list[int] = []

    async def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        if not self._chunks:
            return b""
        if size == -1:
            joined = b"".join(self._chunks)
            self._chunks = []
            return joined
        chunk = self._chunks.pop(0)
        if len(chunk) <= size:
            return chunk
        self._chunks.insert(0, chunk[size:])
        return chunk[:size]


def test_upload_file_is_streamed_in_chunks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(storage_service.config, "settings", Settings(storage_dir=str(tmp_path), max_upload_mb=1))
    upload = FakeUploadFile([b"%PDF-1.4\n", b"x" * 128])

    saved_path = asyncio.run(storage_service.save_upload_file(bundle_id="bundle", file=upload))

    assert Path(saved_path).exists()
    assert upload.read_sizes
    assert all(size != -1 for size in upload.read_sizes)


def test_upload_file_rejects_oversize_during_streaming(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(storage_service.config, "settings", Settings(storage_dir=str(tmp_path), max_upload_mb=0, max_upload_bytes=0))
    upload = FakeUploadFile([b"%PDF-1.4\n", b"x" * 128])

    with pytest.raises(Exception) as exc_info:
        asyncio.run(storage_service.save_upload_file(bundle_id="bundle", file=upload))

    assert getattr(exc_info.value, "status_code", None) == 413
    assert not list((tmp_path / "bundle").glob("*.pdf"))
    assert upload.read_sizes
    assert all(size != -1 for size in upload.read_sizes)
