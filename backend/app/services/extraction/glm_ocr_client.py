from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import fitz

from app.config import settings
from app.services.extraction.model_prompts import (
    OCR_ONLY_PROMPT,
    VENDOR_INVOICE_HEADER_OCR_PROMPT,
)


@dataclass
class OcrResult:
    text: str
    pages: list[dict[str, Any]]
    provider: str
    model: str
    diagnostics: dict[str, Any]


@dataclass
class HeaderOcrResult:
    text: str
    provider: str
    model: str
    image_data: bytes | None
    diagnostics: dict[str, Any]
    error: str | None = None


HEADER_CROP_FRACTION = 0.4
HEADER_OCR_MAX_OUTPUT_TOKENS = 256


def extract_text_with_ocr(
    file_path: str,
    max_pages: int,
    dpi: int,
    timeout_seconds: int,
    rotation_degrees: int = 0,
) -> OcrResult:
    page_results: list[dict[str, Any]] = []
    text_by_page: dict[int, str] = {}
    provider = settings.ocr_provider
    model = settings.ocr_model
    started = time.perf_counter()

    with fitz.open(file_path) as document:
        for index in range(min(max_pages, document.page_count)):
            page = document.load_page(index)
            page_started = time.perf_counter()
            page_result: dict[str, Any] = {"page_number": index + 1}
            try:
                image_bytes, width, height = _render_page_png(page, dpi, rotation_degrees)
                page_result.update(
                    {
                        "image_format": "png",
                        "dpi": dpi,
                        "image_width": width,
                        "image_height": height,
                        "image_bytes": len(image_bytes),
                        "base64_bytes": len(base64.b64encode(image_bytes)),
                        "request_endpoints": ["generate", "chat_fallback"],
                        "rotation_degrees": rotation_degrees,
                    }
                )
                text = _call_ollama_generate_with_retries(image_bytes, timeout_seconds=timeout_seconds)
                text = text.strip()
                page_result["ocr_text_length"] = len(text)
                if text:
                    text_by_page[index] = text
            except Exception as exc:
                page_result["ocr_text_length"] = 0
                page_result["error"] = str(exc)
            finally:
                page_result["duration_ms"] = round((time.perf_counter() - page_started) * 1000)
                page_results.append(page_result)

        _retry_failed_pages(
            document=document,
            page_results=page_results,
            text_by_page=text_by_page,
            max_pages=max_pages,
            dpi=dpi,
            timeout_seconds=timeout_seconds,
            rotation_degrees=rotation_degrees,
        )

    text = "\n".join(text_by_page[index] for index in sorted(text_by_page) if text_by_page[index]).strip()
    diagnostics = {
        "ocr_provider": provider,
        "ocr_model": model,
        "ocr_base_url_host_only": _host_only(settings.ocr_base_url),
        "ocr_pages_attempted": len(page_results),
        "ocr_text_length": len(text),
        "ocr_page_results": page_results,
        "ocr_context_length": settings.ocr_context_length,
        "ocr_duration_ms": round((time.perf_counter() - started) * 1000),
        "ocr_rotation_degrees": rotation_degrees,
    }
    return OcrResult(text=text, pages=page_results, provider=provider, model=model, diagnostics=diagnostics)


