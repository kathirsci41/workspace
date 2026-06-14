from __future__ import annotations

import re
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
from app.services.extraction.glm_ocr_client import (
    HEADER_CROP_FRACTION,
    HEADER_OCR_MAX_OUTPUT_TOKENS,
    extract_header_text_with_ocr,
    extract_text_with_ocr,
)
from app.services.extraction.model_layer2 import extract_structured_fields_with_model
from app.services.extraction.ocr_providers.paddle_provider import PaddleOcrProvider, paddle_runtime_info
from app.services.extraction.pdf_field_locator import build_field_locations
from app.services.extraction.structured_text_parser import FailureCode, parse_structured_text


MIN_DIGITAL_TEXT_LENGTH = 25
VENDOR_INVOICE_HEADER_FIELDS = (
    "vendor_invoice_no",
    "vendor_invoice_date",
    "po_reference",
)
VENDOR_INVOICE_REQUIRED_FIELDS = (
    "vendor_invoice_no",
    "vendor_invoice_date",
    "po_reference",
    "invoice_total",
)
VENDOR_INVOICE_CANDIDATE_FIELDS = (
    "vendor_invoice_no",
    "vendor_invoice_date",
    "po_reference",
    "taxable_amount",
    "invoice_total",
)
HEADER_FIELD_ALIASES = {
    "vendor_invoice_no": ("invoice_number",),
    "vendor_invoice_date": ("invoice_date",),
    "po_reference": ("customer_ref_no",),
}
WEAK_HEADER_FIELD_SOURCES = {"filename_fallback"}
MIN_STRONG_HEADER_CONFIDENCE = 0.8
HEADER_OCR_TARGET_LABELS = (
    ("Invoice No", ("Invoice No", "Tax Invoice No", "Invoice Number")),
    ("Invoice Date", ("Invoice Date", "Tax Invoice Date", "Invoice Dt")),
    ("PO Reference", ("PO Reference", "PO No", "PO Number", "Buyer PO No")),
)


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
        doc_type = str(document.document_type)
        if _paddleocr_route_enabled(doc_type):
            raw_ocr_text, text_for_parse, extraction_route = _run_paddleocr_route(db, document, diagnostics)
        elif _glm_route_enabled(doc_type):
            extraction_route = "ocr_glm"
            diagnostics["ocr_route"] = "glm"
            raw_ocr_text, text_for_parse = _run_glm_ocr_route(db, document, diagnostics)
        elif settings.ocr_enabled:
            extraction_route = "scanned"
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
            extraction_route = "scanned"
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
        if _should_attempt_vendor_invoice_header_ocr(
            document=document,
            parsed=parsed,
            text_for_parse=text_for_parse,
        ):
            parsed, header_diagnostics = _apply_vendor_invoice_header_ocr(
                db=db,
                document=document,
                parsed=parsed,
            )
            diagnostics.update(header_diagnostics)
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

    _capture_selected_rule_field_candidates(
        db,
        document,
        extracted_data=extracted_data,
        field_metadata=field_metadata,
        diagnostics=diagnostics,
        extraction_route=extraction_route,
    )

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


_GLM_OCR_PROVIDER_NAMES = {"glm_ocr", "glm"}
_PADDLE_GPU_PROVIDER_NAME = "paddleocr_gpu"


def _paddleocr_route_enabled(document_type: str) -> bool:
    return (
        settings.ocr_enabled
        and settings.ocr_provider == _PADDLE_GPU_PROVIDER_NAME
        and document_type.upper() == "VENDOR_INVOICE"
    )


def _glm_route_enabled(document_type: str) -> bool:
    if not settings.ocr_enabled:
        return False
    if settings.ocr_provider in _GLM_OCR_PROVIDER_NAMES:
        return True
    if settings.ocr_provider == _PADDLE_GPU_PROVIDER_NAME:
        return not _paddleocr_route_enabled(document_type)
    return False


def _run_glm_ocr_route(
    db: Session,
    document: DocumentRecord,
    diagnostics: dict[str, Any],
) -> tuple[str, str]:
    """Run the GLM OCR provider, returning (raw_ocr_text, text_for_parse).

    Mutates `diagnostics` in place. Used for the default GLM route and as the
    fallback target when the optional PaddleOCR route fails.
    """
    raw_ocr_text = ""
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
    return raw_ocr_text, text_for_parse


