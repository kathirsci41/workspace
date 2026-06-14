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

Phase 1xB — process-level timeout enforcement:
- Optional enforce_timeout= kwarg (default False) preserves prior behavior
  (timeout_seconds accepted but not enforced) when disabled.
- When enforce_timeout=True, run_full_page() runs PaddleOCR inference in a
  child process (multiprocessing, spawn context) and enforces timeout_seconds
  at the OS process level: join(timeout) -> terminate() -> join(grace) ->
  kill() if still alive. A timed-out result is returned as a failed
  OcrProviderResult with provider_name preserved (e.g. "paddleocr_gpu").
- The child worker (_paddle_ocr_worker) is a module-level function so it can
  be pickled by the spawn start method on Windows.
"""
from __future__ import annotations

import importlib.metadata
import importlib.util
import multiprocessing
import time
from typing import Any

from app.services.extraction.ocr_providers.base import OcrProviderBase, OcrProviderResult

_UNAVAILABLE_ERROR = "PaddleOCR is not installed"
_TERMINATE_GRACE_SECONDS = 5

PADDLE_INIT_ARGS: dict[str, Any] = {"lang": "en"}


def _paddle_available() -> bool:
    return importlib.util.find_spec("paddleocr") is not None


def paddle_runtime_info() -> dict[str, Any]:
    """Best-effort PaddleOCR/PaddlePaddle runtime diagnostics.

    Never raises: version lookups fall back to "unknown" if the packages
    are not installed or metadata is unavailable.
    """
    info: dict[str, Any] = {
        "paddleocr_available": _paddle_available(),
        "paddleocr_version": "unknown",
        "paddlepaddle_version": "unknown",
        "paddle_init_args": dict(PADDLE_INIT_ARGS),
    }
    for package, key in (("paddleocr", "paddleocr_version"), ("paddlepaddle", "paddlepaddle_version")):
        try:
            info[key] = importlib.metadata.version(package)
        except Exception:
            pass
    return info


def _extract_paddle_text_blocks(results) -> list[dict[str, Any]]:
    """Extract per-line text blocks (text, confidence, bbox, page) from PaddleOCR results.

    Each element in `results` is a dict-like OCRResult for one page. Confidence
    ("rec_scores") and bbox ("rec_polys") are included only when present.
    """
    blocks: list[dict[str, Any]] = []
    for page_number, result in enumerate(results or [], start=1):
        if result is None:
            continue
        texts = result["rec_texts"] if "rec_texts" in result else []
        scores = result["rec_scores"] if "rec_scores" in result else None
        polys = result["rec_polys"] if "rec_polys" in result else None
        for index, text in enumerate(texts or []):
            if not text:
                continue
            block: dict[str, Any] = {"text": str(text), "page": page_number}
            if scores is not None and index < len(scores):
                try:
                    block["confidence"] = float(scores[index])
                except (TypeError, ValueError):
                    pass
            if polys is not None and index < len(polys):
                poly = polys[index]
                try:
                    block["bbox"] = [[float(x), float(y)] for x, y in poly]
                except (TypeError, ValueError):
                    pass
            blocks.append(block)
    return blocks


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


def _paddle_ocr_worker(payload: dict, queue) -> None:
    """Run PaddleOCR inference in a child process and put the result on `queue`.

    Must remain a module-level function so it can be pickled by the
    multiprocessing "spawn" start method on Windows.
    """
    started = time.perf_counter()
    device = payload.get("device")
    file_path = payload["file_path"]

    if device is not None:
        device_error = _set_paddle_device(device)
        if device_error is not None:
            queue.put({
                "success": False,
                "raw_text": "",
                "error": f"Device setup failed for {device!r}: {device_error}",
                "duration_ms": round((time.perf_counter() - started) * 1000),
            })
            return

    try:
        import paddleocr  # noqa: PLC0415 — lazy import, runs in child process only
        ocr = paddleocr.PaddleOCR(**PADDLE_INIT_ARGS)
        results = ocr.predict(file_path)
        raw_text = _flatten_paddle_result(results)
        text_blocks = _extract_paddle_text_blocks(results)
    except Exception as exc:
        queue.put({
            "success": False,
            "raw_text": "",
            "error": str(exc),
            "duration_ms": round((time.perf_counter() - started) * 1000),
        })
        return

    queue.put({
        "success": True,
        "raw_text": raw_text,
        "error": None,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "text_blocks": text_blocks,
    })


def _run_paddle_ocr_in_subprocess(
    file_path: str,
    device: str | None,
    timeout_seconds: int,
    *,
    worker=_paddle_ocr_worker,
) -> dict:
    """Run `worker` in a child process and enforce timeout_seconds at the OS level.

    Returns a dict with keys: success, raw_text, error, duration_ms.
    On timeout, terminates (then kills if necessary) the child process and
    returns a failed result whose error mentions "timed out" and the
    configured timeout_seconds.
    """
    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(
        target=worker,
        args=({"file_path": file_path, "device": device}, result_queue),
    )

    started = time.perf_counter()
    process.start()
    process.join(timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join(_TERMINATE_GRACE_SECONDS)
        if process.is_alive():
            process.kill()
            process.join()
        return {
            "success": False,
            "raw_text": "",
            "error": f"PaddleOCR subprocess timed out after {timeout_seconds}s",
            "duration_ms": round((time.perf_counter() - started) * 1000),
        }

    if not result_queue.empty():
        return result_queue.get()

    return {
        "success": False,
        "raw_text": "",
        "error": "PaddleOCR subprocess exited without a result",
        "duration_ms": round((time.perf_counter() - started) * 1000),
    }


class PaddleOcrProvider(OcrProviderBase):
    def __init__(
        self,
        *,
        device: str | None = None,
        provider_name: str | None = None,
        enforce_timeout: bool = False,
    ) -> None:
        self._device = device
        self._enforce_timeout = enforce_timeout
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

        if self._enforce_timeout:
            result_dict = _run_paddle_ocr_in_subprocess(file_path, self._device, timeout_seconds)
            return OcrProviderResult(
                provider_name=self.provider_name,
                source_type="ocr",
                raw_text=result_dict.get("raw_text", ""),
                success=result_dict.get("success", False),
                error=result_dict.get("error"),
                duration_ms=result_dict.get("duration_ms", 0),
                model=None,
                model_info=paddle_runtime_info(),
                text_blocks=result_dict.get("text_blocks"),
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
            ocr = paddleocr.PaddleOCR(**PADDLE_INIT_ARGS)
            results = ocr.predict(file_path)
            raw_text = _flatten_paddle_result(results)
            text_blocks = _extract_paddle_text_blocks(results)
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
                model_info=paddle_runtime_info(),
            )

        return OcrProviderResult(
            provider_name=self.provider_name,
            source_type="ocr",
            raw_text=raw_text,
            success=True,
            error=None,
            duration_ms=round((time.perf_counter() - started) * 1000),
            model=None,
            model_info=paddle_runtime_info(),
            text_blocks=text_blocks,
        )
