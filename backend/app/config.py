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
    ocr_save_debug_markdown: bool = False
    # Extractor cloud override — if set, Layer 2 calls this URL instead of ocr_base_url
    ocr_extractor_base_url: str = ""   # empty = use local ocr_base_url
    ocr_extractor_api_key: str = ""    # empty = no auth header

    # CORS
    cors_origins: List[str] = ["http://localhost:5174"]

    # Debug
    debug: bool = True

    model_config = {
        "env_file": str(_PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
    }


settings = Settings()
