from __future__ import annotations

import json
from urllib.error import URLError

import pytest

from app.config import Settings
import app.services.extraction.model_layer2 as model_layer2
from app.services.extraction.model_prompts import GLOBAL_STRUCTURED_EXTRACTION_PROMPT, prompt_for


class _Response:
    status = 200

    def __init__(self, response: str) -> None:
        self._body = json.dumps({"response": response}).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return self._body


@pytest.mark.parametrize("document_type", ["CUSTOMER_PO", "COMPANY_INVOICE", "COMPANY_DC", "COMPANY_PO", "VENDOR_INVOICE"])
def test_model_prompt_exists_for_supported_document_types(document_type: str):
    prompt = prompt_for(document_type)

    assert "Required fields:" in prompt
    assert "Do not perform business validation" in GLOBAL_STRUCTURED_EXTRACTION_PROMPT
    assert "bundle_status" in GLOBAL_STRUCTURED_EXTRACTION_PROMPT
    assert "line-item description matching" in GLOBAL_STRUCTURED_EXTRACTION_PROMPT
    assert "Do not use Markdown." in GLOBAL_STRUCTURED_EXTRACTION_PROMPT
    assert 'The first character must be "{" and the last character must be "}".' in GLOBAL_STRUCTURED_EXTRACTION_PROMPT


def test_model_layer2_valid_json_extracts_only_schema_fields_and_evidence(monkeypatch):
    monkeypatch.setattr(
        model_layer2,
        "settings",
        Settings(model_layer2_enabled=True, model_layer2_model="gemma4:31b-cloud"),
    )
    captured = {}

    def fake_urlopen(request, timeout):
        captured.update(json.loads(request.data.decode("utf-8")))
        return _Response(
            json.dumps(
                {
                    "document_type": "VENDOR_INVOICE",
                    "extracted_fields": {"po_reference": "1PTR2526000467", "invoice_total": 554600, "unsupported": "x"},
                    "field_evidence": {"po_reference": "PO No: 1PTR2526000467", "invoice_total": "Grand Total: 554600"},
                    "missing_required_fields": [],
                    "confidence": 0.84,
                    "diagnostics": {"warnings": [], "alternative_values": {}},
                }
            )
        )

    monkeypatch.setattr(model_layer2.urllib.request, "urlopen", fake_urlopen)
    diagnostics: dict[str, object] = {}
    result = model_layer2.extract_structured_fields_with_model(
        "VENDOR_INVOICE",
        "PO No: 1PTR2526000467\nGrand Total: 554600",
        {"po_reference": None, "invoice_total": None},
        ["po_reference", "invoice_total"],
        diagnostics,
    )

    assert result["fields"] == {"po_reference": "1PTR2526000467", "invoice_total": 554600}
    assert result["field_metadata"]["po_reference"]["evidence_text"] == "PO No: 1PTR2526000467"
    assert result["field_metadata"]["po_reference"]["source"] == "model_layer2"
    assert captured["model"] == "gemma4:31b-cloud"
    assert captured["options"] == {"num_ctx": 8192}
    assert captured["format"] == "json"
    assert diagnostics["model_layer2_used"] is True
    assert diagnostics["model_extracted_keys"] == ["invoice_total", "po_reference"]
    assert diagnostics["model_response_format"] == "raw_json"
    assert diagnostics["model_response_warning"] is None
    assert diagnostics["model_validation_errors"] == []
    assert "Unsupported extracted fields removed: unsupported" in result["diagnostics"]["warnings"]


def test_model_layer2_accepts_single_fenced_json_object_with_warning():
    result = model_layer2.validate_model_json(
        """```json
{"document_type":"VENDOR_INVOICE","extracted_fields":{"invoice_total":554600},"field_evidence":{"invoice_total":"Grand Total: 554600"},"missing_required_fields":[]}
```""",
        {"invoice_total": None},
    )

    assert result["fields"] == {"invoice_total": 554600}
    assert result["diagnostics"]["model_response_format"] == "fenced_json"
    assert result["diagnostics"]["model_response_warning"] == "model_response_wrapped_in_code_fence"
    assert "model_response_wrapped_in_code_fence" in result["diagnostics"]["warnings"]


def test_model_layer2_rejects_prose_wrapped_json():
    result = model_layer2.validate_model_json(
        'Here is the result:\n{"extracted_fields":{"invoice_total":554600}}',
        {"invoice_total": None},
    )

    assert result["fields"] == {}
    assert result["failure_code"] == "MODEL_LAYER2_FAILED"
    assert result["diagnostics"]["model_response_format"] == "rejected"
    assert result["diagnostics"]["model_validation_errors"]


def test_model_layer2_rejects_multiple_json_objects():
    result = model_layer2.validate_model_json(
        '{"extracted_fields":{"invoice_total":554600}}\n{"extracted_fields":{"po_reference":"1PTR2526000467"}}',
        {"invoice_total": None, "po_reference": None},
    )

    assert result["fields"] == {}
    assert result["failure_code"] == "MODEL_LAYER2_FAILED"
    assert result["diagnostics"]["model_response_format"] == "rejected"


def test_model_layer2_does_not_accept_vendor_reference_without_evidence():
    result = model_layer2.validate_model_json(
        json.dumps(
            {
                "document_type": "VENDOR_INVOICE",
                "extracted_fields": {"po_reference": "1PTR2526000467", "invoice_total": 554600},
                "field_evidence": {"invoice_total": "Grand Total: 554600"},
                "missing_required_fields": [],
            }
        ),
        {"po_reference": None, "invoice_total": None},
    )

    assert result["fields"] == {"invoice_total": 554600}
    assert result["missing_required_fields"] == ["po_reference"]
    assert "reference_field_missing_evidence:po_reference" in result["diagnostics"]["model_validation_errors"]


def test_model_layer2_invalid_json_fails_softly(monkeypatch):
    monkeypatch.setattr(model_layer2, "settings", Settings(model_layer2_enabled=True))
    monkeypatch.setattr(model_layer2.urllib.request, "urlopen", lambda request, timeout: _Response("not-json"))
    diagnostics: dict[str, object] = {}

    result = model_layer2.extract_structured_fields_with_model(
        "CUSTOMER_PO", "text", {"customer_po_no": None}, ["customer_po_no"], diagnostics
    )

    assert result["fields"] == {}
    assert result["failure_code"] == "MODEL_LAYER2_FAILED"
    assert diagnostics["model_layer2_used"] is True
    assert "valid JSON" in diagnostics["model_failure_reason"]
    assert diagnostics["model_response_format"] == "invalid"


def test_model_layer2_timeout_fails_softly(monkeypatch):
    monkeypatch.setattr(model_layer2, "settings", Settings(model_layer2_enabled=True))

    def fail(*args, **kwargs):
        raise URLError("timed out")

    monkeypatch.setattr(model_layer2.urllib.request, "urlopen", fail)
    diagnostics: dict[str, object] = {}

    result = model_layer2.extract_structured_fields_with_model(
        "CUSTOMER_PO", "text", {"customer_po_no": None}, ["customer_po_no"], diagnostics
    )

    assert result["fields"] == {}
    assert result["failure_code"] == "MODEL_LAYER2_FAILED"
    assert diagnostics["model_layer2_used"] is True
    assert "timed out" in diagnostics["model_failure_reason"]
