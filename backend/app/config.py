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
    ocr_model: str = os.getenv("OCR_MODEL", "glm-ocr:latest")
    ocr_base_url: str = os.getenv("OCR_BASE_URL", "http://localhost:11434")
    ocr_dpi: int = int(os.getenv("OCR_DPI", "200"))
    ocr_max_pages: int = int(os.getenv("OCR_MAX_PAGES", "5"))
    ocr_timeout_seconds: int = int(os.getenv("OCR_TIMEOUT_SECONDS", "90"))
    ocr_retry_attempts: int = int(os.getenv("OCR_RETRY_ATTEMPTS", "1"))
    ocr_min_text_length: int = int(os.getenv("OCR_MIN_TEXT_LENGTH", "30"))
    ocr_context_length: int = int(os.getenv("OCR_CONTEXT_LENGTH", "8192"))
    structured_rules_enabled: bool = os.getenv("STRUCTURED_RULES_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    model_layer2_enabled: bool = os.getenv("MODEL_LAYER2_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    model_layer2_provider: str = os.getenv("MODEL_LAYER2_PROVIDER", "ollama")
    model_layer2_model: str = os.getenv("MODEL_LAYER2_MODEL", "gemma4:31b-cloud")
    model_layer2_base_url: str = os.getenv("MODEL_LAYER2_BASE_URL", "http://localhost:11434")
    model_layer2_timeout_seconds: int = int(os.getenv("MODEL_LAYER2_TIMEOUT_SECONDS", "120"))
    model_layer2_context_length: int = int(os.getenv("MODEL_LAYER2_CONTEXT_LENGTH", "8192"))
    model_layer2_retry_attempts: int = int(os.getenv("MODEL_LAYER2_RETRY_ATTEMPTS", "1"))
    # Backward-compatible aliases for existing local settings.
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "gemma4:31b-cloud")


settings = Settings()


def replace_settings(new_settings: Settings) -> None:
    global settings
    settings = new_settings
