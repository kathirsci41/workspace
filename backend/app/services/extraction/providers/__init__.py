"""Provider factory helpers.

Usage in pipeline.py:
    layer1 = build_layer1_provider(settings)
    layer2 = build_layer2_provider(settings)

Adding a new provider:
  1. Create providers/<name>_provider.py
  2. Implement Layer1Provider and/or Layer2Provider
  3. Register the name string in build_layer1_provider / build_layer2_provider
  4. Set LAYER1_PROVIDER=<name> in .env
"""
from app.services.extraction.providers.base import (  # noqa: F401
    OcrResult,
    ExtractionResult,
    Layer1Provider,
    Layer2Provider,
    ProviderError,
)


def build_layer1_provider(settings) -> "Layer1Provider":
    """Construct a Layer1Provider from app settings.

    Provider selection order:
      1. settings.layer1_provider  (new-style, explicit)
      2. settings.ocr_two_layer_enabled  (legacy — builds OllamaLayer1Provider)
      3. fallback → OCRClientLayer1Adapter  (legacy single-layer path)
    """
    name = (settings.layer1_provider or "").strip().lower()

    if name == "ollama":
        from app.services.extraction.providers.ollama_provider import OllamaLayer1Provider
        return OllamaLayer1Provider(
            base_url=settings.ocr_base_url,
            model=settings.ocr_custom_model or "glm-ocr:latest",
            timeout=settings.ocr_timeout,
            max_retries=settings.ocr_max_retries,
            num_ctx=settings.ocr_num_ctx,
            save_debug_markdown=settings.ocr_save_debug_markdown,
            debug_markdown_dir=settings.ocr_debug_markdown_dir,
        )

    if name == "datalab":
        from app.services.extraction.providers.datalab_provider import DatalabLayer1Provider
        return DatalabLayer1Provider(
            api_key=settings.datalab_api_key,
            base_url=settings.datalab_base_url,
            timeout=settings.datalab_timeout,
            poll_interval=settings.datalab_poll_interval,
        )

    if name == "openai_compat":
        from app.services.extraction.providers.openai_compat_provider import OpenAICompatLayer1Provider
        return OpenAICompatLayer1Provider(
            base_url=settings.openai_compat_base_url,
            model=settings.openai_compat_layer1_model,
            api_key=settings.openai_compat_api_key,
            timeout=settings.openai_compat_timeout,
            max_tokens=settings.openai_compat_max_tokens,
        )

    if name == "digital":
        from app.services.extraction.providers.digital_provider import DigitalLayer1Provider
        return DigitalLayer1Provider(max_pages=settings.ocr_max_pages)

    if name:
        raise ValueError(
            f"Unknown LAYER1_PROVIDER='{name}'. "
            f"Valid values: ollama, datalab, openai_compat, digital"
        )

    # ── Legacy fallback ────────────────────────────────────────────────
    if getattr(settings, "ocr_two_layer_enabled", False):
        from app.services.extraction.providers.ollama_provider import OllamaLayer1Provider
        return OllamaLayer1Provider(
            base_url=settings.ocr_base_url,
            model=settings.ocr_custom_model or "glm-ocr:latest",
            timeout=settings.ocr_timeout,
            max_retries=settings.ocr_max_retries,
            num_ctx=settings.ocr_num_ctx,
            save_debug_markdown=settings.ocr_save_debug_markdown,
            debug_markdown_dir=settings.ocr_debug_markdown_dir,
        )

    from app.services.extraction.providers.ollama_provider import OCRClientLayer1Adapter
    return OCRClientLayer1Adapter(settings)


def build_layer2_provider(settings) -> "Layer2Provider":
    """Construct a Layer2Provider from app settings.

    Provider selection order:
      1. settings.layer2_provider  (new-style, explicit)
      2. settings.ocr_two_layer_enabled  (legacy — builds OllamaLayer2Provider)
      3. None  (single-layer path — pipeline skips Layer 2)
    """
    name = (settings.layer2_provider or "").strip().lower()

    if name == "ollama":
        from app.services.extraction.providers.ollama_provider import OllamaLayer2Provider
        extractor_url = (
            getattr(settings, "ocr_extractor_base_url", "") or settings.ocr_base_url
        )
        return OllamaLayer2Provider(
            base_url=extractor_url,
            model=getattr(settings, "ocr_extractor_model", "") or "qwen2.5:7b",
            timeout=settings.ocr_timeout,
            max_retries=settings.ocr_max_retries,
            num_ctx=getattr(settings, "ocr_extractor_num_ctx", 4096),
            num_predict=getattr(settings, "ocr_extractor_num_predict", 4096),
            api_key=getattr(settings, "ocr_extractor_api_key", ""),
        )

    if name == "openai_compat":
        from app.services.extraction.providers.openai_compat_provider import OpenAICompatLayer2Provider
        return OpenAICompatLayer2Provider(
            base_url=settings.openai_compat_base_url,
            model=settings.openai_compat_layer2_model,
            api_key=settings.openai_compat_api_key,
            timeout=settings.openai_compat_timeout,
            max_tokens=settings.openai_compat_max_tokens,
        )

    if name:
        raise ValueError(
            f"Unknown LAYER2_PROVIDER='{name}'. "
            f"Valid values: ollama, openai_compat"
        )

    # ── Legacy fallback ────────────────────────────────────────────────
    if getattr(settings, "ocr_two_layer_enabled", False):
        from app.services.extraction.providers.ollama_provider import OllamaLayer2Provider
        extractor_url = (
            getattr(settings, "ocr_extractor_base_url", "") or settings.ocr_base_url
        )
        return OllamaLayer2Provider(
            base_url=extractor_url,
            model=getattr(settings, "ocr_extractor_model", "") or "qwen2.5:7b",
            timeout=settings.ocr_timeout,
            max_retries=settings.ocr_max_retries,
            num_ctx=getattr(settings, "ocr_extractor_num_ctx", 4096),
            num_predict=getattr(settings, "ocr_extractor_num_predict", 4096),
            api_key=getattr(settings, "ocr_extractor_api_key", ""),
        )

    return None
