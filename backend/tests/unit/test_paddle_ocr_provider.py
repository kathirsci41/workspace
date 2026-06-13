"""Phase 1u/1v: PaddleOCR provider adapter tests.

Real API (PaddleOCR 3.7.0 / paddlex 3.7.x, verified in Phase 1v):
- Instantiate:  PaddleOCR(lang="en")
- Call:         ocr.predict(file_path)  (.ocr() is deprecated)
- Result:       list of dict-like OCRResult objects; result["rec_texts"] = list[str]

Covers:
- PaddleOcrProvider can be imported without paddleocr installed
- No paddleocr import at module load time
- is_available() when unavailable (mocked _paddle_available=False)
- run_full_page() failure result shape when unavailable
- is_available() and run_full_page() when available (mocked paddleocr module)
- PaddleOCR output flattened from rec_texts to plain text
- Registry: "paddleocr" key returns PaddleOcrProvider, default still GLM
- Production extraction_service not mutated
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from app.services.extraction.ocr_providers import (
    get_default_ocr_provider,
    get_ocr_provider,
)
from app.services.extraction.ocr_providers.base import OcrProviderBase, OcrProviderResult
from app.services.extraction.ocr_providers.paddle_provider import PaddleOcrProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_paddle_result(texts: list[str]):
    """Minimal PaddleOCR 3.7.0 predict() output: one page, rec_texts = list of strings."""
    # Real format: list of dict-like OCRResult objects with result["rec_texts"]
    page_result = {"rec_texts": list(texts)}
    return [page_result]


def _make_mock_paddle_module(texts: list[str] | None = None):
    if texts is None:
        texts = ["LINE ONE", "LINE TWO"]
    mock_module = MagicMock()
    mock_ocr_instance = MagicMock()
    mock_ocr_instance.predict.return_value = _make_paddle_result(texts)
    mock_module.PaddleOCR.return_value = mock_ocr_instance
    return mock_module, mock_ocr_instance


# ---------------------------------------------------------------------------
# Unavailable — PaddleOCR not installed
# ---------------------------------------------------------------------------


class TestPaddleOcrProviderUnavailable:
    def test_can_be_imported_without_paddleocr(self):
        from app.services.extraction.ocr_providers.paddle_provider import PaddleOcrProvider  # noqa: F401

    def test_no_paddleocr_import_at_module_level(self):
        import app.services.extraction.ocr_providers.paddle_provider  # noqa: F401
        assert "paddleocr" not in sys.modules

    def test_is_subclass_of_ocr_provider_base(self):
        assert issubclass(PaddleOcrProvider, OcrProviderBase)

    def test_provider_name_is_paddleocr(self):
        assert PaddleOcrProvider().provider_name == "paddleocr"

    def test_supports_header_is_false(self):
        assert PaddleOcrProvider().supports_header is False

    def test_is_available_false_when_package_missing(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=False):
            assert PaddleOcrProvider().is_available() is False

    def test_run_full_page_success_false_when_missing(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=False):
            result = PaddleOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.success is False

    def test_run_full_page_error_message_when_missing(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=False):
            result = PaddleOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.error is not None
        assert "not installed" in result.error.lower() or "paddleocr" in result.error.lower()

    def test_run_full_page_raw_text_empty_when_missing(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=False):
            result = PaddleOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.raw_text == ""

    def test_run_full_page_provider_name_when_missing(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=False):
            result = PaddleOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.provider_name == "paddleocr"

    def test_run_full_page_source_type_when_missing(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=False):
            result = PaddleOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.source_type == "ocr"

    def test_run_header_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            PaddleOcrProvider().run_header("f.pdf", dpi=150, timeout_seconds=60)


# ---------------------------------------------------------------------------
# Available — mocked paddleocr module
# ---------------------------------------------------------------------------


class TestPaddleOcrProviderAvailable:
    def test_is_available_true_when_package_found(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True):
            assert PaddleOcrProvider().is_available() is True

    def test_run_full_page_success_true_when_available(self):
        mock_module, _ = _make_mock_paddle_module()
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True):
            with patch.dict(sys.modules, {"paddleocr": mock_module}):
                result = PaddleOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.success is True
        assert result.error is None

    def test_run_full_page_raw_text_flattened(self):
        mock_module, _ = _make_mock_paddle_module(["FIRST LINE", "SECOND LINE"])
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True):
            with patch.dict(sys.modules, {"paddleocr": mock_module}):
                result = PaddleOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert "FIRST LINE" in result.raw_text
        assert "SECOND LINE" in result.raw_text

    def test_run_full_page_provider_name_when_available(self):
        mock_module, _ = _make_mock_paddle_module()
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True):
            with patch.dict(sys.modules, {"paddleocr": mock_module}):
                result = PaddleOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.provider_name == "paddleocr"

    def test_run_full_page_source_type_when_available(self):
        mock_module, _ = _make_mock_paddle_module()
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True):
            with patch.dict(sys.modules, {"paddleocr": mock_module}):
                result = PaddleOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.source_type == "ocr"

    def test_run_full_page_has_duration_ms(self):
        mock_module, _ = _make_mock_paddle_module()
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True):
            with patch.dict(sys.modules, {"paddleocr": mock_module}):
                result = PaddleOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert isinstance(result.duration_ms, int)
        assert result.duration_ms >= 0

    def test_run_full_page_paddle_class_instantiated(self):
        mock_module, mock_ocr_instance = _make_mock_paddle_module()
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True):
            with patch.dict(sys.modules, {"paddleocr": mock_module}):
                PaddleOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        mock_module.PaddleOCR.assert_called_once()

    def test_run_full_page_predict_called_with_file_path(self):
        mock_module, mock_ocr_instance = _make_mock_paddle_module()
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True):
            with patch.dict(sys.modules, {"paddleocr": mock_module}):
                PaddleOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        mock_ocr_instance.predict.assert_called_once_with("f.pdf")

    def test_run_full_page_success_false_on_exception(self):
        mock_module = MagicMock()
        mock_module.PaddleOCR.side_effect = RuntimeError("paddle internal error")
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True):
            with patch.dict(sys.modules, {"paddleocr": mock_module}):
                result = PaddleOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.success is False
        assert "paddle internal error" in (result.error or "")


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


class TestPaddleRegistryIntegration:
    def test_registry_returns_paddle_provider_for_paddleocr_key(self):
        provider = get_ocr_provider("paddleocr")
        assert isinstance(provider, PaddleOcrProvider)

    def test_paddle_provider_name_from_registry(self):
        provider = get_ocr_provider("paddleocr")
        assert provider.provider_name == "paddleocr"

    def test_default_provider_still_glm(self):
        assert get_default_ocr_provider().provider_name == "glm"

    def test_unknown_provider_still_raises_value_error(self):
        with pytest.raises(ValueError):
            get_ocr_provider("azure_vision")

    def test_unknown_provider_error_still_mentions_glm(self):
        with pytest.raises(ValueError, match="glm"):
            get_ocr_provider("nonexistent_xyz")


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------


class TestPaddleProviderSafety:
    def test_no_paddleocr_import_triggered_by_registry_import(self):
        import app.services.extraction.ocr_providers  # noqa: F401
        assert "paddleocr" not in sys.modules
        assert "paddle" not in sys.modules

    def test_production_extraction_service_not_mutated(self):
        import app.services.extraction_service as svc  # noqa: F401
        import app.services.extraction.glm_ocr_client as glm  # noqa: F401
        assert hasattr(glm, "extract_text_with_ocr")
        assert hasattr(glm, "extract_header_text_with_ocr")

    def test_no_installation_required_for_test_suite(self):
        # If this line is reached, tests run without paddleocr installed.
        assert "paddleocr" not in sys.modules
