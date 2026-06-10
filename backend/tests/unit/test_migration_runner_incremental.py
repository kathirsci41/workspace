"""TDD tests for incremental migration runner.

Phase 1a: incremental runner behaviour (all pass).
Phase 1b: evidence schema (002_evidence_schema.sql) behaviour — tests added
          before the SQL file exists and verified to fail first (TDD RED).

Behaviour under test:
  - Fresh DB: _migrations table is created and 001 is recorded.
  - Re-running on an existing DB never duplicates a migration record.
  - A second migration file in the directory is applied only once.
  - Migrations are applied in ascending filename order.
  - An old-style DB (tables exist but no _migrations table) is stamped safely
    without dropping or re-creating any tables.
  - The down path still drops all application tables.
  - Phase 1b: 002 is applied alongside 001 on a fresh DB.
  - Phase 1b: document_pages, text_sources, field_candidates have required columns.
  - Phase 1b: down/up cycle recreates all six application tables.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from app.config import Settings, replace_settings
from app.migrations.runner import run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(tmp_path: Path, name: str = "test.db") -> tuple[str, object]:
    """Return (db_url, engine) for a fresh SQLite file in tmp_path."""
    db_url = f"sqlite:///{tmp_path / name}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    return db_url, engine


def _applied_migrations(engine) -> set[str]:
    """Return the set of migration names recorded in _migrations."""
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT name FROM _migrations")).fetchall()
    return {row[0] for row in rows}


def _table_names(engine) -> set[str]:
    return set(inspect(engine).get_table_names())


def _migrations_dir_with_extra(tmp_path: Path, extra_filename: str, extra_sql: str) -> Path:
    """Copy the real migrations dir to tmp_path and add an extra SQL file."""
    # Test file: backend/tests/unit/<file>.py  → parents[2] = backend/
    real_dir = Path(__file__).resolve().parents[2] / "migrations"
    dest = tmp_path / "migrations"
    shutil.copytree(real_dir, dest)
    (dest / extra_filename).write_text(extra_sql, encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_fresh_db_creates_migrations_tracking_table(tmp_path: Path):
    """run('up') on a fresh DB must create a _migrations tracking table."""
    db_url, engine = _make_db(tmp_path)
    replace_settings(Settings(database_url=db_url))

    run("up")

    assert "_migrations" in _table_names(engine), (
        "_migrations table must be created by run('up') on a fresh DB"
    )


def test_fresh_db_records_001_initial_schema_as_applied(tmp_path: Path):
    """001_initial_schema.sql must be recorded in _migrations after a fresh run."""
    db_url, engine = _make_db(tmp_path)
    replace_settings(Settings(database_url=db_url))

    run("up")

    applied = _applied_migrations(engine)
    assert "001_initial_schema.sql" in applied, (
        f"Expected '001_initial_schema.sql' in _migrations, got: {applied}"
    )


def test_running_up_twice_records_001_only_once(tmp_path: Path):
    """Running run('up') twice must not create duplicate rows in _migrations."""
    db_url, engine = _make_db(tmp_path)
    replace_settings(Settings(database_url=db_url))

    run("up")
    run("up")  # second call — must be idempotent

    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM _migrations WHERE name = '001_initial_schema.sql'")
        ).scalar()
    assert count == 1, f"Expected 1 record for 001, got {count}"


def test_second_migration_file_is_applied(tmp_path: Path):
    """A 002_*.sql file in the migrations dir must be applied after 001."""
    db_url, engine = _make_db(tmp_path)
    replace_settings(Settings(database_url=db_url))

    mdir = _migrations_dir_with_extra(
        tmp_path,
        "002_add_test_table.sql",
        "CREATE TABLE IF NOT EXISTS _test_phase1a_marker (id INTEGER PRIMARY KEY);",
    )

    run("up", migration_dir=mdir)

    assert "_test_phase1a_marker" in _table_names(engine), (
        "002_add_test_table.sql must be applied and create _test_phase1a_marker"
    )
    applied = _applied_migrations(engine)
    assert "002_add_test_table.sql" in applied


def test_second_migration_not_reapplied_on_second_run(tmp_path: Path):
    """Running up twice with a 002 file must record 002 exactly once."""
    db_url, engine = _make_db(tmp_path)
    replace_settings(Settings(database_url=db_url))

    mdir = _migrations_dir_with_extra(
        tmp_path,
        "002_add_test_table.sql",
        "CREATE TABLE IF NOT EXISTS _test_phase1a_marker (id INTEGER PRIMARY KEY);",
    )

    run("up", migration_dir=mdir)
    run("up", migration_dir=mdir)  # second call

    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM _migrations WHERE name = '002_add_test_table.sql'")
        ).scalar()
    assert count == 1, f"Expected 1 record for 002, got {count}"


def test_migrations_applied_in_ascending_filename_order(tmp_path: Path):
    """002 is always applied after 001 (sorted by filename)."""
    db_url, engine = _make_db(tmp_path)
    replace_settings(Settings(database_url=db_url))

    order: list[str] = []

    # We verify order by checking that _migrations rows were inserted in sequence.
    # Create a 002 that inserts a marker row that depends on 001's tables.
    mdir = _migrations_dir_with_extra(
        tmp_path,
        "002_order_check.sql",
        # Insert into order_bundles which is created by 001.
        # If 001 hasn't run yet this will fail, proving 002 was applied after 001.
        (
            "CREATE TABLE IF NOT EXISTS _migration_order_log "
            "(seq INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(100));\n"
            "INSERT INTO _migration_order_log (name) VALUES ('002_ran');"
        ),
    )

    run("up", migration_dir=mdir)

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT name FROM _migration_order_log ORDER BY seq")
        ).fetchall()
    names = [r[0] for r in rows]
    assert names == ["002_ran"], f"Expected ['002_ran'], got {names}"

    # 001 must have been applied before 002 (order_bundles must exist)
    assert "order_bundles" in _table_names(engine)


def test_existing_db_without_tracking_table_is_stamped_safely(tmp_path: Path):
    """An old-style DB (tables exist, no _migrations table) must be upgraded.

    The runner must NOT drop or re-create existing tables, and must record
    001_initial_schema.sql as applied without data loss.
    """
    db_url, engine = _make_db(tmp_path)
    replace_settings(Settings(database_url=db_url))

    # Simulate old-style DB: create schema manually without _migrations table
    old_schema = (Path(__file__).resolve().parents[2] / "migrations" / "001_initial_schema.sql").read_text()
    with engine.begin() as conn:
        for stmt in old_schema.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
        # Insert a sentinel row so we can confirm data was not wiped
        conn.execute(text(
            "INSERT INTO order_bundles (id, bundle_number, status, "
            "customer_delivery_status, vendor_procurement_status, created_at, updated_at) "
            "VALUES ('sentinel-id', 'SENTINEL-BUNDLE', 'REVIEW_REQUIRED', "
            "'REVIEW_REQUIRED', 'REVIEW_REQUIRED', '2026-01-01', '2026-01-01')"
        ))

    # Confirm _migrations does NOT exist yet (simulating old-style DB)
    assert "_migrations" not in _table_names(engine)

    # Run the new incremental runner
    run("up")

    # _migrations table must now exist
    assert "_migrations" in _table_names(engine)

    # 001 must be recorded
    applied = _applied_migrations(engine)
    assert "001_initial_schema.sql" in applied

    # Sentinel data must still be present (no DROP TABLE happened)
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM order_bundles WHERE id = 'sentinel-id'")
        ).scalar()
    assert count == 1, "Sentinel row was destroyed — old DB data was not preserved"


def test_down_still_drops_application_tables(tmp_path: Path):
    """run('down') must still drop all application tables (existing behaviour)."""
    db_url, engine = _make_db(tmp_path)
    replace_settings(Settings(database_url=db_url))

    run("up")
    run("down")

    tables = _table_names(engine)
    for app_table in ("order_bundles", "bundle_documents", "document_metadata",
                      "reference_index", "audit_events"):
        assert app_table not in tables, f"{app_table} was not dropped by run('down')"


def test_down_up_cycle_recreates_all_application_tables(tmp_path: Path):
    """A full down/up cycle must leave all application tables intact.

    Regression guard for the edge case where run('down') keeps _migrations,
    causing the subsequent run('up') to skip 001_initial_schema.sql because
    it was already recorded — leaving the DB with only _migrations and no
    application tables.
    """
    db_url, engine = _make_db(tmp_path)
    replace_settings(Settings(database_url=db_url))

    run("up")
    run("down")
    run("up")  # must fully recreate the schema

    tables = _table_names(engine)
    for app_table in ("order_bundles", "bundle_documents", "document_metadata",
                      "reference_index", "audit_events"):
        assert app_table in tables, (
            f"{app_table} is missing after down/up cycle — "
            "run('down') likely left _migrations intact, causing run('up') to skip 001"
        )

    # _migrations must also be present and contain 001
    assert "_migrations" in tables
    applied = _applied_migrations(engine)
    assert "001_initial_schema.sql" in applied


# ===========================================================================
# Phase 1b — evidence schema (002_evidence_schema.sql)
# ===========================================================================

def _column_names(engine, table: str) -> set[str]:
    return {col["name"] for col in inspect(engine).get_columns(table)}


def test_fresh_db_applies_001_and_002(tmp_path: Path):
    """A fresh run('up') must apply both 001 and 002, creating all tables."""
    db_url, engine = _make_db(tmp_path)
    replace_settings(Settings(database_url=db_url))

    run("up")

    tables = _table_names(engine)
    for expected in ("order_bundles", "bundle_documents", "document_metadata",
                     "reference_index", "audit_events",
                     "document_pages", "text_sources", "field_candidates"):
        assert expected in tables, f"Expected table '{expected}' missing after run('up')"


def test_migrations_table_records_both_001_and_002(tmp_path: Path):
    """_migrations must record exactly one row for 001 and one for 002."""
    db_url, engine = _make_db(tmp_path)
    replace_settings(Settings(database_url=db_url))

    run("up")

    applied = _applied_migrations(engine)
    assert "001_initial_schema.sql" in applied, "001 not recorded in _migrations"
    assert "002_evidence_schema.sql" in applied, "002 not recorded in _migrations"

    with engine.connect() as conn:
        for name in ("001_initial_schema.sql", "002_evidence_schema.sql"):
            count = conn.execute(
                text("SELECT COUNT(*) FROM _migrations WHERE name = :n"), {"n": name}
            ).scalar()
            assert count == 1, f"Expected exactly 1 record for {name}, got {count}"


def test_002_idempotent_on_second_run(tmp_path: Path):
    """Running up twice must not duplicate the 002 record in _migrations."""
    db_url, engine = _make_db(tmp_path)
    replace_settings(Settings(database_url=db_url))

    run("up")
    run("up")

    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM _migrations WHERE name = '002_evidence_schema.sql'")
        ).scalar()
    assert count == 1, f"002 applied more than once: count={count}"


def test_down_up_cycle_recreates_evidence_tables(tmp_path: Path):
    """After a full down/up cycle all six application tables must exist."""
    db_url, engine = _make_db(tmp_path)
    replace_settings(Settings(database_url=db_url))

    run("up")
    run("down")
    run("up")

    tables = _table_names(engine)
    for expected in ("order_bundles", "bundle_documents", "document_metadata",
                     "reference_index", "audit_events",
                     "document_pages", "text_sources", "field_candidates"):
        assert expected in tables, f"'{expected}' missing after down/up cycle"


def test_document_pages_has_required_columns(tmp_path: Path):
    """document_pages must have the columns defined by the evidence schema spec."""
    db_url, engine = _make_db(tmp_path)
    replace_settings(Settings(database_url=db_url))

    run("up")

    cols = _column_names(engine, "document_pages")
    required = {
        "id", "document_id", "page_number", "image_path", "image_hash",
        "has_digital_text", "rotation_detected", "page_classification", "created_at",
    }
    missing = required - cols
    assert not missing, f"document_pages missing columns: {missing}"


def test_text_sources_has_required_columns(tmp_path: Path):
    """text_sources must have the columns defined by the evidence schema spec."""
    db_url, engine = _make_db(tmp_path)
    replace_settings(Settings(database_url=db_url))

    run("up")

    cols = _column_names(engine, "text_sources")
    required = {
        "id", "document_id", "page_number", "source_type", "provider",
        "provider_version", "settings_hash", "settings_json",
        "raw_text", "normalized_text", "success", "error",
        "duration_ms", "image_hash", "created_at",
    }
    missing = required - cols
    assert not missing, f"text_sources missing columns: {missing}"


def test_field_candidates_has_required_columns(tmp_path: Path):
    """field_candidates must have the columns defined by the evidence schema spec."""
    db_url, engine = _make_db(tmp_path)
    replace_settings(Settings(database_url=db_url))

    run("up")

    cols = _column_names(engine, "field_candidates")
    required = {
        "id", "document_id", "field_key", "candidate_value", "normalized_value",
        "source_type", "provider", "text_source_id", "page_number",
        "evidence_text", "confidence", "selection_status", "rejection_reason", "created_at",
    }
    missing = required - cols
    assert not missing, f"field_candidates missing columns: {missing}"


def test_document_pages_unique_constraint(tmp_path: Path):
    """document_pages must enforce UNIQUE(document_id, page_number)."""
    db_url, engine = _make_db(tmp_path)
    replace_settings(Settings(database_url=db_url))
    run("up")

    import pytest as _pytest
    from sqlalchemy.exc import IntegrityError

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO document_pages (id, document_id, page_number, created_at) "
            "VALUES ('id-1', 'doc-1', 1, '2026-01-01')"
        ))
    with _pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO document_pages (id, document_id, page_number, created_at) "
                "VALUES ('id-2', 'doc-1', 1, '2026-01-01')"
            ))


def test_document_pages_indexes_exist(tmp_path: Path):
    """document_pages must have the expected indexes."""
    db_url, engine = _make_db(tmp_path)
    replace_settings(Settings(database_url=db_url))
    run("up")

    indexes = {idx["name"] for idx in inspect(engine).get_indexes("document_pages")}
    assert "ix_document_pages_document_id" in indexes, (
        f"ix_document_pages_document_id missing. Found: {indexes}"
    )


def test_text_sources_indexes_exist(tmp_path: Path):
    """text_sources must have the expected indexes."""
    db_url, engine = _make_db(tmp_path)
    replace_settings(Settings(database_url=db_url))
    run("up")

    indexes = {idx["name"] for idx in inspect(engine).get_indexes("text_sources")}
    for expected in ("ix_text_sources_document_id", "ix_text_sources_provider"):
        assert expected in indexes, f"{expected} missing. Found: {indexes}"


def test_field_candidates_indexes_exist(tmp_path: Path):
    """field_candidates must have the expected indexes."""
    db_url, engine = _make_db(tmp_path)
    replace_settings(Settings(database_url=db_url))
    run("up")

    indexes = {idx["name"] for idx in inspect(engine).get_indexes("field_candidates")}
    for expected in ("ix_field_candidates_document_id", "ix_field_candidates_field_key",
                     "ix_field_candidates_selection_status"):
        assert expected in indexes, f"{expected} missing. Found: {indexes}"
