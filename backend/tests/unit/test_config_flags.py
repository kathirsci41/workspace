from app.config import Settings


def test_extraction_mode_flags_have_release_candidate_defaults():
    settings = Settings()

    assert settings.digital_text_enabled is True
    assert settings.digital_text_max_pages == 10
    assert settings.ocr_enabled is True
    assert settings.ocr_provider == "glm_ocr"
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
