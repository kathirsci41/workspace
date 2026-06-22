from __future__ import annotations

from types import SimpleNamespace

import app.services.verification_summary_service as summary_service
from app.services.document_normalizer import NormalizedDocument
from app.services.order_bundle_verifier import verify_order_bundle


def _record(document_id: str, document_type: str, metadata_status: str, extracted_data: dict):
    return SimpleNamespace(
        id=document_id,
        document_type=document_type,
        metadata_record=SimpleNamespace(status=metadata_status, extracted_data=extracted_data),
    )


def test_verification_summary_excludes_pending_and_failed_documents(monkeypatch):
    records = [
        _record("company-invoice", "COMPANY_INVOICE", "EXTRACTED", {"invoice_no": "INV-1"}),
        _record("customer-invoice", "CUSTOMER_INVOICE", "MANUAL_ENTRY", {"invoice_no": "INV-2"}),
        _record("pending-vendor-bill", "VENDOR_INVOICE", "PENDING", {}),
        _record("failed-vendor-bill", "VENDOR_BILL", "FAILED", {"invoice_total": 100}),
    ]
    captured: dict[str, list[NormalizedDocument]] = {}

    class FakeRepository:
        def __init__(self, _db):
            pass

        def list_for_bundle(self, _bundle_id):
            return records

    def fake_verify(documents):
        captured["documents"] = documents
        return {"document_ids": [document.document_id for document in documents]}

    monkeypatch.setattr(summary_service, "DocumentRepository", FakeRepository)
    monkeypatch.setattr(summary_service, "verify_order_bundle", fake_verify)

    result = summary_service.build_verification_summary(object(), "bundle-1")

    assert result["document_ids"] == ["company-invoice", "customer-invoice"]
    assert [document.document_type for document in captured["documents"]] == [
        "CUSTOMER_INVOICE",
        "CUSTOMER_INVOICE",
    ]
    assert [document.raw_document_type for document in captured["documents"]] == [
        "COMPANY_INVOICE",
        "CUSTOMER_INVOICE",
    ]


def test_vendor_coverage_sums_multiple_extracted_invoices_for_the_same_po():
    summary = verify_order_bundle(
        [
            NormalizedDocument(
                document_id="vendor-po",
                document_type="VENDOR_PO",
                fields={"vendor_po_no": "PO-1", "grand_total": 100},
            ),
            NormalizedDocument(
                document_id="vendor-invoice-1",
                document_type="VENDOR_INVOICE",
                fields={"vendor_invoice_no": "BILL-1", "po_reference": "PO-1", "invoice_total": 40},
            ),
            NormalizedDocument(
                document_id="vendor-invoice-2",
                document_type="VENDOR_INVOICE",
                fields={"vendor_invoice_no": "BILL-2", "po_reference": "PO-1", "invoice_total": 60},
            ),
        ]
    )

    coverage = next(check for check in summary["checks"] if check["check_id"] == "VENDOR_BILLING_COVERAGE")
    assert coverage["result"] == "PASS"
    assert coverage["right_value"] == 100
    assert summary["extracted_summary"]["vendor_total"] == 100
