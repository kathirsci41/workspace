from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, configure_database, init_db
from app.main import app
from app.models.order_bundle import OrderBundleRecord


@pytest.fixture()
def client(tmp_path: Path):
    configure_database(f"sqlite:///{tmp_path / 'order_assurance_test.db'}")
    init_db(drop_existing=True)
    return TestClient(app)


def _fixture() -> dict:
    fixture_path = Path(__file__).resolve().parents[3] / "shared" / "fixtures" / "panimalar_expected.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))["expected"]


def _create_bundle(client: TestClient) -> str:
    response = client.post(
        "/api/bundles",
        json={
            "bundle_number": "OA-PANIMALAR-001",
            "customer_name": "PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _add_document(client: TestClient, bundle_id: str, document_type: str, filename: str) -> str:
    response = client.post(
        f"/api/bundles/{bundle_id}/documents",
        data={"document_type": document_type},
        files={"file": (filename, b"%PDF-1.4 test", "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _patch(client: TestClient, document_id: str, fields: dict) -> dict:
    response = client.patch(
        f"/api/documents/{document_id}/extracted-data",
        json={"fields": fields, "actor": "qa", "reason": "OCR failed"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_health_endpoint_works(client: TestClient):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["ocr"]["provider"] == "glm_ocr"
    assert response.json()["ocr"]["model"] == "glm-ocr:latest"
    assert "reachable" in response.json()["ocr"]


def test_panimalar_manual_vendor_bill_verification_summary(client: TestClient):
    expected = _fixture()
    bundle_id = _create_bundle(client)

    invoice_doc = _add_document(client, bundle_id, "COMPANY_INVOICE", "Customer Invoice 1ITR2526001878.pdf")
    dc_doc = _add_document(client, bundle_id, "COMPANY_DC", "DC 1DNT2526DC3100.pdf")
    vendor_po_doc = _add_document(client, bundle_id, "COMPANY_PO", "Vendor PO 1PTR2526000467.pdf")
    vendor_bill_doc = _add_document(client, bundle_id, "VENDOR_INVOICE", "Vendor Bill 2526PSI25087738.pdf")

    _patch(client, invoice_doc, expected["customer_invoice"])
    _patch(client, dc_doc, expected["delivery_challan"])
    _patch(client, vendor_po_doc, expected["vendor_po"])
    patch_response = _patch(client, vendor_bill_doc, expected["vendor_bill_manual_expected"])

    assert patch_response["metadata"]["extracted_data"]["extraction_source"] == "manual_entry"
    assert patch_response["audit_event"]["event_type"] == "manual_extracted_data_patched"
    assert patch_response["audit_event"]["payload"]["reason"] == "OCR failed"
    assert any(change["field"] == "vendor_invoice_no" for change in patch_response["audit_event"]["payload"]["changes"])
    assert any(ref["reference_type"] == "po_reference" for ref in patch_response["references"])

    with SessionLocal() as db:
        persisted_bundle = db.get(OrderBundleRecord, bundle_id)
        assert persisted_bundle.status == "REVIEW_REQUIRED"
        assert persisted_bundle.customer_delivery_status == "PARTIAL_PASS"
        assert persisted_bundle.vendor_procurement_status == "REVIEW_REQUIRED"

    audit_response = client.get(f"/api/bundles/{bundle_id}/audit-events")
    assert audit_response.status_code == 200, audit_response.text
    audit_events = audit_response.json()
    assert any(event["payload"].get("reason") == "OCR failed" for event in audit_events)

    response = client.get(f"/api/bundles/{bundle_id}/verification-summary")
    assert response.status_code == 200, response.text
    summary = response.json()

    assert summary["customer_delivery_status"] == "PARTIAL_PASS"
    assert summary["vendor_procurement_status"] == "REVIEW_REQUIRED"
    assert summary["bundle_status"] == "REVIEW_REQUIRED"
    assert summary["extracted_summary"]["vendor_total"] == 554600
    assert any(issue.get("difference") == 141600 for issue in summary["issues"])

    bundle_response = client.get(f"/api/bundles/{bundle_id}")
    assert bundle_response.status_code == 200, bundle_response.text
    bundle = bundle_response.json()
    assert bundle["status"] == summary["bundle_status"]
    assert bundle["customer_delivery_status"] == summary["customer_delivery_status"]
    assert bundle["vendor_procurement_status"] == summary["vendor_procurement_status"]

    list_response = client.get("/api/bundles")
    assert list_response.status_code == 200, list_response.text
    listed_bundle = next(item for item in list_response.json() if item["id"] == bundle_id)
    assert listed_bundle["status"] == summary["bundle_status"]
    assert listed_bundle["customer_delivery_status"] == summary["customer_delivery_status"]
    assert listed_bundle["vendor_procurement_status"] == summary["vendor_procurement_status"]


def test_vendor_bill_amount_without_reference_is_not_counted_as_coverage(client: TestClient):
    expected = _fixture()
    bundle_id = _create_bundle(client)
    vendor_po_doc = _add_document(client, bundle_id, "COMPANY_PO", "Vendor PO 1PTR2526000467.pdf")
    vendor_bill_doc = _add_document(client, bundle_id, "VENDOR_INVOICE", "Vendor Bill 2526PSI25087738.pdf")

    _patch(client, vendor_po_doc, expected["vendor_po"])
    _patch(
        client,
        vendor_bill_doc,
        {
            "vendor_invoice_no": "2526PSI25087738",
            "vendor_invoice_date": "12-02-2026",
            "vendor_name": "SUPREME COMPUTERS INDIA P LTD",
            "invoice_total": 554600,
        },
    )

    response = client.get(f"/api/bundles/{bundle_id}/verification-summary")
    assert response.status_code == 200, response.text
    summary = response.json()

    assert summary["vendor_procurement_status"] in {"REVIEW_REQUIRED", "BLOCKED"}
    assert any(issue.get("code") == "VENDOR_BILL_REFERENCE_MISSING" for issue in summary["issues"])
    assert not any(issue.get("difference") == 141600 for issue in summary["issues"])
