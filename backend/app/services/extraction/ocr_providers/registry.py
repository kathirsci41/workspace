"""OCR provider registry.

GLM is the production default.  Unknown provider names raise ValueError.

Sprint 2 additions:
  "paddleocr_vl" - PaddleOCR-VL-1.6 VLM fallback (HuggingFace, GPU >=4 GB).
  Set OCR_PROVIDER=paddleocr_vl to use as primary provider.
"""
from __future__ import annotations

from app.services.extraction.ocr_providers.base import OcrProviderBase
from app.services.extraction.ocr_providers.glm_provider import GlmOcrProvider
from app.services.extraction.ocr_providers.paddle_provider import PaddleOcrProvider
from app.services.paddleocr_vl_service import PaddleOcrVlProvider

_DEFAULT_PROVIDER = "glm"

_REGISTRY: dict[str, OcrProviderBase] = {
    "glm": GlmOcrProvider(),
    "paddleocr": PaddleOcrProvider(),
    "paddleocr_vl": PaddleOcrVlProvider(),
}


def get_ocr_provider(name: str) -> OcrProviderBase:
    provider = _REGISTRY.get(name)
    if provider is None:
        known = ", ".join(sorted(_REGISTRY))
        raise ValueError(f"Unknown OCR provider: {name!r}. Known providers: {known}")
    return provider


def get_default_ocr_provider() -> OcrProviderBase:
    return get_ocr_provider(_DEFAULT_PROVIDER)
