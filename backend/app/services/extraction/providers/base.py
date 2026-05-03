"""Abstract base classes for the extraction provider layer.

The pipeline calls these interfaces. Providers implement them.
No provider-specific logic lives here — only contracts.

Adding a new provider:
  1. Create providers/<name>_provider.py
  2. Implement Layer1Provider and/or Layer2Provider
  3. Register in providers/__init__.py build_layer1_provider()
  4. Set LAYER1_PROVIDER=<name> in .env
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OcrResult:
    """Returned by every Layer1Provider.run_ocr()."""
    markdown: str     # cleaned markdown text from the document page
    elapsed_ms: int   # wall-clock time for this call
    provider: str     # e.g. "ollama", "datalab", "openai_compat", "digital"


@dataclass
class ExtractionResult:
    """Returned by every Layer2Provider.run_extraction()."""
    fields: dict      # raw parsed JSON — field_validator is called by the pipeline, not here
    elapsed_ms: int
    provider: str


class Layer1Provider(ABC):
    """Contract for the OCR layer: image bytes → markdown text.

    Implementations handle their own retries and circuit-breaking internally.
    The pipeline always calls await provider.run_ocr(...) — it never calls
    internal retry helpers or private methods directly.
    """

    @abstractmethod
    async def run_ocr(
        self,
        image_data: bytes,
        doc_type: str,
        page_label: str = "",
    ) -> OcrResult:
        """Convert a single page image to markdown text.

        Args:
            image_data: raw PNG bytes of a single document page
            doc_type:   DocumentType enum value string (e.g. "COMPANY_DC")
            page_label: human-readable label for logging ("doc123_p1")

        Returns:
            OcrResult. If the page produces empty/useless text, returns
            OcrResult(markdown="", ...) — never raises for empty content.

        Raises:
            ProviderError: on unrecoverable failure after internal retries.
        """
        ...

    async def release_vram(self) -> None:
        """Release GPU memory after all pages are OCR'd.

        Default is a no-op. OllamaLayer1Provider overrides this to call
        Ollama's keep_alive=0 endpoint. All other providers inherit the no-op.
        """
        pass

    async def wait_until_ready(self) -> None:
        """Wait for the model to be ready before the next phase.

        Default is a no-op. OllamaLayer1Provider overrides this with a
        post-release readiness poll. All other providers inherit the no-op.
        """
        pass

    @abstractmethod
    async def health_check(self) -> tuple[bool, str]:
        """Verify the provider is reachable and the required model is available.

        Returns:
            (True, "")               — healthy
            (False, "reason string") — unhealthy; reason is stored in last_error
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Short identifier used in logs and the model_version DB field."""
        ...


class Layer2Provider(ABC):
    """Contract for the extraction layer: markdown text → structured JSON dict.

    Implementations receive markdown text and a doc_type string.
    They MUST call build_extraction_prompt() from glm_ocr_prompts.py internally.
    They MUST NOT call validate_extracted_fields() — that is the pipeline's job.
    """

    @abstractmethod
    async def run_extraction(
        self,
        markdown: str,
        doc_type: str,
        customer_hint: str = "",
    ) -> ExtractionResult:
        """Extract structured fields from markdown text.

        Args:
            markdown:      cleaned OCR output from Layer 1
            doc_type:      DocumentType enum value string
            customer_hint: optional customer name for per-customer schema hints
                           (passed through to build_extraction_prompt)

        Returns:
            ExtractionResult. If JSON cannot be parsed, returns
            ExtractionResult(fields={}, ...) — never raises for empty/bad JSON.

        Raises:
            ProviderError: on unrecoverable failure after internal retries.
        """
        ...

    @abstractmethod
    async def health_check(self) -> tuple[bool, str]:
        """Same contract as Layer1Provider.health_check()."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...


class ProviderError(Exception):
    """Raised by providers on unrecoverable failures (after internal retries).

    The pipeline catches this at the page level and continues where possible,
    or propagates to the Celery task for PENDING_MODEL handling.
    """
    pass
