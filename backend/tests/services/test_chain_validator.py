from app.services.chain_validator import compute_chain_status
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


def _doc_with_address(doc_type, delivery_address=None, so_number=None, cpo_ref=None, extraction_ok=True):
    return {
        "document_type": doc_type,
        "so_number": so_number,
        "vpo_numbers": [],
        "extraction_ok": extraction_ok,
        "cpo_ref": cpo_ref,
        "delivery_address": delivery_address,
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
    """VPO registered but no VENDOR_INVOICE document uploaded → INCOMPLETE (not MISMATCH)."""
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
    mismatch_check = next((rc for rc in so_checks if rc["result"] == "mismatch"), None)
    assert mismatch_check is not None, "Expected a mismatch check entry but none found"
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


def test_reference_checks_cpo_skip_reason_no_extracted_value():
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
            _doc(DocumentType.COMPANY_DC, so_number="SO-001", cpo_ref=None, extraction_ok=True),
            _doc(DocumentType.COMPANY_INVOICE, so_number="SO-001", cpo_ref="CPO-001"),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    cpo_checks = [
        rc for rc in result["reference_checks"]
        if rc["check"] == "cpo_reference" and rc["document_type"] == DocumentType.COMPANY_DC
    ]
    assert len(cpo_checks) == 1
    assert cpo_checks[0]["result"] == "skip"
    assert cpo_checks[0]["skip_reason"] == "no_extracted_value"


def test_address_mismatch_sets_mismatch_status():
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc_with_address(DocumentType.CUSTOMER_PO, delivery_address="123 Main St, Chennai, Tamil Nadu 600001"),
            _doc_with_address(DocumentType.COMPANY_DC,  delivery_address="456 Other St, Mumbai, Maharashtra 400001",
                              so_number="SO-001", cpo_ref="CPO-001"),
            _doc_with_address(DocumentType.COMPANY_INVOICE, so_number="SO-001", cpo_ref="CPO-001"),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    addr_checks = [rc for rc in result["reference_checks"] if rc["check"] == "delivery_address"]
    assert len(addr_checks) == 1
    assert addr_checks[0]["result"] == "mismatch"
    assert result["chain_status"] == ChainStatus.MISMATCH


def test_address_match_does_not_affect_chain_status():
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc_with_address(DocumentType.CUSTOMER_PO, delivery_address="123 Main St, Chennai, Tamil Nadu 600001"),
            _doc_with_address(DocumentType.COMPANY_DC,  delivery_address="123 Main St, Chennai, Tamil Nadu 600001",
                              so_number="SO-001", cpo_ref="CPO-001"),
            _doc_with_address(DocumentType.COMPANY_INVOICE, so_number="SO-001", cpo_ref="CPO-001"),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    addr_checks = [rc for rc in result["reference_checks"] if rc["check"] == "delivery_address"]
    assert len(addr_checks) == 1
    assert addr_checks[0]["result"] == "pass"
    assert result["chain_status"] == ChainStatus.COMPLETE


def test_address_skip_when_addresses_missing():
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
        ],
        requires_install_report=False,
    )
    addr_checks = [rc for rc in result["reference_checks"] if rc["check"] == "delivery_address"]
    assert len(addr_checks) == 1
    assert addr_checks[0]["result"] == "skip"


def test_address_partial_match_treated_as_pass():
    """City+state match without PIN code → PARTIAL → should be treated as PASS."""
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc_with_address(DocumentType.CUSTOMER_PO, delivery_address="123 Main St, Chennai, Tamil Nadu"),
            _doc_with_address(DocumentType.COMPANY_DC,  delivery_address="456 Other Rd, Chennai, Tamil Nadu",
                              so_number="SO-001", cpo_ref="CPO-001"),
            _doc_with_address(DocumentType.COMPANY_INVOICE, so_number="SO-001", cpo_ref="CPO-001"),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    addr_checks = [rc for rc in result["reference_checks"] if rc["check"] == "delivery_address"]
    assert len(addr_checks) == 1
    assert addr_checks[0]["result"] == "pass"
    assert result["chain_status"] == ChainStatus.COMPLETE


