"""
Unit tests for paddleocr_vl_service.py (Sprint 2, Task 2.3).

All tests run without transformers/torch/GPU installed — dependencies are mocked.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from app.services.paddleocr_vl_service import (
    PaddleOcrVlProvider,
    _transformers_available,
    extract_text_vl,
)
from app.services.extraction.ocr_providers.base import OcrProviderResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_transformers(output_text: str = "EXTRACTED TEXT"):
    """Return a mock transformers module that simulates PaddleOCR-VL-1.6 inference."""
    mock_processor = MagicMock()
    mock_model = MagicMock()

    # Processor produces inputs dict-like
    mock_inputs = MagicMock()
    mock_inputs.__getitem__ = lambda self, k: MagicMock(shape=(1, 10)) if k == "input_ids" else MagicMock()
    mock_inputs.to.return_value = mock_inputs
    mock_processor.return_value = mock_inputs

    # Model generates output ids; decode returns the text
    import torch
    mock_output = torch.zeros(1, 15, dtype=torch.long)
    mock_model.generate.return_value = mock_output
    mock_model.device = "cpu"
    mock_processor.decode.return_value = output_text

    mock_tf = MagicMock()
    mock_tf.AutoProcessor.from_pretrained.return_value = mock_processor
    mock_tf.AutoModelForCausalLM.from_pretrained.return_value = mock_model
    return mock_tf, mock_processor, mock_model


# ---------------------------------------------------------------------------
# _transformers_available
# ---------------------------------------------------------------------------

class TestTransformersAvailable:
    def test_returns_false_when_transformers_missing(self):
        with patch("importlib.util.find_spec", return_value=None):
            assert _transformers_available() is False

    def test_returns_true_when_both_present(self):
        with patch("importlib.util.find_spec", return_value=MagicMock()):
            assert _transformers_available() is True


# ---------------------------------------------------------------------------
# PaddleOcrVlProvider — interface
# ---------------------------------------------------------------------------

class TestPaddleOcrVlProviderInterface:
    def test_provider_name(self):
        assert PaddleOcrVlProvider().provider_name == "paddleocr_vl"

    def test_supports_header(self):
        # VLM reads full page including header
        assert PaddleOcrVlProvider().supports_header is True

    def test_is_available_false_when_transformers_missing(self):
        with patch("app.services.paddleocr_vl_service._transformers_available", return_value=False):
            assert PaddleOcrVlProvider().is_available() is False

    def test_is_available_true_when_transformers_present(self):
        with patch("app.services.paddleocr_vl_service._transformers_available", return_value=True):
            assert PaddleOcrVlProvider().is_available() is True

    def test_is_subclass_of_ocr_provider_base(self):
        from app.services.extraction.ocr_providers.base import OcrProviderBase
        assert issubclass(PaddleOcrVlProvider, OcrProviderBase)


# ---------------------------------------------------------------------------
# PaddleOcrVlProvider — run_full_page when unavailable
# ---------------------------------------------------------------------------

class TestPaddleOcrVlProviderUnavailable:
    def test_run_full_page_success_false_when_unavailable(self):
        with patch("app.services.paddleocr_vl_service._transformers_available", return_value=False):
            result = PaddleOcrVlProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.success is False

    def test_run_full_page_error_when_unavailable(self):
        with patch("app.services.paddleocr_vl_service._transformers_available", return_value=False):
            result = PaddleOcrVlProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.error is not None
        assert "transformers" in result.error.lower() or "torch" in result.error.lower()

    def test_run_full_page_raw_text_empty_when_unavailable(self):
        with patch("app.services.paddleocr_vl_service._transformers_available", return_value=False):
            result = PaddleOcrVlProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.raw_text == ""

    def test_run_full_page_provider_name_when_unavailable(self):
        with patch("app.services.paddleocr_vl_service._transformers_available", return_value=False):
            result = PaddleOcrVlProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.provider_name == "paddleocr_vl"

    def test_run_full_page_source_type_when_unavailable(self):
        with patch("app.services.paddleocr_vl_service._transformers_available", return_value=False):
            result = PaddleOcrVlProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.source_type == "ocr"


# ---------------------------------------------------------------------------
# extract_text_vl — safe failure paths
# ---------------------------------------------------------------------------

class TestExtractTextVl:
    def test_returns_empty_when_transformers_not_available(self):
        import app.services.paddleocr_vl_service as svc
        # Reset module state
        svc._model = None
        svc._processor = None
        svc._load_error = None
        with patch("app.services.paddleocr_vl_service._transformers_available", return_value=False):
            result = extract_text_vl("/tmp/fake.png")
        assert result == ""

    def test_returns_empty_on_load_failure(self):
        import app.services.paddleocr_vl_service as svc
        svc._model = None
        svc._processor = None
        svc._load_error = None
        with patch("app.services.paddleocr_vl_service._transformers_available", return_value=True), \
             patch("app.services.paddleocr_vl_service._load_model") as mock_load:
            # Simulate load setting _load_error without loading model
            def _fail_load():
                svc._load_error = "GPU OOM"
            mock_load.side_effect = _fail_load
            result = extract_text_vl("/tmp/fake.png")
        assert result == ""

    def test_returns_empty_on_inference_exception(self):
        import app.services.paddleocr_vl_service as svc
        svc._model = MagicMock()
        svc._processor = MagicMock()
        svc._load_error = None
        with patch("app.services.paddleocr_vl_service._load_model"):
            with patch("builtins.open", side_effect=FileNotFoundError("no file")):
                # Patch PIL import to raise
                with patch.dict(sys.modules, {"PIL": None, "PIL.Image": None}):
                    result = extract_text_vl("/tmp/missing.png")
        # Must not raise, must return ""
        assert isinstance(result, str)

    def test_does_not_raise_on_any_failure(self):
        import app.services.paddleocr_vl_service as svc
        svc._model = MagicMock(side_effect=RuntimeError("GPU exploded"))
        svc._processor = MagicMock()
        svc._load_error = None
        try:
            result = extract_text_vl("/tmp/fake.png")
            assert isinstance(result, str)
        except Exception as exc:
            pytest.fail(f"extract_text_vl raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------

class TestVlProviderRegistryIntegration:
    def test_paddleocr_vl_registered(self):
        from app.services.extraction.ocr_providers import get_ocr_provider
        provider = get_ocr_provider("paddleocr_vl")
        assert isinstance(provider, PaddleOcrVlProvider)

    def test_default_provider_still_glm(self):
        from app.services.extraction.ocr_providers import get_default_ocr_provider
        assert get_default_ocr_provider().provider_name == "glm"

    def test_all_three_providers_registered(self):
        from app.services.extraction.ocr_providers import get_ocr_provider
        assert get_ocr_provider("glm").provider_name == "glm"
        assert get_ocr_provider("paddleocr").provider_name == "paddleocr"
        assert get_ocr_provider("paddleocr_vl").provider_name == "paddleocr_vl"


# ---------------------------------------------------------------------------
# Config: ocr_paddle_vl_fallback setting
# ---------------------------------------------------------------------------

class TestVlFallbackConfig:
    def test_vl_fallback_disabled_by_default(self):
        from app.config import Settings
        s = Settings()
        assert s.ocr_paddle_vl_fallback is False

    def test_vl_fallback_enabled_via_env(self, monkeypatch):
        # Settings is a frozen dataclass: defaults bind at import, so the env
        # var only takes effect after reloading the module (see test_config_flags).
        import importlib
        import app.config as config_module
        monkeypatch.setenv("OCR_PADDLE_VL_FALLBACK", "true")
        try:
            reloaded = importlib.reload(config_module)
            assert reloaded.Settings().ocr_paddle_vl_fallback is True
        finally:
            monkeypatch.delenv("OCR_PADDLE_VL_FALLBACK", raising=False)
            importlib.reload(config_module)
