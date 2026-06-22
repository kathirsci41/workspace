from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.config import Settings, replace_settings
from app.migrations.runner import run


def test_lightweight_migration_up_down(tmp_path: Path):
    db_url = f"sqlite:///{tmp_path / 'migration.db'}"
    replace_settings(Settings(database_url=db_url))

    run("up")
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    inspector = inspect(engine)
    assert {"order_bundles", "bundle_documents", "document_metadata", "reference_index", "audit_events", "vendor_master"} <= set(inspector.get_table_names())

    run("down")
    inspector = inspect(engine)
    assert "order_bundles" not in set(inspector.get_table_names())


def test_migration_up_adds_reference_provenance_columns_to_existing_schema(tmp_path: Path):
    db_url = f"sqlite:///{tmp_path / 'existing.db'}"
    replace_settings(Settings(database_url=db_url))
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE reference_index ("
                "id VARCHAR(36) PRIMARY KEY, "
                "document_id VARCHAR(36) NOT NULL, "
                "order_bundle_id VARCHAR(36), "
                "reference_type VARCHAR(80) NOT NULL, "
                "reference_value VARCHAR(255) NOT NULL)"
            )
        )

    run("up")

    columns = {column["name"] for column in inspect(engine).get_columns("reference_index")}
    assert {"source_type", "document_type", "field_name", "confidence", "evidence_text", "created_at"} <= columns
