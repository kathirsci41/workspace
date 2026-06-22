import importlib

import pytest

import app.config as config_module
from app.config import Settings, validate_ocr_runtime_settings


def test_extraction_mode_flags_have_release_candidate_defaults():
    settings = Settings()

    assert settings.digital_text_enabled is True
    assert settings.digital_text_max_pages == 10
    assert settings.ocr_enabled is True
    assert settings.ocr_provider == "glm_ocr"
    assert settings.ocr_require_paddle_provider is False
    assert settings.ocr_model == "glm-ocr:latest"
    assert settings.ocr_base_url == "http://localhost:11434"
    assert settings.ocr_dpi == 200
    assert settings.ocr_max_pages == 5
    assert settings.ocr_timeout_seconds == 90
    assert settings.ocr_retry_attempts == 1
    assert settings.ocr_min_text_length == 30
    assert settings.ocr_context_length == 8192
    assert settings.extraction_queue_enabled is True
    assert settings.ocr_extraction_max_concurrent == 1
    assert settings.ocr_extraction_queue_timeout_seconds == 900
    assert settings.ocr_extraction_queue_max_size == 10
    assert settings.structured_rules_enabled is True
    assert settings.model_layer2_enabled is False
    assert settings.model_layer2_provider == "ollama"
    assert settings.model_layer2_model == "gemma4:31b-cloud"
    assert settings.model_layer2_base_url == "http://localhost:11434"
    assert settings.model_layer2_timeout_seconds == 120
    assert settings.model_layer2_context_length == 8192
    assert settings.model_layer2_retry_attempts == 1


def test_ocr_require_paddle_provider_allows_paddle_provider():
    settings = Settings(ocr_require_paddle_provider=True, ocr_provider="paddleocr_gpu")

    validate_ocr_runtime_settings(settings)


def test_ocr_require_paddle_provider_rejects_glm_provider():
    settings = Settings(ocr_require_paddle_provider=True, ocr_provider="glm_ocr")

    with pytest.raises(
        RuntimeError,
        match=(
            "OCR_REQUIRE_PADDLE_PROVIDER=true but OCR_PROVIDER='glm_ocr'. "
            "Set OCR_PROVIDER=paddleocr_gpu or disable OCR_REQUIRE_PADDLE_PROVIDER."
        ),
    ):
        validate_ocr_runtime_settings(settings)


def test_paddle_fallback_uses_ocr_paddle_fallback_to_glm_env(monkeypatch: pytest.MonkeyPatch):
    with monkeypatch.context() as env:
        env.setenv("GLM_FALLBACK_ENABLED", "false")
        env.delenv("OCR_PADDLE_FALLBACK_TO_GLM", raising=False)
        reloaded = importlib.reload(config_module)
        assert reloaded.Settings().ocr_paddle_fallback_to_glm is True

        env.setenv("OCR_PADDLE_FALLBACK_TO_GLM", "false")
        reloaded = importlib.reload(config_module)
        assert reloaded.Settings().ocr_paddle_fallback_to_glm is False

    importlib.reload(config_module)
