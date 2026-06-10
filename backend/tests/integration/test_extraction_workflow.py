from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.database import SessionLocal, configure_database, init_db
from app.main import app
from app.models.order_bundle import OrderBundleRecord
from app.models.reference_index import ReferenceIndexRecord
from app.services.extraction.glm_ocr_client import OcrResult
from app.services.verification_summary_service import build_verification_summary


@pytest.fixture()
def client(tmp_path: Path):
    configure_database(f"sqlite:///{tmp_path / 'order_assurance_extract_test.db'}")
    init_db(drop_existing=True)
    return TestClient(app)


def _fixture() -> dict:
    fixture_path = Path(__file__).resolve().parents[3] / "shared" / "fixtures" / "panimalar_expected.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))["expected"]


def _pdf_bytes(text: str) -> bytes:
    import fitz

    document = fitz.open()
    page = document.new_page()
    page.insert_text((36, 36), text, fontsize=10)
    return document.tobytes()


def _create_bundle(client: TestClient) -> str:
    response = client.post(
        "/api/bundles",
        json={
            "bundle_number": "OA-EXTRACT-PANIMALAR",
            "customer_name": "PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _upload_pdf(client: TestClient, bundle_id: str, document_type: str, filename: str, text: str) -> str:
    response = client.post(
        f"/api/bundles/{bundle_id}/documents",
        data={"document_type": document_type},
        files={"file": (filename, _pdf_bytes(text), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "UPLOADED"
    assert payload["metadata"]["diagnostics"]["page_count"] == 1
    return payload["id"]


def test_upload_rejects_non_pdf(client: TestClient):
    bundle_id = _create_bundle(client)

    response = client.post(
        f"/api/bundles/{bundle_id}/documents",
        data={"document_type": "COMPANY_INVOICE"},
        files={"file": ("invoice.txt", b"not a pdf", "text/plain")},
    )

    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_extract_and_reextract_digital_panimalar_documents(client: TestClient):
    expected = _fixture()
    bundle_id = _create_bundle(client)
    invoice_id = _upload_pdf(
        client,
        bundle_id,
        "COMPANY_INVOICE",
        "Customer Invoice 1ITR2526001878.pdf",
        """
        Tax Invoice
        1ITR2526001878
        1OTM2526001611
        PMCH&RI/024/2025-2026
        Invoice Date
        13/02/2026
        Customer Name & Detail
        PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE
        Nett Amount
        874439
        133389
        741050
        """,
    )
    dc_id = _upload_pdf(
        client,
        bundle_id,
        "COMPANY_DC",
        "DC 1DNT2526DC3100.pdf",
        """
        Delivery Challan
        1DNT2526DC3100
        1OTM2526001611
        PMCH&RI/024/2025-2026
        DC Date
        13/02/2026
        Delivery To
        PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE
        Chennai 600123
        741050
        0
        9
        Total
        """,
    )
    vendor_po_id = _upload_pdf(
        client,
        bundle_id,
        "COMPANY_PO",
        "Vendor PO 1PTR2526000467.pdf",
        """
        Purchase Order
        SUPREME COMPUTERS INDIA P LTD
        Vendor Name & Address
        1PTR2526000467
        Order Date
        30/01/2026
        NOT ALLOWED
        ON FULL DELIVERY
        Net Amount
        696200
        """,
    )

    invoice = client.post(f"/api/documents/{invoice_id}/extract").json()
    dc = client.post(f"/api/documents/{dc_id}/extract").json()
    vendor_po = client.post(f"/api/documents/{vendor_po_id}/extract").json()

    assert invoice["metadata"]["extracted_data"]["invoice_no"] == expected["customer_invoice"]["invoice_no"]
    assert invoice["metadata"]["diagnostics"]["digital_text_enabled"] is True
    assert invoice["metadata"]["diagnostics"]["digital_text_used"] is True
    assert invoice["metadata"]["diagnostics"]["ocr_status"] == "skipped_digital_text"
    assert invoice["metadata"]["diagnostics"]["manual_fallback_available"] is True
    assert invoice["metadata"]["diagnostics"]["structured_rules_enabled"] is True
    assert invoice["metadata"]["diagnostics"]["model_layer2_enabled"] is False
    assert invoice["metadata"]["diagnostics"]["model_layer2_used"] is False
    assert invoice["metadata"]["diagnostics"]["field_metadata"]["invoice_no"]["source"] == "rules"
    assert invoice["metadata"]["diagnostics"]["field_metadata"]["invoice_no"]["confidence"] >= 0.8
    invoice_location = invoice["metadata"]["field_locations"]["invoice_no"]
    assert invoice_location["page"] == 1
    assert invoice_location["bbox"]
    assert invoice_location["page_width"] > 0
    assert invoice["metadata"]["field_confidences"]["invoice_no"] >= 0.8
    assert invoice["metadata"]["field_evidence"]["invoice_no"] == expected["customer_invoice"]["invoice_no"]
    artifact_dir = Path(__file__).resolve().parents[3] / "tests" / "artifacts" / "field-highlighting"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "sample-field-locations.json").write_text(
        json.dumps(
            {
                "document_type": "COMPANY_INVOICE",
                "filename": "Customer Invoice 1ITR2526001878.pdf",
                "field_locations": invoice["metadata"]["field_locations"],
                "field_confidences": invoice["metadata"]["field_confidences"],
                "field_evidence": invoice["metadata"]["field_evidence"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    assert invoice["metadata"]["diagnostics"]["extraction_runs"][-1]["status"] == "EXTRACTED"
    assert invoice["metadata"]["extracted_data"]["customer_order_no"] == expected["customer_invoice"]["customer_order_no"]
    assert invoice["metadata"]["extracted_data"]["taxable_amount"] == expected["customer_invoice"]["taxable_amount"]
    assert dc["metadata"]["extracted_data"]["dc_no"] == expected["delivery_challan"]["dc_no"]
    assert dc["metadata"]["extracted_data"]["estimated_amount"] == expected["delivery_challan"]["estimated_amount"]
    assert vendor_po["metadata"]["extracted_data"]["vendor_po_no"] == expected["vendor_po"]["vendor_po_no"]
    assert vendor_po["metadata"]["extracted_data"]["net_amount"] == expected["vendor_po"]["net_amount"]

    reextract = client.post(f"/api/documents/{invoice_id}/re-extract")
    assert reextract.status_code == 200
    assert reextract.json()["metadata"]["diagnostics"]["extraction_route"] == "digital"

    with SessionLocal() as db:
        refs = list(db.scalars(select(ReferenceIndexRecord).where(ReferenceIndexRecord.document_id == invoice_id)))
        persisted_bundle = db.get(OrderBundleRecord, bundle_id)
        summary = build_verification_summary(db, bundle_id)
    assert {ref.reference_type for ref in refs} >= {"invoice_no", "customer_order_no", "so_no"}
    assert persisted_bundle.status == summary["bundle_status"]
    assert persisted_bundle.customer_delivery_status == summary["customer_delivery_status"]
    assert persisted_bundle.vendor_procurement_status == summary["vendor_procurement_status"]

    preview = client.get(f"/api/documents/{invoice_id}/preview")
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("application/pdf")
    assert preview.content.startswith(b"%PDF")

    page_preview = client.get(f"/api/documents/{invoice_id}/preview/pages/1.png")
    assert page_preview.status_code == 200
    assert page_preview.headers["content-type"].startswith("image/png")


def test_extraction_failure_preserves_manual_fallback_and_verification(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    import app.services.extraction_service as extraction_service

    monkeypatch.setattr(extraction_service, "settings", Settings(ocr_enabled=False))
    expected = _fixture()
    bundle_id = _create_bundle(client)
    vendor_po_id = _upload_pdf(
        client,
        bundle_id,
        "COMPANY_PO",
        "Vendor PO 1PTR2526000467.pdf",
        """
        SUPREME COMPUTERS INDIA P LTD
        Vendor Name & Address
        1PTR2526000467
        Order Date
        30/01/2026
        NOT ALLOWED
        ON FULL DELIVERY
        Net Amount
        696200
        """,
    )
    vendor_bill_id = _upload_pdf(client, bundle_id, "VENDOR_INVOICE", "Vendor Bill blank.pdf", "   ")

    client.post(f"/api/documents/{vendor_po_id}/extract")
    failed = client.post(f"/api/documents/{vendor_bill_id}/extract")
    assert failed.status_code == 200
    assert failed.json()["document"]["status"] == "EXTRACTION_FAILED"
    failed_payload = failed.json()
    assert failed_payload["metadata"]["diagnostics"]["ocr_enabled"] is False
    assert failed_payload["metadata"]["diagnostics"]["failure_code"] == "MANUAL_ENTRY_REQUIRED"
    assert failed_payload["metadata"]["diagnostics"]["ocr_status"] == "disabled"
    assert failed_payload["metadata"]["diagnostics"]["manual_fallback_available"] is True
    assert "OCR is disabled" in failed_payload["metadata"]["diagnostics"]["failure_reason"]
    assert failed_payload["metadata"]["diagnostics"]["extraction_runs"][-1]["failure_code"] == "MANUAL_ENTRY_REQUIRED"

    manual = client.patch(
        f"/api/documents/{vendor_bill_id}/extracted-data",
        json={"fields": expected["vendor_bill_manual_expected"], "actor": "qa", "reason": "OCR failed"},
    )
    assert manual.status_code == 200
    assert manual.json()["audit_event"]["event_type"] == "manual_extracted_data_patched"
    assert manual.json()["metadata"]["field_locations"]["vendor_invoice_no"]["bbox"] is None
    assert manual.json()["metadata"]["field_locations"]["vendor_invoice_no"]["source"] == "manual_entry"

    summary = client.get(f"/api/bundles/{bundle_id}/verification-summary").json()
    assert summary["bundle_status"] in {"REVIEW_REQUIRED", "MISSING_DOCUMENTS"}
    assert any(issue.get("difference") == 141600 for issue in summary["issues"])


def test_glm_ocr_success_feeds_structured_parser_and_saves_diagnostics(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    import app.services.extraction_service as extraction_service

    monkeypatch.setattr(extraction_service, "settings", Settings(ocr_enabled=True, ocr_provider="glm_ocr"))

    def fake_ocr(*args, **kwargs):
        return OcrResult(
            text="""
            Tax Invoice No 2526PSI25087738
            Invoice Date 12-02-2026
            Vendor Name SUPREME COMPUTERS INDIA P LTD
            PO No 1PTR2526000467
            Invoice Total 554600
            """,
            pages=[{"page_number": 1, "image_width": 1200, "image_height": 1600, "ocr_text_length": 160, "duration_ms": 20}],
            provider="glm_ocr",
            model="glm-ocr:latest",
            diagnostics={
                "ocr_provider": "glm_ocr",
                "ocr_model": "glm-ocr:latest",
                "ocr_base_url_host_only": "localhost:11434",
                "ocr_pages_attempted": 1,
                "ocr_text_length": 160,
                "ocr_page_results": [{"page_number": 1, "image_width": 1200, "image_height": 1600, "ocr_text_length": 160, "duration_ms": 20}],
            },
        )

    monkeypatch.setattr(extraction_service, "extract_text_with_ocr", fake_ocr)
    bundle_id = _create_bundle(client)
    vendor_bill_id = _upload_pdf(client, bundle_id, "VENDOR_INVOICE", "Vendor Bill scanned.pdf", "   ")

    response = client.post(f"/api/documents/{vendor_bill_id}/extract")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["document"]["status"] == "PENDING_REVIEW"
    extracted = payload["metadata"]["extracted_data"]
    assert extracted["vendor_invoice_no"] == "2526PSI25087738"
    assert extracted["po_reference"] == "1PTR2526000467"
    assert extracted["invoice_total"] == 554600
    diagnostics = payload["metadata"]["diagnostics"]
    assert diagnostics["extraction_route"] == "ocr_glm"
    assert diagnostics["ocr_provider"] == "glm_ocr"
    assert diagnostics["ocr_model"] == "glm-ocr:latest"
    assert diagnostics["ocr_text_length"] > 100
    assert diagnostics["ocr_status"] == "text_acquired"
    assert diagnostics["digital_text_used"] is False
    assert diagnostics["manual_fallback_available"] is True
    assert diagnostics["parser_route"] == "ocr_rules"
    assert diagnostics["failure_code"] is None
    assert diagnostics["rules_extracted_fields"]["po_reference"] == "1PTR2526000467"
    assert diagnostics["rules_missing_fields"] == []
    assert diagnostics["model_extracted_fields"] == {}
    assert diagnostics["model_field_evidence"] == {}
    assert payload["metadata"]["field_locations"]["po_reference"]["bbox"] is None
    assert payload["metadata"]["field_locations"]["po_reference"]["source"] == "ocr"
    assert payload["metadata"]["field_locations"]["po_reference"]["evidence_text"] == "1PTR2526000467"


def test_glm_ocr_empty_text_fails_softly(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    import app.services.extraction_service as extraction_service

    monkeypatch.setattr(extraction_service, "settings", Settings(ocr_enabled=True, ocr_provider="glm_ocr"))
    monkeypatch.setattr(
        extraction_service,
        "extract_text_with_ocr",
        lambda *args, **kwargs: OcrResult(
            text="",
            pages=[{"page_number": 1, "ocr_text_length": 0, "duration_ms": 10}],
            provider="glm_ocr",
            model="glm-ocr:latest",
            diagnostics={"ocr_provider": "glm_ocr", "ocr_model": "glm-ocr:latest", "ocr_pages_attempted": 1, "ocr_text_length": 0},
        ),
    )
    bundle_id = _create_bundle(client)
    vendor_bill_id = _upload_pdf(client, bundle_id, "VENDOR_INVOICE", "Vendor Bill blank.pdf", "   ")

    response = client.post(f"/api/documents/{vendor_bill_id}/extract")

    assert response.status_code == 200, response.text
    diagnostics = response.json()["metadata"]["diagnostics"]
    assert response.json()["document"]["status"] == "EXTRACTION_FAILED"
    assert diagnostics["failure_code"] == "OCR_EMPTY"
    assert diagnostics["ocr_status"] == "empty"
    assert diagnostics["failure_reason"] == "glm-ocr returned no usable text."


def test_glm_ocr_timeout_fails_softly(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    import app.services.extraction_service as extraction_service

    monkeypatch.setattr(extraction_service, "settings", Settings(ocr_enabled=True, ocr_provider="glm_ocr"))

    def fail_ocr(*args, **kwargs):
        raise TimeoutError("request timed out")

    monkeypatch.setattr(extraction_service, "extract_text_with_ocr", fail_ocr)
    bundle_id = _create_bundle(client)
    vendor_bill_id = _upload_pdf(client, bundle_id, "VENDOR_INVOICE", "Vendor Bill timeout.pdf", "   ")

    response = client.post(f"/api/documents/{vendor_bill_id}/extract")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["document"]["status"] == "EXTRACTION_FAILED"
    diagnostics = payload["metadata"]["diagnostics"]
    assert diagnostics["failure_code"] == "OCR_FAILED"
    assert diagnostics["ocr_status"] == "provider_error"
    assert "glm-ocr" in diagnostics["failure_reason"]
    assert "request timed out" in diagnostics["ocr_error"]


def test_glm_ocr_page_provider_error_is_not_reported_as_empty_text(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    import app.services.extraction_service as extraction_service

    monkeypatch.setattr(extraction_service, "settings", Settings(ocr_enabled=True, ocr_provider="glm_ocr"))
    monkeypatch.setattr(
        extraction_service,
        "extract_text_with_ocr",
        lambda *args, **kwargs: OcrResult(
            text="",
            pages=[
                {
                    "page_number": 1,
                    "image_format": "png",
                    "image_width": 934,
                    "image_height": 934,
                    "image_bytes": 2048,
                    "base64_bytes": 2732,
                    "ocr_text_length": 0,
                    "error": "glm-ocr generate failed: HTTP 500: model failed to load",
                }
            ],
            provider="glm_ocr",
            model="glm-ocr:latest",
            diagnostics={
                "ocr_provider": "glm_ocr",
                "ocr_model": "glm-ocr:latest",
                "ocr_pages_attempted": 1,
                "ocr_text_length": 0,
                "ocr_page_results": [{"page_number": 1, "error": "glm-ocr generate failed: HTTP 500: model failed to load"}],
            },
        ),
    )
    bundle_id = _create_bundle(client)
    vendor_bill_id = _upload_pdf(client, bundle_id, "VENDOR_INVOICE", "Vendor Bill provider error.pdf", "   ")

    response = client.post(f"/api/documents/{vendor_bill_id}/extract")

    assert response.status_code == 200, response.text
    diagnostics = response.json()["metadata"]["diagnostics"]
    assert diagnostics["failure_code"] == "OCR_FAILED"
    assert diagnostics["ocr_status"] == "provider_error"
    assert "model failed to load" in diagnostics["ocr_error"]
    assert diagnostics["manual_fallback_available"] is True


def test_model_layer2_fills_missing_field_without_overwriting_rule_value(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    import app.services.extraction_service as extraction_service

    monkeypatch.setattr(
        extraction_service,
        "settings",
        Settings(ocr_enabled=True, ocr_provider="glm_ocr", model_layer2_enabled=True, model_layer2_provider="ollama"),
    )
    monkeypatch.setattr(
        extraction_service,
        "extract_text_with_ocr",
        lambda *args, **kwargs: OcrResult(
            text="""
            Invoice No: 2526PSI25087738
            Invoice Date: 12-02-2026
            Vendor Name: SUPREME COMPUTERS INDIA P LTD
            """,
            pages=[{"page_number": 1, "ocr_text_length": 100}],
            provider="glm_ocr",
            model="glm-ocr:latest",
            diagnostics={"ocr_provider": "glm_ocr", "ocr_model": "glm-ocr:latest", "ocr_text_length": 100},
        ),
    )

    def fake_model(document_type, raw_text, expected_schema, missing_fields, diagnostics):
        diagnostics.update(
            {
                "model_layer2_used": True,
                "model_extracted_keys": ["invoice_total", "po_reference", "vendor_invoice_no"],
                "model_missing_fields": [],
                "model_response_format": "fenced_json",
                "model_response_warning": "model_response_wrapped_in_code_fence",
                "model_validation_errors": [],
            }
        )
        return {
            "fields": {
                "vendor_invoice_no": "MODEL-WRONG",
                "po_reference": "1PTR2526000467",
                "invoice_total": 554600,
            },
            "missing_required_fields": [],
            "field_metadata": {
                "vendor_invoice_no": {"field": "vendor_invoice_no", "value": "MODEL-WRONG", "source": "model_layer2", "confidence": 0.8, "evidence_text": "Invoice No: MODEL-WRONG"},
                "po_reference": {"field": "po_reference", "value": "1PTR2526000467", "source": "model_layer2", "confidence": 0.8, "evidence_text": "PO No: 1PTR2526000467"},
                "invoice_total": {"field": "invoice_total", "value": 554600, "source": "model_layer2", "confidence": 0.8, "evidence_text": "Total: 554600"},
            },
        }

    monkeypatch.setattr(extraction_service, "extract_structured_fields_with_model", fake_model)
    bundle_id = _create_bundle(client)
    vendor_bill_id = _upload_pdf(
        client,
        bundle_id,
        "VENDOR_INVOICE",
        "Vendor Bill model assist.pdf",
        " ",
    )

    payload = client.post(f"/api/documents/{vendor_bill_id}/extract").json()
    extracted = payload["metadata"]["extracted_data"]
    diagnostics = payload["metadata"]["diagnostics"]

    assert extracted["vendor_invoice_no"] == "2526PSI25087738"
    assert extracted["po_reference"] == "1PTR2526000467"
    assert extracted["invoice_total"] == 554600
    assert diagnostics["field_metadata"]["vendor_invoice_no"]["source"] == "rules"
    assert diagnostics["field_metadata"]["po_reference"]["source"] == "model_layer2"
    assert diagnostics["alternative_values"]["vendor_invoice_no"] == "MODEL-WRONG"
    assert diagnostics["model_layer2_used"] is True
    assert diagnostics["model_response_format"] == "fenced_json"
    assert diagnostics["model_response_warning"] == "model_response_wrapped_in_code_fence"
    assert diagnostics["model_validation_errors"] == []
    assert "po_reference" not in diagnostics["rules_extracted_fields"]
    assert diagnostics["rules_missing_fields"]
    assert diagnostics["model_extracted_fields"]["po_reference"] == "1PTR2526000467"
    assert diagnostics["model_field_evidence"]["po_reference"] == "PO No: 1PTR2526000467"
    assert diagnostics["final_extracted_keys"]
