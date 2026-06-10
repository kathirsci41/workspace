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
from app.services.extraction.model_prompts import OCR_ONLY_PROMPT


@dataclass
class OcrResult:
    text: str
    pages: list[dict[str, Any]]
    provider: str
    model: str
    diagnostics: dict[str, Any]


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


def _call_ollama_generate_with_retries(image_bytes: bytes, *, timeout_seconds: int) -> str:
    attempts = max(1, settings.ocr_retry_attempts + 1)
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return _call_ollama_generate(image_bytes, timeout_seconds=timeout_seconds)
        except Exception as exc:
            last_error = exc
    raise RuntimeError(str(last_error) if last_error else "glm-ocr request failed")


def _call_ollama_generate(image_bytes: bytes, *, timeout_seconds: int) -> str:
    try:
        return _call_generate_endpoint(image_bytes, timeout_seconds=timeout_seconds)
    except Exception as generate_error:
        try:
            return _call_chat_endpoint(image_bytes, timeout_seconds=timeout_seconds)
        except Exception as chat_error:
            raise RuntimeError(f"generate failed: {generate_error}; chat failed: {chat_error}") from chat_error


def _call_generate_endpoint(image_bytes: bytes, *, timeout_seconds: int) -> str:
    payload = {
        "model": settings.ocr_model,
        "prompt": OCR_ONLY_PROMPT,
        "images": [base64.b64encode(image_bytes).decode("ascii")],
        "stream": False,
        "options": {"num_ctx": settings.ocr_context_length},
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


def _call_chat_endpoint(image_bytes: bytes, *, timeout_seconds: int) -> str:
    payload = {
        "model": settings.ocr_model,
        "messages": [
            {
                "role": "user",
                "content": OCR_ONLY_PROMPT,
                "images": [base64.b64encode(image_bytes).decode("ascii")],
            }
        ],
        "stream": False,
        "options": {"num_ctx": settings.ocr_context_length},
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


def _host_only(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc or parsed.path
