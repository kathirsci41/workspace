from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def delete_document_file(document: Any) -> dict[str, Any]:
    storage_path = getattr(document, "storage_path", None)
    if not storage_path:
        return {"deleted": False, "reason": "no_storage_path"}
    path = Path(storage_path)
    if not path.exists():
        return {"deleted": False, "reason": "missing", "path": str(path)}
    if path.is_dir():
        return {"deleted": False, "reason": "not_file", "path": str(path)}
    try:
        path.unlink()
    except OSError as exc:
        # On CIFS/network mounts unlink may raise PermissionError even when the
        # file is successfully removed.  Treat it as a soft failure so that
        # DELETE /bundles/:id returns 204 instead of 500.
        return {"deleted": False, "reason": "unlink_failed", "error": str(exc), "path": str(path)}
    return {"deleted": True, "path": str(path)}


def cleanup_orphaned_files(
    *,
    storage_root: str | Path,
    known_paths: set[str],
    retention_days: int,
    dry_run: bool = True,
) -> dict[str, list[str]]:
    root = Path(storage_root)
    cutoff = (
        datetime.max.replace(tzinfo=timezone.utc)
        if retention_days <= 0
        else datetime.now(timezone.utc) - timedelta(days=retention_days)
    )
    candidates: list[str] = []
    deleted: list[str] = []
    if not root.exists():
        return {"candidates": [], "deleted": []}

    normalized_known = {str(Path(path).resolve()) for path in known_paths if path}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        resolved = str(path.resolve())
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if resolved in normalized_known or modified > cutoff:
            continue
        candidates.append(str(path))
        if not dry_run:
            path.unlink(missing_ok=True)
            deleted.append(str(path))
    return {"candidates": candidates, "deleted": deleted}
