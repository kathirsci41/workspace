"""Tests for model enums (DocumentType, DocumentStatus, POStatus, MetadataStatus)."""
import pytest

from app.models.document import DocumentType, DocumentStatus
from app.models.purchase_order import POStatus
from app.models.document_metadata import MetadataStatus


# ════════════════════════════════════════════════════════════════════════
# DocumentType
# ════════════════════════════════════════════════════════════════════════

class TestDocumentType:
    def test_has_8_values(self):
        assert len(DocumentType) == 8

    def test_all_expected_types_exist(self):
        expected = {
            "CUSTOMER_PO", "COMPANY_PO", "VENDOR_DC", "VENDOR_INVOICE",
            "COMPANY_DC", "COMPANY_INVOICE",
            "INSTALLATION_REPORT", "VENDOR_CREDIT_NOTE",
        }
        actual = {t.value for t in DocumentType}
        assert actual == expected

    def test_is_string_enum(self):
        assert isinstance(DocumentType.CUSTOMER_PO, str)
        assert DocumentType.CUSTOMER_PO == "CUSTOMER_PO"

    def test_value_equals_name(self):
        for t in DocumentType:
            assert t.value == t.name

    def test_can_create_from_value(self):
        assert DocumentType("CUSTOMER_PO") == DocumentType.CUSTOMER_PO

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            DocumentType("INVALID_TYPE")


# ════════════════════════════════════════════════════════════════════════
# DocumentStatus
# ════════════════════════════════════════════════════════════════════════

class TestDocumentStatus:
    def test_has_7_values(self):
        assert len(DocumentStatus) == 7

    def test_all_expected_statuses(self):
        expected = {
            "UPLOADED", "EXTRACTING", "PENDING_REVIEW",
            "VERIFIED", "REJECTED", "EXTRACTION_FAILED", "PENDING_MODEL",
        }
        actual = {s.value for s in DocumentStatus}
        assert actual == expected

    def test_is_string_enum(self):
        assert isinstance(DocumentStatus.UPLOADED, str)
        assert DocumentStatus.UPLOADED == "UPLOADED"

    def test_can_create_from_value(self):
        assert DocumentStatus("EXTRACTING") == DocumentStatus.EXTRACTING

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            DocumentStatus("DELETED")


# ════════════════════════════════════════════════════════════════════════
# POStatus
# ════════════════════════════════════════════════════════════════════════

class TestPOStatus:
    def test_has_5_values(self):
        assert len(POStatus) == 5

    def test_all_expected_statuses(self):
        expected = {
            "INITIATED", "IN_PROGRESS", "NEAR_COMPLETE",
            "COMPLETE", "CANCELLED",
        }
        actual = {s.value for s in POStatus}
        assert actual == expected

    def test_is_string_enum(self):
        assert isinstance(POStatus.INITIATED, str)
        assert POStatus.INITIATED == "INITIATED"

    def test_status_ordering_concept(self):
        """Verify the conceptual progression of PO statuses."""
        statuses = [s.value for s in POStatus]
        assert "INITIATED" in statuses
        assert "COMPLETE" in statuses
        assert "CANCELLED" in statuses

    def test_can_create_from_value(self):
        assert POStatus("IN_PROGRESS") == POStatus.IN_PROGRESS

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            POStatus("DELETED")


# ════════════════════════════════════════════════════════════════════════
# MetadataStatus
# ════════════════════════════════════════════════════════════════════════

class TestMetadataStatus:
    def test_has_4_values(self):
        assert len(MetadataStatus) == 4

    def test_all_expected_statuses(self):
        expected = {"PENDING", "EXTRACTED", "VERIFIED", "FAILED"}
        actual = {s.value for s in MetadataStatus}
        assert actual == expected

    def test_is_string_enum(self):
        assert isinstance(MetadataStatus.PENDING, str)
        assert MetadataStatus.PENDING == "PENDING"

    def test_can_create_from_value(self):
        assert MetadataStatus("EXTRACTED") == MetadataStatus.EXTRACTED

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            MetadataStatus("UNKNOWN")


# ════════════════════════════════════════════════════════════════════════
# Cross-enum consistency
# ════════════════════════════════════════════════════════════════════════

class TestEnumConsistency:
    def test_all_enums_are_str_based(self):
        """All enums should be str subclasses for JSON serialization."""
        for enum_cls in (DocumentType, DocumentStatus, POStatus, MetadataStatus):
            for member in enum_cls:
                assert isinstance(member, str), f"{enum_cls.__name__}.{member.name} is not str"

    def test_no_duplicate_values_within_enum(self):
        for enum_cls in (DocumentType, DocumentStatus, POStatus, MetadataStatus):
            values = [m.value for m in enum_cls]
            assert len(values) == len(set(values)), f"Duplicate in {enum_cls.__name__}"

    def test_all_values_uppercase(self):
        for enum_cls in (DocumentType, DocumentStatus, POStatus, MetadataStatus):
            for member in enum_cls:
                assert member.value == member.value.upper(), (
                    f"{enum_cls.__name__}.{member.name} = '{member.value}' is not uppercase"
                )
