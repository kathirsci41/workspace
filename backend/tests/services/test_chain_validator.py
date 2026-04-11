from app.services.chain_validator import compute_chain_status, SlotState
from app.models.purchase_order import OrderScenario, ChainStatus
from app.models.document import DocumentType


def _doc(doc_type, so_number=None, vpo_numbers=None, extraction_ok=True, cpo_ref=None):
    return {
        "document_type": doc_type,
        "so_number": so_number,
        "vpo_numbers": vpo_numbers or [],
        "extraction_ok": extraction_ok,
        "cpo_ref": cpo_ref,
    }


def test_stock_missing_dc_is_incomplete():
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc(DocumentType.CUSTOMER_PO),
            _doc(DocumentType.COMPANY_INVOICE, so_number="SO-001", cpo_ref="CPO-001"),
        ],
        requires_install_report=False,
    )
    assert result["chain_status"] == ChainStatus.INCOMPLETE
    assert DocumentType.COMPANY_DC in result["missing_slots"]


def test_stock_all_present_and_billing_complete_is_complete():
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc(DocumentType.CUSTOMER_PO),
            _doc(DocumentType.COMPANY_DC, so_number="SO-001", cpo_ref="CPO-001"),
            _doc(DocumentType.COMPANY_INVOICE, so_number="SO-001", cpo_ref="CPO-001"),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    assert result["chain_status"] == ChainStatus.COMPLETE


def test_so_mismatch_sets_mismatch_status():
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc(DocumentType.CUSTOMER_PO),
            _doc(DocumentType.COMPANY_DC, so_number="SO-WRONG", cpo_ref="CPO-001"),
            _doc(DocumentType.COMPANY_INVOICE, so_number="SO-001", cpo_ref="CPO-001"),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    assert result["chain_status"] == ChainStatus.MISMATCH


def test_procurement_missing_vendor_invoice_is_incomplete():
    result = compute_chain_status(
        scenario=OrderScenario.PROCUREMENT,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=["VPO-001"],
        documents=[
            _doc(DocumentType.CUSTOMER_PO),
            _doc(DocumentType.COMPANY_PO),
            _doc(DocumentType.COMPANY_DC, so_number="SO-001", cpo_ref="CPO-001"),
            _doc(DocumentType.COMPANY_INVOICE, so_number="SO-001", cpo_ref="CPO-001"),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    assert result["chain_status"] == ChainStatus.INCOMPLETE
    assert "VPO-001" in result["missing_vendor_invoices"]
