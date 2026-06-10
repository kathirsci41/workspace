from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

from app.config import settings
from app.services.extraction.model_prompts import GLOBAL_STRUCTURED_EXTRACTION_PROMPT, prompt_for


BLOCKED_KEYS = {
    "bundle_status",
    "customer_delivery_status",
    "vendor_procurement_status",
    "checks",
    "issues",
    "recommendation",
    "business_decision",
    "validation_status",
}
REFERENCE_FIELDS = {"po_reference", "customer_ref_no", "external_doc_no"}
MODEL_FAILURE_CODE = "MODEL_LAYER2_FAILED"
FENCED_JSON_PATTERN = re.compile(r"\A```(?:json)?\s*(?P<payload>.*?)\s*```\Z", flags=re.IGNORECASE | re.DOTALL)


def extract_structured_fields_with_model(
    document_type: str,
    raw_text: str,
    expected_schema: dict[str, Any],
    missing_fields: list[str],
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    diagnostics.update(
        {
            "model_layer2_enabled": settings.model_layer2_enabled,
            "model_layer2_provider": settings.model_layer2_provider,
            "model_layer2_model": settings.model_layer2_model,
            "model_layer2_used": False,
            "model_extracted_keys": [],
            "model_missing_fields": list(missing_fields),
        }
    )
    if not settings.model_layer2_enabled:
        return _empty_result()
    if settings.model_layer2_provider != "ollama":
        return _failed_result(diagnostics, f"Unsupported model provider: {settings.model_layer2_provider}")

    payload = {
        "model": settings.model_layer2_model,
        "system": GLOBAL_STRUCTURED_EXTRACTION_PROMPT,
        "prompt": _build_prompt(document_type, raw_text, expected_schema, missing_fields),
        "format": "json",
        "stream": False,
        "options": {"num_ctx": settings.model_layer2_context_length},
    }
    diagnostics["model_layer2_used"] = True
    last_error: Exception | None = None
    for _ in range(max(1, settings.model_layer2_retry_attempts + 1)):
        try:
            request = urllib.request.Request(
                f"{settings.model_layer2_base_url.rstrip('/')}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=settings.model_layer2_timeout_seconds) as response:  # noqa: S310 - configured local/cloud Ollama endpoint
                body = json.loads(response.read().decode("utf-8"))
            parsed = validate_model_json(str(body.get("response") or ""), expected_schema)
            diagnostics.update(
                {
                    "model_version": f"{settings.model_layer2_provider}:{settings.model_layer2_model}",
                    "model_extracted_keys": sorted(parsed["fields"].keys()),
                    "model_missing_fields": parsed["missing_required_fields"],
                    "model_failure_reason": parsed.get("failure_reason"),
                }
            )
            if parsed.get("diagnostics"):
                diagnostics["model_diagnostics"] = parsed["diagnostics"]
                diagnostics["model_response_format"] = parsed["diagnostics"].get("model_response_format")
                diagnostics["model_response_warning"] = parsed["diagnostics"].get("model_response_warning")
                diagnostics["model_validation_errors"] = parsed["diagnostics"].get("model_validation_errors", [])
            return parsed
        except Exception as exc:
            last_error = exc
    return _failed_result(diagnostics, f"Model Layer 2 request failed: {last_error}")


def validate_model_json(raw_response: str, expected_schema: dict[str, Any]) -> dict[str, Any]:
    payload, response_format, response_warning, validation_errors = _decode_single_json_object(raw_response)
    if payload is None:
        return _empty_result(
            failure_code=MODEL_FAILURE_CODE,
            failure_reason="Model Layer 2 did not return valid JSON.",
            response_format=response_format,
            response_warning=response_warning,
            validation_errors=validation_errors,
        )

    warnings: list[str] = [response_warning] if response_warning else []
    forbidden = sorted(key for key in BLOCKED_KEYS if key in payload)
    raw_fields = payload.get("extracted_fields")
    if not isinstance(raw_fields, dict):
        return _empty_result(
            failure_code=MODEL_FAILURE_CODE,
            failure_reason="Model Layer 2 JSON is missing extracted_fields.",
            response_format=response_format,
            response_warning=response_warning,
            validation_errors=[*validation_errors, "model_json_missing_extracted_fields"],
        )
    forbidden.extend(sorted(key for key in BLOCKED_KEYS if key in raw_fields))
    if forbidden:
        warnings.append("Forbidden output fields removed: " + ", ".join(sorted(set(forbidden))))

    expected = set(expected_schema)
    unsupported = sorted(key for key in raw_fields if key not in expected and key not in BLOCKED_KEYS)
    if unsupported:
        warnings.append("Unsupported extracted fields removed: " + ", ".join(unsupported))
    fields = {
        key: value
        for key, value in raw_fields.items()
        if key in expected and key not in BLOCKED_KEYS and value not in (None, "")
    }
    evidence = payload.get("field_evidence") if isinstance(payload.get("field_evidence"), dict) else {}
    missing = payload.get("missing_required_fields") if isinstance(payload.get("missing_required_fields"), list) else []
    missing = [field for field in missing if field in expected]
    for field in sorted(REFERENCE_FIELDS & set(fields)):
        if not evidence.get(field):
            fields.pop(field)
            validation_errors.append(f"reference_field_missing_evidence:{field}")
            warnings.append(f"Model reference field removed without evidence: {field}")
            if field in expected and field not in missing:
                missing.append(field)
    field_metadata = {
        key: {
            "field": key,
            "value": value,
            "confidence": 0.8 if evidence.get(key) else 0.6,
            "source": "model_layer2",
            "evidence_text": evidence.get(key),
        }
        for key, value in fields.items()
    }
    nested = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), dict) else {}
    existing_warnings = nested.get("warnings") if isinstance(nested.get("warnings"), list) else []
    model_diagnostics = {
        "parser_route": "model_layer2",
        "warnings": [*existing_warnings, *warnings],
        "alternative_values": nested.get("alternative_values") if isinstance(nested.get("alternative_values"), dict) else {},
        "model_response_format": response_format,
        "model_response_warning": response_warning,
        "model_validation_errors": validation_errors,
    }
    return {
        "fields": fields,
        "missing_required_fields": missing,
        "field_metadata": field_metadata,
        "failure_code": None,
        "failure_reason": None,
        "diagnostics": model_diagnostics,
    }