def _run_paddleocr_route(
    db: Session,
    document: DocumentRecord,
    diagnostics: dict[str, Any],
) -> tuple[str, str, str]:
    """Optional PaddleOCR GPU route for VENDOR_INVOICE.

    Returns (raw_ocr_text, text_for_parse, extraction_route). On success,
    extraction_route is "ocr_paddleocr_gpu" and GLM is not called. On
    failure/timeout/empty text, falls back to _run_glm_ocr_route() when
    settings.ocr_paddle_fallback_to_glm is True (extraction_route="ocr_glm"),
    otherwise returns a controlled failure result (extraction_route="scanned").
    """
    provider = PaddleOcrProvider(device=settings.ocr_paddle_device, enforce_timeout=True)
    diagnostics["ocr_paddle_provider_name"] = provider.provider_name
    diagnostics["ocr_paddle_device"] = settings.ocr_paddle_device
    diagnostics["ocr_paddle_timeout_seconds"] = settings.ocr_paddle_timeout_seconds
    diagnostics["paddle_device"] = settings.ocr_paddle_device

    if not provider.is_available():
        success, raw_text, error, duration_ms = False, "", "PaddleOCR is not installed", 0
        diagnostics.update(paddle_runtime_info())
    else:
        result = provider.run_full_page(
            str(document.storage_path),
            max_pages=settings.ocr_max_pages,
            dpi=settings.ocr_dpi,
            timeout_seconds=settings.ocr_paddle_timeout_seconds,
        )
        success, raw_text, error, duration_ms = result.success, result.raw_text or "", result.error, result.duration_ms
        diagnostics.update(result.model_info or paddle_runtime_info())
        if result.text_blocks:
            diagnostics["ocr_paddle_text_blocks"] = result.text_blocks

    diagnostics["ocr_paddle_duration_ms"] = duration_ms
    diagnostics["ocr_paddle_text_length"] = len(raw_text.strip())

    if success and raw_text.strip():
        diagnostics["ocr_route"] = "paddleocr_gpu"
        diagnostics["ocr_provider"] = provider.provider_name
        diagnostics["ocr_available"] = True
        diagnostics["ocr_status"] = "text_acquired"
        diagnostics["raw_ocr_text_length"] = len(raw_text.strip())
        diagnostics["ocr_text_length"] = len(raw_text.strip())
        text_for_parse = normalize_ocr_text(raw_text)
        _capture_ocr_text_evidence(
            db, document,
            ocr_text=raw_text,
            ocr_success=True,
            provider_version=provider.provider_name,
            duration_ms=duration_ms,
        )
        return raw_text, text_for_parse, "ocr_paddleocr_gpu"

    diagnostics["ocr_paddle_error"] = error
    _capture_ocr_text_evidence(
        db, document,
        ocr_text=raw_text or None,
        ocr_success=False,
        provider_version=provider.provider_name,
        duration_ms=duration_ms,
        error=(error or "PaddleOCR returned no text")[:500],
    )

    if settings.ocr_paddle_fallback_to_glm:
        raw_ocr_text, text_for_parse = _run_glm_ocr_route(db, document, diagnostics)
        diagnostics["ocr_route"] = "paddleocr_gpu_then_glm_fallback"
        return raw_ocr_text, text_for_parse, "ocr_glm"

    diagnostics["ocr_route"] = "paddleocr_gpu"
    diagnostics["ocr_available"] = False
    diagnostics["ocr_text_length"] = 0
    diagnostics["raw_ocr_text_length"] = 0
    diagnostics["ocr_status"] = "provider_error"
    diagnostics["failure_code"] = FailureCode.OCR_FAILED.value
    diagnostics["failure_reason"] = f"paddleocr_gpu failed: {error or 'no text returned'}"
    return "", "", "scanned"


def _should_attempt_vendor_invoice_header_ocr(
    *,
    document: DocumentRecord,
    parsed: dict[str, Any],
    text_for_parse: str,
) -> bool:
    if str(document.document_type).upper() != "VENDOR_INVOICE":
        return False
    if not text_for_parse.strip() or not document.storage_path:
        return False
    if not settings.ocr_enabled or settings.ocr_provider != "glm_ocr":
        return False
    return any(
        _header_field_is_missing_or_weak(parsed, field)
        for field in VENDOR_INVOICE_HEADER_FIELDS
    )


