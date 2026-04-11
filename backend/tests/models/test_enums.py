from app.models.purchase_order import BillingType, ChainStatus
from app.models.document import DocumentType

def test_billing_type_values():
    assert BillingType.FULL == "full"
    assert BillingType.STAGED == "staged"
    assert BillingType.RECURRING == "recurring"

def test_chain_status_values():
    assert ChainStatus.INCOMPLETE == "incomplete"
    assert ChainStatus.COMPLETE == "complete"
    assert ChainStatus.VERIFIED == "verified"
    assert ChainStatus.MISMATCH == "mismatch"

def test_new_document_types():
    assert DocumentType.INSTALLATION_REPORT == "INSTALLATION_REPORT"
    assert DocumentType.VENDOR_CREDIT_NOTE == "VENDOR_CREDIT_NOTE"
