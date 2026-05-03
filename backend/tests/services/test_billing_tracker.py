from app.services.billing_tracker import (
    check_full_billing,
    check_staged_billing,
    BillingStatus,
)


def test_full_billing_exact_match():
    result = check_full_billing(invoiced_total=503137.0, po_total=503137.0)
    assert result == BillingStatus.COMPLETE


def test_full_billing_within_tolerance():
    # 0.5% rounding difference — within 1% tolerance
    result = check_full_billing(invoiced_total=500500.0, po_total=503137.0)
    assert result == BillingStatus.COMPLETE


def test_full_billing_underpaid():
    result = check_full_billing(invoiced_total=200000.0, po_total=503137.0)
    assert result == BillingStatus.PARTIAL


def test_full_billing_no_invoices():
    result = check_full_billing(invoiced_total=0.0, po_total=503137.0)
    assert result == BillingStatus.PENDING


def test_staged_billing_first_stage_paid():
    milestones = [{"stage": 1, "percent": 40}, {"stage": 2, "percent": 60}]
    invoices = [{"billing_stage": 1, "amount": 201254.8}]
    result = check_staged_billing(po_total=503137.0, milestones=milestones, stage_invoices=invoices)
    assert result["stages"][0]["status"] == BillingStatus.PAID
    assert result["stages"][1]["status"] == BillingStatus.PENDING
    assert result["overall"] == BillingStatus.PARTIAL


def test_staged_billing_all_stages_paid():
    milestones = [{"stage": 1, "percent": 40}, {"stage": 2, "percent": 60}]
    invoices = [
        {"billing_stage": 1, "amount": 201254.8},
        {"billing_stage": 2, "amount": 301882.2},
    ]
    result = check_staged_billing(po_total=503137.0, milestones=milestones, stage_invoices=invoices)
    assert result["overall"] == BillingStatus.COMPLETE


def test_staged_billing_amount_mismatch():
    milestones = [{"stage": 1, "percent": 40}]
    # 10% paid, not 40% — way outside 5% tolerance
    invoices = [{"billing_stage": 1, "amount": 50313.7}]
    result = check_staged_billing(po_total=503137.0, milestones=milestones, stage_invoices=invoices)
    assert result["stages"][0]["status"] == BillingStatus.MISMATCH


def test_full_billing_none_po_total_returns_pending():
    result = check_full_billing(invoiced_total=100.0, po_total=None)
    assert result == BillingStatus.PENDING


def test_full_billing_zero_po_total_returns_pending():
    result = check_full_billing(invoiced_total=0.0, po_total=0)
    assert result == BillingStatus.PENDING


def test_staged_billing_zero_percent_milestone_no_crash():
    milestones = [{"stage": 1, "percent": 0}]
    invoices = [{"billing_stage": 1, "amount": 0}]
    result = check_staged_billing(po_total=100000.0, milestones=milestones, stage_invoices=invoices)
    assert result["stages"][0]["status"] == BillingStatus.PAID


def test_staged_billing_all_mismatch_returns_mismatch_overall():
    milestones = [{"stage": 1, "percent": 40}, {"stage": 2, "percent": 60}]
    # Both stages invoiced at ~10% — way outside 5% tolerance
    invoices = [
        {"billing_stage": 1, "amount": 5000.0},
        {"billing_stage": 2, "amount": 5000.0},
    ]
    result = check_staged_billing(po_total=503137.0, milestones=milestones, stage_invoices=invoices)
    assert result["overall"] == BillingStatus.MISMATCH
