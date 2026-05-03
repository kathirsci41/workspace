"""Tests for duplicate primary_ref_no detection within a PO."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.document_service import check_duplicate_ref_in_po


def _make_db_mock(scalar_value):
    """Build an AsyncMock db where execute() returns a result with scalar_one_or_none()."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = scalar_value
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result
    return mock_db


@pytest.mark.asyncio
async def test_no_duplicate_returns_false():
    mock_db = _make_db_mock(scalar_value=None)
    result = await check_duplicate_ref_in_po(
        db=mock_db,
        po_id="po-uuid-001",
        document_type="VENDOR_INVOICE",
        primary_ref_no="C190224826",
        exclude_doc_id=None,
    )
    assert result is False


@pytest.mark.asyncio
async def test_duplicate_found_returns_true():
    existing = MagicMock()
    existing.id = "doc-uuid-existing"
    mock_db = _make_db_mock(scalar_value=existing)
    result = await check_duplicate_ref_in_po(
        db=mock_db,
        po_id="po-uuid-001",
        document_type="VENDOR_INVOICE",
        primary_ref_no="C190224826",
        exclude_doc_id=None,
    )
    assert result is True


@pytest.mark.asyncio
async def test_same_document_excluded_returns_false():
    """Editing a document's own metadata should not flag itself as duplicate.
    With exclude_doc_id applied to the query, the DB returns no other match."""
    mock_db = _make_db_mock(scalar_value=None)
    result = await check_duplicate_ref_in_po(
        db=mock_db,
        po_id="po-uuid-001",
        document_type="VENDOR_INVOICE",
        primary_ref_no="C190224826",
        exclude_doc_id="doc-uuid-self",
    )
    assert result is False
