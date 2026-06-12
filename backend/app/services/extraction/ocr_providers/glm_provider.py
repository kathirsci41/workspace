"""GLM OCR provider — wraps glm_ocr_client without changing any behavior."""
from __future__ import annotations

import time

import app.services.extraction.glm_ocr_client as _glm_ocr_client

from app.services.extraction.ocr_providers.base import OcrProviderBase, OcrProviderResult


class GlmOcrProvider(OcrProviderBase):
    @property
    def provider_name(self) -> str:
        return "glm"

    @property
    def supports_header(self) -> bool:
        return True

    def is_available(self) -> bool:
        health = _glm_ocr_client.check_ocr_provider_health()
        return bool(health.get("reachable", False))

    def run_full_page(
        self,
        file_path: str,
        *,
        max_pages: int,
        dpi: int,
        timeout_seconds: int,
    ) -> OcrProviderResult:
        started = time.perf_counter()
        try:
            r = _glm_ocr_client.extract_text_with_ocr(file_path, max_pages, dpi, timeout_seconds)
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
            raw_text=r.text,
            success=True,
            error=None,
            duration_ms=r.diagnostics.get("ocr_duration_ms", 0),
            model=r.model,
        )

    def run_header(
        self,
        file_path: str,
        *,
        dpi: int,
        timeout_seconds: int,
    ) -> OcrProviderResult:
        r = _glm_ocr_client.extract_header_text_with_ocr(
            file_path, dpi=dpi, timeout_seconds=timeout_seconds
        )
        return OcrProviderResult(
            provider_name=self.provider_name,
            source_type="ocr_header",
            raw_text=r.text,
            success=r.error is None,
            error=r.error,
            duration_ms=r.diagnostics.get("ocr_header_duration_ms", 0),
            model=r.model,
        )
