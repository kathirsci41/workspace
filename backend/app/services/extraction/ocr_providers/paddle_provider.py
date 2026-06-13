"""PaddleOCR provider adapter.

Uses lazy imports so the module loads regardless of whether paddleocr is
installed. When unavailable, is_available() returns False and run_full_page()
returns a failed result.

API notes (PaddleOCR 3.7.0 / paddlex 3.7.x):
- Instantiate:  PaddleOCR(lang="en")  — use_angle_cls and show_log removed
- Call:         ocr.predict(file_path)  — .ocr() is deprecated
- Result:       list of OCRResult objects (one per page); each is dict-like
                with result["rec_texts"] = list[str] of recognized text lines

Phase 1xA — constructor hardening:
- Optional device= kwarg selects the Paddle compute device ("gpu:0", "cpu", etc.)
- Optional provider_name= kwarg overrides the result provenance label
- When device starts with "gpu" and provider_name is not set, provider_name
  defaults to "paddleocr_gpu" so callers can distinguish GPU results
- _set_paddle_device() attempts paddle.device.set_device() with a lazy import;
  failure is surfaced as a safe failed OcrProviderResult rather than a crash

Timeout note (Phase 1xA limitation):
  timeout_seconds is accepted but NOT enforced at the process level.
  The PaddleOCR predict() call is synchronous with no process-level preemption.
  Thread-based timeout would leave OCR running in background — unsafe for
  production. This must be solved in Phase 1xB before production routing
  is enabled. timeout_seconds is not recorded on the result.
"""
from __future__ import annotations

import importlib.util
import time

from app.services.extraction.ocr_providers.base import OcrProviderBase, OcrProviderResult

_UNAVAILABLE_ERROR = "PaddleOCR is not installed"


def _paddle_available() -> bool:
    return importlib.util.find_spec("paddleocr") is not None


def _set_paddle_device(device: str) -> str | None:
    """Call paddle.device.set_device(device); return error string on failure, None on success.

    Uses a lazy import so paddle is never required at module load time.
    """
    try:
        import paddle  # noqa: PLC0415
        paddle.device.set_device(device)
        return None
    except Exception as exc:
        return str(exc)


def _flatten_paddle_result(results) -> str:
    """Flatten PaddleOCR predict() results into plain newline-separated text.

    Each element in `results` is a dict-like OCRResult with a "rec_texts" key
    that holds a list of recognized text strings for one page.
    """
    lines = []
    for result in (results or []):
        texts = result["rec_texts"] if result is not None else []
        for text in (texts or []):
            if text:
                lines.append(str(text))
    return "\n".join(lines)


class PaddleOcrProvider(OcrProviderBase):
    def __init__(
        self,
        *,
        device: str | None = None,
        provider_name: str | None = None,
    ) -> None:
        self._device = device
        if provider_name is not None:
            self._provider_name = provider_name
        elif device is not None and device.startswith("gpu"):
            self._provider_name = "paddleocr_gpu"
        else:
            self._provider_name = "paddleocr"

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def supports_header(self) -> bool:
        return False

    def is_available(self) -> bool:
        return _paddle_available()

    def run_full_page(
        self,
        file_path: str,
        *,
        max_pages: int,
        dpi: int,
        timeout_seconds: int,
    ) -> OcrProviderResult:
        if not _paddle_available():
            return OcrProviderResult(
                provider_name=self.provider_name,
                source_type="ocr",
                raw_text="",
                success=False,
                error=_UNAVAILABLE_ERROR,
                duration_ms=0,
                model=None,
            )

        if self._device is not None:
            device_error = _set_paddle_device(self._device)
            if device_error is not None:
                return OcrProviderResult(
                    provider_name=self.provider_name,
                    source_type="ocr",
                    raw_text="",
                    success=False,
                    error=f"Device setup failed for {self._device!r}: {device_error}",
                    duration_ms=0,
                    model=None,
                )

        started = time.perf_counter()
        try:
            import paddleocr  # lazy — only reached when _paddle_available() is True
            ocr = paddleocr.PaddleOCR(lang="en")
            results = ocr.predict(file_path)
            raw_text = _flatten_paddle_result(results)
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            return OcrProviderResult(
                provider_name=self.provider_name,
                source_type="ocr",
                raw_text="",
                success=False,
                error=str(exc),
                duration_ms=elapsed_ms,
                model=None,
            )

        return OcrProviderResult(
            provider_name=self.provider_name,
            source_type="ocr",
            raw_text=raw_text,
            success=True,
            error=None,
            duration_ms=round((time.perf_counter() - started) * 1000),
            model=None,
        )
