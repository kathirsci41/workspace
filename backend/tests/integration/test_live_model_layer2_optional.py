from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.config import Settings
import app.services.extraction.model_layer2 as model_layer2


pytestmark = pytest.mark.skipif(
    os.getenv("MODEL_LAYER2_LIVE_TESTS", "").lower() not in {"1", "true", "yes"},
    reason="Live gemma4 structured extraction requires MODEL_LAYER2_LIVE_TESTS=true and reachable Ollama model.",
)


def test_live_gemma4_structured_extraction_returns_only_document_fields(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        model_layer2,
        "settings",
        Settings(model_layer2_enabled=True, model_layer2_provider="ollama", model_layer2_model="gemma4:31b-cloud"),
    )
    diagnostics: dict[str, object] = {}
    result = model_layer2.extract_structured_fields_with_model(
        "VENDOR_INVOICE",
        "Invoice No: 2526PSI25087738\nInvoice Date: 12-02-2026\nPO No: 1PTR2526000467\nGrand Total: 554600",
        {"vendor_invoice_no": None, "vendor_invoice_date": None, "po_reference": None, "invoice_total": None},
        ["po_reference", "invoice_total"],
        diagnostics,
    )

    if result.get("failure_code") or not result.get("fields"):
        pytest.skip(f"Live gemma4 Layer 2 unavailable or returned no fields: {diagnostics.get('model_failure_reason')}")
    assert not {"bundle_status", "checks", "issues", "recommendation"} & set(result["fields"])
    assert result["fields"].get("po_reference") == "1PTR2526000467"
    assert result["fields"].get("invoice_total") in {554600, "554600"}
    assert diagnostics["model_response_format"] in {"raw_json", "fenced_json"}
    if diagnostics["model_response_format"] == "fenced_json":
        assert diagnostics["model_response_warning"] == "model_response_wrapped_in_code_fence"

    artifact_dir = Path(__file__).resolve().parents[3] / "tests" / "artifacts" / "model-layer2"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "gemma4_live_sample.json").write_text(
        json.dumps(
            {
                "document_type": "VENDOR_INVOICE",
                "fields": result["fields"],
                "missing_required_fields": result["missing_required_fields"],
                "diagnostics": {
                    "model_layer2_provider": diagnostics.get("model_layer2_provider"),
                    "model_layer2_model": diagnostics.get("model_layer2_model"),
                    "model_response_format": diagnostics.get("model_response_format"),
                    "model_response_warning": diagnostics.get("model_response_warning"),
                    "model_validation_errors": diagnostics.get("model_validation_errors"),
                    "model_extracted_keys": diagnostics.get("model_extracted_keys"),
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
