"""Backend contract fix tests: live statuses and issue document targeting."""

from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.routes import bundles as bundle_routes
from app.schemas.bundle import BundleRead
from app.services.document_normalizer import NormalizedDocument
from app.services.order_bundle_verifier import verify_order_bundle


def _doc(did, dtype, **fields):
    return NormalizedDocument(document_id=did, document_type=dtype, fields=fields)


def test_bundle_read_computed_status_fields_are_optional():
    bundle = BundleRead(
        id="bundle-1",
        bundle_number="OA-001",
        customer_name=None,
        customer_po_no=None,
        so_no=None,
        status="REVIEW_REQUIRED",
        customer_delivery_status="REVIEW_REQUIRED",
        vendor_procurement_status="REVIEW_REQUIRED",
        created_at=datetime(2026, 5, 25, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 25, tzinfo=timezone.utc),
    )

    assert bundle.computed_status is None
    assert bundle.computed_customer_status is None
    assert bundle.computed_vendor_status is None
    assert bundle.status_computed_at is None


def test_bundle_list_attaches_authoritative_computed_statuses(monkeypatch):
    updated_at = datetime(2026, 5, 25, tzinfo=timezone.utc)
    bundle = SimpleNamespace(
        id="bundle-1",
        bundle_number="OA-001",
        customer_name="ACME",
        customer_po_no=None,
        so_no=None,
        status="OK",
        customer_delivery_status="PASS",
        vendor_procurement_status="PASS",
        dismissed_check_ids="[]",
        created_at=updated_at,
        updated_at=updated_at,
    )

    class FakeBundleRepository:
        def list(self):
            return [bundle]

    monkeypatch.setattr(bundle_routes, "BundleRepository", lambda db: FakeBundleRepository())
    monkeypatch.setattr(
        bundle_routes,
        "build_verification_summary",
        lambda db, bundle_id: {
            "bundle_status": "MISSING_DOCUMENTS",
            "customer_delivery_status": "MISSING_DOCUMENTS",
            "vendor_procurement_status": "MISSING_DOCUMENTS",
        },
    )

    result = bundle_routes.list_bundles(object())

    assert result[0]["status"] == "OK"
    assert result[0]["computed_status"] == "MISSING_DOCUMENTS"
    assert result[0]["computed_customer_status"] == "MISSING_DOCUMENTS"
    assert result[0]["computed_vendor_status"] == "MISSING_DOCUMENTS"
    assert result[0]["status_computed_at"] == updated_at


def test_customer_delivery_missing_has_document_type():
    summary = verify_order_bundle([])
    issues = {issue["code"]: issue for issue in summary["issues"]}
    issue = issues["CUSTOMER_DELIVERY_DOCUMENTS_MISSING"]

    assert issue["document_type"] == "COMPANY_INVOICE"
    assert issue["document_id"] is None


def test_customer_delivery_missing_names_delivery_challan_when_invoice_exists():
    summary = verify_order_bundle(
        [
            _doc(
                "inv",
                "CUSTOMER_INVOICE",
                invoice_no="INV001",
                customer_order_no="PO-001",
                so_no="SO-001",
                customer_name="ACME",
                taxable_amount=100000,
            )
        ]
    )
    issue = next(issue for issue in summary["issues"] if issue["code"] == "CUSTOMER_DELIVERY_DOCUMENTS_MISSING")

    assert issue["message"] == "Delivery challan is missing."
    assert issue["document_type"] == "DELIVERY_CHALLAN"


def test_vendor_po_missing_has_document_type():
    summary = verify_order_bundle(
        [
            _doc(
                "inv",
                "CUSTOMER_INVOICE",
                invoice_no="INV001",
                customer_order_no="PO-001",
                so_no="SO-001",
                customer_name="ACME",
                taxable_amount=100000,
            ),
            _doc(
                "dc",
                "DELIVERY_CHALLAN",
                dc_no="DC001",
                customer_order_no="PO-001",
                so_no="SO-001",
                customer_name="ACME",
                estimated_amount=100000,
            ),
        ]
    )
    issues = {issue["code"]: issue for issue in summary["issues"]}

    assert issues["VENDOR_PO_MISSING"]["document_type"] == "COMPANY_PO"
    assert issues["VENDOR_PO_MISSING"]["document_id"] is None


def test_vendor_invoice_missing_has_document_type():
    summary = verify_order_bundle(
        [_doc("vpo", "VENDOR_PO", vendor_po_no="1PTR001", vendor_name="ACME VENDOR", net_amount=50000)]
    )
    issues = {issue["code"]: issue for issue in summary["issues"]}

    assert issues["VENDOR_INVOICE_MISSING"]["document_type"] == "VENDOR_INVOICE"
    assert issues["VENDOR_INVOICE_MISSING"]["document_id"] is None