def extract_header_text_with_ocr(
    file_path: str,
    *,
    dpi: int,
    timeout_seconds: int,
    crop_fraction: float = HEADER_CROP_FRACTION,
    rotation_degrees: int = 0,
) -> HeaderOcrResult:
    provider = settings.ocr_provider
    model = settings.ocr_model
    started = time.perf_counter()
    image_data: bytes | None = None
    text = ""
    error: str | None = None
    diagnostics: dict[str, Any] = {
        "ocr_header_provider": provider,
        "ocr_header_model": model,
        "ocr_header_page_number": 1,
        "ocr_header_crop_fraction": crop_fraction,
        "ocr_header_dpi": dpi,
        "ocr_header_max_output_tokens": HEADER_OCR_MAX_OUTPUT_TOKENS,
        "ocr_header_rotation_degrees": rotation_degrees,
    }

    try:
        with fitz.open(file_path) as document:
            if document.page_count < 1:
                raise ValueError("PDF has no pages")
            page = document.load_page(0)
            image_data, width, height = _render_header_page_png(
                page,
                dpi=dpi,
                crop_fraction=crop_fraction,
                rotation_degrees=rotation_degrees,
            )
            diagnostics.update(
                {
                    "ocr_header_image_width": width,
                    "ocr_header_image_height": height,
                    "ocr_header_image_bytes": len(image_data),
                }
            )
            text = _call_ollama_generate_with_retries(
                image_data,
                timeout_seconds=timeout_seconds,
                prompt=VENDOR_INVOICE_HEADER_OCR_PROMPT,
                max_output_tokens=HEADER_OCR_MAX_OUTPUT_TOKENS,
            ).strip()
    except Exception as exc:
        error = str(exc)

    diagnostics.update(
        {
            "ocr_header_text_length": len(text),
            "ocr_header_duration_ms": round((time.perf_counter() - started) * 1000),
        }
    )
    if error:
        diagnostics["ocr_header_error"] = error
    return HeaderOcrResult(
        text=text,
        provider=provider,
        model=model,
        image_data=image_data,
        diagnostics=diagnostics,
        error=error,
    )


def _retry_failed_pages(
    *,
    document: fitz.Document,
    page_results: list[dict[str, Any]],
    text_by_page: dict[int, str],
    max_pages: int,
    dpi: int,
    timeout_seconds: int,
    rotation_degrees: int,
) -> None:
    failed_pages = [
        (index, page_result)
        for index, page_result in enumerate(page_results[: min(max_pages, document.page_count)])
        if page_result.get("error") and not text_by_page.get(index)
    ]
    if not failed_pages or settings.ocr_retry_attempts <= 0:
        return

    for index, page_result in failed_pages:
        retry_started = time.perf_counter()
        page_result["ocr_retry_attempted"] = True
        page_result["initial_error"] = page_result.get("error")
        try:
            page = document.load_page(index)
            image_bytes, width, height = _render_page_png(page, dpi, rotation_degrees)
            page_result.setdefault("image_width", width)
            page_result.setdefault("image_height", height)
            text = _call_ollama_generate_with_retries(image_bytes, timeout_seconds=timeout_seconds).strip()
            page_result["ocr_retry_text_length"] = len(text)
            page_result["ocr_retry_duration_ms"] = round((time.perf_counter() - retry_started) * 1000)
            if text:
                text_by_page[index] = text
                page_result["ocr_text_length"] = len(text)
                page_result.pop("error", None)
        except Exception as exc:
            page_result["ocr_retry_text_length"] = 0
            page_result["ocr_retry_duration_ms"] = round((time.perf_counter() - retry_started) * 1000)
            page_result["retry_error"] = str(exc)


def check_ocr_provider_health(timeout_seconds: int = 2) -> dict[str, Any]:
    if not settings.ocr_enabled:
        return {
            "enabled": False,
            "provider": settings.ocr_provider,
            "model": settings.ocr_model,
            "reachable": False,
        }
    try:
        request = Request(f"{settings.ocr_base_url.rstrip('/')}/api/tags", method="GET")
        with urlopen(request, timeout=timeout_seconds) as response:
            reachable = 200 <= response.status < 500
    except Exception:
        reachable = False
    return {
        "enabled": True,
        "provider": settings.ocr_provider,
        "model": settings.ocr_model,
        "reachable": reachable,
    }


def _render_page_png(page: fitz.Page, dpi: int, rotation_degrees: int = 0) -> tuple[bytes, int, int]:
    matrix = fitz.Matrix(dpi / 72, dpi / 72).prerotate(rotation_degrees)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    return pixmap.tobytes("png"), pixmap.width, pixmap.height


