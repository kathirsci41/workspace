from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.database import configure_database, init_db
from app.main import app


@pytest.fixture()
def client(tmp_path: Path):
    configure_database(f"sqlite:///{tmp_path / 'order_assurance_export_test.db'}")
    init_db(drop_existing=True)
    return TestClient(app)


def test_seed_panimalar_demo_creates_expected_review_required_summary(client: TestClient):
    response = client.post("/api/dev/seed-panimalar")

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["verification_summary"]["bundle_status"] == "REVIEW_REQUIRED"
    assert payload["verification_summary"]["customer_delivery_status"] == "PARTIAL_PASS"
    assert payload["verification_summary"]["vendor_procurement_status"] == "REVIEW_REQUIRED"
    assert payload["bundle"]["status"] == payload["verification_summary"]["bundle_status"]
    assert payload["bundle"]["customer_delivery_status"] == payload["verification_summary"]["customer_delivery_status"]
    assert payload["bundle"]["vendor_procurement_status"] == payload["verification_summary"]["vendor_procurement_status"]
    assert any(issue.get("difference") == 141600 for issue in payload["verification_summary"]["issues"])


def test_bundle_export_contains_summary_documents_checks_and_fields(client: TestClient):
    seed = client.post("/api/dev/seed-panimalar").json()
    bundle_id = seed["bundle"]["id"]

    response = client.get(f"/api/bundles/{bundle_id}/export.xlsx")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    workbook = load_workbook(BytesIO(response.content), data_only=True)
    assert workbook.sheetnames[:6] == ["Verification Summary", "Documents", "Checks", "Extracted Fields", "References", "Audit Trail"]

    summary_values = [cell.value for row in workbook["Verification Summary"].iter_rows() for cell in row]
    summary_rows = {
        row[0].value: row[1].value
        for row in workbook["Verification Summary"].iter_rows(min_row=1, max_col=2)
    }
    assert "REVIEW_REQUIRED" in summary_values
    assert "PARTIAL_PASS" in summary_values
    assert 141600 in summary_values
    assert "Review vendor-side partial billing before closure." in summary_values
    assert summary_rows["Vendor PO Total"] == 696200
    assert summary_rows["Vendor Invoice Total"] == 554600

    document_headers = [cell.value for cell in next(workbook["Documents"].iter_rows())]
    assert document_headers == ["Document Type", "Filename", "Document Status", "Metadata Status", "Extraction Route", "Failure Code", "Failure Reason"]

    check_headers = [cell.value for cell in next(workbook["Checks"].iter_rows())]
    assert check_headers == ["Check ID", "Check Name", "Result", "Severity", "Left Document", "Left Value", "Right Document", "Right Value", "Message"]

    field_headers = [cell.value for cell in next(workbook["Extracted Fields"].iter_rows())]
    assert field_headers == ["Document Type", "Field", "Value", "Source", "Confidence", "Evidence Text", "Page", "BBox", "Failure Reason"]
    field_rows = list(workbook["Extracted Fields"].iter_rows(min_row=2, values_only=True))
    assert any(row[3] == "manual_entry" and row[4] == 1 for row in field_rows)
    assert any(row[5] for row in field_rows)

    audit_headers = [cell.value for cell in next(workbook["Audit Trail"].iter_rows())]
    reference_headers = [cell.value for cell in next(workbook["References"].iter_rows())]
    assert reference_headers == ["Document Type", "Field Name", "Reference Type", "Reference Value", "Source Type", "Confidence", "Evidence Text", "Created At"]

    assert audit_headers == ["Timestamp", "Document Type", "Action", "Field", "Old Value", "New Value", "Source/Actor", "Reason", "Request ID"]
    audit_values = [cell.value for row in workbook["Audit Trail"].iter_rows() for cell in row]
    assert "manual_extracted_data_patched" in audit_values
    first_timestamp = next(workbook["Audit Trail"].iter_rows(min_row=2))[0].value
    assert getattr(first_timestamp, "tzinfo", None) is None