def test_vendor_bill_reference_missing_has_document_id():
    summary = verify_order_bundle(
        [
            _doc("vpo", "VENDOR_PO", vendor_po_no="1PTR001", vendor_name="ACME VENDOR", net_amount=50000),
            _doc("vbill", "VENDOR_INVOICE", vendor_invoice_no="INV999", invoice_total=50000),
        ]
    )
    issue = next(issue for issue in summary["issues"] if issue["code"] == "VENDOR_BILL_REFERENCE_MISSING")

    assert issue["document_type"] == "VENDOR_INVOICE"
    assert issue["document_id"] == "vbill"


def test_vendor_bill_reference_unmatched_has_document_id():
    summary = verify_order_bundle(
        [
            _doc("vpo", "VENDOR_PO", vendor_po_no="1PTR001", vendor_name="ACME VENDOR", net_amount=50000),
            _doc(
                "vbill",
                "VENDOR_INVOICE",
                vendor_invoice_no="INV999",
                invoice_total=50000,
                po_reference="WRONG_REF",
            ),
        ]
    )
    issue = next(issue for issue in summary["issues"] if issue["code"] == "VENDOR_BILL_REFERENCE_UNMATCHED")

    assert issue["document_type"] == "VENDOR_INVOICE"
    assert issue["document_id"] == "vbill"


def test_customer_po_missing_issue_has_document_type():
    summary = verify_order_bundle(
        [
            _doc(
                "inv",
                "CUSTOMER_INVOICE",
                invoice_no="INV001",
                customer_order_no="PO-001",
                so_no="SO-001",
                customer_name="ACME",
                taxable_amount=100000,
            ),
            _doc(
                "dc",
                "DELIVERY_CHALLAN",
                dc_no="DC001",
                customer_order_no="PO-001",
                so_no="SO-001",
                customer_name="ACME",
                estimated_amount=100000,
            ),
        ]
    )
    issues = {issue["code"]: issue for issue in summary["issues"]}

    assert issues["CUSTOMER_PO_MISSING"]["document_type"] == "CUSTOMER_PO"
    assert issues["CUSTOMER_PO_MISSING"]["document_id"] is None


def test_delivery_challan_missing_so_targets_delivery_challan():
    summary = verify_order_bundle(
        [
            _doc("inv", "CUSTOMER_INVOICE", so_no="SO-001", customer_name="ACME", taxable_amount=100),
            _doc("dc", "DELIVERY_CHALLAN", customer_name="ACME", estimated_amount=100),
        ]
    )
    issue = next(issue for issue in summary["issues"] if issue["code"] == "DC_SO_NUMBER_MISSING")

    assert issue["document_type"] == "COMPANY_DC"
    assert issue["document_id"] == "dc"


def test_vendor_bill_missing_for_po_targets_vendor_invoice_upload():
    summary = verify_order_bundle(
        [
            _doc("vpo", "VENDOR_PO", vendor_po_no="PO-001", vendor_name="ACME VENDOR", net_amount=50000),
            _doc("vbill", "VENDOR_INVOICE", vendor_invoice_no="INV999", po_reference="OTHER", invoice_total=50000),
        ]
    )
    issue = next(issue for issue in summary["issues"] if issue["code"] == "VENDOR_BILL_MISSING_FOR_PO")

    assert issue["document_type"] == "VENDOR_INVOICE"
    assert issue["document_id"] is None


def test_partial_billing_issue_targets_vendor_po():
    summary = verify_order_bundle(
        [
            _doc(
                "vpo",
                "VENDOR_PO",
                vendor_po_no="PO-001",
                vendor_name="ACME VENDOR",
                net_amount=50000,
                part_shipment_allowed="NOT ALLOWED",
            ),
            _doc(
                "vbill",
                "VENDOR_INVOICE",
                vendor_invoice_no="INV999",
                po_reference="PO-001",
                vendor_name="ACME VENDOR",
                invoice_total=40000,
            ),
        ]
    )
    issue = next(issue for issue in summary["issues"] if issue["code"] == "VENDOR_PARTIAL_BILLING_REVIEW_REQUIRED")

    assert issue["document_type"] == "COMPANY_PO"
    assert issue["document_id"] == "vpo"


def test_all_issues_have_document_type_and_document_id_keys():
    scenarios = [
        [],
        [_doc("inv", "CUSTOMER_INVOICE", invoice_no="I1", customer_order_no="P1", so_no="S1", customer_name="X", taxable_amount=1000)],
        [
            _doc("vpo", "VENDOR_PO", vendor_po_no="VP1", vendor_name="V", net_amount=1000),
            _doc("vb", "VENDOR_INVOICE", vendor_invoice_no="VB1", po_reference="WRONG", invoice_total=1000),
        ],
    ]
    for documents in scenarios:
        summary = verify_order_bundle(documents)
        for issue in summary["issues"]:
            assert "document_type" in issue, f"Missing document_type in: {issue}"
            assert "document_id" in issue, f"Missing document_id in: {issue}"
