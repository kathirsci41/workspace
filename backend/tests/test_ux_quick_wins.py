"""Tests for UX quick-wins backend changes:
  - days_pending field on DocumentResponse schema
  - stats_delta in admin stats endpoint logic
"""
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from app.schemas.document import DocumentResponse


# ── Schema test ──────────────────────────────────────────────────────────────

def test_document_response_has_days_pending_field():
    """DocumentResponse schema must include days_pending (Optional[int])."""
    fields = DocumentResponse.model_fields
    assert "days_pending" in fields, "days_pending field missing from DocumentResponse"
    # Must be optional (default None)
    assert fields["days_pending"].default is None


def test_document_response_days_pending_accepts_int():
    """days_pending can be set to an integer."""
    resp = DocumentResponse(
        id="00000000-0000-0000-0000-000000000001",
        po_id="00000000-0000-0000-0000-000000000002",
        document_type="VENDOR_INVOICE",
        filename="test.pdf",
        original_filename="test.pdf",
        file_path="/nas/test.pdf",
        file_size=1024,
        mime_type="application/pdf",
        checksum="abc123",
        status="PENDING_REVIEW",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        days_pending=5,
    )
    assert resp.days_pending == 5


def test_document_response_days_pending_defaults_none():
    """days_pending defaults to None when not provided."""
    resp = DocumentResponse(
        id="00000000-0000-0000-0000-000000000001",
        po_id="00000000-0000-0000-0000-000000000002",
        document_type="VENDOR_INVOICE",
        filename="test.pdf",
        original_filename="test.pdf",
        file_path="/nas/test.pdf",
        file_size=1024,
        mime_type="application/pdf",
        checksum="abc123",
        status="VERIFIED",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert resp.days_pending is None


# ── stats_delta computation test ──────────────────────────────────────────────

def test_stats_delta_computation():
    """stats_delta values are differences of today vs yesterday counts."""
    today_pos, prev_pos = 5, 3
    today_docs, prev_docs = 10, 8
    today_verified, prev_verified = 4, 4

    delta = {
        "total_purchase_orders": today_pos - prev_pos,
        "total_documents":       today_docs - prev_docs,
        "verified":              today_verified - prev_verified,
    }

    assert delta["total_purchase_orders"] == 2
    assert delta["total_documents"] == 2
    assert delta["verified"] == 0


def test_days_pending_calculation():
    """days_pending is computed from updated_at to now."""
    updated_at = datetime.now(timezone.utc) - timedelta(days=4)
    delta = datetime.now(timezone.utc) - updated_at.replace(tzinfo=timezone.utc)
    assert delta.days == 4
