from __future__ import annotations

import time
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.logging_config import log_event
from app.models.document import DocumentRecord
from app.models.document_metadata import DocumentMetadataRecord
from app.repositories.reference_index import ReferenceIndexRepository
from app.services.evidence_service import EvidenceService
from app.services.extraction.digital_text_extractor import extract_pdf_text_pages, normalize_ocr_text
from app.services.extraction.glm_ocr_client import extract_text_with_ocr
from app.services.extraction.model_layer2 import extract_structured_fields_with_model
from app.services.extraction.pdf_field_locator import build_field_locations
from app.services.extraction.structured_text_parser import FailureCode, parse_structured_text


MIN_DIGITAL_TEXT_LENGTH = 25


def extract_document(db: Session, document: DocumentRecord, *, force: bool = False) -> dict[str, Any]:
    started = time.perf_counter()
    log_event(
        "extraction_started",
        bundle_id=document.order_bundle_id,
        document_id=document.id,
        document_type=document.document_type,
        force=force,
    )
    metadata = document.metadata_record
    if metadata is None:
        metadata = DocumentMetadataRecord(document_id=document.id, status="PENDING", extracted_data={}, diagnostics={})
        db.add(metadata)
        db.flush()

    document.status = "EXTRACTING"
    metadata.status = "PENDING"
    db.flush()

    existing_field_meta: dict[str, Any] = (metadata.diagnostics or {}).get("field_metadata", {})
    manual_fields: dict[str, Any] = {
        field: (metadata.extracted_data or {})[field]
        for field, details in existing_field_meta.items()
        if isinstance(details, dict)
        and details.get("source") == "manual_entry"
        and (metadata.extracted_data or {}).get(field) not in (None, "")
    }

    diagnostics: dict[str, Any] = dict(metadata.diagnostics or {})
    diagnostics["force"] = force
    diagnostics["filename"] = document.filename
    diagnostics.update(_mode_diagnostics())

    raw_text = ""
    raw_ocr_text = ""
    extraction_route = "digital"
    if settings.digital_text_enabled:
        try:
            pages = extract_pdf_text_pages(str(document.storage_path), max_pages=settings.digital_text_max_pages)
            page_lengths = [len(page.strip()) for page in pages]
            raw_text = "\n".join(pages)
            diagnostics.update(
                {
                    "page_count": len(pages),
                    "digital_text_length": len(raw_text.strip()),
                    "digital_text_page_lengths": page_lengths,
                }
            )
            _capture_digital_text_evidence(db, document, pages)
        except Exception as exc:
            diagnostics.update(
                {
                    "digital_text_length": 0,
                    "failure_code": FailureCode.TEXT_EXTRACTION_FAILED.value,
                    "failure_reason": f"Digital text extraction failed: {exc}",
                }
            )
    else:
        diagnostics.update({"digital_text_length": 0, "failure_code": FailureCode.TEXT_EXTRACTION_FAILED.value, "failure_reason": "Digital text extraction is disabled."})

    if len(raw_text.strip()) < MIN_DIGITAL_TEXT_LENGTH:
        diagnostics["digital_text_used"] = False
        extraction_route = "ocr_glm" if settings.ocr_enabled and settings.ocr_provider == "glm_ocr" else "scanned"
        if settings.ocr_enabled and settings.ocr_provider == "glm_ocr":
            try:
                ocr_started = time.perf_counter()
                log_event(
                    "ocr_started",
                    bundle_id=document.order_bundle_id,
                    document_id=document.id,
                    document_type=document.document_type,
                    ocr_provider=settings.ocr_provider,
                    ocr_model=settings.ocr_model,
                )
                ocr_result = extract_text_with_ocr(
                    str(document.storage_path),
                    max_pages=settings.ocr_max_pages,
                    dpi=settings.ocr_dpi,
                    timeout_seconds=settings.ocr_timeout_seconds,
                )
                raw_ocr_text = ocr_result.text
                diagnostics.update(ocr_result.diagnostics)
                diagnostics["ocr_available"] = True
                page_errors = [str(page.get("error")) for page in ocr_result.pages if page.get("error")]
                if not raw_ocr_text.strip() and page_errors:
                    diagnostics.update(
                        {
                            "ocr_status": "provider_error",
                            "ocr_error": page_errors[0][:500],
                            "failure_code": FailureCode.OCR_FAILED.value,
                            "failure_reason": f"glm-ocr ({settings.ocr_model}) provider error: {page_errors[0][:300]}",
                        }
                    )
                elif len(raw_ocr_text.strip()) < settings.ocr_min_text_length:
                    diagnostics.update(
                        {
                            "ocr_status": "empty",
                            "failure_code": FailureCode.OCR_EMPTY.value,
                            "failure_reason": "glm-ocr returned no usable text.",
                        }
                    )
                else:
                    diagnostics["ocr_status"] = "text_acquired"
                ocr_event = "ocr_failed" if diagnostics.get("ocr_status") in {"provider_error", "empty"} else "ocr_completed"
                log_event(
                    ocr_event,
                    bundle_id=document.order_bundle_id,
                    document_id=document.id,
                    document_type=document.document_type,
                    ocr_status=diagnostics.get("ocr_status"),
                    ocr_text_length=len(raw_ocr_text.strip()),
                    failure_code=diagnostics.get("failure_code"),
                    failure_reason=diagnostics.get("failure_reason"),
                    duration_ms=round((time.perf_counter() - ocr_started) * 1000, 2),
                )
                _capture_ocr_text_evidence(
                    db, document,
                    ocr_text=raw_ocr_text,
                    ocr_success=(diagnostics.get("ocr_status") == "text_acquired"),
                    provider_version=ocr_result.model,
                    duration_ms=ocr_result.diagnostics.get("ocr_duration_ms"),
                    error=diagnostics.get("failure_reason") if diagnostics.get("ocr_status") != "text_acquired" else None,
                )
                text_for_parse = normalize_ocr_text(raw_ocr_text)
            except Exception as exc:
                diagnostics.update(
                    {
                        "ocr_text_length": 0,
                        "raw_ocr_text_length": 0,
                        "ocr_error": str(exc),
                        "ocr_status": "provider_error",
                        "failure_code": FailureCode.OCR_FAILED.value,
                        "failure_reason": f"glm-ocr ({settings.ocr_model}) failed: {exc}",
                    }
                )
                log_event(
                    "ocr_failed",
                    bundle_id=document.order_bundle_id,
                    document_id=document.id,
                    document_type=document.document_type,
                    failure_code=FailureCode.OCR_FAILED.value,
                    failure_reason=str(exc),
                    duration_ms=round((time.perf_counter() - ocr_started) * 1000, 2) if "ocr_started" in locals() else None,
                )
                _capture_ocr_text_evidence(
                    db, document,
                    ocr_text=None,
                    ocr_success=False,
                    error=str(exc)[:500],
                    duration_ms=round((time.perf_counter() - ocr_started) * 1000, 2) if "ocr_started" in locals() else None,
                )
                text_for_parse = ""
        elif settings.ocr_enabled:
            diagnostics.update(
                {
                    "ocr_text_length": 0,
                    "raw_ocr_text_length": 0,
                    "ocr_status": "provider_error",
                    "failure_code": FailureCode.OCR_FAILED.value,
                    "failure_reason": f"Unsupported OCR provider: {settings.ocr_provider}",
                }
            )
            text_for_parse = ""
        else:
            diagnostics.update(
                {
                    "ocr_text_length": 0,
                    "raw_ocr_text_length": 0,
                    "ocr_status": "disabled",
                    "failure_code": FailureCode.MANUAL_ENTRY_REQUIRED.value,
                    "failure_reason": "OCR is disabled; manual entry is required for scanned or low-text documents.",
                }
            )
            text_for_parse = ""
    else:
        diagnostics["digital_text_used"] = True
        diagnostics["ocr_status"] = "skipped_digital_text"
        text_for_parse = raw_text

    pre_parse_failure_code = diagnostics.get("failure_code")
    pre_parse_failure_reason = diagnostics.get("failure_reason")
    if settings.structured_rules_enabled:
        parsed = parse_structured_text(
            str(document.document_type),
            text_for_parse,
            extraction_route=extraction_route,
            filename=document.filename,
            context={"document_id": document.id},
        )
        if (
            extraction_route == "ocr_glm"
            and str(document.document_type).upper() == "VENDOR_INVOICE"
            and raw_ocr_text.strip()
        ):
            parsed, raw_ocr_text, text_for_parse, retry_diagnostics = _retry_sideways_vendor_invoice_ocr(
                document=document,
                initial_raw_ocr_text=raw_ocr_text,
                initial_parsed=parsed,
            )
            diagnostics.update(retry_diagnostics)
    else:
        parsed = {
            "fields": {},
            "missing_required_fields": [],
            "confidence": 0.0,
            "parser_route": "rules_disabled",
            "diagnostics": {"failure_code": FailureCode.STRUCTURED_PARSE_FAILED.value, "failure_reason": "Structured rules are disabled."},
            "field_metadata": {},
        }
    fields = dict(parsed["fields"])
    field_metadata = dict(parsed.get("field_metadata") or {})
    diagnostics.update(parsed["diagnostics"])
    rules_failure_code = diagnostics.get("failure_code")
    schema = _expected_schema(str(document.document_type))
    missing_for_model = _missing_schema_fields(schema, fields)
    diagnostics["rules_extracted_fields"] = dict(fields)
    diagnostics["rules_missing_fields"] = list(parsed.get("missing_required_fields") or [])
    diagnostics["rules_schema_missing_fields"] = list(missing_for_model)
    diagnostics["alternative_values"] = {}

    if settings.model_layer2_enabled and text_for_parse and missing_for_model:
        model_started = time.perf_counter()
        log_event(
            "model_layer2_started",
            bundle_id=document.order_bundle_id,
            document_id=document.id,
            document_type=document.document_type,
            missing_required_fields=missing_for_model,
        )
        model_result = extract_structured_fields_with_model(
            str(document.document_type),
            text_for_parse,
            schema,
            missing_for_model,
            diagnostics,
        )
        diagnostics["model_extracted_fields"] = dict(model_result.get("fields") or {})
        diagnostics["model_field_evidence"] = {
            field: details.get("evidence_text")
            for field, details in (model_result.get("field_metadata") or {}).items()
            if details.get("evidence_text")
        }
        _merge_model_fields(fields, field_metadata, model_result, diagnostics)
        model_event = "model_layer2_failed" if model_result.get("failure_code") else "model_layer2_completed"
        log_event(
            model_event,
            bundle_id=document.order_bundle_id,
            document_id=document.id,
            document_type=document.document_type,
            model_layer2_used=diagnostics.get("model_layer2_used"),
            extracted_field_count=len(model_result.get("fields") or {}),
            missing_required_fields=model_result.get("missing_required_fields") or [],
            failure_code=model_result.get("failure_code"),
            failure_reason=model_result.get("failure_reason"),
            duration_ms=round((time.perf_counter() - model_started) * 1000, 2),
        )
    else:
        diagnostics["model_layer2_used"] = False
        diagnostics["model_extracted_keys"] = []
        diagnostics["model_missing_fields"] = missing_for_model

    if manual_fields:
        for field, value in manual_fields.items():
            fields[field] = value
            field_metadata[field] = {
                "field": field,
                "value": value,
                "confidence": 1.0,
                "source": "manual_entry",
                "evidence_text": "preserved from prior manual correction",
            }
        diagnostics["manual_fields_preserved"] = sorted(manual_fields.keys())
    else:
        diagnostics["manual_fields_preserved"] = []

    final_missing = _missing_schema_fields(schema, fields)
    blocking_missing = [field for field in parsed.get("missing_required_fields", []) if fields.get(field) in (None, "")]
    if _failure_value(rules_failure_code) in {
        FailureCode.REQUIRED_FIELDS_MISSING.value,
        FailureCode.STRUCTURED_PARSE_FAILED.value,
    } and not blocking_missing and fields:
        diagnostics["failure_code"] = None
        diagnostics["failure_reason"] = None
    elif blocking_missing and _failure_value(rules_failure_code) == FailureCode.REQUIRED_FIELDS_MISSING.value:
        diagnostics["missing_required_fields"] = blocking_missing
        diagnostics["failure_reason"] = "Document text was acquired but required fields are missing: " + ", ".join(blocking_missing)

    if pre_parse_failure_code in {FailureCode.MANUAL_ENTRY_REQUIRED.value, FailureCode.OCR_FAILED.value}:
        diagnostics["failure_code"] = pre_parse_failure_code
        diagnostics["failure_reason"] = pre_parse_failure_reason
    if pre_parse_failure_code == FailureCode.OCR_EMPTY.value and not fields:
        diagnostics["failure_code"] = pre_parse_failure_code
        diagnostics["failure_reason"] = pre_parse_failure_reason
    field_locations = build_field_locations(
        str(document.storage_path) if document.storage_path else None,
        fields,
        field_metadata,
        digital_text_used=bool(diagnostics.get("digital_text_used")),
        extraction_route=extraction_route,
    )
    diagnostics.update(
        {
            "extraction_route": extraction_route,
            "parser_route": parsed["parser_route"],
            "parser_confidence": parsed["confidence"],
            "raw_text_length": len(raw_text.strip()),
            "raw_ocr_text_length": len(raw_ocr_text.strip()),
            "ocr_text_length": len(raw_ocr_text.strip()),
            "field_metadata": field_metadata,
            "field_locations": field_locations,
            "final_extracted_keys": sorted(fields.keys()),
            "final_missing_fields": final_missing,
            "confidence_summary": _confidence_summary(field_metadata, diagnostics.get("alternative_values", {})),
        }
    )

    extracted_data = dict(fields)

    metadata.extracted_data = extracted_data
    metadata.primary_ref_no = _primary_ref(extracted_data)
    metadata.po_ref_no = _po_ref(extracted_data)

    failure_code = diagnostics.get("failure_code")
    if failure_code:
        metadata.status = "FAILED" if failure_code in {FailureCode.TEXT_EXTRACTION_FAILED.value, FailureCode.OCR_EMPTY.value, FailureCode.OCR_FAILED.value, FailureCode.STRUCTURED_PARSE_FAILED.value} else "MANUAL_ENTRY"
        metadata.last_error = f"{failure_code}: {diagnostics.get('failure_reason') or 'Extraction requires review.'}"
        document.status = "EXTRACTION_FAILED"
        document.last_error = metadata.last_error
    else:
        metadata.status = "EXTRACTED"
        metadata.last_error = None
        document.status = "PENDING_REVIEW"
        document.last_error = None

    references = ReferenceIndexRepository(db).replace_for_document(
        document.id,
        extracted_data,
        document.order_bundle_id,
        document_type=document.document_type,
        diagnostics=diagnostics,
    )
    log_event(
        "reference_index_rebuilt",
        bundle_id=document.order_bundle_id,
        document_id=document.id,
        document_type=document.document_type,
        reference_count=len(references),
    )
    _record_extraction_run(diagnostics, status=metadata.status)
    metadata.diagnostics = diagnostics
    db.flush()
    event = "extraction_failed" if failure_code else "extraction_completed"
    log_event(
        event,
        bundle_id=document.order_bundle_id,
        document_id=document.id,
        document_type=document.document_type,
        extraction_route=diagnostics.get("extraction_route"),
        parser_route=diagnostics.get("parser_route"),
        failure_code=diagnostics.get("failure_code"),
        failure_reason=diagnostics.get("failure_reason"),
        ocr_status=diagnostics.get("ocr_status"),
        ocr_text_length=diagnostics.get("ocr_text_length"),
        model_layer2_used=diagnostics.get("model_layer2_used"),
        extracted_field_count=len(fields),
        missing_required_fields=diagnostics.get("missing_required_fields"),
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    return {"document": document, "metadata": metadata, "references": references}


def _retry_sideways_vendor_invoice_ocr(
    *,
    document: DocumentRecord,
    initial_raw_ocr_text: str,
    initial_parsed: dict[str, Any],
) -> tuple[dict[str, Any], str, str, dict[str, Any]]:
    target_fields = ("vendor_invoice_no", "po_reference", "taxable_amount")
    parsed = initial_parsed
    raw_ocr_text = initial_raw_ocr_text
    normalized_text = normalize_ocr_text(raw_ocr_text)
    attempts: list[dict[str, Any]] = []
    recovered = {field for field in target_fields if parsed.get("fields", {}).get(field) not in (None, "")}
    if len(recovered) == len(target_fields):
        return parsed, raw_ocr_text, normalized_text, {
            "ocr_orientation_retry_used": False,
            "ocr_orientation_retries": attempts,
        }

    for rotation_degrees in (0, 90, 270):
        try:
            retry_result = extract_text_with_ocr(
                str(document.storage_path),
                max_pages=settings.ocr_max_pages,
                dpi=settings.ocr_dpi,
                timeout_seconds=settings.ocr_timeout_seconds,
                rotation_degrees=rotation_degrees,
            )
            retry_text = retry_result.text.strip()
            candidate_raw_text = "\n".join(part for part in (raw_ocr_text, retry_text) if part).strip()
            candidate_normalized = normalize_ocr_text(candidate_raw_text)
            candidate_parsed = parse_structured_text(
                str(document.document_type),
                candidate_normalized,
                extraction_route="ocr_glm",
                filename=document.filename,
                context={"document_id": document.id},
            )
            candidate_recovered = {
                field
                for field in target_fields
                if candidate_parsed.get("fields", {}).get(field) not in (None, "")
            }
            newly_recovered = sorted(candidate_recovered - recovered)
            attempts.append(
                {
                    "rotation_degrees": rotation_degrees,
                    "ocr_text_length": len(retry_text),
                    "newly_recovered_fields": newly_recovered,
                }
            )
            if len(candidate_recovered) > len(recovered):
                parsed = candidate_parsed
                raw_ocr_text = candidate_raw_text
                normalized_text = candidate_normalized
                recovered = candidate_recovered
            if len(recovered) == len(target_fields):
                break
        except Exception as exc:
            attempts.append(
                {
                    "rotation_degrees": rotation_degrees,
                    "ocr_text_length": 0,
                    "newly_recovered_fields": [],
                    "error": str(exc)[:500],
                }
            )

    return parsed, raw_ocr_text, normalized_text, {
        "ocr_orientation_retry_used": any(attempt.get("newly_recovered_fields") for attempt in attempts),
        "ocr_orientation_retries": attempts,
    }


def _primary_ref(data: dict[str, Any]) -> str | None:
    for key in ("customer_po_no", "customer_order_no", "invoice_no", "dc_no", "vendor_po_no", "vendor_invoice_no"):
        if data.get(key):
            return str(data[key])
    return None


def _po_ref(data: dict[str, Any]) -> str | None:
    for key in ("customer_po_no", "customer_order_no", "vendor_po_no", "po_reference", "customer_ref_no", "external_doc_no"):
        if data.get(key):
            return str(data[key])
    return None


def _mode_diagnostics() -> dict[str, Any]:
    return {
        "digital_text_enabled": settings.digital_text_enabled,
        "digital_text_max_pages": settings.digital_text_max_pages,
        "evidence_capture_enabled": settings.evidence_capture_enabled,
        "digital_text_used": False,
        "ocr_enabled": settings.ocr_enabled,
        "ocr_provider": settings.ocr_provider,
        "ocr_model": settings.ocr_model,
        "ocr_base_url_host_only": _host_only(settings.ocr_base_url),
        "ocr_dpi": settings.ocr_dpi,
        "ocr_max_pages": settings.ocr_max_pages,
        "ocr_timeout_seconds": settings.ocr_timeout_seconds,
        "ocr_min_text_length": settings.ocr_min_text_length,
        "ocr_available": settings.ocr_enabled and settings.ocr_provider == "glm_ocr",
        "ocr_status": "not_attempted",
        "structured_rules_enabled": settings.structured_rules_enabled,
        "model_layer2_enabled": settings.model_layer2_enabled,
        "model_layer2_provider": settings.model_layer2_provider,
        "model_layer2_model": settings.model_layer2_model,
        "model_layer2_used": False,
        "model_extracted_keys": [],
        "model_extracted_fields": {},
        "model_field_evidence": {},
        "model_missing_fields": [],
        "model_failure_reason": None,
        "model_response_format": None,
        "model_response_warning": None,
        "model_validation_errors": [],
        "alternative_values": {},
        "manual_fallback_available": True,
    }


def _host_only(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return parsed.netloc or parsed.path


def _expected_schema(document_type: str) -> dict[str, Any]:
    doc_type = document_type.upper()
    schemas = {
        "CUSTOMER_PO": {"customer_po_no": None, "customer_po_date": None, "customer_name": None, "billing_address": None, "delivery_address": None, "subtotal_amount": None, "tax_amount": None, "grand_total": None, "total_quantity": None},
        "COMPANY_INVOICE": {"invoice_no": None, "invoice_date": None, "customer_order_no": None, "so_no": None, "customer_name": None, "customer_address": None, "taxable_amount": None, "tax_amount": None, "net_amount": None},
        "COMPANY_DC": {"dc_no": None, "dc_date": None, "customer_order_no": None, "so_no": None, "customer_name": None, "delivery_address": None, "total_quantity": None, "estimated_amount": None},
        "COMPANY_PO": {"vendor_po_no": None, "vendor_po_date": None, "vendor_name": None, "part_shipment_allowed": None, "mode_of_bill": None, "taxable_amount": None, "tax_amount": None, "net_amount": None},
        "VENDOR_INVOICE": {"vendor_invoice_no": None, "vendor_invoice_date": None, "vendor_name": None, "po_reference": None, "customer_ref_no": None, "external_doc_no": None, "taxable_amount": None, "tax_amount": None, "invoice_total": None},
    }
    return schemas.get(doc_type, {})


def _missing_schema_fields(schema: dict[str, Any], fields: dict[str, Any]) -> list[str]:
    return [field for field in schema if fields.get(field) in (None, "")]


def _merge_model_fields(
    fields: dict[str, Any],
    field_metadata: dict[str, dict[str, Any]],
    model_result: dict[str, Any],
    diagnostics: dict[str, Any],
) -> None:
    alternatives = dict(diagnostics.get("alternative_values") or {})
    warnings = list(diagnostics.get("merge_warnings") or [])
    for field, value in (model_result.get("fields") or {}).items():
        if value in (None, ""):
            continue
        if fields.get(field) in (None, ""):
            fields[field] = value
            details = (model_result.get("field_metadata") or {}).get(field)
            if details:
                field_metadata[field] = details
        elif fields[field] != value:
            alternatives[field] = value
            warnings.append(f"Rules value retained for {field}; model returned an alternative value.")
    for field, value in ((model_result.get("diagnostics") or {}).get("alternative_values") or {}).items():
        alternatives.setdefault(field, value)
    diagnostics["alternative_values"] = alternatives
    diagnostics["merge_warnings"] = warnings


def _failure_value(code: Any) -> str | None:
    return code.value if isinstance(code, FailureCode) else code


def _confidence_summary(field_metadata: dict[str, dict[str, Any]], alternatives: dict[str, Any]) -> str:
    rules = sum(1 for details in field_metadata.values() if details.get("source") == "rules")
    model = sum(1 for details in field_metadata.values() if details.get("source") == "model_layer2")
    manual = sum(1 for details in field_metadata.values() if details.get("source") == "manual_entry")
    return f"rules={rules}; model_layer2={model}; manual_entry={manual}; conflicts={len(alternatives)}"


def _capture_digital_text_evidence(
    db: Session, document: DocumentRecord, pages: list[str]
) -> None:
    """Record each digital PDF page as a text_sources row.

    Uses a fresh module attribute access for settings so that replace_settings()
    in tests is reflected correctly. Silently logs and returns on any error so
    extraction is never disrupted.
    """
    import app.config as _cfg  # module reference tracks replace_settings() rebinds
    cur = _cfg.settings
    if not cur.evidence_capture_enabled:
        return
    try:
        svc = EvidenceService(db)
        svc_settings = {"max_pages": cur.digital_text_max_pages}
        for page_number, page_text in enumerate(pages, start=1):
            svc.record_text_source(
                document_id=document.id,
                page_number=page_number,
                source_type="digital_text",
                provider="digital_pdf",
                settings=svc_settings,
                image_data=None,
                success=True,
                raw_text=page_text,
            )
    except Exception as exc:
        log_event("evidence_capture_failed", document_id=document.id, error=str(exc)[:200])


def _capture_ocr_text_evidence(
    db: Session,
    document: DocumentRecord,
    *,
    ocr_text: str | None,
    ocr_success: bool,
    provider_version: str | None = None,
    duration_ms: int | float | None = None,
    error: str | None = None,
) -> None:
    """Record the combined OCR text output as a single text_sources row at page_number=1.

    Uses a fresh module attribute access for settings so replace_settings() in tests
    is reflected correctly. Silently logs and returns on any error so extraction is
    never disrupted.
    """
    import app.config as _cfg  # module reference tracks replace_settings() rebinds
    cur = _cfg.settings
    if not cur.evidence_capture_enabled:
        return
    try:
        svc = EvidenceService(db)
        svc_settings = {
            "provider": cur.ocr_provider,
            "model": cur.ocr_model,
            "max_pages": cur.ocr_max_pages,
            "dpi": cur.ocr_dpi,
        }
        svc.record_text_source(
            document_id=document.id,
            page_number=1,
            source_type="ocr",
            provider=cur.ocr_provider,
            provider_version=provider_version or cur.ocr_model,
            settings=svc_settings,
            image_data=None,
            success=ocr_success,
            raw_text=ocr_text,
            error=error,
            duration_ms=int(duration_ms) if duration_ms is not None else None,
        )
    except Exception as exc:
        log_event("evidence_capture_failed", document_id=document.id, error=str(exc)[:200])


def _record_extraction_run(diagnostics: dict[str, Any], *, status: str) -> None:
    runs = list(diagnostics.get("extraction_runs") or [])
    run = {
        "attempt_no": len(runs) + 1,
        "extraction_route": diagnostics.get("extraction_route"),
        "parser_route": diagnostics.get("parser_route"),
        "model_version": diagnostics.get("model_version"),
        "status": status,
        "failure_code": diagnostics.get("failure_code"),
        "failure_reason": diagnostics.get("failure_reason"),
        "raw_text_length": diagnostics.get("raw_text_length", 0),
        "ocr_text_length": diagnostics.get("ocr_text_length", 0),
        "extracted_field_keys": diagnostics.get("extracted_field_keys", []),
        "missing_required_fields": diagnostics.get("missing_required_fields", []),
        "model_layer2_used": diagnostics.get("model_layer2_used", False),
        "model_extracted_keys": diagnostics.get("model_extracted_keys", []),
    }
    runs.append(run)
    diagnostics["extraction_runs"] = runs[-10:]
