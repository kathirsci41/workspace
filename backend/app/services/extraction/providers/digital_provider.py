"""Digital PDF Layer 1 provider — programmatic text extraction, no model needed.

Wraps the existing DigitalExtractor (PyMuPDF + pdfplumber) behind the
Layer1Provider interface. The pipeline calls run_ocr_from_path() instead
of run_ocr() because DigitalExtractor needs a file path, not image bytes.
"""
import logging

from app.services.extraction.providers.base import (
    Layer1Provider,
    OcrResult,
    ProviderError,
)

logger = logging.getLogger(__name__)


class DigitalLayer1Provider(Layer1Provider):
    """Extracts text from digital-native PDFs without any model invocation.

    Accuracy: 100% (no OCR errors possible)
    Speed: < 100ms per page
    GPU cost: zero

    health_check() always returns (True, "") — no network dependency.
    release_vram() and wait_until_ready() are no-ops (inherited defaults).
    """

    def __init__(self, max_pages: int = 10):
        self.max_pages = max_pages
        from app.services.extraction.digital_extractor import DigitalExtractor
        self._extractor = DigitalExtractor()

    @property
    def provider_name(self) -> str:
        return "digital"

    async def run_ocr(
        self,
        image_data: bytes,
        doc_type: str,
        page_label: str = "",
    ) -> OcrResult:
        """Not used for digital PDFs — call run_ocr_from_path() instead.

        Raises ProviderError to prevent accidental use with image bytes.
        """
        raise ProviderError(
            "DigitalLayer1Provider.run_ocr() requires a file path. "
            "Call run_ocr_from_path(pdf_path) instead."
        )

    async def run_ocr_from_path(self, pdf_path: str) -> OcrResult:
        """Extract text from a digital PDF file.

        Returns OcrResult with empty markdown if the PDF is scanned/image-only.
        Never raises — caller should check markdown == "" to decide to fall through
        to the two-layer (image → model) path.
        """
        try:
            result = self._extractor.extract(pdf_path, max_pages=self.max_pages)
            markdown = result.full_text if result.is_digital else ""
            if markdown:
                logger.debug(
                    f"[Digital] Extracted {len(markdown)} chars from {pdf_path}"
                )
            return OcrResult(markdown=markdown, elapsed_ms=0, provider=self.provider_name)
        except Exception as e:
            logger.warning(f"[Digital] Extraction failed for {pdf_path}: {e}")
            return OcrResult(markdown="", elapsed_ms=0, provider=self.provider_name)

    async def health_check(self) -> tuple[bool, str]:
        """Always healthy — no network or model dependency."""
        return True, ""