def _header_field_is_missing_or_weak(
    parsed: dict[str, Any],
    field: str,
) -> bool:
    value = (parsed.get("fields") or {}).get(field)
    if value in (None, ""):
        return True
    metadata = (parsed.get("field_metadata") or {}).get(field) or {}
    if metadata.get("source") in WEAK_HEADER_FIELD_SOURCES:
        return True
    confidence = metadata.get("confidence")
    return confidence is not None and float(confidence) < MIN_STRONG_HEADER_CONFIDENCE


def _apply_vendor_invoice_header_ocr(
    *,
    db: Session,
    document: DocumentRecord,
    parsed: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.perf_counter()
    needed_fields = [
        field
        for field in VENDOR_INVOICE_HEADER_FIELDS
        if _header_field_is_missing_or_weak(parsed, field)
    ]
    diagnostics: dict[str, Any] = {
        "ocr_header_attempted": True,
        "ocr_header_status": "not_attempted",
        "ocr_header_requested_fields": needed_fields,
        "ocr_header_recovered_fields": [],
    }

    try:
        result = extract_header_text_with_ocr(
            str(document.storage_path),
            dpi=settings.ocr_dpi,
            timeout_seconds=settings.ocr_timeout_seconds,
        )
        diagnostics.update(result.diagnostics)
        if result.error:
            diagnostics["ocr_header_status"] = "provider_error"
            diagnostics["ocr_header_error"] = result.error[:500]
            _capture_header_ocr_text_evidence(
                db,
                document,
                ocr_text=result.text or None,
                image_data=result.image_data,
                success=False,
                provider=result.provider,
                provider_version=result.model,
                duration_ms=result.diagnostics.get("ocr_header_duration_ms"),
                error=result.error[:500],
            )
            return parsed, diagnostics

        header_text = _normalize_vendor_invoice_header_ocr_text(result.text)
        if not header_text.strip():
            error = "Header OCR returned no usable text."
            diagnostics["ocr_header_status"] = "empty"
            diagnostics["ocr_header_error"] = error
            _capture_header_ocr_text_evidence(
                db,
                document,
                ocr_text=result.text or None,
                image_data=result.image_data,
                success=False,
                provider=result.provider,
                provider_version=result.model,
                duration_ms=result.diagnostics.get("ocr_header_duration_ms"),
                error=error,
            )
            return parsed, diagnostics

        _capture_header_ocr_text_evidence(
            db,
            document,
            ocr_text=result.text,
            image_data=result.image_data,
            success=True,
            provider=result.provider,
            provider_version=result.model,
            duration_ms=result.diagnostics.get("ocr_header_duration_ms"),
        )
        header_parsed = parse_structured_text(
            "VENDOR_INVOICE",
            header_text,
            extraction_route="ocr_glm",
            filename=None,
            context={"document_id": document.id, "region": "header"},
        )
        recovered = _merge_header_fields(
            parsed=parsed,
            header_parsed=header_parsed,
            needed_fields=needed_fields,
            provider=result.provider,
        )
        diagnostics["ocr_header_status"] = "text_acquired"
        diagnostics["ocr_header_recovered_fields"] = recovered
        return parsed, diagnostics
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started) * 1000)
        diagnostics.update(
            {
                "ocr_header_status": "provider_error",
                "ocr_header_error": str(exc)[:500],
                "ocr_header_duration_ms": duration_ms,
            }
        )
        _capture_header_ocr_text_evidence(
            db,
            document,
            ocr_text=None,
            image_data=None,
            success=False,
            provider=settings.ocr_provider,
            provider_version=settings.ocr_model,
            duration_ms=duration_ms,
            error=str(exc)[:500],
        )
        return parsed, diagnostics


def _normalize_vendor_invoice_header_ocr_text(raw_text: str) -> str:
    text = normalize_ocr_text(raw_text)
    parser_lines: list[str] = []
    for canonical_label, label_variants in HEADER_OCR_TARGET_LABELS:
        labels = "|".join(re.escape(label) for label in label_variants)
        match = re.search(
            rf"""["']?(?:{labels})["']?\s*:\s*["']?([^"',}}\r\n]+)""",
            text,
            flags=re.I,
        )
        if not match:
            continue
        value = match.group(1).strip(" .,:")
        if canonical_label == "PO Reference":
            value = re.sub(
                r"^PO\s+(?=\S*\d)",
                "",
                value,
                flags=re.I,
            )
        if value:
            parser_lines.append(f"{canonical_label}: {value}")
    if not parser_lines:
        return text
    return "\n".join((text, *parser_lines))


