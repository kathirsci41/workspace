from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "Order Assurance"
    api_prefix: str = "/api"
    app_env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_format: str = os.getenv("LOG_FORMAT", "text")
    enable_dev_tools: bool = os.getenv("ENABLE_DEV_TOOLS", "true").lower() in {"1", "true", "yes", "on"}
    backend_port: int = int(os.getenv("BACKEND_PORT", "8100"))
    frontend_port: int = 5180
    storage_dir: str = os.getenv("STORAGE_DIR", "storage/documents")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "20"))
    max_upload_bytes: int = max_upload_mb * 1024 * 1024
    file_retention_days: int = int(os.getenv("FILE_RETENTION_DAYS", "30"))
    temp_file_retention_hours: int = int(os.getenv("TEMP_FILE_RETENTION_HOURS", "24"))
    database_url: str = os.getenv("DATABASE_URL", os.getenv("ORDER_ASSURANCE_DATABASE_URL", "sqlite:///./order_assurance.db"))
    db_startup_max_attempts: int = int(os.getenv("DB_STARTUP_MAX_ATTEMPTS", "30"))
    db_startup_retry_seconds: float = float(os.getenv("DB_STARTUP_RETRY_SECONDS", "2"))
    digital_text_enabled: bool = os.getenv("DIGITAL_TEXT_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    digital_text_max_pages: int = int(os.getenv("DIGITAL_TEXT_MAX_PAGES", "10"))
    ocr_enabled: bool = os.getenv("OCR_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    ocr_provider: str = os.getenv("OCR_PROVIDER", "glm_ocr")
    ocr_require_paddle_provider: bool = os.getenv("OCR_REQUIRE_PADDLE_PROVIDER", "false").lower() in {"1", "true", "yes", "on"}
    ocr_model: str = os.getenv("OCR_MODEL", "glm-ocr:latest")
    ocr_base_url: str = os.getenv("OCR_BASE_URL", "http://localhost:11434")
    ocr_dpi: int = int(os.getenv("OCR_DPI", "200"))
    ocr_max_pages: int = int(os.getenv("OCR_MAX_PAGES", "5"))
    ocr_timeout_seconds: int = int(os.getenv("OCR_TIMEOUT_SECONDS", "90"))
    ocr_retry_attempts: int = int(os.getenv("OCR_RETRY_ATTEMPTS", "1"))
    ocr_min_text_length: int = int(os.getenv("OCR_MIN_TEXT_LENGTH", "30"))
    ocr_context_length: int = int(os.getenv("OCR_CONTEXT_LENGTH", "8192"))
    ocr_paddle_device: str = os.getenv("OCR_PADDLE_DEVICE", "gpu:0")
    ocr_paddle_timeout_seconds: int = int(os.getenv("OCR_PADDLE_TIMEOUT_SECONDS", "60"))
    ocr_paddle_fallback_to_glm: bool = os.getenv("OCR_PADDLE_FALLBACK_TO_GLM", "true").lower() in {"1", "true", "yes", "on"}
    # Comma-separated allowlist of document types that may use PaddleOCR when
    # OCR_PROVIDER=paddleocr_gpu. Conservative default keeps only VENDOR_INVOICE
    # so unset-env behavior is unchanged; local validation can widen it.
    ocr_paddle_document_types: str = os.getenv("OCR_PADDLE_DOCUMENT_TYPES", "VENDOR_INVOICE")
    ocr_auto_rotate_enabled: bool = os.getenv("OCR_AUTO_ROTATE_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    ocr_auto_rotate_timeout_seconds: int = int(os.getenv("OCR_AUTO_ROTATE_TIMEOUT_SECONDS", "30"))
    extraction_queue_enabled: bool = os.getenv("EXTRACTION_QUEUE_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    ocr_extraction_max_concurrent: int = int(os.getenv("OCR_EXTRACTION_MAX_CONCURRENT", "1"))
    ocr_extraction_queue_timeout_seconds: int = int(os.getenv("OCR_EXTRACTION_QUEUE_TIMEOUT_SECONDS", "900"))
    ocr_extraction_queue_max_size: int = int(os.getenv("OCR_EXTRACTION_QUEUE_MAX_SIZE", "10"))
    structured_rules_enabled: bool = os.getenv("STRUCTURED_RULES_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    model_layer2_enabled: bool = os.getenv("MODEL_LAYER2_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    model_layer2_provider: str = os.getenv("MODEL_LAYER2_PROVIDER", "ollama")
    model_layer2_model: str = os.getenv("MODEL_LAYER2_MODEL", "gemma4:31b-cloud")
    model_layer2_base_url: str = os.getenv("MODEL_LAYER2_BASE_URL", "http://localhost:11434")
    model_layer2_timeout_seconds: int = int(os.getenv("MODEL_LAYER2_TIMEOUT_SECONDS", "120"))
    model_layer2_context_length: int = int(os.getenv("MODEL_LAYER2_CONTEXT_LENGTH", "8192"))
    model_layer2_retry_attempts: int = int(os.getenv("MODEL_LAYER2_RETRY_ATTEMPTS", "1"))
    evidence_capture_enabled: bool = os.getenv("EVIDENCE_CAPTURE_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    # Backward-compatible aliases for existing local settings.
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "gemma4:31b-cloud")


settings = Settings()


def validate_ocr_runtime_settings(current_settings: Settings | None = None) -> None:
    current = current_settings or settings
    if current.ocr_require_paddle_provider and current.ocr_provider != "paddleocr_gpu":
        raise RuntimeError(
            "OCR_REQUIRE_PADDLE_PROVIDER=true but "
            f"OCR_PROVIDER='{current.ocr_provider}'. "
            "Set OCR_PROVIDER=paddleocr_gpu or disable OCR_REQUIRE_PADDLE_PROVIDER."
        )


def replace_settings(new_settings: Settings) -> None:
    global settings
    settings = new_settings
