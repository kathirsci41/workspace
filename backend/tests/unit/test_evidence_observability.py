"""TDD tests for Phase 1f: read-only evidence observability endpoints.

Tests cover:
  - dev-gate blocks both endpoints when dev tools disabled
  - document evidence response includes document_pages, text_sources, field_candidates
  - bundle evidence response groups evidence by document
  - raw_text not returned in full; raw_text_preview and raw_text_length are returned
  - normalized_text_preview and normalized_text_length are returned
  - settings_hash and image_hash are visible in text_sources
  - GET requests do not mutate evidence row counts
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings, replace_settings
from app.database import SessionLocal, configure_database, init_db
from app.main import app
from app.models.document import DocumentRecord
from app.models.document_page import DocumentPageRecord
from app.models.field_candidate import FieldCandidateRecord
from app.models.order_bundle import OrderBundleRecord
from app.models.text_source import TextSourceRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def restore_settings():
    original = Settings()
    yield
    replace_settings(original)


def _client(tmp_path: Path, *, dev_tools: bool = True) -> tuple[TestClient, str, str]:
    """Return (client, bundle_id, document_id) with one seeded document + evidence rows."""
    db_path = tmp_path / f"obs_{uuid4().hex[:8]}.db"
    configure_database(f"sqlite:///{db_path}")
    init_db(drop_existing=True)
    replace_settings(Settings(
        app_env="development" if dev_tools else "production",
        enable_dev_tools=dev_tools,
        database_url=f"sqlite:///{db_path}",
    ))

    db = SessionLocal()
    now = datetime.now(timezone.utc)

    bundle = OrderBundleRecord(
        id=str(uuid4()),
        bundle_number="OBS-TEST-001",
        customer_name="Test Customer",
        created_at=now,
        updated_at=now,
    )
    db.add(bundle)
    db.flush()

    doc = DocumentRecord(
        id=str(uuid4()),
        order_bundle_id=bundle.id,
        document_type="COMPANY_INVOICE",
        filename="Invoice_001.pdf",
        status="UPLOADED",
        created_at=now,
        updated_at=now,
    )
    db.add(doc)
    db.flush()

    page = DocumentPageRecord(
        id=str(uuid4()),
        document_id=doc.id,
        page_number=1,
        has_digital_text=True,
        created_at=now,
    )
    db.add(page)

    raw = "Invoice No\n1ITR2526001878\nDate 13/02/2026\nAmount 874439\n" * 30
    ts = TextSourceRecord(
        id=str(uuid4()),
        document_id=doc.id,
        page_number=1,
        source_type="digital_text",
        provider="digital_pdf",
        settings_hash="sha256:aaaa",
        image_hash="sha256:bbbb",
        success=True,
        raw_text=raw,
        normalized_text="normalized " * 40,
        created_at=now,
    )
    db.add(ts)

    fc = FieldCandidateRecord(
        id=str(uuid4()),
        document_id=doc.id,
        field_key="invoice_no",
        source_type="digital_text",
        candidate_value="1ITR2526001878",
        selection_status="candidate",
        created_at=now,
    )
    db.add(fc)

    bundle_id = bundle.id
    doc_id = doc.id
    db.commit()
    db.close()

    return TestClient(app), bundle_id, doc_id


# ---------------------------------------------------------------------------
# Dev-gate tests
# ---------------------------------------------------------------------------

class TestDevGate:
    def test_document_evidence_blocked_when_dev_tools_disabled(self, tmp_path: Path):
        client, _, doc_id = _client(tmp_path, dev_tools=False)
        response = client.get(f"/api/dev/documents/{doc_id}/evidence")
        assert response.status_code == 403
        assert "disabled" in response.text.lower()

    def test_bundle_evidence_blocked_when_dev_tools_disabled(self, tmp_path: Path):
        client, bundle_id, _ = _client(tmp_path, dev_tools=False)
        response = client.get(f"/api/dev/bundles/{bundle_id}/evidence")
        assert response.status_code == 403
        assert "disabled" in response.text.lower()


# ---------------------------------------------------------------------------
# Document evidence structure tests
# ---------------------------------------------------------------------------

class TestDocumentEvidence:
    def test_returns_document_pages_text_sources_and_field_candidates(self, tmp_path: Path):
        client, _, doc_id = _client(tmp_path)
        response = client.get(f"/api/dev/documents/{doc_id}/evidence")
        assert response.status_code == 200
        body = response.json()
        assert "document_pages" in body
        assert "text_sources" in body
        assert "field_candidates" in body
        assert len(body["document_pages"]) == 1
        assert len(body["text_sources"]) == 1
        assert len(body["field_candidates"]) == 1

    def test_raw_text_not_returned_in_full(self, tmp_path: Path):
        client, _, doc_id = _client(tmp_path)
        response = client.get(f"/api/dev/documents/{doc_id}/evidence")
        assert response.status_code == 200
        ts = response.json()["text_sources"][0]
        assert "raw_text" not in ts

    def test_raw_text_preview_is_returned(self, tmp_path: Path):
        client, _, doc_id = _client(tmp_path)
        response = client.get(f"/api/dev/documents/{doc_id}/evidence")
        assert response.status_code == 200
        ts = response.json()["text_sources"][0]
        assert "raw_text_preview" in ts
        assert ts["raw_text_preview"] is not None
        assert len(ts["raw_text_preview"]) <= 300

    def test_raw_text_length_is_returned(self, tmp_path: Path):
        client, _, doc_id = _client(tmp_path)
        response = client.get(f"/api/dev/documents/{doc_id}/evidence")
        assert response.status_code == 200
        ts = response.json()["text_sources"][0]
        assert "raw_text_length" in ts
        assert isinstance(ts["raw_text_length"], int)
        assert ts["raw_text_length"] > 0

    def test_normalized_text_preview_and_length_are_returned(self, tmp_path: Path):
        client, _, doc_id = _client(tmp_path)
        response = client.get(f"/api/dev/documents/{doc_id}/evidence")
        assert response.status_code == 200
        ts = response.json()["text_sources"][0]
        assert "normalized_text_preview" in ts
        assert "normalized_text_length" in ts
        assert ts["normalized_text_length"] > 0
        assert len(ts["normalized_text_preview"]) <= 300

    def test_settings_hash_and_image_hash_are_visible(self, tmp_path: Path):
        client, _, doc_id = _client(tmp_path)
        response = client.get(f"/api/dev/documents/{doc_id}/evidence")
        assert response.status_code == 200
        ts = response.json()["text_sources"][0]
        assert ts["settings_hash"] == "sha256:aaaa"
        assert ts["image_hash"] == "sha256:bbbb"

    def test_summary_counts_match_list_lengths(self, tmp_path: Path):
        client, _, doc_id = _client(tmp_path)
        response = client.get(f"/api/dev/documents/{doc_id}/evidence")
        assert response.status_code == 200
        body = response.json()
        s = body["summary"]
        assert s["document_pages_count"] == len(body["document_pages"])
        assert s["text_sources_count"] == len(body["text_sources"])
        assert s["field_candidates_count"] == len(body["field_candidates"])


# ---------------------------------------------------------------------------
# Bundle evidence tests
# ---------------------------------------------------------------------------

class TestBundleEvidence:
    def test_groups_evidence_by_document(self, tmp_path: Path):
        client, bundle_id, doc_id = _client(tmp_path)
        response = client.get(f"/api/dev/bundles/{bundle_id}/evidence")
        assert response.status_code == 200
        body = response.json()
        assert "documents" in body
        assert len(body["documents"]) == 1
        doc_evidence = body["documents"][0]
        assert doc_evidence["document_id"] == doc_id
        assert "text_sources" in doc_evidence
        assert "document_pages" in doc_evidence
        assert "field_candidates" in doc_evidence

    def test_bundle_evidence_includes_document_metadata(self, tmp_path: Path):
        client, bundle_id, _ = _client(tmp_path)
        response = client.get(f"/api/dev/bundles/{bundle_id}/evidence")
        assert response.status_code == 200
        doc_ev = response.json()["documents"][0]
        assert doc_ev["document_type"] == "COMPANY_INVOICE"
        assert doc_ev["filename"] == "Invoice_001.pdf"


# ---------------------------------------------------------------------------
# Read-only mutation test
# ---------------------------------------------------------------------------

class TestReadOnly:
    def test_get_requests_do_not_mutate_evidence_row_counts(self, tmp_path: Path):
        db_path = tmp_path / "readonly.db"
        configure_database(f"sqlite:///{db_path}")
        init_db(drop_existing=True)
        replace_settings(Settings(
            app_env="development",
            enable_dev_tools=True,
            database_url=f"sqlite:///{db_path}",
        ))

        db = SessionLocal()
        now = datetime.now(timezone.utc)
        bundle = OrderBundleRecord(
            id=str(uuid4()), bundle_number="RO-001", created_at=now, updated_at=now,
        )
        db.add(bundle)
        db.flush()
        doc = DocumentRecord(
            id=str(uuid4()), order_bundle_id=bundle.id,
            document_type="COMPANY_DC", filename="dc.pdf", status="UPLOADED",
            created_at=now, updated_at=now,
        )
        db.add(doc)
        ts = TextSourceRecord(
            id=str(uuid4()), document_id=doc.id, page_number=1,
            source_type="digital_text", provider="digital_pdf",
            settings_hash="sha256:cc", image_hash="sha256:dd",
            success=True, raw_text="some text", created_at=now,
        )
        db.add(ts)
        doc_id = doc.id
        db.commit()
        db.close()

        client = TestClient(app)
        client.get(f"/api/dev/documents/{doc_id}/evidence")
        client.get(f"/api/dev/documents/{doc_id}/evidence")

        db2 = SessionLocal()
        rows_after = db2.scalars(
            select(TextSourceRecord).where(TextSourceRecord.document_id == doc_id)
        ).all()
        db2.close()
        assert len(rows_after) == 1
