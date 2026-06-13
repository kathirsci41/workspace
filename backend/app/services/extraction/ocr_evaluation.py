"""OCR provider evaluation harness — Phase 1m / 1w.

Evaluation-only module. Never writes production document records.
Never changes extraction behavior. Composes OCR leaf functions directly.
"""
from __future__ import annotations

import importlib.util
import time
from dataclasses import dataclass, field
from typing import Any

from app.services.extraction.glm_ocr_client import (
    extract_header_text_with_ocr,
    extract_text_with_ocr,
)
from app.services.extraction.ocr_providers import get_ocr_provider
from app.services.extraction.structured_text_parser import parse_structured_text
from app.services.extraction_service import _normalize_vendor_invoice_header_ocr_text

_PREVIEW_MAX = 300
_EVAL_DPI_DEFAULT = 150
_EVAL_TIMEOUT_DEFAULT = 60
_EVAL_MAX_PAGES = 3

# Fields extracted by the vendor invoice parser that the harness optionally reports.
_VENDOR_INVOICE_TARGET_FIELDS = (
    "vendor_invoice_no",
    "vendor_invoice_date",
    "po_reference",
    "invoice_total",
)


@dataclass
class OcrProviderResult:
    """Shape of a single provider evaluation run."""

    provider_name: str          # "glm_full_page", "glm_header", "paddleocr"
    source_type: str            # "ocr_full_page", "ocr_header", "paddleocr"
    provider_version: str | None
    duration_ms: int
    success: bool
    error: str | None
    raw_text_length: int
    normalized_text_preview: str     # first _PREVIEW_MAX chars
    extracted_fields: dict[str, Any]  # vendor invoice fields if parser run
    provider_status: str             # "ok", "error", "unavailable"
    parse_mode: str = "raw"          # "raw" | "header_normalized"


def _set_paddle_device(device: str) -> str | None:
    """Try to set the active Paddle device; return error string on failure, None on success.

    Uses a lazy import so paddle is never required at module load time.
    """
    try:
        import paddle  # noqa: PLC0415
        paddle.device.set_device(device)
        return None
    except Exception as exc:
        return str(exc)


def check_paddleocr_availability() -> str:
    """Return "available" if paddleocr can be imported, else "unavailable".

    Uses find_spec so paddleocr is never actually imported or executed.
    """
    spec = importlib.util.find_spec("paddleocr")
    return "available" if spec is not None else "unavailable"