def test_vpo_and_logic_both_vpos_must_appear():
    """VPO-002 registered but missing from invoice → MISMATCH (not PASS)."""
    result = compute_chain_status(
        scenario=OrderScenario.PROCUREMENT,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=["VPO-001", "VPO-002"],
        documents=[
            _doc(DocumentType.CUSTOMER_PO),
            _doc(DocumentType.COMPANY_PO),
            _doc(DocumentType.COMPANY_DC, so_number="SO-001", cpo_ref="CPO-001"),
            _doc(DocumentType.COMPANY_INVOICE, so_number="SO-001", cpo_ref="CPO-001"),
            {
                "document_type": DocumentType.VENDOR_INVOICE,
                "so_number": "SO-001",
                "vpo_numbers": ["VPO-001"],
                "extraction_ok": True,
                "cpo_ref": None,
                "delivery_address": None,
            },
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    vpo_checks = [rc for rc in result["reference_checks"] if rc["check"] == "vpo_reference"]
    assert len(vpo_checks) == 1
    assert vpo_checks[0]["result"] == "mismatch"
    assert result["chain_status"] == ChainStatus.MISMATCH


# ── Module 3 integration tests ────────────────────────────────────────────────

from datetime import date as _date


def _doc_full(doc_type, **kwargs):
    """Extended doc dict with all Module 3 fields."""
    return {
        "document_type": doc_type,
        "so_number": kwargs.get("so_number"),
        "vpo_numbers": kwargs.get("vpo_numbers", []),
        "extraction_ok": kwargs.get("extraction_ok", True),
        "cpo_ref": kwargs.get("cpo_ref"),
        "billing_stage": kwargs.get("billing_stage"),
        "amount": kwargs.get("amount", 0),
        "delivery_address": kwargs.get("delivery_address"),
        "customer_gstin": kwargs.get("customer_gstin"),
        "vendor_gstin": kwargs.get("vendor_gstin"),
        "customer_name": kwargs.get("customer_name"),
        "vendor_name": kwargs.get("vendor_name"),
        "serial_numbers": kwargs.get("serial_numbers", []),
        "dc_number": kwargs.get("dc_number"),
        "dc_reference": kwargs.get("dc_reference"),
        "po_reference": kwargs.get("po_reference"),
        "doc_date": kwargs.get("doc_date"),
        "order_items": kwargs.get("order_items", []),
    }


def test_ci_amount_mismatch_sets_chain_mismatch():
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="PWFA251127016",
        so_number="SO-001",
        po_total=503137.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc_full(DocumentType.CUSTOMER_PO, amount=503137.0),
            _doc_full(DocumentType.COMPANY_DC, so_number="SO-001", cpo_ref="PWFA251127016"),
            _doc_full(DocumentType.COMPANY_INVOICE,
                      so_number="SO-001", cpo_ref="PWFA251127016",
                      amount=490000.0),  # 2.6% diff → MISMATCH
        ],
        requires_install_report=False,
        invoiced_total=490000.0,
    )
    ci_checks = [rc for rc in result["reference_checks"] if rc["check"] == "ci_vs_cpo_total"]
    assert len(ci_checks) == 1
    assert ci_checks[0]["result"] == "mismatch"
    assert result["chain_status"] == ChainStatus.MISMATCH


def test_gstin_mismatch_sets_chain_mismatch():
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc_full(DocumentType.CUSTOMER_PO, customer_gstin="33AAICS1881D1ZJ"),
            _doc_full(DocumentType.COMPANY_DC,
                      so_number="SO-001", cpo_ref="CPO-001",
                      customer_gstin="29AAICS1881D1ZK"),
            _doc_full(DocumentType.COMPANY_INVOICE,
                      so_number="SO-001", cpo_ref="CPO-001",
                      customer_gstin="33AAICS1881D1ZJ",
                      amount=100000.0),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    gstin_checks = [rc for rc in result["reference_checks"] if rc["check"] == "customer_gstin_consistency"]
    assert gstin_checks[0]["result"] == "mismatch"
    assert result["chain_status"] == ChainStatus.MISMATCH