def _merge_header_fields(
    *,
    parsed: dict[str, Any],
    header_parsed: dict[str, Any],
    needed_fields: list[str],
    provider: str,
) -> list[str]:
    fields = parsed.setdefault("fields", {})
    metadata = parsed.setdefault("field_metadata", {})
    header_fields = header_parsed.get("fields") or {}
    header_metadata = header_parsed.get("field_metadata") or {}
    recovered: list[str] = []

    for field in needed_fields:
        value = header_fields.get(field)
        if value in (None, "") or not _header_field_is_missing_or_weak(parsed, field):
            continue
        candidate_metadata = dict(header_metadata.get(field) or {})
        if candidate_metadata.get("source") != "rules":
            continue
        fields[field] = value
        field_metadata = {
            **candidate_metadata,
            "field": field,
            "value": value,
            "source": "ocr_header",
            "provider": provider,
            "evidence_text": f"header OCR; {candidate_metadata.get('evidence_text', '').strip()}".rstrip("; "),
        }
        metadata[field] = field_metadata
        for alias in HEADER_FIELD_ALIASES.get(field, ()):
            fields[alias] = value
            metadata[alias] = {
                **field_metadata,
                "field": alias,
            }
        recovered.append(field)

    if recovered:
        parser_diagnostics = parsed.setdefault("diagnostics", {})
        if "vendor_invoice_no" in recovered:
            parser_diagnostics["vendor_invoice_no_source"] = "ocr_header"
        _refresh_vendor_invoice_parse_result(parsed)
    return recovered


def _refresh_vendor_invoice_parse_result(parsed: dict[str, Any]) -> None:
    fields = parsed.get("fields") or {}
    missing = [
        field
        for field in VENDOR_INVOICE_REQUIRED_FIELDS
        if fields.get(field) in (None, "")
    ]
    diagnostics = parsed.setdefault("diagnostics", {})
    diagnostics["extracted_field_keys"] = sorted(
        field for field, value in fields.items() if value not in (None, "")
    )
    diagnostics["missing_required_fields"] = missing
    if missing:
        diagnostics["failure_code"] = FailureCode.REQUIRED_FIELDS_MISSING
        diagnostics["failure_reason"] = (
            "OCR text was acquired but required fields are missing: "
            + ", ".join(missing)
        )
    else:
        diagnostics["failure_code"] = None
        diagnostics["failure_reason"] = None
    parsed["missing_required_fields"] = missing
    parsed["confidence"] = round(
        (
            (len(VENDOR_INVOICE_REQUIRED_FIELDS) - len(missing))
            / len(VENDOR_INVOICE_REQUIRED_FIELDS)
        )
        * 100,
        1,
    )


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
        "ocr_header_attempted": False,
        "ocr_header_status": "not_attempted",
        "ocr_header_recovered_fields": [],
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


def _capture_selected_rule_field_candidates(
    db: Session,
    document: DocumentRecord,
    *,
    extracted_data: dict[str, Any],
    field_metadata: dict[str, dict[str, Any]],
    diagnostics: dict[str, Any],
    extraction_route: str,
) -> None:
    import app.config as _cfg

    cur = _cfg.settings
    if not cur.evidence_capture_enabled:
        return
    if str(document.document_type).upper() != "VENDOR_INVOICE":
        return
    try:
        svc = EvidenceService(db)
        existing_keys = {
            (
                row.field_key,
                row.candidate_value,
                row.source_type,
                row.selection_status,
            )
            for row in svc.list_field_candidates(document.id)
        }
        text_sources = svc.list_text_sources(document.id)

        for field_key in VENDOR_INVOICE_CANDIDATE_FIELDS:
            value = extracted_data.get(field_key)
            if value in (None, ""):
                continue
            details = dict(field_metadata.get(field_key) or {})
            source_type = _field_candidate_source_type(
                details,
                diagnostics,
                extraction_route=extraction_route,
            )
            if source_type is None:
                continue
            candidate_value = _field_candidate_value(value)
            dedupe_key = (field_key, candidate_value, source_type, "selected")
            if dedupe_key in existing_keys:
                continue
            provider = _field_candidate_provider(source_type, details, diagnostics, cur)
            svc.insert_field_candidate(
                document_id=document.id,
                field_key=field_key,
                source_type=source_type,
                provider=provider,
                text_source_id=_field_candidate_text_source_id(
                    text_sources,
                    source_type=source_type,
                    provider=provider,
                ),
                page_number=_field_candidate_page_number(
                    field_key,
                    diagnostics,
                    source_type=source_type,
                ),
                candidate_value=candidate_value,
                normalized_value=_field_candidate_value(value),
                evidence_text=_field_candidate_evidence_text(
                    field_key,
                    source_type=source_type,
                    details=details,
                ),
                confidence=_field_candidate_confidence(details),
                selection_status="selected",
            )
            existing_keys.add(dedupe_key)
    except Exception as exc:
        log_event(
            "evidence_capture_failed",
            document_id=document.id,
            error=str(exc)[:200],
        )