def _render_header_page_png(
    page: fitz.Page,
    *,
    dpi: int,
    crop_fraction: float,
    rotation_degrees: int = 0,
) -> tuple[bytes, int, int]:
    if not 0 < crop_fraction <= 1:
        raise ValueError("crop_fraction must be greater than 0 and at most 1")
    matrix = fitz.Matrix(dpi / 72, dpi / 72).prerotate(rotation_degrees)
    # Compute the device-space rect for the full page, then take the top
    # crop_fraction of it. Transform that crop region back to page coordinates
    # and use it as the clip — works correctly for all rotation angles without
    # any direction-specific geometry.
    device_rect = page.rect * matrix
    clip_in_device = fitz.Rect(
        device_rect.x0,
        device_rect.y0,
        device_rect.x1,
        device_rect.y0 + device_rect.height * crop_fraction,
    )
    clip_in_page = clip_in_device * (~matrix)
    pixmap = page.get_pixmap(matrix=matrix, clip=clip_in_page, alpha=False)
    return pixmap.tobytes("png"), pixmap.width, pixmap.height


def _call_ollama_generate_with_retries(
    image_bytes: bytes,
    *,
    timeout_seconds: int,
    prompt: str = OCR_ONLY_PROMPT,
    max_output_tokens: int | None = None,
) -> str:
    attempts = max(1, settings.ocr_retry_attempts + 1)
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return _call_ollama_generate(
                image_bytes,
                timeout_seconds=timeout_seconds,
                prompt=prompt,
                max_output_tokens=max_output_tokens,
            )
        except Exception as exc:
            last_error = exc
    raise RuntimeError(str(last_error) if last_error else "glm-ocr request failed")


def _call_ollama_generate(
    image_bytes: bytes,
    *,
    timeout_seconds: int,
    prompt: str = OCR_ONLY_PROMPT,
    max_output_tokens: int | None = None,
) -> str:
    try:
        return _call_generate_endpoint(
            image_bytes,
            timeout_seconds=timeout_seconds,
            prompt=prompt,
            max_output_tokens=max_output_tokens,
        )
    except Exception as generate_error:
        try:
            return _call_chat_endpoint(
                image_bytes,
                timeout_seconds=timeout_seconds,
                prompt=prompt,
                max_output_tokens=max_output_tokens,
            )
        except Exception as chat_error:
            raise RuntimeError(f"generate failed: {generate_error}; chat failed: {chat_error}") from chat_error


def _call_generate_endpoint(
    image_bytes: bytes,
    *,
    timeout_seconds: int,
    prompt: str = OCR_ONLY_PROMPT,
    max_output_tokens: int | None = None,
) -> str:
    payload = {
        "model": settings.ocr_model,
        "prompt": prompt,
        "images": [base64.b64encode(image_bytes).decode("ascii")],
        "stream": False,
        "options": _request_options(max_output_tokens),
    }
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{settings.ocr_base_url.rstrip('/')}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"glm-ocr generate failed: HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"glm-ocr generate failed: {exc}") from exc
    return str(body.get("response") or "")


def _call_chat_endpoint(
    image_bytes: bytes,
    *,
    timeout_seconds: int,
    prompt: str = OCR_ONLY_PROMPT,
    max_output_tokens: int | None = None,
) -> str:
    payload = {
        "model": settings.ocr_model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [base64.b64encode(image_bytes).decode("ascii")],
            }
        ],
        "stream": False,
        "options": _request_options(max_output_tokens),
    }
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{settings.ocr_base_url.rstrip('/')}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"glm-ocr chat failed: HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"glm-ocr chat failed: {exc}") from exc
    message = body.get("message") or {}
    return str(message.get("content") or "")


def _request_options(max_output_tokens: int | None) -> dict[str, int]:
    options = {"num_ctx": settings.ocr_context_length}
    if max_output_tokens is not None:
        options["num_predict"] = max_output_tokens
    return options


def _host_only(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc or parsed.path
