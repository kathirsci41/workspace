"""OCR provider abstraction and registry.

GLM remains the production default.  Production extraction_service.py
imports glm_ocr_client directly and is not wired here yet (Phase 1t scope).
"""
from app.services.extraction.ocr_providers.registry import (
    get_default_ocr_provider,
    get_ocr_provider,
)
from app.services.extraction.ocr_providers.base import OcrProviderBase, OcrProviderResult

__all__ = [
    "get_ocr_provider",
    "get_default_ocr_provider",
    "OcrProviderBase",
    "OcrProviderResult",
]