def _field_candidate_source_type(
    details: dict[str, Any],
    diagnostics: dict[str, Any],
    *,
    extraction_route: str,
) -> str | None:
    source = str(details.get("source") or "").lower()
    if source in {"manual_entry", "model_layer2"}:
        return None
    if source == "ocr_header":
        return "ocr_header"
    if source == "filename_fallback":
        return "filename_fallback"
    if bool(diagnostics.get("digital_text_used")) or extraction_route == "digital":
        return "digital_text"
    if extraction_route in {"ocr_glm", "scanned"} or diagnostics.get("parser_route") == "ocr_rules":
        return "ocr"
    return None


def _field_candidate_provider(
    source_type: str,
    details: dict[str, Any],
    diagnostics: dict[str, Any],
    cur: Any,
) -> str | None:
    provider = details.get("provider")
    if provider:
        return str(provider)
    if source_type in {"ocr", "ocr_header"}:
        return str(diagnostics.get("ocr_provider") or cur.ocr_provider)
    if source_type == "digital_text":
        return "digital_pdf"
    return None


def _field_candidate_text_source_id(
    text_sources: list[Any],
    *,
    source_type: str,
    provider: str | None,
) -> str | None:
    if source_type == "filename_fallback":
        return None
    for text_source in text_sources:
        if text_source.source_type != source_type:
            continue
        if provider is not None and text_source.provider != provider:
            continue
        return text_source.id
    return None


def _field_candidate_page_number(
    field_key: str,
    diagnostics: dict[str, Any],
    *,
    source_type: str,
) -> int | None:
    if source_type == "filename_fallback":
        return None
    location = (diagnostics.get("field_locations") or {}).get(field_key) or {}
    page = location.get("page")
    if isinstance(page, int):
        return page
    return 1


def _field_candidate_value(value: Any) -> str:
    return " ".join(str(value).split())


def _field_candidate_evidence_text(
    field_key: str,
    *,
    source_type: str,
    details: dict[str, Any],
) -> str:
    source_labels = {
        "digital_text": "selected from digital text rules",
        "ocr": "selected from OCR rules",
        "ocr_header": "selected from targeted header OCR",
        "filename_fallback": "selected from filename fallback",
    }
    label = source_labels.get(source_type, f"selected from {source_type}")
    evidence = str(details.get("evidence_text") or "").strip()
    if evidence:
        return f"{field_key}: {label}; {evidence}"[:1000]
    return f"{field_key}: {label}"[:1000]


def _field_candidate_confidence(details: dict[str, Any]) -> float | None:
    confidence = details.get("confidence")
    if confidence is None:
        return None
    try:
        return float(confidence)
    except (TypeError, ValueError):
        return None


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


def _capture_header_ocr_text_evidence(
    db: Session,
    document: DocumentRecord,
    *,
    ocr_text: str | None,
    image_data: bytes | None,
    success: bool,
    provider: str,
    provider_version: str | None,
    duration_ms: int | float | None = None,
    error: str | None = None,
) -> None:
    import app.config as _cfg

    cur = _cfg.settings
    if not cur.evidence_capture_enabled:
        return
    try:
        EvidenceService(db).record_text_source(
            document_id=document.id,
            page_number=1,
            source_type="ocr_header",
            provider=provider,
            provider_version=provider_version or cur.ocr_model,
            settings={
                "provider": provider,
                "model": provider_version or cur.ocr_model,
                "page_number": 1,
                "crop_fraction": HEADER_CROP_FRACTION,
                "max_output_tokens": HEADER_OCR_MAX_OUTPUT_TOKENS,
                "dpi": cur.ocr_dpi,
            },
            image_data=image_data,
            success=success,
            raw_text=ocr_text,
            normalized_text=_normalize_vendor_invoice_header_ocr_text(ocr_text) if ocr_text else None,
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
