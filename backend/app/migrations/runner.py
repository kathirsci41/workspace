"""Incremental migration runner for the Order Assurance SQLite schema.

Usage (CLI):
    python -m app.migrations.runner up
    python -m app.migrations.runner down

Incremental behaviour (up):
  - Creates a _migrations tracking table on first use.
  - Scans the migrations directory for *.sql files that do NOT end in _down.sql.
  - Applies only migrations not yet recorded in _migrations, in ascending
    filename order.
  - Records each applied migration with a timestamp.
  - Safe to re-run on an existing DB: already-applied migrations are skipped.
  - Safe on old-style DBs (created before this runner): the runner stamps
    001_initial_schema.sql as applied if the tables already exist, without
    dropping or re-creating them.

Down behaviour:
  - Runs 001_initial_schema_down.sql to drop all application tables.
  - Does not touch _migrations (intentional: leaves tracking intact for audits).
"""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app import config


MIGRATION_DIR = Path(__file__).resolve().parents[2] / "migrations"

_CREATE_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS _migrations (
    name VARCHAR(255) PRIMARY KEY,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def run(direction: str, migration_dir: Path | None = None) -> None:
    """Apply or roll back migrations.

    Args:
        direction:     "up" to apply pending migrations, "down" to drop tables.
        migration_dir: Override the migrations directory (used in tests).
    """
    if direction not in {"up", "down"}:
        raise SystemExit("Usage: python -m app.migrations.runner [up|down]")

    mdir = migration_dir or MIGRATION_DIR
    engine = create_engine(
        config.settings.database_url,
        connect_args={"check_same_thread": False}
        if config.settings.database_url.startswith("sqlite")
        else {},
    )

    if direction == "up":
        _run_up(engine, mdir)
    else:
        _run_down(engine, mdir)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_up(engine, migration_dir: Path) -> None:
    # Step 1: ensure the tracking table exists.
    with engine.begin() as conn:
        conn.execute(text(_CREATE_MIGRATIONS_TABLE))

    # Step 2: find which migrations have already been applied.
    with engine.connect() as conn:
        applied: set[str] = {
            row[0] for row in conn.execute(text("SELECT name FROM _migrations")).fetchall()
        }

    # Step 3: collect and sort candidate migration files.
    up_files = sorted(
        f for f in migration_dir.glob("*.sql") if not f.name.endswith("_down.sql")
    )

    # Step 4: apply pending migrations in order.
    for filepath in up_files:
        if filepath.name in applied:
            continue
        sql = filepath.read_text(encoding="utf-8")
        with engine.begin() as conn:
            for statement in sql.split(";"):
                statement = statement.strip()
                if statement:
                    conn.execute(text(statement))
            conn.execute(
                text("INSERT INTO _migrations (name) VALUES (:name)"),
                {"name": filepath.name},
            )

    # Step 5: backward-compat column additions for old DBs.
    with engine.begin() as conn:
        _ensure_reference_provenance_columns(conn)


def _run_down(engine, migration_dir: Path) -> None:
    sql = (migration_dir / "001_initial_schema_down.sql").read_text(encoding="utf-8")
    with engine.begin() as conn:
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))
        # Drop the migration tracking table so a subsequent run("up") re-applies
        # all migrations from scratch instead of skipping already-recorded ones.
        conn.execute(text("DROP TABLE IF EXISTS _migrations"))


def _ensure_reference_provenance_columns(connection) -> None:
    """Add provenance columns to reference_index if they are missing.

    This guard exists for databases created before these columns were
    added to 001_initial_schema.sql. It is idempotent and safe to run
    on every startup.
    """
    existing = {column["name"] for column in inspect(connection).get_columns("reference_index")}
    additions = {
        "source_type": "VARCHAR(50)",
        "document_type": "VARCHAR(50)",
        "field_name": "VARCHAR(80)",
        "confidence": "FLOAT",
        "evidence_text": "VARCHAR(500)",
        "created_at": "DATETIME",
    }
    for column, definition in additions.items():
        if column not in existing:
            connection.execute(text(f"ALTER TABLE reference_index ADD COLUMN {column} {definition}"))
    connection.execute(
        text("CREATE INDEX IF NOT EXISTS ix_reference_index_document_type ON reference_index(document_type)")
    )


def main() -> None:
    run(sys.argv[1] if len(sys.argv) > 1 else "up")


if __name__ == "__main__":
    main()
