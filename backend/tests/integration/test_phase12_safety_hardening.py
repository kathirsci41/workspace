from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.database import SessionLocal, configure_database, init_db
from app.main import app
from app.models.document import DocumentRecord
from app.models.order_bundle import OrderBundleRecord


def _pdf_bytes(text: str = "Test PDF") -> bytes:
    import fitz

    document = fitz.open()
    page = document.new_page()
    page.insert_text((36, 36), text, fontsize=10)
    return document.tobytes()


def _client(tmp_path: Path) -> TestClient:
    configure_database(f"sqlite:///{tmp_path / 'phase12.db'}")
    init_db(drop_existing=True)
    return TestClient(app)


def _create_bundle(client: TestClient) -> str:
    response = client.post("/api/bundles", json={"bundle_number": "PHASE12-001", "customer_name": "Demo Customer"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _upload_document(client: TestClient, bundle_id: str, document_type: str, filename: str = "document.pdf") -> str:
    response = client.post(
        f"/api/bundles/{bundle_id}/documents",
        data={"document_type": document_type},
        files={"file": (filename, _pdf_bytes(), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_verification_summary_get_does_not_persist_bundle_status(tmp_path: Path):
    client = _client(tmp_path)
    bundle_id = _create_bundle(client)
    old_updated = (datetime.now(timezone.utc) - timedelta(days=3)).replace(tzinfo=None)
    with SessionLocal() as db:
        bundle = db.get(OrderBundleRecord, bundle_id)
        bundle.status = "OK"
        bundle.customer_delivery_status = "PASS"
        bundle.vendor_procurement_status = "PASS"
        bundle.updated_at = old_updated
        db.commit()

    response = client.get(f"/api/bundles/{bundle_id}/verification-summary")

    assert response.status_code == 200, response.text
    assert response.json()["bundle_status"] == "MISSING_DOCUMENTS"
    with SessionLocal() as db:
        persisted = db.get(OrderBundleRecord, bundle_id)
        assert persisted.status == "OK"
        assert persisted.customer_delivery_status == "PASS"
        assert persisted.vendor_procurement_status == "PASS"
        assert persisted.updated_at == old_updated


def test_bundle_get_and_export_do_not_persist_computed_status(tmp_path: Path):
    client = _client(tmp_path)
    bundle_id = _create_bundle(client)
    old_updated = (datetime.now(timezone.utc) - timedelta(days=3)).replace(tzinfo=None)
    with SessionLocal() as db:
        bundle = db.get(OrderBundleRecord, bundle_id)
        bundle.status = "OK"
        bundle.customer_delivery_status = "PASS"
        bundle.vendor_procurement_status = "PASS"
        bundle.updated_at = old_updated
        db.commit()

    assert client.get(f"/api/bundles/{bundle_id}").status_code == 200
    assert client.get(f"/api/bundles/{bundle_id}/export.xlsx").status_code == 200

    with SessionLocal() as db:
        persisted = db.get(OrderBundleRecord, bundle_id)
        assert persisted.status == "OK"
        assert persisted.customer_delivery_status == "PASS"
        assert persisted.vendor_procurement_status == "PASS"
        assert persisted.updated_at == old_updated


def test_bundle_list_get_does_not_resync_stale_status(tmp_path: Path):
    client = _client(tmp_path)
    bundle_id = _create_bundle(client)
    with SessionLocal() as db:
        bundle = db.get(OrderBundleRecord, bundle_id)
        bundle.status = "OK"
        bundle.customer_delivery_status = "PASS"
        bundle.vendor_procurement_status = "PASS"
        db.commit()

    response = client.get("/api/bundles")

    assert response.status_code == 200, response.text
    listed = next(item for item in response.json() if item["id"] == bundle_id)
    assert listed["status"] == "OK"
    with SessionLocal() as db:
        persisted = db.get(OrderBundleRecord, bundle_id)
        assert persisted.status == "OK"
        assert persisted.customer_delivery_status == "PASS"
        assert persisted.vendor_procurement_status == "PASS"


def test_public_document_payload_excludes_storage_path_and_raw_text(tmp_path: Path):
    client = _client(tmp_path)
    bundle_id = _create_bundle(client)
    document_id = _upload_document(client, bundle_id, "COMPANY_INVOICE")

    with SessionLocal() as db:
        document = db.get(DocumentRecord, document_id)
        document.metadata_record.extracted_data = {"invoice_no": "INV-1", "raw_text": "secret text", "raw_ocr_text": "secret ocr"}
        document.metadata_record.diagnostics = {"raw_text_length": 11, "raw_ocr_text_length": 10}
        db.commit()

    payload = client.get(f"/api/documents/{document_id}").json()

    assert "storage_path" not in payload
    assert "raw_text" not in payload["metadata"]["extracted_data"]
    assert "raw_ocr_text" not in payload["metadata"]["extracted_data"]
    assert payload["metadata"]["diagnostics"]["raw_text_length"] == 11


def test_preview_rejects_document_path_outside_storage_root(tmp_path: Path):
    client = _client(tmp_path)
    bundle_id = _create_bundle(client)
    document_id = _upload_document(client, bundle_id, "COMPANY_INVOICE")
    outside_pdf = tmp_path / "outside.pdf"
    outside_pdf.write_bytes(_pdf_bytes())
    with SessionLocal() as db:
        document = db.get(DocumentRecord, document_id)
        document.storage_path = str(outside_pdf)
        db.commit()

    response = client.get(f"/api/documents/{document_id}/preview")

    assert response.status_code in {403, 404}


def test_manual_patch_rejects_unknown_fields(tmp_path: Path):
    client = _client(tmp_path)
    bundle_id = _create_bundle(client)
    document_id = _upload_document(client, bundle_id, "VENDOR_INVOICE")

    response = client.patch(
        f"/api/documents/{document_id}/extracted-data",
        json={"fields": {"vendor_invoice_no": "INV-1", "bundle_status": "OK"}, "actor": "qa"},
    )

    assert response.status_code == 400
    assert "bundle_status" in response.json()["detail"]


def test_manual_patch_accepts_company_invoice_emitted_reference_fields(tmp_path: Path):
    client = _client(tmp_path)
    bundle_id = _create_bundle(client)
    document_id = _upload_document(client, bundle_id, "COMPANY_INVOICE")

    response = client.patch(
        f"/api/documents/{document_id}/extracted-data",
        json={
            "fields": {
                "so_number": "1OTM2526001429",
                "po_reference": "PMCH&RI/024/2025-2026",
            },
            "actor": "qa",
            "reason": "Reviewer corrected company invoice references",
        },
    )

    assert response.status_code == 200, response.text
    extracted_data = response.json()["metadata"]["extracted_data"]
    assert extracted_data["so_number"] == "1OTM2526001429"
    assert extracted_data["po_reference"] == "PMCH&RI/024/2025-2026"


def test_manual_patch_clears_stale_extraction_failure_diagnostics(tmp_path: Path):
    client = _client(tmp_path)
    bundle_id = _create_bundle(client)
    document_id = _upload_document(client, bundle_id, "VENDOR_INVOICE")
    with SessionLocal() as db:
        document = db.get(DocumentRecord, document_id)
        document.status = "EXTRACTION_FAILED"
        document.last_error = "OCR_EMPTY"
        document.metadata_record.status = "FAILED"
        document.metadata_record.last_error = "OCR_EMPTY"
        document.metadata_record.diagnostics = {"failure_code": "OCR_EMPTY", "failure_reason": "OCR returned no text."}
        db.commit()

    response = client.patch(
        f"/api/documents/{document_id}/extracted-data",
        json={
            "fields": {
                "vendor_invoice_no": "2526PSI25087738",
                "vendor_invoice_date": "12-02-2026",
                "vendor_name": "SUPREME COMPUTERS INDIA P LTD",
                "po_reference": "1PTR2526000467",
                "invoice_total": 554600,
            },
            "actor": "qa",
            "reason": "OCR failed",
        },
    )

    assert response.status_code == 200, response.text
    metadata = response.json()["metadata"]
    assert metadata["status"] == "EXTRACTED"
    assert metadata["last_error"] is None
    assert metadata["diagnostics"].get("failure_code") is None
    assert metadata["diagnostics"].get("failure_reason") is None
    assert metadata["diagnostics"].get("previous_failure_code") == "OCR_EMPTY"


def test_document_delete_resyncs_stale_vendor_status(tmp_path: Path):
    client = _client(tmp_path)
    bundle_id = _create_bundle(client)
    vendor_document_id = _upload_document(client, bundle_id, "COMPANY_PO")
    with SessionLocal() as db:
        bundle = db.get(OrderBundleRecord, bundle_id)
        bundle.vendor_procurement_status = "REVIEW_REQUIRED"
        bundle.status = "REVIEW_REQUIRED"
        db.commit()

    response = client.delete(f"/api/documents/{vendor_document_id}")

    assert response.status_code == 204, response.text
    with SessionLocal() as db:
        bundle = db.get(OrderBundleRecord, bundle_id)
        assert bundle.vendor_procurement_status == "MISSING_DOCUMENTS"
        assert bundle.status == "MISSING_DOCUMENTS"


def test_failed_extraction_does_not_overwrite_existing_bundle_header_with_empty_values(tmp_path: Path, monkeypatch):
    import app.services.extraction_service as extraction_service
    from app.config import Settings

    monkeypatch.setattr(extraction_service, "settings", Settings(ocr_enabled=False))
    client = _client(tmp_path)
    bundle_id = _create_bundle(client)
    document_id = _upload_document(client, bundle_id, "COMPANY_INVOICE", "blank.pdf")
    with SessionLocal() as db:
        bundle = db.get(OrderBundleRecord, bundle_id)
        bundle.customer_po_no = "PMCH&RI/024/2025-2026"
        bundle.so_no = "1OTM2526001611"
        bundle.customer_name = "PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE"
        db.commit()

    response = client.post(f"/api/documents/{document_id}/extract")

    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        bundle = db.get(OrderBundleRecord, bundle_id)
        assert bundle.customer_po_no == "PMCH&RI/024/2025-2026"
        assert bundle.so_no == "1OTM2526001611"
        assert bundle.customer_name == "PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE"
