"""ExtractionPipeline — provider-agnostic extraction orchestrator.

Replaces the 3-branch extraction block in tasks.py with a single unified
flow that works with any Layer1/Layer2 provider combination.

Usage:
    pipeline = build_pipeline_from_config(settings)
    error = await pipeline.health_check()
    if error:
        # mark document as PENDING_MODEL
        ...

    # Digital path (programmatic text extraction)
    ocr_result = await pipeline.try_digital(pdf_path)
    if not ocr_result.markdown:
        # Scanned path: convert pages to images, then OCR each one
        ocr_result = await pipeline.run_ocr(image_data, doc_type, page_label)

    # After all OCR pages done:
    await pipeline.release_vram()
    await pipeline.wait_until_ready()

    # Extract structured fields from each page's markdown
    fields = await pipeline.run_extraction(markdown, doc_type)
"""
import logging
from typing import Optional

from app.services.extraction.providers.base import (
    Layer1Provider,
    Layer2Provider,
    OcrResult,
)
from app.services.extraction.providers.digital_provider import DigitalLayer1Provider
from app.services.extraction.field_validator import validate_extracted_fields

logger = logging.getLogger(__name__)


class ExtractionPipeline:
    """Coordinates Layer1 (OCR) and Layer2 (extraction) providers.

    The pipeline itself contains no provider-specific logic. All
    transport details live inside the provider implementations.
    """

    def __init__(
        self,
        layer1: Layer1Provider,
        layer2: Optional[Layer2Provider] = None,
        digital: Optional[DigitalLayer1Provider] = None,
    ):
        self.layer1 = layer1
        self.layer2 = layer2
        self.digital = digital or DigitalLayer1Provider()

    # ------------------------------------------------------------------
    # OCR
    # ------------------------------------------------------------------

    async def try_digital(self, pdf_path: str) -> OcrResult:
        """Attempt programmatic text extraction from a digital PDF.

        Returns OcrResult with empty markdown for scanned/image-only PDFs.
        Never raises.
        """
        return await self.digital.run_ocr_from_path(pdf_path)

    async def run_ocr(
        self,
        image_data: bytes,
        doc_type: str,
        page_label: str = "",
    ) -> OcrResult:
        """Run Layer 1 OCR on a single page image."""
        return await self.layer1.run_ocr(image_data, doc_type, page_label)

    # ------------------------------------------------------------------
    # VRAM lifecycle
    # ------------------------------------------------------------------

    async def release_vram(self) -> None:
        """Release GPU memory after all pages are OCR'd."""
        await self.layer1.release_vram()

    async def wait_until_ready(self) -> None:
        """Wait for the OCR model endpoint to become ready."""
        await self.layer1.wait_until_ready()

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    async def run_extraction(
        self,
        markdown: str,
        doc_type: str,
        customer_hint: str = "",
    ) -> dict:
        """Run Layer 2 extraction and validate the result.

        Returns a validated fields dict (never raises for bad/empty JSON).
        Raises RuntimeError when no Layer2 provider is configured.
        """
        if self.layer2 is None:
            raise RuntimeError(
                "No Layer2 provider configured. "
                "Set LAYER2_PROVIDER in .env or enable ocr_two_layer_enabled."
            )
        result: ExtractionResult = await self.layer2.run_extraction(
            markdown, doc_type, customer_hint
        )
        return validate_extracted_fields(result.fields, doc_type)

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> str:
        """Check that all configured providers are reachable and ready.

        Returns "" when healthy.
        Returns a human-readable error string when any provider is unhealthy.
        """
        errors = []

        ok1, msg1 = await self.layer1.health_check()
        if not ok1:
            errors.append(f"Layer1({self.layer1.provider_name}): {msg1}")

        if self.layer2 is not None:
            ok2, msg2 = await self.layer2.health_check()
            if not ok2:
                errors.append(f"Layer2({self.layer2.provider_name}): {msg2}")

        return "; ".join(errors)

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    @property
    def model_version(self) -> str:
        """Short string recorded in the model_version DB field."""
        l2_name = self.layer2.provider_name if self.layer2 else "none"
        return f"{self.layer1.provider_name}+{l2_name}"


def build_pipeline_from_config(settings) -> ExtractionPipeline:
    """Construct an ExtractionPipeline from app settings.

    Reads LAYER1_PROVIDER / LAYER2_PROVIDER first.
    Falls back to legacy ocr_* settings if those are empty.

    This is the single entry point for pipeline construction in tasks.py.
    """
    from app.services.extraction.providers import (
        build_layer1_provider,
        build_layer2_provider,
    )
    from app.services.extraction.providers.digital_provider import DigitalLayer1Provider

    layer1 = build_layer1_provider(settings)
    layer2 = build_layer2_provider(settings)
    digital = DigitalLayer1Provider(
        max_pages=getattr(settings, "ocr_max_pages", 10)
    )

    return ExtractionPipeline(layer1=layer1, layer2=layer2, digital=digital)
