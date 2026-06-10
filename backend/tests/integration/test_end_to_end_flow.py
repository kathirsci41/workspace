from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.database import configure_database, init_db
from app.main import app


KNOWN_BUNDLE_STATUSES = {"OK", "REVIEW_REQUIRED", "MISMATCH", "MISSING_DOCUMENTS", "BLOCKED"}
KNOWN_CHECK_RESULTS = KNOWN_BUNDLE_STATUSES | {"PASS", "PARTIAL_PASS"}
KNOWN_SEVERITIES = {"BLOCKER", "WARNING"}


@pytest.fixture()
def client(tmp_path: Path):
    configure_database(f"sqlite:///{tmp_path / 'order_assurance_test.db'}")
    init_db(drop_existing=True)
    return TestClient(app)


def _pdf_bytes(text: str) -> bytes:
    import fitz

    document = fitz.open()
    page = document.new_page()
    page.insert_text((36, 36), text, fontsize=10)
    return document.tobytes()


def _create_bundle(client: TestClient, bundle_number: str) -> str:
    response = client.post(
        "/api/bundles",
        json={"bundle_number": bundle_number, "customer_name": "PANIMALAR MEDICAL HOSPITAL"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _upload_document(client: TestClient, bundle_id: str, document_type: str) -> str:
    response = client.post(
        f"/api/bundles/{bundle_id}/documents",
        data={"document_type": document_type},
        files={"file": (f"{document_type}.pdf", _pdf_bytes(f"{document_type} inline fixture"), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "UPLOADED"
    return payload["id"]


def _patch_fields(client: TestClient, document_id: str, fields: dict[str, Any]) -> dict:
    response = client.patch(
        f"/api/documents/{document_id}/extracted-data",
        json={"fields": fields, "actor": "qa", "reason": "seeded for test"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _check(summary: dict, check_id: str) -> dict:
    return next(check for check in summary["checks"] if check["check_id"] == check_id)


def _seed_bundle(client: TestClient, *, bundle_number: str, dc_so_no: str = "1OTM2526001611") -> str:
    bundle_id = _create_bundle(client, bundle_number)
    customer_po_id = _upload_document(client, bundle_id, "CUSTOMER_PO")
    customer_invoice_id = _upload_document(client, bundle_id, "COMPANY_INVOICE")
    delivery_challan_id = _upload_document(client, bundle_id, "COMPANY_DC")
    vendor_po_id = _upload_document(client, bundle_id, "COMPANY_PO")
    vendor_invoice_id = _upload_document(client, bundle_id, "VENDOR_INVOICE")

    missing_reason_response = client.patch(
        f"/api/documents/{customer_po_id}/extracted-data",
        json={"fields": {"customer_po_no": "PMCH/024"}, "actor": "qa"},
    )
    assert missing_reason_response.status_code == 400
    assert "reason" in missing_reason_response.json()["detail"].lower()

    _patch_fields(
        client,
        customer_po_id,
        {
            "customer_po_no": "PMCH/024",
            "customer_po_date": "29/01/2026",
            "customer_name": "PANIMALAR MEDICAL HOSPITAL",
            "billing_address": "Poonamallee Chennai",
            "delivery_address": "Poonamallee Chennai",
            "subtotal_amount": 741050,
            "tax_amount": 133389,
            "grand_total": 874439,
            "total_quantity": 9,
        },
    )
    _patch_fields(
        client,
        customer_invoice_id,
        {
            "invoice_no": "1ITR2526001878",
            "invoice_date": "13/02/2026",
            "customer_order_no": "PMCH/024",
            "so_no": "1OTM2526001611",
            "customer_name": "PANIMALAR MEDICAL HOSPITAL",
            "taxable_amount": 741050,
            "tax_amount": 133389,
            "net_amount": 874439,
            "grand_total": 874439,
        },
    )
    _patch_fields(
        client,
        delivery_challan_id,
        {
            "dc_no": "1DNT2526DC3100",
            "dc_date": "13/02/2026",
            "customer_order_no": "PMCH/024",
            "so_no": dc_so_no,
            "customer_name": "PANIMALAR MEDICAL HOSPITAL",
            "total_quantity": 9,
            "estimated_amount": 741050,
        },
    )
    _patch_fields(
        client,
        vendor_po_id,
        {
            "vendor_po_no": "1PTR2526000467",
            "vendor_po_date": "30/01/2026",
            "vendor_name": "SUPREME COMPUTERS INDIA P LTD",
            "part_shipment_allowed": "NOT ALLOWED",
            "mode_of_bill": "ON FULL DELIVERY",
            "net_amount": 696200,
        },
    )
    _patch_fields(
        client,
        vendor_invoice_id,
        {
            "vendor_invoice_no": "2526PSI25087738",
            "vendor_invoice_date": "12/02/2026",
            "vendor_name": "SUPREME COMPUTERS INDIA P LTD",
            "po_reference": "1PTR2526000467",
            "invoice_total": 696200,
        },
    )
    return bundle_id


def test_create_upload_manual_extract_verify_and_list_computed_status(client: TestClient):
    bundle_id = _seed_bundle(client, bundle_number="OA-E2E-PASS")

    response = client.get(f"/api/bundles/{bundle_id}/verification-summary")
    assert response.status_code == 200, response.text
    summary = response.json()

    assert summary["bundle_status"] in KNOWN_BUNDLE_STATUSES
    assert summary["bundle_status"] == "OK"
    assert summary["checks"]
    for check in summary["checks"]:
        assert check["check_id"]
        assert check["result"] in KNOWN_CHECK_RESULTS
        assert check["severity"] in KNOWN_SEVERITIES
        assert "left_value" in check
        assert "right_value" in check

    assert _check(summary, "INVOICE_DC_SO_MATCH")["result"] == "PASS"
    assert _check(summary, "VENDOR_PO_INVOICE_REFERENCE_MATCH")["result"] == "PASS"
    assert _check(summary, "VENDOR_BILLING_COVERAGE")["result"] == "PASS"

    list_response = client.get("/api/bundles")
    assert list_response.status_code == 200, list_response.text
    listed_bundle = next(bundle for bundle in list_response.json() if bundle["id"] == bundle_id)
    assert listed_bundle["computed_status"] == summary["bundle_status"]
    assert listed_bundle["computed_status"] == "OK"


def test_end_to_end_summary_reflects_mismatched_dc_so_number(client: TestClient):
    bundle_id = _seed_bundle(client, bundle_number="OA-E2E-MISMATCH", dc_so_no="1OTM2526009999")

    response = client.get(f"/api/bundles/{bundle_id}/verification-summary")
    assert response.status_code == 200, response.text
    summary = response.json()

    assert _check(summary, "INVOICE_DC_SO_MATCH")["result"] == "MISMATCH"
    assert summary["customer_delivery_status"] == "MISMATCH"
    assert summary["bundle_status"] == "MISMATCH"
