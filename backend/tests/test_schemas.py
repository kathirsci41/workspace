"""Tests for Pydantic schemas (validation, serialisation)."""
import pytest
from uuid import uuid4, UUID
from datetime import date, datetime
from pydantic import ValidationError

from app.schemas.customer import CustomerCreate, CustomerUpdate, CustomerResponse, CustomerListResponse
from app.schemas.purchase_order import (
    POCreate, POUpdate, POResponse, POListResponse,
    ChainSlot, ChainStatusResponse,
)
from app.schemas.document import DocumentUploadResponse, DocumentResponse, DocumentListResponse
from app.schemas.extraction import (
    ExtractionResponse, VerifyRequest, SearchResult, SearchResponse,
)


# ════════════════════════════════════════════════════════════════════════
# CustomerCreate
# ════════════════════════════════════════════════════════════════════════

class TestCustomerCreate:
    def test_valid_customer_id(self):
        c = CustomerCreate(customer_id="SKY-AB123", name="Acme")
        assert c.customer_id == "SKY-AB123"

    def test_two_letter_prefix(self):
        c = CustomerCreate(customer_id="AB-123", name="Test")
        assert c.customer_id == "AB-123"

    def test_five_letter_prefix(self):
        c = CustomerCreate(customer_id="ABCDE-X1", name="Test")
        assert c.customer_id == "ABCDE-X1"

    def test_rejects_lowercase(self):
        with pytest.raises(ValidationError):
            CustomerCreate(customer_id="sky-ab123", name="Bad")

    def test_rejects_no_hyphen(self):
        with pytest.raises(ValidationError):
            CustomerCreate(customer_id="SKYAB123", name="Bad")

    def test_rejects_one_letter_prefix(self):
        with pytest.raises(ValidationError):
            CustomerCreate(customer_id="A-123", name="Bad")

    def test_rejects_six_letter_prefix(self):
        with pytest.raises(ValidationError):
            CustomerCreate(customer_id="ABCDEF-123", name="Bad")

    def test_rejects_empty_suffix(self):
        with pytest.raises(ValidationError):
            CustomerCreate(customer_id="SKY-", name="Bad")

    def test_min_length_3(self):
        with pytest.raises(ValidationError):
            CustomerCreate(customer_id="AB", name="Bad")

    def test_max_length_50(self):
        long_id = "ABCDE-" + "A" * 50
        with pytest.raises(ValidationError):
            CustomerCreate(customer_id=long_id, name="Bad")

    def test_name_required(self):
        with pytest.raises(ValidationError):
            CustomerCreate(customer_id="SKY-AB123")  # type: ignore[call-arg]

    def test_name_min_length(self):
        with pytest.raises(ValidationError):
            CustomerCreate(customer_id="SKY-AB123", name="")

    def test_optional_fields_default_none(self):
        c = CustomerCreate(customer_id="SKY-AB123", name="Test")
        assert c.contact_email is None
        assert c.contact_phone is None
        assert c.address is None
        assert c.gst_number is None
        assert c.notes is None

    def test_all_optional_fields_set(self):
        c = CustomerCreate(
            customer_id="SKY-AB123",
            name="Test",
            contact_email="a@b.com",
            contact_phone="+1234",
            address="123 Street",
            gst_number="GST123",
            notes="Some notes",
        )
        assert c.contact_email == "a@b.com"
        assert c.notes == "Some notes"


# ════════════════════════════════════════════════════════════════════════
# CustomerUpdate
# ════════════════════════════════════════════════════════════════════════

class TestCustomerUpdate:
    def test_all_fields_optional(self):
        u = CustomerUpdate()
        assert u.name is None

    def test_partial_update(self):
        u = CustomerUpdate(name="New Name")
        assert u.name == "New Name"
        assert u.contact_email is None


# ════════════════════════════════════════════════════════════════════════
# CustomerResponse
# ════════════════════════════════════════════════════════════════════════

