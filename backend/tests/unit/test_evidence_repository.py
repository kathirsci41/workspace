"""TDD tests for EvidenceRepository.

Phase 1c: persistence layer for document_pages, text_sources, field_candidates.

All tests use run("up") to build the schema from the real migration SQL, so
the repository is tested against the actual 002_evidence_schema.sql tables.

One schema-parity test verifies that Base.metadata.create_all() produces the
same column set as run("up"), guarding against ORM/SQL drift.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session

from app.config import Settings, replace_settings
from app.migrations.runner import run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(tmp_path: Path, name: str = "test.db") -> Session:
    """Return a Session backed by a freshly migrated SQLite DB."""
    db_url = f"sqlite:///{tmp_path / name}"
    replace_settings(Settings(database_url=db_url))
    run("up")
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _doc_id() -> str:
    return str(uuid4())


# ---------------------------------------------------------------------------
# Imports under test — these will fail (ImportError) until the modules exist
# ---------------------------------------------------------------------------
from app.repositories.evidence import EvidenceRepository  # noqa: E402


# ---------------------------------------------------------------------------
# document_pages
# ---------------------------------------------------------------------------

class TestUpsertDocumentPage:
    def test_upsert_creates_new_page(self, tmp_path: Path):
        session = _make_session(tmp_path)
        repo = EvidenceRepository(session)
        doc_id = _doc_id()

        page = repo.upsert_document_page(
            doc_id, 1,
            image_path="storage/doc1/page_1.png",
            has_digital_text=False,
        )
        session.commit()

        assert page.id is not None
        assert page.document_id == doc_id
        assert page.page_number == 1
        assert page.image_path == "storage/doc1/page_1.png"
        assert page.has_digital_text is False

    def test_upsert_updates_existing_page(self, tmp_path: Path):
        session = _make_session(tmp_path)
        repo = EvidenceRepository(session)
        doc_id = _doc_id()

        first = repo.upsert_document_page(doc_id, 1, image_hash="oldhash")
        session.commit()

        second = repo.upsert_document_page(doc_id, 1, image_hash="newhash", rotation_detected=90)
        session.commit()

        # Same row — same id
        assert second.id == first.id
        assert second.image_hash == "newhash"
        assert second.rotation_detected == 90

    def test_upsert_different_pages_are_independent(self, tmp_path: Path):
        session = _make_session(tmp_path)
        repo = EvidenceRepository(session)
        doc_id = _doc_id()

        p1 = repo.upsert_document_page(doc_id, 1)
        p2 = repo.upsert_document_page(doc_id, 2)
        session.commit()

        assert p1.id != p2.id
        assert p1.page_number == 1
        assert p2.page_number == 2


class TestGetDocumentPage:
    def test_get_returns_existing_page(self, tmp_path: Path):
        session = _make_session(tmp_path)
        repo = EvidenceRepository(session)
        doc_id = _doc_id()

        repo.upsert_document_page(doc_id, 3, page_classification="invoice")
        session.commit()

        found = repo.get_document_page(doc_id, 3)
        assert found is not None
        assert found.page_classification == "invoice"

    def test_get_returns_none_for_missing(self, tmp_path: Path):
        session = _make_session(tmp_path)
        repo = EvidenceRepository(session)

        result = repo.get_document_page(_doc_id(), 99)
        assert result is None


# ---------------------------------------------------------------------------
# text_sources
# ---------------------------------------------------------------------------

def _ts_kwargs(**overrides) -> dict:
    """Return minimal valid keyword args for insert_text_source."""
    base = dict(
        document_id=_doc_id(),
        page_number=1,
        source_type="digital_pdf",
        provider="pdfminer",
        settings_hash="sha256:settings_abc",
        image_hash="sha256:image_abc",
        success=True,
    )
    base.update(overrides)
    return base


class TestTextSources:
    def test_insert_and_get_by_cache_key(self, tmp_path: Path):
        session = _make_session(tmp_path)
        repo = EvidenceRepository(session)
        doc_id = _doc_id()
        kwargs = _ts_kwargs(document_id=doc_id, raw_text="hello world")

        inserted = repo.insert_text_source(**kwargs)
        session.commit()

        found = repo.get_text_source_by_cache_key(
            doc_id, kwargs["page_number"],
            kwargs["provider"], kwargs["settings_hash"], kwargs["image_hash"],
        )
        assert found is not None
        assert found.id == inserted.id
        assert found.raw_text == "hello world"

    def test_get_by_cache_key_returns_none_for_missing(self, tmp_path: Path):
        session = _make_session(tmp_path)
        repo = EvidenceRepository(session)

        result = repo.get_text_source_by_cache_key(
            _doc_id(), 1, "pdfminer", "sha256:nope", "sha256:nope2"
        )
        assert result is None

    def test_list_text_sources_for_document(self, tmp_path: Path):
        session = _make_session(tmp_path)
        repo = EvidenceRepository(session)
        doc_id = _doc_id()
        other_doc = _doc_id()

        repo.insert_text_source(**_ts_kwargs(document_id=doc_id, page_number=1, settings_hash="h1", image_hash="i1"))
        repo.insert_text_source(**_ts_kwargs(document_id=doc_id, page_number=2, settings_hash="h2", image_hash="i2"))
        repo.insert_text_source(**_ts_kwargs(document_id=other_doc, page_number=1))
        session.commit()

        results = repo.list_text_sources(doc_id)
        assert len(results) == 2
        assert all(r.document_id == doc_id for r in results)

    def test_list_text_sources_filtered_by_page(self, tmp_path: Path):
        session = _make_session(tmp_path)
        repo = EvidenceRepository(session)
        doc_id = _doc_id()

        repo.insert_text_source(**_ts_kwargs(document_id=doc_id, page_number=1, settings_hash="h1", image_hash="i1"))
        repo.insert_text_source(**_ts_kwargs(document_id=doc_id, page_number=2, settings_hash="h2", image_hash="i2"))
        session.commit()

        results = repo.list_text_sources(doc_id, page_number=1)
        assert len(results) == 1
        assert results[0].page_number == 1


# ---------------------------------------------------------------------------
# field_candidates
# ---------------------------------------------------------------------------

def _fc_kwargs(**overrides) -> dict:
    """Return minimal valid keyword args for insert_field_candidate."""
    base = dict(
        document_id=_doc_id(),
        field_key="vendor_name",
        source_type="digital_pdf",
        selection_status="candidate",
        candidate_value="ACME Ltd",
    )
    base.update(overrides)
    return base


class TestFieldCandidates:
    def test_insert_field_candidate(self, tmp_path: Path):
        session = _make_session(tmp_path)
        repo = EvidenceRepository(session)
        doc_id = _doc_id()

        fc = repo.insert_field_candidate(
            **_fc_kwargs(document_id=doc_id, candidate_value="Panimalar", confidence=0.95)
        )
        session.commit()

        assert fc.id is not None
        assert fc.document_id == doc_id
        assert fc.candidate_value == "Panimalar"
        assert fc.confidence == pytest.approx(0.95)
        assert fc.selection_status == "candidate"

    def test_list_field_candidates_for_document(self, tmp_path: Path):
        session = _make_session(tmp_path)
        repo = EvidenceRepository(session)
        doc_id = _doc_id()
        other = _doc_id()

        repo.insert_field_candidate(**_fc_kwargs(document_id=doc_id, field_key="vendor_name"))
        repo.insert_field_candidate(**_fc_kwargs(document_id=doc_id, field_key="invoice_number"))
        repo.insert_field_candidate(**_fc_kwargs(document_id=other, field_key="vendor_name"))
        session.commit()

        results = repo.list_field_candidates(doc_id)
        assert len(results) == 2
        assert all(r.document_id == doc_id for r in results)

    def test_list_field_candidates_filtered_by_field_key(self, tmp_path: Path):
        session = _make_session(tmp_path)
        repo = EvidenceRepository(session)
        doc_id = _doc_id()

        repo.insert_field_candidate(**_fc_kwargs(document_id=doc_id, field_key="vendor_name", candidate_value="A"))
        repo.insert_field_candidate(**_fc_kwargs(document_id=doc_id, field_key="vendor_name", candidate_value="B"))
        repo.insert_field_candidate(**_fc_kwargs(document_id=doc_id, field_key="invoice_number", candidate_value="INV-001"))
        session.commit()

        vendor_results = repo.list_field_candidates(doc_id, field_key="vendor_name")
        assert len(vendor_results) == 2
        assert all(r.field_key == "vendor_name" for r in vendor_results)


class TestSelectFieldCandidate:
    def test_select_marks_candidate_selected_and_others_rejected(self, tmp_path: Path):
        session = _make_session(tmp_path)
        repo = EvidenceRepository(session)
        doc_id = _doc_id()

        c1 = repo.insert_field_candidate(**_fc_kwargs(document_id=doc_id, field_key="vendor_name", candidate_value="A"))
        c2 = repo.insert_field_candidate(**_fc_kwargs(document_id=doc_id, field_key="vendor_name", candidate_value="B"))
        c3 = repo.insert_field_candidate(**_fc_kwargs(document_id=doc_id, field_key="invoice_number", candidate_value="INV-1"))
        session.commit()

        result = repo.select_field_candidate(c1.id)
        session.commit()

        session.refresh(c1)
        session.refresh(c2)
        session.refresh(c3)

        assert result is not None
        assert result.id == c1.id
        assert c1.selection_status == "selected"
        assert c2.selection_status == "rejected"
        assert c2.rejection_reason == "superseded_by_selection"
        # Different field_key: untouched
        assert c3.selection_status == "candidate"

    def test_select_leaves_manual_override_untouched(self, tmp_path: Path):
        session = _make_session(tmp_path)
        repo = EvidenceRepository(session)
        doc_id = _doc_id()

        c1 = repo.insert_field_candidate(**_fc_kwargs(document_id=doc_id, field_key="vendor_name", candidate_value="A"))
        c2 = repo.insert_field_candidate(
            **_fc_kwargs(
                document_id=doc_id, field_key="vendor_name",
                candidate_value="B", selection_status="manual_override",
            )
        )
        session.commit()

        repo.select_field_candidate(c1.id)
        session.commit()

        session.refresh(c2)
        assert c2.selection_status == "manual_override"

    def test_select_unknown_id_returns_none(self, tmp_path: Path):
        session = _make_session(tmp_path)
        repo = EvidenceRepository(session)

        result = repo.select_field_candidate(str(uuid4()))
        assert result is None


# ---------------------------------------------------------------------------
# Schema parity: run("up") vs Base.metadata.create_all()
# ---------------------------------------------------------------------------

def _build_schemas(tmp_path: Path):
    """Return (mig_inspector, orm_inspector) for independently built schemas."""
    from app.database import Base

    mig_url = f"sqlite:///{tmp_path / 'mig.db'}"
    replace_settings(Settings(database_url=mig_url))
    run("up")
    mig_engine = create_engine(mig_url, connect_args={"check_same_thread": False})

    orm_url = f"sqlite:///{tmp_path / 'orm.db'}"
    orm_engine = create_engine(orm_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=orm_engine)

    return inspect(mig_engine), inspect(orm_engine)


_EVIDENCE_TABLES = ["document_pages", "text_sources", "field_candidates"]

# Index names expected from 002_evidence_schema.sql
_EXPECTED_INDEXES: dict[str, set[str]] = {
    "document_pages": {"ix_document_pages_document_id"},
    "text_sources": {"ix_text_sources_document_id", "ix_text_sources_provider"},
    "field_candidates": {
        "ix_field_candidates_document_id",
        "ix_field_candidates_field_key",
        "ix_field_candidates_selection_status",
        "ix_field_candidates_text_source_id",
    },
}

# UNIQUE constraint column sets expected from 002_evidence_schema.sql
_EXPECTED_UNIQUE_COL_SETS: dict[str, set[frozenset]] = {
    "document_pages": {frozenset({"document_id", "page_number"})},
    "text_sources": {
        frozenset({"document_id", "page_number", "provider", "settings_hash", "image_hash"})
    },
    "field_candidates": set(),
}


class TestSchemaParity:
    def test_column_names_match(self, tmp_path: Path):
        """ORM create_all and run('up') must produce identical column names."""
        mig_insp, orm_insp = _build_schemas(tmp_path)
        for table in _EVIDENCE_TABLES:
            mig_cols = {c["name"] for c in mig_insp.get_columns(table)}
            orm_cols = {c["name"] for c in orm_insp.get_columns(table)}
            assert mig_cols == orm_cols, (
                f"Column name mismatch in '{table}':\n"
                f"  migration-only: {mig_cols - orm_cols}\n"
                f"  orm-only:       {orm_cols - mig_cols}"
            )

    def test_nullable_flags_match(self, tmp_path: Path):
        """Non-PK column nullable flags must agree between migration and ORM schemas.

        The 'id' (PK) column is excluded: SQLite's PRAGMA table_info reports
        notnull=0 for inline PRIMARY KEY columns regardless of NOT NULL, so the
        migration inspector returns nullable=True while the ORM inspector returns
        nullable=False.  This is a known SQLite pragma quirk with no functional
        impact.  All other columns must agree.
        """
        mig_insp, orm_insp = _build_schemas(tmp_path)
        for table in _EVIDENCE_TABLES:
            mig_map = {c["name"]: c["nullable"] for c in mig_insp.get_columns(table) if c["name"] != "id"}
            orm_map = {c["name"]: c["nullable"] for c in orm_insp.get_columns(table) if c["name"] != "id"}
            assert mig_map == orm_map, (
                f"Nullable-flag mismatch in '{table}':\n"
                + "\n".join(
                    f"  {col}: migration={mig_map.get(col, '?')} orm={orm_map.get(col, '?')}"
                    for col in mig_map.keys() | orm_map.keys()
                    if mig_map.get(col) != orm_map.get(col)
                )
            )

    def test_critical_not_null_columns(self, tmp_path: Path):
        """text_sources cache-key columns must be NOT NULL in both schemas.

        These were corrected in Phase 1b.  Nullable cache keys break the UNIQUE
        constraint because SQLite treats NULL != NULL.
        """
        mig_insp, orm_insp = _build_schemas(tmp_path)
        for insp, label in ((mig_insp, "migration"), (orm_insp, "orm")):
            col_map = {c["name"]: c["nullable"] for c in insp.get_columns("text_sources")}
            assert col_map["settings_hash"] is False, (
                f"text_sources.settings_hash must be NOT NULL in {label} schema"
            )
            assert col_map["image_hash"] is False, (
                f"text_sources.image_hash must be NOT NULL in {label} schema"
            )

    def test_index_names_match(self, tmp_path: Path):
        """All expected index names from 002_evidence_schema.sql must exist in
        both the migration schema and the ORM schema."""
        mig_insp, orm_insp = _build_schemas(tmp_path)
        for table in _EVIDENCE_TABLES:
            expected = _EXPECTED_INDEXES[table]
            mig_idx = {i["name"] for i in mig_insp.get_indexes(table)}
            orm_idx = {i["name"] for i in orm_insp.get_indexes(table)}
            assert expected <= mig_idx, (
                f"Missing indexes in migration schema for '{table}': {expected - mig_idx}"
            )
            assert expected <= orm_idx, (
                f"Missing indexes in ORM schema for '{table}': {expected - orm_idx}"
            )

    def test_unique_constraint_column_sets(self, tmp_path: Path):
        """UNIQUE constraints must cover the expected column sets in both schemas.

        Constraint names are intentionally ignored: SQLite assigns None to
        inline constraints while the ORM assigns explicit names.
        """
        mig_insp, orm_insp = _build_schemas(tmp_path)
        for table in _EVIDENCE_TABLES:
            expected = _EXPECTED_UNIQUE_COL_SETS[table]
            mig_uc = {frozenset(uc["column_names"]) for uc in mig_insp.get_unique_constraints(table)}
            orm_uc = {frozenset(uc["column_names"]) for uc in orm_insp.get_unique_constraints(table)}
            assert expected == mig_uc, (
                f"Unique constraint mismatch (migration) in '{table}': "
                f"expected {expected}, got {mig_uc}"
            )
            assert expected == orm_uc, (
                f"Unique constraint mismatch (orm) in '{table}': "
                f"expected {expected}, got {orm_uc}"
            )

    def test_create_all_includes_evidence_tables_via_package_import(self, tmp_path: Path):
        """Base.metadata.create_all() creates evidence tables through the
        app.models package import, without manually importing each model class.

        This proves models/__init__.py is the single registration point:
        importing the package is sufficient for create_all() to know about all
        eight application tables.
        """
        import app.models  # noqa: F401 — triggers __init__.py, registers all models

        from app.database import Base
        orm_url = f"sqlite:///{tmp_path / 'reg.db'}"
        orm_engine = create_engine(orm_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=orm_engine)

        table_names = set(inspect(orm_engine).get_table_names())
        for table in _EVIDENCE_TABLES:
            assert table in table_names, (
                f"Evidence table '{table}' not created by create_all() — "
                "check that app/models/__init__.py imports its model"
            )
