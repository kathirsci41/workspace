"""Tests for search index correctness fixes."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


class TestRejectClearsReferenceIndex:
    """Rejecting a document must remove its entries from reference_index."""

    @pytest.mark.asyncio
    async def test_reject_deletes_reference_index_rows(self):
        """After reject, reference_index rows for the document must be deleted."""
        from app.api.v1.extraction import reject_metadata
        from app.models import DocumentStatus, MetadataStatus

        doc_id = uuid4()
        po_id = uuid4()

        mock_meta = MagicMock()
        mock_meta.status = MetadataStatus.EXTRACTED
        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.po_id = po_id
        mock_doc.status = DocumentStatus.PENDING_REVIEW

        deleted_doc_ids = []

        async def mock_execute(stmt):
            stmt_str = str(stmt)
            if "reference_index" in stmt_str.lower() and "delete" in stmt_str.lower():
                deleted_doc_ids.append(doc_id)
            result = MagicMock()
            result.scalar_one_or_none.return_value = mock_meta if "document_metadata" in stmt_str.lower() else mock_doc
            return result

        db = MagicMock()
        db.execute = AsyncMock(side_effect=mock_execute)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        with patch("app.api.v1.extraction.update_chain_completeness", new_callable=AsyncMock):
            await reject_metadata(doc_id, db)

        assert len(deleted_doc_ids) > 0, "Expected DELETE on reference_index but none was executed"


class TestFuzzySearchFallback:
    """Similarity search returns results for near-matches."""

    def test_sort_key_fuzzy_match_ranks_last(self):
        """Fuzzy-only matches (no substring) should rank below contains matches."""
        from app.services.search_service import _search_sort_key

        exact    = {"ref_number": "INV-2024-001"}
        prefix   = {"ref_number": "INV-2024-001-A"}
        contains = {"ref_number": "REF-INV-2024-001-X"}
        fuzzy    = {"ref_number": "INV-2024-OO1"}  # two letter-O OCR error

        q = "inv-2024-001"
        assert _search_sort_key(exact, q)    == 0
        assert _search_sort_key(prefix, q)   == 1
        assert _search_sort_key(contains, q) == 2
        assert _search_sort_key(fuzzy, q)    == 3
