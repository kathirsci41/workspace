from __future__ import annotations

from pathlib import Path

import pytest

from app.scripts.cleanup_files import run_cleanup


def test_cleanup_cli_dry_run_reports_orphans(tmp_path: Path):
    orphan = tmp_path / "orphan.pdf"
    orphan.write_bytes(b"%PDF-1.4")

    result = run_cleanup(storage_root=tmp_path, known_paths=set(), retention_days=0, dry_run=True)

    assert str(orphan) in result["candidates"]
    assert result["deleted"] == []
    assert orphan.exists()


def test_cleanup_cli_execute_removes_orphans(tmp_path: Path):
    orphan = tmp_path / "orphan.pdf"
    orphan.write_bytes(b"%PDF-1.4")

    result = run_cleanup(storage_root=tmp_path, known_paths=set(), retention_days=0, dry_run=False, allow_empty_known_paths=True)

    assert str(orphan) in result["deleted"]
    assert not orphan.exists()


def test_cleanup_cli_execute_refuses_empty_known_paths_without_override(tmp_path: Path):
    orphan = tmp_path / "orphan.pdf"
    orphan.write_bytes(b"%PDF-1.4")

    with pytest.raises(RuntimeError, match="known_paths is empty"):
        run_cleanup(storage_root=tmp_path, known_paths=set(), retention_days=0, dry_run=False)

    assert orphan.exists()
