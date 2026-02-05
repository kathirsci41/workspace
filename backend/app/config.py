from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "postgresql://docplatform:docplatform@localhost:5432/docplatform"
    
    # Storage
    nas_base_path: str = "/nas/cases"
    
    # Application
    app_name: str = "Document Platform V1.1"
    debug: bool = True
    
    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    
    class Config:
        env_file = Path(__file__).resolve().parent.parent / ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
