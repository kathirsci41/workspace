from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List

# Resolve the project root (.env lives two levels above this file: app/ → backend/ → project/)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://docplatform:docplatform@localhost:5432/docplatform"
    sync_database_url: str = "postgresql://docplatform:docplatform@localhost:5432/docplatform"

    # Redis
    redis_url: str = "redis://localhost:6380/0"

    # Storage
    nas_base_path: str = "/nas/documents"

    # Company info (used for GST auto-detection)
    company_state: str = ""  # e.g. "Tamil Nadu" — set in .env for GST IGST/CGST detection

    # OCR
    ocr_base_url: str = "http://localhost:11434"
    ocr_model_name: str = "glm-ocr"
    ocr_timeout: int = 120
    ocr_max_retries: int = 3
    ocr_pdf_dpi: int = 300
    ocr_max_pages: int = 10

    # Two-layer OCR pipeline (GLM-OCR → Qwen2.5 extraction)
    ocr_two_layer_enabled: bool = False
    ocr_custom_model: str = "glm-ocr:latest"
    ocr_extractor_model: str = "qwen2.5:7b"
    ocr_extractor_num_ctx: int = 4096
    ocr_extractor_num_predict: int = 4096
    ocr_save_debug_markdown: bool = False
    ocr_debug_markdown_dir: str = "debug_markdown"
    # Extractor cloud override — if set, Layer 2 calls this URL instead of ocr_base_url
    ocr_extractor_base_url: str = ""   # empty = use local ocr_base_url
    ocr_extractor_api_key: str = ""    # empty = no auth header
    # TLS verification for extractor HTTP calls.
    # Set to a CA bundle path (e.g. /etc/ssl/certs/ca-certificates.crt) when the
    # extractor endpoint uses a private/self-signed cert.  Leave empty to use the
    # system default trust store (recommended for public endpoints).
    ocr_extractor_ca_bundle: str | None = None

    # ── Provider abstraction layer ────────────────────────────────────────────
    # Set layer1_provider to activate new-style config.
    # Leave empty to use legacy ocr_* settings (zero disruption).
    layer1_provider: str = ""   # "ollama" | "datalab" | "openai_compat" | "digital"
    layer2_provider: str = ""   # "ollama" | "openai_compat"

    # Datalab (Layer 1) — https://documentation.datalab.to/
    datalab_api_key: str = ""
    datalab_base_url: str = "https://api.datalab.to"
    datalab_timeout: int = 300
    datalab_poll_interval: int = 3

    # OpenAI-compatible — vLLM, LM Studio, Groq, OpenAI, or any /v1/chat/completions endpoint
    openai_compat_base_url: str = ""
    openai_compat_api_key: str = ""
    openai_compat_layer1_model: str = ""   # vision model for Layer 1 OCR
    openai_compat_layer2_model: str = ""   # text model for Layer 2 extraction
    openai_compat_max_tokens: int = 4096
    openai_compat_timeout: int = 120

    # OCR context window (shared by legacy and new Ollama provider)
    ocr_num_ctx: int = 16384

    # Chat assistant model (separate from extraction — must support /api/chat)
    chat_model: str = "qwen2.5:3b"
    chat_base_url: str = ""  # empty = use ocr_base_url (localhost:11434)

    # CORS
    cors_origins: List[str] = []

    # Debug
    debug: bool = False

    # Benchmark mode (safety gates for local-only testing)
    benchmark_mode_enabled: bool = False
    benchmark_ollama_endpoint: str = "http://localhost:11434"

    model_config = {
        "env_file": str(_PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
    }

    def validate_benchmark_config(self) -> None:
        """Ensure benchmarks cannot leak customer data to external services"""
        if not self.benchmark_mode_enabled:
            return  # Benchmark mode disabled, no validation needed

        # Only allow local endpoints
        local_endpoints = [
            "http://localhost:11434",
            "http://127.0.0.1:11434",
        ]

        is_local = any(
            self.benchmark_ollama_endpoint.startswith(endpoint)
            for endpoint in local_endpoints
        )

        if not is_local:
            raise RuntimeError(
                f"SECURITY: Benchmark mode requires local Ollama endpoint only.\n"
                f"  Configured: {self.benchmark_ollama_endpoint}\n"
                f"  Allowed: {local_endpoints}\n"
                f"  Reason: Prevents accidental customer data exfiltration to external services.\n"
                f"  Fix: Set BENCHMARK_OLLAMA_ENDPOINT to http://localhost:11434 in .env"
            )

        # Log for audit trail
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            "BENCHMARK MODE ACTIVE - Using synthetic data only. "
            "No customer documents will be processed."
        )


settings = Settings()
