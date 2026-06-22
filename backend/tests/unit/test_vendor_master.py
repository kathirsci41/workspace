from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.database import Base
from app.services.document_normalizer import NormalizedDocument
from app.services.vendor_master_service import (
    apply_vendor_master_checks,
    check_vendor,
    upsert_vendor,
)


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_upsert_vendor_creates_and_updates_vendor_master():
    db = _session()

    record = upsert_vendor(db, "33AAGCS1406H1ZR", "Skylark Information Technologies Private Limited")
    updated = upsert_vendor(db, "33AAGCS1406H1ZR", "Skylark Information Technologies Pvt Ltd")

    assert record.gstin == "33AAGCS1406H1ZR"
    assert updated.vendor_name == "Skylark Information Technologies Pvt Ltd"
    assert updated.state_code == "33"


def test_upsert_vendor_rejects_invalid_gstin():
    db = _session()

    try:
        upsert_vendor(db, "bad", "Bad Vendor")
    except ValueError as exc:
        assert "Invalid GSTIN" in str(exc)
    else:
        raise AssertionError("Invalid GSTIN should be rejected")


def test_check_vendor_flags_name_divergence():
    db = _session()
    upsert_vendor(db, "33AAGCS1406H1ZR", "Skylark Information Technologies Private Limited")

    issues = check_vendor(db, "33AAGCS1406H1ZR", "Unrelated Trading Company")

    assert issues
    assert "Vendor name mismatch" in issues[0]


def test_apply_vendor_master_checks_augments_summary_without_verifier_db_dependency():
    db = _session()
    upsert_vendor(db, "33AAGCS1406H1ZR", "Skylark Information Technologies Private Limited")
    summary = {
        "bundle_status": "OK",
        "vendor_procurement_status": "PASS",
        "checks": [],
        "issues": [],
    }
    documents = [
        NormalizedDocument(
            document_id="bill-1",
            document_type="VENDOR_INVOICE",
            fields={"vendor_gstin": "33AAGCS1406H1ZR", "vendor_name": "Unrelated Trading Company"},
        )
    ]

    result = apply_vendor_master_checks(db, documents, summary)

    assert result["bundle_status"] == "REVIEW_REQUIRED"
    assert result["vendor_procurement_status"] == "REVIEW_REQUIRED"
    assert result["checks"][0]["check_id"] == "VENDOR_MASTER_NAME_MATCH"
    assert result["checks"][0]["result"] == "REVIEW_REQUIRED"
    assert result["issues"][0]["code"] == "VENDOR_MASTER_NAME_REVIEW_REQUIRED"
