"""PaddleOCR provider adapter.

Uses lazy imports so the module loads regardless of whether paddleocr is
installed. When unavailable, is_available() returns False and run_full_page()
returns a failed result.

API notes (PaddleOCR 3.7.0 / paddlex 3.7.x):
- Instantiate:  PaddleOCR(lang="en")  — use_angle_cls and show_log removed
- Call:         ocr.predict(file_path)  — .ocr() is deprecated
- Result:       list of OCRResult objects (one per page); each is dict-like
                with result["rec_texts"] = list[str] of recognized text lines
"""
from __future__ import annotations

import importlib.util
import time

from app.services.extraction.ocr_providers.base import OcrProviderBase, OcrProviderResult

_UNAVAILABLE_ERROR = "PaddleOCR is not installed"


def _paddle_available() -> bool:
    return importlib.util.find_spec("paddleocr") is not None


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
    @property
    def provider_name(self) -> str:
        return "paddleocr"

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
