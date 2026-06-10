from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import select

from app import config
from app.database import SessionLocal
from app.models.document import DocumentRecord
from app.services.file_cleanup_service import cleanup_orphaned_files
from app.services.storage_service import storage_root


def known_document_paths() -> set[str]:
    with SessionLocal() as db:
        return {path for path in db.scalars(select(DocumentRecord.storage_path)).all() if path}


def run_cleanup(
    *,
    storage_root: str | Path,
    known_paths: set[str],
    retention_days: int,
    dry_run: bool,
    allow_empty_known_paths: bool = False,
) -> dict[str, list[str]]:
    if not dry_run and not known_paths and not allow_empty_known_paths:
        raise RuntimeError("known_paths is empty; refusing execute cleanup without --allow-empty-known-paths")
    return cleanup_orphaned_files(
        storage_root=storage_root,
        known_paths=known_paths,
        retention_days=retention_days,
        dry_run=dry_run,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean orphaned local Order Assurance files.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Report files that would be removed.")
    mode.add_argument("--execute", action="store_true", help="Remove orphaned files.")
    parser.add_argument(
        "--allow-empty-known-paths",
        action="store_true",
        help="Allow execute mode to continue when the database returns no referenced document paths.",
    )
    args = parser.parse_args()

    result = run_cleanup(
        storage_root=storage_root(),
        known_paths=known_document_paths(),
        retention_days=config.settings.file_retention_days,
        dry_run=not args.execute,
        allow_empty_known_paths=args.allow_empty_known_paths,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
