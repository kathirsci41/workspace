from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://docplatform:docplatform@localhost:5432/docplatform"
    sync_database_url: str = "postgresql://docplatform:docplatform@localhost:5432/docplatform"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Storage
    nas_base_path: str = "/nas/documents"

    # OCR
    ocr_base_url: str = "http://localhost:11434"
    ocr_model_name: str = "glm-ocr"
    ocr_timeout: int = 120
    ocr_max_retries: int = 3
    ocr_pdf_dpi: int = 200
    ocr_max_pages: int = 10

    # CORS
    cors_origins: List[str] = ["http://localhost:5173"]

    # Debug
    debug: bool = True

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