def run_paddleocr_evaluation(
    file_path: str,
    *,
    dpi: int = _EVAL_DPI_DEFAULT,
    timeout_seconds: int = _EVAL_TIMEOUT_DEFAULT,
    run_parser: bool = True,
    device: str | None = None,
) -> OcrProviderResult:
    """Run PaddleOCR evaluation on *file_path* and return an evaluation result.

    Evaluation-only. Never writes to any database.
    When device is provided, attempts to set the Paddle device before inference;
    a device-setting failure does not abort the evaluation — OCR proceeds and the
    error is surfaced only if OCR itself also fails.
    """
    provider = get_ocr_provider("paddleocr")

    if not provider.is_available():
        return OcrProviderResult(
            provider_name="paddleocr",
            source_type="paddleocr",
            provider_version=None,
            duration_ms=0,
            success=False,
            error="PaddleOCR not installed",
            raw_text_length=0,
            normalized_text_preview="",
            extracted_fields={},
            provider_status="unavailable",
        )

    device_error: str | None = None
    if device is not None:
        device_error = _set_paddle_device(device)

    try:
        result = provider.run_full_page(
            file_path,
            max_pages=1,
            dpi=dpi,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        return OcrProviderResult(
            provider_name="paddleocr",
            source_type="paddleocr",
            provider_version=None,
            duration_ms=0,
            success=False,
            error=str(exc),
            raw_text_length=0,
            normalized_text_preview="",
            extracted_fields={},
            provider_status="error",
        )

    text = result.raw_text or ""

    if not result.success:
        return OcrProviderResult(
            provider_name="paddleocr",
            source_type="paddleocr",
            provider_version=None,
            duration_ms=result.duration_ms,
            success=False,
            error=result.error,
            raw_text_length=len(text),
            normalized_text_preview=text[:_PREVIEW_MAX],
            extracted_fields={},
            provider_status="error",
        )

    extracted = _run_parser("VENDOR_INVOICE", text, route="ocr") if run_parser else {}

    return OcrProviderResult(
        provider_name="paddleocr",
        source_type="paddleocr",
        provider_version=None,
        duration_ms=result.duration_ms,
        success=True,
        error=None,
        raw_text_length=len(text),
        normalized_text_preview=text[:_PREVIEW_MAX],
        extracted_fields=extracted,
        provider_status="ok",
    )


def run_glm_full_page_evaluation(
    pdf_path: str,
    *,
    dpi: int = _EVAL_DPI_DEFAULT,
    timeout_seconds: int = _EVAL_TIMEOUT_DEFAULT,
    run_parser: bool = True,
    document_type: str = "VENDOR_INVOICE",
    parse_mode: str = "raw",
) -> OcrProviderResult:
    """Run GLM full-page OCR on *pdf_path* and return an evaluation result.

    No DB writes. No side effects on production extraction.
    Full-page provider always uses raw parse_mode regardless of the argument.
    """
    started = time.perf_counter()
    text = ""
    error: str | None = None
    provider_version: str | None = None
    success = False

    try:
        ocr = extract_text_with_ocr(
            pdf_path,
            max_pages=_EVAL_MAX_PAGES,
            dpi=dpi,
            timeout_seconds=timeout_seconds,
        )
        text = ocr.text or ""
        provider_version = ocr.model
        success = True
    except Exception as exc:
        error = str(exc)

    duration_ms = round((time.perf_counter() - started) * 1000)
    extracted = _run_parser(document_type, text, route="ocr_glm") if run_parser and success else {}

    return OcrProviderResult(
        provider_name="glm_full_page",
        source_type="ocr_full_page",
        provider_version=provider_version,
        duration_ms=duration_ms,
        success=success,
        error=error,
        raw_text_length=len(text),
        normalized_text_preview=text[:_PREVIEW_MAX],
        extracted_fields=extracted,
        provider_status="ok" if success else "error",
        parse_mode="raw",
    )


def run_glm_header_evaluation(
    pdf_path: str,
    *,
    dpi: int = _EVAL_DPI_DEFAULT,
    timeout_seconds: int = _EVAL_TIMEOUT_DEFAULT,
    run_parser: bool = True,
    document_type: str = "VENDOR_INVOICE",
    parse_mode: str = "raw",
) -> OcrProviderResult:
    """Run GLM header OCR on *pdf_path* and return an evaluation result.

    No DB writes. No side effects on production extraction.
    When parse_mode='header_normalized', applies production normalization before parsing.
    """
    started = time.perf_counter()
    text = ""
    error: str | None = None
    provider_version: str | None = None
    success = False

    try:
        header = extract_header_text_with_ocr(
            pdf_path,
            dpi=dpi,
            timeout_seconds=timeout_seconds,
        )
        text = header.text or ""
        provider_version = header.model
        if header.error:
            error = header.error
            success = False
        else:
            success = True
    except Exception as exc:
        error = str(exc)

    duration_ms = round((time.perf_counter() - started) * 1000)

    if run_parser and success:
        parse_text = (
            _normalize_vendor_invoice_header_ocr_text(text)
            if parse_mode == "header_normalized"
            else text
        )
        extracted = _run_parser(document_type, parse_text, route="ocr_glm")
    else:
        extracted = {}

    return OcrProviderResult(
        provider_name="glm_header",
        source_type="ocr_header",
        provider_version=provider_version,
        duration_ms=duration_ms,
        success=success,
        error=error,
        raw_text_length=len(text),
        normalized_text_preview=text[:_PREVIEW_MAX],
        extracted_fields=extracted,
        provider_status="ok" if success else "error",
        parse_mode=parse_mode,
    )


def evaluate_pdf(
    pdf_path: str,
    *,
    dpi: int = _EVAL_DPI_DEFAULT,
    timeout_seconds: int = _EVAL_TIMEOUT_DEFAULT,
    run_parser: bool = True,
    document_type: str = "VENDOR_INVOICE",
) -> list[OcrProviderResult]:
    """Evaluate all configured OCR providers against *pdf_path*.

    Returns one result per provider. PaddleOCR is included as a
    capability-check-only entry when not installed.

    Never writes to any database. Never changes extraction behavior.
    """
    results: list[OcrProviderResult] = []

    results.append(
        run_glm_full_page_evaluation(
            pdf_path,
            dpi=dpi,
            timeout_seconds=timeout_seconds,
            run_parser=run_parser,
            document_type=document_type,
        )
    )
    results.append(
        run_glm_header_evaluation(
            pdf_path,
            dpi=dpi,
            timeout_seconds=timeout_seconds,
            run_parser=run_parser,
            document_type=document_type,
        )
    )

    paddle_status = check_paddleocr_availability()
    results.append(
        OcrProviderResult(
            provider_name="paddleocr",
            source_type="paddleocr",
            provider_version=None,
            duration_ms=0,
            success=False,
            error=None if paddle_status == "available" else "PaddleOCR not installed",
            raw_text_length=0,
            normalized_text_preview="",
            extracted_fields={},
            provider_status=paddle_status,
        )
    )

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_parser(document_type: str, text: str, route: str) -> dict[str, Any]:
    """Run the structured text parser and return just the target fields."""
    try:
        parsed = parse_structured_text(
            document_type,
            text,
            extraction_route=route,
            filename=None,
        )
        fields = parsed.get("fields") or {}
        return {k: fields.get(k) for k in _VENDOR_INVOICE_TARGET_FIELDS}
    except Exception:
        return {}
