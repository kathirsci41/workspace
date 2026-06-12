"""PaddleOCR provider adapter.

PaddleOCR is not installed in this environment. Lazy imports ensure the module
loads regardless of whether paddleocr is available. When unavailable,
is_available() returns False and run_full_page() returns a failed result.
"""
from __future__ import annotations

import importlib.util
import time

from app.services.extraction.ocr_providers.base import OcrProviderBase, OcrProviderResult

_UNAVAILABLE_ERROR = "PaddleOCR is not installed"


def _paddle_available() -> bool:
    return importlib.util.find_spec("paddleocr") is not None


def _flatten_paddle_result(pages) -> str:
    """Flatten PaddleOCR page results into plain newline-separated text."""
    lines = []
    for page in (pages or []):
        for detection in (page or []):
            if detection and len(detection) >= 2:
                text_tuple = detection[1]
                if text_tuple and len(text_tuple) >= 1:
                    lines.append(str(text_tuple[0]))
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
            ocr = paddleocr.PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            pages = ocr.ocr(file_path, cls=True)
            raw_text = _flatten_paddle_result(pages)
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
