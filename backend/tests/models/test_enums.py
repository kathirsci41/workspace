from app.models.purchase_order import BillingType, ChainStatus
from app.models.document import DocumentType


def test_billing_type_values():
    assert {e.value for e in BillingType} == {"full", "staged", "recurring"}


def test_chain_status_values():
    assert {e.value for e in ChainStatus} == {"incomplete", "complete", "verified", "mismatch"}


def test_new_document_types():
    values = {e.value for e in DocumentType}
    assert "INSTALLATION_REPORT" in values
    assert "VENDOR_CREDIT_NOTE" in values


def test_billing_type_server_defaults_are_valid():
    valid_values = {e.value for e in BillingType}
    assert "full" in valid_values  # matches server_default="full"


def test_chain_status_server_default_is_valid():
    valid_values = {e.value for e in ChainStatus}
    assert "incomplete" in valid_values  # matches server_default="incomplete"
