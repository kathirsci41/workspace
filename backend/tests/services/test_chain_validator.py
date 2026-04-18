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


def test_staged_billing_partial_is_incomplete():
    """Stage 1 paid, stage 2 pending → chain is INCOMPLETE."""
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=500000.0,
        billing_type="staged",
        billing_milestones=[
            {"stage": 1, "percent": 40},
            {"stage": 2, "percent": 60},
        ],
        vpo_numbers=[],
        documents=[
            _doc(DocumentType.CUSTOMER_PO),
            _doc(DocumentType.COMPANY_DC, so_number="SO-001", cpo_ref="CPO-001"),
            {
                "document_type": DocumentType.COMPANY_INVOICE,
                "so_number": "SO-001",
                "vpo_numbers": [],
                "extraction_ok": True,
                "cpo_ref": "CPO-001",
                "billing_stage": 1,
                "amount": 200000.0,
            },
        ],
        requires_install_report=False,
    )
    assert result["chain_status"] == ChainStatus.INCOMPLETE
    assert result["billing"]["overall"] == "partial"


def test_staged_billing_all_stages_complete_is_complete():
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=500000.0,
        billing_type="staged",
        billing_milestones=[
            {"stage": 1, "percent": 40},
            {"stage": 2, "percent": 60},
        ],
        vpo_numbers=[],
        documents=[
            _doc(DocumentType.CUSTOMER_PO),
            _doc(DocumentType.COMPANY_DC, so_number="SO-001", cpo_ref="CPO-001"),
            {
                "document_type": DocumentType.COMPANY_INVOICE,
                "so_number": "SO-001",
                "vpo_numbers": [],
                "extraction_ok": True,
                "cpo_ref": "CPO-001",
                "billing_stage": 1,
                "amount": 200000.0,
            },
            {
                "document_type": DocumentType.COMPANY_INVOICE,
                "so_number": "SO-001",
                "vpo_numbers": [],
                "extraction_ok": True,
                "cpo_ref": "CPO-001",
                "billing_stage": 2,
                "amount": 300000.0,
            },
        ],
        requires_install_report=False,
    )
    assert result["chain_status"] == ChainStatus.COMPLETE
    assert result["billing"]["overall"] == "complete"


def test_reference_checks_include_extracted_and_expected_on_mismatch():
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
    so_checks = [rc for rc in result["reference_checks"] if rc["check"] == "so_consistency"]
    assert len(so_checks) > 0
    mismatch_check = next(rc for rc in so_checks if rc["result"] == "mismatch")
    assert mismatch_check["extracted"] == "SO-WRONG"
    assert mismatch_check["expected"] == "SO-001"


def test_reference_checks_include_skip_reason_when_extraction_failed():
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
            _doc(DocumentType.COMPANY_DC, so_number=None, cpo_ref=None, extraction_ok=False),
            _doc(DocumentType.COMPANY_INVOICE, so_number="SO-001", cpo_ref="CPO-001"),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    dc_checks = [
        rc for rc in result["reference_checks"]
        if rc["document_type"] == DocumentType.COMPANY_DC
    ]
    assert all(rc["result"] == "skip" for rc in dc_checks)
    assert all(rc["skip_reason"] == "extraction_failed" for rc in dc_checks)


def test_reference_checks_skip_reason_no_so_when_so_not_set():
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number=None,   # no SO set on PO
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc(DocumentType.CUSTOMER_PO),
            _doc(DocumentType.COMPANY_DC, so_number=None, cpo_ref="CPO-001"),
        ],
        requires_install_report=False,
    )
    so_checks = [
        rc for rc in result["reference_checks"]
        if rc["check"] == "so_consistency"
    ]
    assert all(rc["result"] == "skip" for rc in so_checks)
    assert all(rc["skip_reason"] == "no_so_number" for rc in so_checks)
