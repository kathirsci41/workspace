from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import configure_database, init_db
from app.main import app


@pytest.fixture()
def client(tmp_path: Path):
    configure_database(f"sqlite:///{tmp_path / 'order_assurance_real_pdf_test.db'}")
    init_db(drop_existing=True)
    return TestClient(app)


def test_panimalar_real_pdf_regression_skips_when_fixtures_are_missing(client: TestClient):
    fixture_dir = Path(
        os.getenv(
            "ORDER_ASSURANCE_REAL_PDF_FIXTURE_DIR",
            Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "real-pdf-regression" / "panimalar",
        )
    )
    expected_path = fixture_dir / "expected.json"
    pdfs = {
        "COMPANY_INVOICE": fixture_dir / "customer-invoice.pdf",
        "COMPANY_DC": fixture_dir / "delivery-challan.pdf",
        "COMPANY_PO": fixture_dir / "vendor-po.pdf",
        "VENDOR_INVOICE": fixture_dir / "vendor-bill.pdf",
    }
    optional_customer_po = fixture_dir / "customer-po.pdf"
    if optional_customer_po.exists():
        pdfs = {"CUSTOMER_PO": optional_customer_po, **pdfs}
    missing = [path.name for path in pdfs.values() if not path.exists()]
    if missing:
        pytest.skip(f"Real/redacted Panimalar PDFs not present: {', '.join(missing)}")

    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    bundle = client.post("/api/bundles", json={"bundle_number": "OA-REAL-PANIMALAR", "customer_name": "PANIMALAR"}).json()
    document_ids: dict[str, str] = {}
    extraction_artifact: dict[str, Any] = {}
    for document_type, pdf_path in pdfs.items():
        with pdf_path.open("rb") as file_handle:
            upload = client.post(
                f"/api/bundles/{bundle['id']}/documents",
                data={"document_type": document_type},
                files={"file": (pdf_path.name, file_handle, "application/pdf")},
            )
        assert upload.status_code == 201, upload.text
        document_ids[document_type] = upload.json()["id"]
        extract = client.post(f"/api/documents/{document_ids[document_type]}/extract")
        assert extract.status_code == 200, extract.text
        extraction_artifact[document_type] = _safe_extraction_artifact(extract.json())

    client.patch(
        f"/api/documents/{document_ids['VENDOR_INVOICE']}/extracted-data",
        json={"fields": expected["manual_vendor_bill"], "actor": "qa", "reason": "OCR failed"},
    )
    summary = client.get(f"/api/bundles/{bundle['id']}/verification-summary").json()
    artifact_dir = Path(__file__).resolve().parents[3] / "tests" / "artifacts" / "real-pdf-regression" / "panimalar"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "extraction-results.json").write_text(json.dumps(extraction_artifact, indent=2), encoding="utf-8")
    (artifact_dir / "verification-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    assert summary["bundle_status"] == expected["bundle_status"]
    assert summary["customer_delivery_status"] == expected["customer_delivery_status"]
    assert summary["vendor_procurement_status"] == expected["vendor_procurement_status"]
    assert any(issue.get("difference") == expected["difference"] for issue in summary["issues"])


@pytest.mark.skipif(
    os.getenv("MODEL_LAYER2_LIVE_TESTS", "").lower() not in {"1", "true", "yes"},
    reason="Real/redacted Model Layer 2 validation requires MODEL_LAYER2_LIVE_TESTS=true.",
)
def test_scanned_real_pdf_layer2_is_optional_and_compares_expected_fields_when_supplied(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    import app.services.extraction_service as extraction_service

    fixture_dir = Path(
        os.getenv(
            "ORDER_ASSURANCE_REAL_PDF_FIXTURE_DIR",
            Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "real-pdf-regression" / "panimalar",
        )
    )
    expected_path = fixture_dir / "expected.json"
    pdfs = {
        "CUSTOMER_PO": fixture_dir / "customer-po.pdf",
        "COMPANY_INVOICE": fixture_dir / "customer-invoice.pdf",
        "COMPANY_DC": fixture_dir / "delivery-challan.pdf",
        "COMPANY_PO": fixture_dir / "vendor-po.pdf",
        "VENDOR_INVOICE": fixture_dir / "vendor-bill.pdf",
    }
    missing = [path.name for path in [*pdfs.values(), expected_path] if not path.exists()]
    if missing:
        pytest.skip(f"Real/redacted Layer 2 fixtures not present: {', '.join(missing)}")

    monkeypatch.setattr(
        extraction_service,
        "settings",
        Settings(
            digital_text_enabled=True,
            ocr_enabled=True,
            ocr_provider="glm_ocr",
            ocr_context_length=8192,
            structured_rules_enabled=True,
            model_layer2_enabled=True,
            model_layer2_provider="ollama",
            model_layer2_model="gemma4:31b-cloud",
        ),
    )
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    bundle = client.post("/api/bundles", json={"bundle_number": "OA-REAL-LAYER2", "customer_name": "PANIMALAR"}).json()
    document_ids: dict[str, str] = {}
    artifact: dict[str, Any] = {}
    ocr_previews: list[str] = []
    for document_type, pdf_path in pdfs.items():
        with pdf_path.open("rb") as file_handle:
            uploaded = client.post(
                f"/api/bundles/{bundle['id']}/documents",
                data={"document_type": document_type},
                files={"file": (pdf_path.name, file_handle, "application/pdf")},
        )
        assert uploaded.status_code == 201, uploaded.text
        document_ids[document_type] = uploaded.json()["id"]
        extracted = client.post(f"/api/documents/{document_ids[document_type]}/extract")
        assert extracted.status_code == 200, extracted.text
        artifact[document_type] = _safe_extraction_artifact(extracted.json())
        diagnostics = ((extracted.json().get("metadata") or {}).get("diagnostics") or {})
        if diagnostics.get("ocr_text_length"):
            ocr_previews.append(f"[{document_type}] OCR text length: {diagnostics.get('ocr_text_length')}")

        expected_fields = (expected.get("model_layer2_expected") or {}).get(document_type, {})
        actual_fields = artifact[document_type]["extracted_data"]
        for field, value in expected_fields.items():
            assert actual_fields.get(field) == value

    vendor_fields = artifact["VENDOR_INVOICE"]["extracted_data"]
    proven_vendor_reference = any(vendor_fields.get(field) for field in ("po_reference", "customer_ref_no", "external_doc_no"))
    summary_before_manual = client.get(f"/api/bundles/{bundle['id']}/verification-summary").json()
    manual_vendor_bill_applied = not proven_vendor_reference or not vendor_fields.get("invoice_total")
    if not proven_vendor_reference and vendor_fields.get("invoice_total"):
        assert not any(issue.get("difference") == expected["difference"] for issue in summary_before_manual["issues"])
    if manual_vendor_bill_applied:
        manual = client.patch(
            f"/api/documents/{document_ids['VENDOR_INVOICE']}/extracted-data",
            json={"fields": expected["manual_vendor_bill"], "actor": "qa", "reason": "Controlled real-PDF fallback"},
        )
        assert manual.status_code == 200, manual.text

    summary = client.get(f"/api/bundles/{bundle['id']}/verification-summary").json()
    assert summary["bundle_status"] == expected["bundle_status"]
    assert summary["customer_delivery_status"] == expected["customer_delivery_status"]
    assert summary["vendor_procurement_status"] == expected["vendor_procurement_status"]
    assert any(issue.get("difference") == expected["difference"] for issue in summary["issues"])

    artifact_dir = Path(__file__).resolve().parents[3] / "tests" / "artifacts" / "real-pdf-regression" / "panimalar"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "extraction-comparison.json").write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    (artifact_dir / "customer-po-layer-result.json").write_text(json.dumps(artifact["CUSTOMER_PO"], indent=2), encoding="utf-8")
    (artifact_dir / "vendor-bill-layer-result.json").write_text(json.dumps(artifact["VENDOR_INVOICE"], indent=2), encoding="utf-8")
    (artifact_dir / "verification-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (artifact_dir / "model-layer2-output-redacted.json").write_text(
        json.dumps(
            {
                document_type: {
                    "model_layer2_used": result["diagnostics"].get("model_layer2_used"),
                    "model_extracted_fields": result["diagnostics"].get("model_extracted_fields"),
                    "model_field_evidence": result["diagnostics"].get("model_field_evidence"),
                    "model_response_format": result["diagnostics"].get("model_response_format"),
                    "model_response_warning": result["diagnostics"].get("model_response_warning"),
                    "model_validation_errors": result["diagnostics"].get("model_validation_errors"),
                }
                for document_type, result in artifact.items()
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (artifact_dir / "ocr-output-preview-redacted.txt").write_text(
        "\n\n".join(ocr_previews) if ocr_previews else "No OCR text was captured for supplied documents.",
        encoding="utf-8",
    )
    (artifact_dir / "controlled-run-context.json").write_text(
        json.dumps(
            {
                "ocr_enabled": True,
                "ocr_provider": "glm_ocr",
                "ocr_context_length": 8192,
                "model_layer2_enabled": True,
                "model_layer2_model": "gemma4:31b-cloud",
                "manual_vendor_bill_applied": manual_vendor_bill_applied,
                "summary_before_manual": summary_before_manual,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _safe_extraction_artifact(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata") or {}
    diagnostics = metadata.get("diagnostics") or {}
    extracted_data = {
        key: value
        for key, value in (metadata.get("extracted_data") or {}).items()
        if not str(key).startswith("raw_")
    }
    allowed_diagnostics = {
        key: diagnostics.get(key)
        for key in (
            "digital_text_length",
            "digital_text_used",
            "ocr_enabled",
            "ocr_provider",
            "ocr_model",
            "ocr_status",
            "ocr_text_length",
            "ocr_page_results",
            "parser_route",
            "extracted_field_keys",
            "missing_required_fields",
            "rules_extracted_fields",
            "rules_missing_fields",
            "rules_schema_missing_fields",
            "failure_code",
            "failure_reason",
            "manual_fallback_available",
            "model_layer2_used",
            "model_response_format",
            "model_response_warning",
            "model_validation_errors",
            "model_extracted_keys",
            "model_extracted_fields",
            "model_field_evidence",
            "final_extracted_keys",
            "final_missing_fields",
            "confidence_summary",
        )
    }
    return {
        "document_type": (payload.get("document") or {}).get("document_type"),
        "document_status": (payload.get("document") or {}).get("status"),
        "metadata_status": metadata.get("status"),
        "extracted_data": extracted_data,
        "diagnostics": allowed_diagnostics,
    }
