"""Phase 1t: OCR provider abstraction and registry tests.

TDD: all tests written before implementation.

Covers:
- OcrProviderResult shape
- GlmOcrProvider delegation, result shape, success/error mapping
- Provider registry: get_ocr_provider, unknown provider, default provider
- is_available backed by check_ocr_provider_health (mocked)
- No PaddleOCR import triggered by the package
- Production extraction_service not mutated
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

import app.services.extraction.glm_ocr_client as glm_ocr_client
from app.services.extraction.glm_ocr_client import HeaderOcrResult, OcrResult
from app.services.extraction.ocr_providers import (
    get_default_ocr_provider,
    get_ocr_provider,
)
from app.services.extraction.ocr_providers.base import OcrProviderBase, OcrProviderResult
from app.services.extraction.ocr_providers.glm_provider import GlmOcrProvider


# ---------------------------------------------------------------------------
# Helpers — realistic fakes of the underlying result objects
# ---------------------------------------------------------------------------

def _make_ocr_result(text: str = "INVOICE TEXT") -> OcrResult:
    return OcrResult(
        text=text,
        pages=[],
        provider="ollama",
        model="glm4v",
        diagnostics={"ocr_duration_ms": 1234, "ocr_text_length": len(text)},
    )


def _make_header_result(text: str = "Header text", error: str | None = None) -> HeaderOcrResult:
    return HeaderOcrResult(
        text=text,
        provider="ollama",
        model="glm4v",
        image_data=b"fakeimg",
        diagnostics={"ocr_header_duration_ms": 567},
        error=error,
    )


# ---------------------------------------------------------------------------
# OcrProviderResult shape
# ---------------------------------------------------------------------------


class TestOcrProviderResult:
    def test_result_has_required_fields(self):
        r = OcrProviderResult(
            provider_name="glm",
            source_type="ocr",
            raw_text="INVOICE TEXT",
            success=True,
            error=None,
            duration_ms=1234,
            model="glm4v",
        )
        assert r.provider_name == "glm"
        assert r.source_type == "ocr"
        assert r.raw_text == "INVOICE TEXT"
        assert r.success is True
        assert r.error is None
        assert r.duration_ms == 1234
        assert r.model == "glm4v"

    def test_result_error_fields(self):
        r = OcrProviderResult(
            provider_name="glm",
            source_type="ocr",
            raw_text="",
            success=False,
            error="connection refused",
            duration_ms=10,
            model=None,
        )
        assert r.success is False
        assert r.error == "connection refused"
        assert r.raw_text == ""


# ---------------------------------------------------------------------------
# GlmOcrProvider
# ---------------------------------------------------------------------------


class TestGlmOcrProvider:
    def test_provider_name_is_glm(self):
        assert GlmOcrProvider().provider_name == "glm"

    def test_supports_header_is_true(self):
        assert GlmOcrProvider().supports_header is True

    def test_is_subclass_of_ocr_provider_base(self):
        assert issubclass(GlmOcrProvider, OcrProviderBase)

    def test_run_full_page_delegates_to_extract_text_with_ocr(self):
        mock_result = _make_ocr_result("FULL PAGE TEXT")
        with patch.object(glm_ocr_client, "extract_text_with_ocr", return_value=mock_result) as mock_fn:
            GlmOcrProvider().run_full_page("fake.pdf", max_pages=1, dpi=150, timeout_seconds=60)
            mock_fn.assert_called_once_with("fake.pdf", 1, 150, 60)

    def test_run_full_page_result_source_type_is_ocr(self):
        with patch.object(glm_ocr_client, "extract_text_with_ocr", return_value=_make_ocr_result()):
            result = GlmOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.source_type == "ocr"

    def test_run_full_page_result_raw_text_from_ocr(self):
        with patch.object(glm_ocr_client, "extract_text_with_ocr", return_value=_make_ocr_result("MY TEXT")):
            result = GlmOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.raw_text == "MY TEXT"

    def test_run_full_page_result_success_true_on_normal_return(self):
        with patch.object(glm_ocr_client, "extract_text_with_ocr", return_value=_make_ocr_result()):
            result = GlmOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.success is True
        assert result.error is None

    def test_run_full_page_result_success_true_even_on_empty_text(self):
        with patch.object(glm_ocr_client, "extract_text_with_ocr", return_value=_make_ocr_result("")):
            result = GlmOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.success is True
        assert result.raw_text == ""

    def test_run_full_page_result_success_false_on_exception(self):
        with patch.object(glm_ocr_client, "extract_text_with_ocr", side_effect=RuntimeError("connection refused")):
            result = GlmOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.success is False

    def test_run_full_page_result_error_message_on_exception(self):
        with patch.object(glm_ocr_client, "extract_text_with_ocr", side_effect=RuntimeError("connection refused")):
            result = GlmOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert "connection refused" in (result.error or "")

    def test_run_full_page_result_provider_name_on_exception(self):
        with patch.object(glm_ocr_client, "extract_text_with_ocr", side_effect=RuntimeError("fail")):
            result = GlmOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.provider_name == "glm"

    def test_run_header_delegates_to_extract_header_text_with_ocr(self):
        mock_result = _make_header_result("HEADER TEXT")
        with patch.object(glm_ocr_client, "extract_header_text_with_ocr", return_value=mock_result) as mock_fn:
            GlmOcrProvider().run_header("fake.pdf", dpi=150, timeout_seconds=60)
            mock_fn.assert_called_once_with("fake.pdf", dpi=150, timeout_seconds=60)

    def test_run_header_result_source_type_is_ocr_header(self):
        with patch.object(glm_ocr_client, "extract_header_text_with_ocr", return_value=_make_header_result()):
            result = GlmOcrProvider().run_header("f.pdf", dpi=150, timeout_seconds=60)
        assert result.source_type == "ocr_header"

    def test_run_header_result_raw_text_from_header_ocr(self):
        with patch.object(glm_ocr_client, "extract_header_text_with_ocr", return_value=_make_header_result("HEADER")):
            result = GlmOcrProvider().run_header("f.pdf", dpi=150, timeout_seconds=60)
        assert result.raw_text == "HEADER"

    def test_run_header_result_success_true_when_no_error(self):
        with patch.object(glm_ocr_client, "extract_header_text_with_ocr", return_value=_make_header_result(error=None)):
            result = GlmOcrProvider().run_header("f.pdf", dpi=150, timeout_seconds=60)
        assert result.success is True
        assert result.error is None

    def test_run_header_result_success_false_when_error(self):
        with patch.object(glm_ocr_client, "extract_header_text_with_ocr", return_value=_make_header_result(error="timeout")):
            result = GlmOcrProvider().run_header("f.pdf", dpi=150, timeout_seconds=60)
        assert result.success is False
        assert result.error == "timeout"

    def test_is_available_true_when_reachable(self):
        with patch.object(glm_ocr_client, "check_ocr_provider_health", return_value={"reachable": True}):
            assert GlmOcrProvider().is_available() is True

    def test_is_available_false_when_not_reachable(self):
        with patch.object(glm_ocr_client, "check_ocr_provider_health", return_value={"reachable": False}):
            assert GlmOcrProvider().is_available() is False

    def test_result_duration_ms_from_diagnostics(self):
        with patch.object(glm_ocr_client, "extract_text_with_ocr", return_value=_make_ocr_result()):
            result = GlmOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.duration_ms == 1234

    def test_result_model_from_ocr_result(self):
        with patch.object(glm_ocr_client, "extract_text_with_ocr", return_value=_make_ocr_result()):
            result = GlmOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.model == "glm4v"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestOcrProviderRegistry:
    def test_get_glm_provider_returns_glm_instance(self):
        provider = get_ocr_provider("glm")
        assert isinstance(provider, GlmOcrProvider)

    def test_unknown_provider_raises_value_error(self):
        with pytest.raises(ValueError):
            get_ocr_provider("paddleocr")

    def test_unknown_provider_error_mentions_known_providers(self):
        with pytest.raises(ValueError, match="glm"):
            get_ocr_provider("unknown_xyz")

    def test_default_provider_is_glm(self):
        provider = get_default_ocr_provider()
        assert provider.provider_name == "glm"

    def test_default_provider_returns_ocr_provider_base_instance(self):
        provider = get_default_ocr_provider()
        assert isinstance(provider, OcrProviderBase)

    def test_no_paddle_ocr_imported_by_package(self):
        import app.services.extraction.ocr_providers  # noqa: F401
        assert "paddleocr" not in sys.modules
        assert "paddle" not in sys.modules

    def test_production_extraction_service_not_mutated(self):
        import app.services.extraction_service as svc  # noqa: F401
        import app.services.extraction.glm_ocr_client as glm  # noqa: F401
        assert hasattr(glm, "extract_text_with_ocr")
        assert hasattr(glm, "extract_header_text_with_ocr")