def test_serial_chain_mismatch_sets_chain_mismatch():
    result = compute_chain_status(
        scenario=OrderScenario.PROCUREMENT,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=["1PTR2526000400"],
        documents=[
            _doc_full(DocumentType.CUSTOMER_PO),
            _doc_full(DocumentType.COMPANY_PO),
            _doc_full(DocumentType.VENDOR_INVOICE,
                      vpo_numbers=["1PTR2526000400"],
                      serial_numbers=["NDKDL1U", "NDLEFAU"],
                      amount=80000.0),
            _doc_full(DocumentType.COMPANY_DC,
                      so_number="SO-001", cpo_ref="CPO-001",
                      serial_numbers=["NDKDL1U"]),  # NDLEFAU not shipped
            _doc_full(DocumentType.COMPANY_INVOICE,
                      so_number="SO-001", cpo_ref="CPO-001",
                      amount=100000.0),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    serial_checks = [rc for rc in result["reference_checks"] if rc["check"] == "serial_chain"]
    assert serial_checks[0]["result"] == "mismatch"
    assert result["chain_status"] == ChainStatus.MISMATCH


def test_warning_checks_do_not_set_chain_mismatch():
    """Vendor GSTIN mismatch = WARNING, should not flip chain_status to MISMATCH."""
    result = compute_chain_status(
        scenario=OrderScenario.PROCUREMENT,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=["1PTR2526000400"],
        documents=[
            _doc_full(DocumentType.CUSTOMER_PO),
            _doc_full(DocumentType.COMPANY_PO, vendor_gstin="33AAACS5403H1Z5"),
            _doc_full(DocumentType.VENDOR_INVOICE,
                      vpo_numbers=["1PTR2526000400"],
                      vendor_gstin="29AAACS5403H1ZK",  # Redington Karnataka GSTIN
                      amount=80000.0),
            _doc_full(DocumentType.COMPANY_DC,
                      so_number="SO-001", cpo_ref="CPO-001"),
            _doc_full(DocumentType.COMPANY_INVOICE,
                      so_number="SO-001", cpo_ref="CPO-001",
                      amount=100000.0),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    vendor_gstin_checks = [rc for rc in result["reference_checks"] if rc["check"] == "vendor_gstin_consistency"]
    assert vendor_gstin_checks[0]["result"] == "warning"
    assert result["chain_status"] != ChainStatus.MISMATCH


def test_date_sequence_violation_produces_warning_check():
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc_full(DocumentType.CUSTOMER_PO, doc_date=_date(2026, 3, 1)),
            _doc_full(DocumentType.COMPANY_DC,
                      so_number="SO-001", cpo_ref="CPO-001",
                      doc_date=_date(2026, 1, 1)),  # DC before CPO — impossible
            _doc_full(DocumentType.COMPANY_INVOICE,
                      so_number="SO-001", cpo_ref="CPO-001",
                      amount=100000.0),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    date_checks = [rc for rc in result["reference_checks"] if rc["check"] == "date_sequence"]
    assert len(date_checks) >= 1
    assert all(rc["result"] == "warning" for rc in date_checks)


def test_missing_item_in_cdc_produces_warning():
    """CPO has two items; CDC only delivers one → WARNING on cpo_vs_cdc check."""
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=200000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc_full(DocumentType.CUSTOMER_PO, order_items=[
                {"part_no": "FG81F", "description": "FortiGate 81F", "qty": "1"},
                {"part_no": "FS108E", "description": "FortiSwitch 108E", "qty": "1"},
            ]),
            _doc_full(DocumentType.COMPANY_DC,
                      so_number="SO-001", cpo_ref="CPO-001",
                      order_items=[
                          {"part_no": "FG81F", "description": "FortiGate 81F", "qty": "1"},
                          # FS108E missing
                      ]),
            _doc_full(DocumentType.COMPANY_INVOICE,
                      so_number="SO-001", cpo_ref="CPO-001",
                      amount=200000.0),
        ],
        requires_install_report=False,
        invoiced_total=200000.0,
    )
    item_checks = [rc for rc in result["reference_checks"] if rc["check"] == "cpo_vs_cdc_items"]
    assert len(item_checks) == 1
    assert item_checks[0]["result"] == "warning"
    # WARNING must not flip chain_status to MISMATCH
    assert result["chain_status"] != ChainStatus.MISMATCH


def test_all_items_delivered_produces_pass():
    """All CPO items present in CDC → PASS on cpo_vs_cdc check."""
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=200000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc_full(DocumentType.CUSTOMER_PO, order_items=[
                {"part_no": "FG81F", "qty": "2"},
            ]),
            _doc_full(DocumentType.COMPANY_DC,
                      so_number="SO-001", cpo_ref="CPO-001",
                      order_items=[
                          {"part_no": "FG81F", "qty": "2"},
                      ]),
            _doc_full(DocumentType.COMPANY_INVOICE,
                      so_number="SO-001", cpo_ref="CPO-001",
                      amount=200000.0),
        ],
        requires_install_report=False,
        invoiced_total=200000.0,
    )
    item_checks = [rc for rc in result["reference_checks"] if rc["check"] == "cpo_vs_cdc_items"]
    assert item_checks[0]["result"] == "pass"


def test_no_part_nos_on_cpo_skips_item_check():
    """Customer PO items have only descriptions (no part_no) → SKIP."""
    result = compute_chain_status(
        scenario=OrderScenario.STOCK,
        po_number="CPO-001",
        so_number="SO-001",
        po_total=100000.0,
        billing_type="full",
        billing_milestones=[],
        vpo_numbers=[],
        documents=[
            _doc_full(DocumentType.CUSTOMER_PO, order_items=[
                {"description": "Firewall unit", "qty": "1"},  # no part_no
            ]),
            _doc_full(DocumentType.COMPANY_DC,
                      so_number="SO-001", cpo_ref="CPO-001"),
            _doc_full(DocumentType.COMPANY_INVOICE,
                      so_number="SO-001", cpo_ref="CPO-001",
                      amount=100000.0),
        ],
        requires_install_report=False,
        invoiced_total=100000.0,
    )
    item_checks = [rc for rc in result["reference_checks"] if rc["check"] == "cpo_vs_cdc_items"]
    assert item_checks[0]["result"] == "skip"
    assert result["chain_status"] != ChainStatus.MISMATCH