class TestCustomerResponse:
    def test_from_dict(self):
        data = {
            "id": uuid4(),
            "customer_id": "SKY-AB123",
            "name": "Acme",
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "po_count": 5,
        }
        r = CustomerResponse(**data)
        assert r.po_count == 5

    def test_po_count_defaults_zero(self):
        data = {
            "id": uuid4(),
            "customer_id": "SKY-AB123",
            "name": "Acme",
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        r = CustomerResponse(**data)
        assert r.po_count == 0


# ════════════════════════════════════════════════════════════════════════
# CustomerListResponse
# ════════════════════════════════════════════════════════════════════════

class TestCustomerListResponse:
    def test_empty_list(self):
        r = CustomerListResponse(items=[], total=0, page=1, per_page=20)
        assert r.total == 0


# ════════════════════════════════════════════════════════════════════════
# POCreate
# ════════════════════════════════════════════════════════════════════════

class TestPOCreate:
    def test_valid_po(self):
        po = POCreate(customer_id=uuid4(), po_number="PO-123")
        assert po.po_number == "PO-123"

    def test_po_number_required(self):
        with pytest.raises(ValidationError):
            POCreate(customer_id=uuid4())  # type: ignore[call-arg]

    def test_po_number_empty_rejected(self):
        with pytest.raises(ValidationError):
            POCreate(customer_id=uuid4(), po_number="")

    def test_po_number_max_100(self):
        with pytest.raises(ValidationError):
            POCreate(customer_id=uuid4(), po_number="X" * 101)

    def test_customer_id_must_be_uuid(self):
        with pytest.raises(ValidationError):
            POCreate(customer_id="not-a-uuid", po_number="PO-1")  # type: ignore[arg-type]

    def test_optional_fields(self):
        po = POCreate(customer_id=uuid4(), po_number="PO-1")
        assert po.po_date is None
        assert po.total_amount is None
        assert po.notes is None

    def test_with_all_fields(self):
        po = POCreate(
            customer_id=uuid4(),
            po_number="PO-999",
            po_date=date(2025, 1, 15),
            total_amount=12345.67,
            notes="Important",
        )
        assert po.po_date == date(2025, 1, 15)
        assert po.total_amount == 12345.67


# ════════════════════════════════════════════════════════════════════════
# POUpdate
# ════════════════════════════════════════════════════════════════════════

class TestPOUpdate:
    def test_all_optional(self):
        u = POUpdate()
        assert u.po_number is None
        assert u.status is None

    def test_partial(self):
        u = POUpdate(status="COMPLETE")
        assert u.status == "COMPLETE"


# ════════════════════════════════════════════════════════════════════════
# ChainSlot
# ════════════════════════════════════════════════════════════════════════

class TestChainSlot:
    def test_minimal(self):
        s = ChainSlot(status="EMPTY")
        assert s.document_id is None
        assert s.confidence is None

    def test_full(self):
        s = ChainSlot(
            status="COMPLETED",
            document_id=uuid4(),
            ref_no="REF-001",
            uploaded_at=datetime.now(),
            confidence=95.5,
        )
        assert s.confidence == 95.5


# ════════════════════════════════════════════════════════════════════════
# ChainStatusResponse
# ════════════════════════════════════════════════════════════════════════

class TestChainStatusResponse:
    def test_structure(self):
        r = ChainStatusResponse(
            po_id=uuid4(),
            po_number="PO-001",
            completeness_pct=66,
            chain={"CUSTOMER_PO": [ChainSlot(status="COMPLETED")]},
        )
        assert r.completeness_pct == 66
        assert "CUSTOMER_PO" in r.chain


# ════════════════════════════════════════════════════════════════════════
# DocumentUploadResponse
# ════════════════════════════════════════════════════════════════════════

class TestDocumentUploadResponse:
    def test_required_fields(self):
        r = DocumentUploadResponse(
            id=uuid4(),
            po_id=uuid4(),
            document_type="CUSTOMER_PO",
            filename="abc_doc.pdf",
            original_filename="doc.pdf",
            file_size=1024,
            checksum="a" * 64,
            status="UPLOADED",
            created_at=datetime.now(),
        )
        assert r.file_size == 1024
        assert r.page_count is None


# ════════════════════════════════════════════════════════════════════════
# ExtractionResponse
# ════════════════════════════════════════════════════════════════════════

class TestExtractionResponse:
    def test_minimal(self):
        r = ExtractionResponse(
            id=uuid4(),
            document_id=uuid4(),
            document_type="VENDOR_DC",
            status="EXTRACTED",
        )
        assert r.extracted_data is None
        assert r.extraction_attempts == 0

    def test_full(self):
        r = ExtractionResponse(
            id=uuid4(),
            document_id=uuid4(),
            document_type="VENDOR_DC",
            status="EXTRACTED",
            extracted_data={"dc_number": "DC-001"},
            confidence_score=88.5,
            extraction_attempts=2,
            model_version="glm-ocr",
            processing_time_ms=3000,
        )
        assert r.confidence_score == 88.5


# ════════════════════════════════════════════════════════════════════════
# VerifyRequest
# ════════════════════════════════════════════════════════════════════════

class TestVerifyRequest:
    def test_requires_dict(self):
        v = VerifyRequest(extracted_data={"key": "value"})
        assert v.extracted_data == {"key": "value"}

    def test_rejects_no_data(self):
        with pytest.raises(ValidationError):
            VerifyRequest()  # type: ignore[call-arg]


# ════════════════════════════════════════════════════════════════════════
# SearchResult / SearchResponse
# ════════════════════════════════════════════════════════════════════════

class TestSearchResult:
    def test_minimal(self):
        r = SearchResult(
            result_type="customer",
            id=uuid4(),
            ref_number="SKY-AB123",
            display_name="Acme Corp",
        )
        assert r.document_type is None

    def test_full(self):
        r = SearchResult(
            result_type="document",
            id=uuid4(),
            ref_number="INV-001",
            display_name="Invoice #001",
            document_type="VENDOR_INVOICE",
            po_number="PO-123",
            po_id=str(uuid4()),
            customer_name="Acme",
            confidence=92.0,
        )
        assert r.confidence == 92.0


class TestSearchResponse:
    def test_structure(self):
        r = SearchResponse(results=[], total=0, query="test")
        assert r.query == "test"
        assert r.total == 0