def _decode_single_json_object(raw_response: str) -> tuple[dict[str, Any] | None, str, str | None, list[str]]:
    text = str(raw_response or "").strip()
    if not text:
        return None, "invalid", None, ["model_response_empty"]

    response_format = "raw_json"
    warning: str | None = None
    candidate = text
    fenced = FENCED_JSON_PATTERN.fullmatch(text)
    if fenced:
        response_format = "fenced_json"
        warning = "model_response_wrapped_in_code_fence"
        candidate = fenced.group("payload").strip()
    elif "```" in text:
        return None, "rejected", None, ["model_response_contains_extraneous_markdown_or_text"]
    elif not (text.startswith("{") and text.endswith("}")):
        response_format = "rejected" if "{" in text or "}" in text else "invalid"
        return None, response_format, None, ["model_response_contains_prose_or_non_object_content"]

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        invalid_format = "rejected" if exc.msg == "Extra data" else "invalid"
        return None, invalid_format, warning, [f"model_json_validation_error:{exc.msg}"]
    if not isinstance(payload, dict):
        return None, "rejected", warning, ["model_response_is_not_json_object"]
    return payload, response_format, warning, []


def _build_prompt(document_type: str, raw_text: str, expected_schema: dict[str, Any], missing_fields: list[str]) -> str:
    return (
        f"{prompt_for(document_type)}\n\n"
        f"Requested document_type: {str(document_type).upper()}\n"
        f"Allowed extracted_fields schema: {json.dumps(list(expected_schema.keys()))}\n"
        f"Fields still missing from deterministic extraction: {json.dumps(missing_fields)}\n"
        "Only extract values clearly visible in the document text below.\n\n"
        f"Document text:\n{raw_text[:12000]}"
    )


def _failed_result(diagnostics: dict[str, Any], reason: str) -> dict[str, Any]:
    diagnostics["model_failure_code"] = MODEL_FAILURE_CODE
    diagnostics["model_failure_reason"] = reason
    return _empty_result(failure_code=MODEL_FAILURE_CODE, failure_reason=reason)


def _empty_result(
    *,
    failure_code: str | None = None,
    failure_reason: str | None = None,
    response_format: str | None = None,
    response_warning: str | None = None,
    validation_errors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "fields": {},
        "missing_required_fields": [],
        "field_metadata": {},
        "failure_code": failure_code,
        "failure_reason": failure_reason,
        "diagnostics": {
            "parser_route": "model_layer2",
            "warnings": [response_warning] if response_warning else [],
            "alternative_values": {},
            "model_response_format": response_format,
            "model_response_warning": response_warning,
            "model_validation_errors": validation_errors or [],
        },
    }
