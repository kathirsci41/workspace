from __future__ import annotations

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import configure_database, init_db
from app.main import app


@pytest.fixture()
def client(tmp_path: Path):
    configure_database(f"sqlite:///{tmp_path / 'order_assurance_logging_test.db'}")
    init_db(drop_existing=True)
    return TestClient(app)


def _pdf_bytes(text: str) -> bytes:
    import fitz

    document = fitz.open()
    page = document.new_page()
    page.insert_text((36, 36), text, fontsize=10)
    return document.tobytes()


def _create_bundle(client: TestClient) -> str:
    response = client.post("/api/bundles", json={"bundle_number": "OA-LOG", "customer_name": "Logging QA"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _upload_pdf(client: TestClient, bundle_id: str, document_type: str, filename: str, text: str) -> str:
    response = client.post(
        f"/api/bundles/{bundle_id}/documents",
        data={"document_type": document_type},
        files={"file": (filename, _pdf_bytes(text), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_request_id_header_and_request_log_are_added(client: TestClient, caplog: pytest.LogCaptureFixture):
    caplog.set_level(logging.INFO)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert any(
        getattr(record, "event", None) == "api_request"
        and getattr(record, "path", None) == "/api/health"
        and getattr(record, "status_code", None) == 200
        and getattr(record, "request_id", None) == response.headers["X-Request-ID"]
        for record in caplog.records
    )


def test_extraction_failure_logs_failure_code(client: TestClient, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch):
    import app.services.extraction_service as extraction_service

    monkeypatch.setattr(extraction_service, "settings", Settings(ocr_enabled=False))
    caplog.set_level(logging.INFO)
    bundle_id = _create_bundle(client)
    document_id = _upload_pdf(client, bundle_id, "VENDOR_INVOICE", "blank-vendor-bill.pdf", " ")

    response = client.post(f"/api/documents/{document_id}/extract")

    assert response.status_code == 200
    assert any(
        getattr(record, "event", None) == "extraction_failed"
        and getattr(record, "document_id", None) == document_id
        and getattr(record, "failure_code", None) == "MANUAL_ENTRY_REQUIRED"
        for record in caplog.records
    )


def test_export_failure_logs_event(client: TestClient, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch):
    import app.api.routes.bundles as bundles_route

    def fail_export(*args, **kwargs):
        raise RuntimeError("workbook writer failed")

    monkeypatch.setattr(bundles_route, "build_bundle_export", fail_export)
    caplog.set_level(logging.INFO)
    bundle_id = _create_bundle(client)

    response = client.get(f"/api/bundles/{bundle_id}/export.xlsx")

    assert response.status_code == 500
    assert any(
        getattr(record, "event", None) == "export_failed"
        and getattr(record, "bundle_id", None) == bundle_id
        and "workbook writer failed" in str(getattr(record, "error", ""))
        for record in caplog.records
    )
