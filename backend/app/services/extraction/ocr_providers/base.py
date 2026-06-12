"""Abstract base class for OCR providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class OcrProviderResult:
    provider_name: str
    source_type: str        # "ocr" | "ocr_header"
    raw_text: str
    success: bool
    error: str | None
    duration_ms: int
    model: str | None = field(default=None)


class OcrProviderBase(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    def supports_header(self) -> bool:
        return False

    def is_available(self) -> bool:
        return True

    @abstractmethod
    def run_full_page(
        self,
        file_path: str,
        *,
        max_pages: int,
        dpi: int,
        timeout_seconds: int,
    ) -> OcrProviderResult:
        ...

    def run_header(
        self,
        file_path: str,
        *,
        dpi: int,
        timeout_seconds: int,
    ) -> OcrProviderResult:
        raise NotImplementedError(f"{self.provider_name} does not support header OCR")
