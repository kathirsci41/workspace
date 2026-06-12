"""TDD tests for Phase 1m: OCR provider evaluation harness.

Covers:
  - GLM full-page provider result has correct shape
  - GLM header provider result has correct shape
  - Unavailable optional provider returns provider_status="unavailable" without crashing
  - Evaluation records duration_ms, success, error, raw_text_length
  - Evaluation does not mutate production extraction output
  - Evaluation does not require PaddleOCR installed
  - No Panimalar-specific hardcoding in evaluation module
"""
from __future__ import annotations

import inspect
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import fitz
import pytest

import app.services.extraction.ocr_evaluation as ocr_evaluation
from app.services.extraction.glm_ocr_client import OcrResult
from app.services.extraction.ocr_evaluation import (
    OcrProviderResult,
    check_paddleocr_availability,
    run_glm_full_page_evaluation,
    run_glm_header_evaluation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_blank_pdf(path: Path) -> None:
    doc = fitz.open()
    doc.new_page(width=400, height=600)
    doc.save(str(path))
    doc.close()


def _mock_ocr_result(text: str) -> OcrResult:
    return OcrResult(
        text=text,
        pages=[{"page_number": 1, "ocr_text_length": len(text)}],
        provider="glm_ocr",
        model="glm-ocr:latest",
        diagnostics={
            "ocr_provider": "glm_ocr",
            "ocr_model": "glm-ocr:latest",
            "ocr_duration_ms": 42,
            "ocr_text_length": len(text),
            "ocr_pages_attempted": 1,
            "ocr_page_results": [{"page_number": 1, "ocr_text_length": len(text)}],
        },
    )


def _mock_header_result(text: str, *, error: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        provider="glm_ocr",
        model="glm-ocr:latest",
        image_data=b"fake-header-png",
        error=error,
        diagnostics={
            "ocr_header_duration_ms": 19,
            "ocr_header_crop_fraction": 0.4,
            "ocr_header_text_length": len(text),
        },
    )


# ---------------------------------------------------------------------------
# GLM full-page result shape
# ---------------------------------------------------------------------------

class TestGlmFullPageResultShape:
    def test_result_is_ocr_provider_result_instance(self, tmp_path: Path):
        pdf = tmp_path / "page.pdf"
        _make_blank_pdf(pdf)
        with patch.object(ocr_evaluation, "extract_text_with_ocr", return_value=_mock_ocr_result("Invoice No: TEST001")):
            result = run_glm_full_page_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        assert isinstance(result, OcrProviderResult)

    def test_result_has_provider_name_glm_full_page(self, tmp_path: Path):
        pdf = tmp_path / "page.pdf"
        _make_blank_pdf(pdf)
        with patch.object(ocr_evaluation, "extract_text_with_ocr", return_value=_mock_ocr_result("Invoice No: TEST001")):
            result = run_glm_full_page_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        assert result.provider_name == "glm_full_page"

    def test_result_has_source_type_ocr_full_page(self, tmp_path: Path):
        pdf = tmp_path / "page.pdf"
        _make_blank_pdf(pdf)
        with patch.object(ocr_evaluation, "extract_text_with_ocr", return_value=_mock_ocr_result("Invoice No: TEST001")):
            result = run_glm_full_page_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        assert result.source_type == "ocr_full_page"

    def test_result_records_raw_text_length(self, tmp_path: Path):
        pdf = tmp_path / "page.pdf"
        _make_blank_pdf(pdf)
        text = "Invoice No: TEST001\nInvoice Date: 01-01-2026\n"
        with patch.object(ocr_evaluation, "extract_text_with_ocr", return_value=_mock_ocr_result(text)):
            result = run_glm_full_page_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        assert result.raw_text_length == len(text)

    def test_result_records_provider_version(self, tmp_path: Path):
        pdf = tmp_path / "page.pdf"
        _make_blank_pdf(pdf)
        with patch.object(ocr_evaluation, "extract_text_with_ocr", return_value=_mock_ocr_result("text")):
            result = run_glm_full_page_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        assert result.provider_version == "glm-ocr:latest"

    def test_result_has_normalized_text_preview(self, tmp_path: Path):
        pdf = tmp_path / "page.pdf"
        _make_blank_pdf(pdf)
        with patch.object(ocr_evaluation, "extract_text_with_ocr", return_value=_mock_ocr_result("Invoice No: TEST001")):
            result = run_glm_full_page_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        assert isinstance(result.normalized_text_preview, str)
        assert len(result.normalized_text_preview) <= 300

    def test_result_has_extracted_fields_dict(self, tmp_path: Path):
        pdf = tmp_path / "page.pdf"
        _make_blank_pdf(pdf)
        with patch.object(ocr_evaluation, "extract_text_with_ocr", return_value=_mock_ocr_result("text")):
            result = run_glm_full_page_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        assert isinstance(result.extracted_fields, dict)

    def test_result_provider_status_ok_on_success(self, tmp_path: Path):
        pdf = tmp_path / "page.pdf"
        _make_blank_pdf(pdf)
        with patch.object(ocr_evaluation, "extract_text_with_ocr", return_value=_mock_ocr_result("text")):
            result = run_glm_full_page_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        assert result.provider_status == "ok"
        assert result.success is True
        assert result.error is None


# ---------------------------------------------------------------------------
# GLM header result shape
# ---------------------------------------------------------------------------

class TestGlmHeaderResultShape:
    def test_result_is_ocr_provider_result_instance(self, tmp_path: Path):
        pdf = tmp_path / "header.pdf"
        _make_blank_pdf(pdf)
        with patch.object(ocr_evaluation, "extract_header_text_with_ocr", return_value=_mock_header_result("Invoice No: HDR001")):
            result = run_glm_header_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        assert isinstance(result, OcrProviderResult)

    def test_result_has_provider_name_glm_header(self, tmp_path: Path):
        pdf = tmp_path / "header.pdf"
        _make_blank_pdf(pdf)
        with patch.object(ocr_evaluation, "extract_header_text_with_ocr", return_value=_mock_header_result("Invoice No: HDR001")):
            result = run_glm_header_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        assert result.provider_name == "glm_header"

    def test_result_has_source_type_ocr_header(self, tmp_path: Path):
        pdf = tmp_path / "header.pdf"
        _make_blank_pdf(pdf)
        with patch.object(ocr_evaluation, "extract_header_text_with_ocr", return_value=_mock_header_result("Invoice No: HDR001")):
            result = run_glm_header_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        assert result.source_type == "ocr_header"

    def test_result_records_duration_ms(self, tmp_path: Path):
        pdf = tmp_path / "header.pdf"
        _make_blank_pdf(pdf)
        with patch.object(ocr_evaluation, "extract_header_text_with_ocr", return_value=_mock_header_result("Invoice No: HDR001")):
            result = run_glm_header_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        assert isinstance(result.duration_ms, int)
        assert result.duration_ms >= 0

    def test_result_records_raw_text_length(self, tmp_path: Path):
        pdf = tmp_path / "header.pdf"
        _make_blank_pdf(pdf)
        text = "Invoice No: HDR001\nInvoice Date: 02-01-2026\n"
        with patch.object(ocr_evaluation, "extract_header_text_with_ocr", return_value=_mock_header_result(text)):
            result = run_glm_header_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        assert result.raw_text_length == len(text)

    def test_result_provider_status_ok_on_success(self, tmp_path: Path):
        pdf = tmp_path / "header.pdf"
        _make_blank_pdf(pdf)
        with patch.object(ocr_evaluation, "extract_header_text_with_ocr", return_value=_mock_header_result("Invoice No: HDR001")):
            result = run_glm_header_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        assert result.provider_status == "ok"
        assert result.success is True


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestEvaluationErrorHandling:
    def test_glm_full_page_records_error_on_exception(self, tmp_path: Path):
        pdf = tmp_path / "error.pdf"
        _make_blank_pdf(pdf)
        with patch.object(
            ocr_evaluation, "extract_text_with_ocr", side_effect=RuntimeError("connection refused")
        ):
            result = run_glm_full_page_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        assert result.success is False
        assert result.error is not None
        assert "connection refused" in result.error
        assert result.provider_status == "error"
        assert result.raw_text_length == 0

    def test_glm_header_records_error_on_exception(self, tmp_path: Path):
        pdf = tmp_path / "header-err.pdf"
        _make_blank_pdf(pdf)
        with patch.object(
            ocr_evaluation, "extract_header_text_with_ocr", side_effect=RuntimeError("timeout")
        ):
            result = run_glm_header_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        assert result.success is False
        assert result.error is not None
        assert result.provider_status == "error"


# ---------------------------------------------------------------------------
# PaddleOCR availability
# ---------------------------------------------------------------------------

class TestPaddleOcrAvailability:
    def test_unavailable_provider_returns_unavailable_not_crash(self):
        with patch("importlib.util.find_spec", return_value=None):
            status = check_paddleocr_availability()
        assert status == "unavailable"

    def test_available_provider_returns_available(self):
        fake_spec = object()
        with patch("importlib.util.find_spec", return_value=fake_spec):
            status = check_paddleocr_availability()
        assert status == "available"

    def test_check_does_not_import_paddleocr(self):
        import sys
        modules_before = set(sys.modules.keys())
        with patch("importlib.util.find_spec", return_value=None):
            check_paddleocr_availability()
        new_modules = set(sys.modules.keys()) - modules_before
        paddle_modules = [m for m in new_modules if "paddle" in m.lower()]
        assert paddle_modules == [], f"unexpected paddle imports: {paddle_modules}"

    def test_evaluation_does_not_require_paddleocr_installed(self):
        import importlib.util
        spec = importlib.util.find_spec("paddleocr")
        if spec is not None:
            pytest.skip("PaddleOCR is actually installed — unavailability path not testable")
        status = check_paddleocr_availability()
        assert status == "unavailable"


# ---------------------------------------------------------------------------
# Duration and metadata recording
# ---------------------------------------------------------------------------

class TestEvaluationMetadataRecording:
    def test_duration_ms_is_non_negative_integer(self, tmp_path: Path):
        pdf = tmp_path / "dur.pdf"
        _make_blank_pdf(pdf)
        with patch.object(ocr_evaluation, "extract_text_with_ocr", return_value=_mock_ocr_result("text")):
            result = run_glm_full_page_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        assert isinstance(result.duration_ms, int)
        assert result.duration_ms >= 0

    def test_duration_ms_reflects_elapsed_time(self, tmp_path: Path):
        pdf = tmp_path / "dur2.pdf"
        _make_blank_pdf(pdf)

        def slow_ocr(*args, **kwargs):
            time.sleep(0.01)
            return _mock_ocr_result("text")

        with patch.object(ocr_evaluation, "extract_text_with_ocr", side_effect=slow_ocr):
            result = run_glm_full_page_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        assert result.duration_ms >= 10

    def test_success_false_when_error_present(self, tmp_path: Path):
        pdf = tmp_path / "fail.pdf"
        _make_blank_pdf(pdf)
        with patch.object(ocr_evaluation, "extract_text_with_ocr", side_effect=RuntimeError("boom")):
            result = run_glm_full_page_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        assert result.success is False
        assert result.error == "boom"

    def test_success_true_when_no_error(self, tmp_path: Path):
        pdf = tmp_path / "ok.pdf"
        _make_blank_pdf(pdf)
        with patch.object(ocr_evaluation, "extract_text_with_ocr", return_value=_mock_ocr_result("Invoice No: OK001")):
            result = run_glm_full_page_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        assert result.success is True
        assert result.error is None


# ---------------------------------------------------------------------------
# Production extraction output not mutated
# ---------------------------------------------------------------------------

class TestEvaluationDoesNotMutateProduction:
    def test_evaluation_does_not_call_extract_document(self, tmp_path: Path):
        """Harness must not call the full extraction orchestrator."""
        pdf = tmp_path / "iso.pdf"
        _make_blank_pdf(pdf)
        with (
            patch.object(ocr_evaluation, "extract_text_with_ocr", return_value=_mock_ocr_result("text")),
            patch("app.services.extraction_service.extract_document") as mock_extract,
        ):
            run_glm_full_page_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        mock_extract.assert_not_called()

    def test_evaluation_result_is_independent_object(self, tmp_path: Path):
        """Running evaluation twice produces two independent results."""
        pdf = tmp_path / "indep.pdf"
        _make_blank_pdf(pdf)
        ocr_text = "Invoice No: IND001"
        with patch.object(ocr_evaluation, "extract_text_with_ocr", return_value=_mock_ocr_result(ocr_text)):
            r1 = run_glm_full_page_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        with patch.object(ocr_evaluation, "extract_text_with_ocr", return_value=_mock_ocr_result(ocr_text)):
            r2 = run_glm_full_page_evaluation(str(pdf), dpi=72, timeout_seconds=5)
        r1.extracted_fields["__sentinel__"] = "mutated"
        assert "__sentinel__" not in r2.extracted_fields


# ---------------------------------------------------------------------------
# No hardcoding
# ---------------------------------------------------------------------------

def test_ocr_evaluation_module_has_no_panimalar_hardcoding():
    source = inspect.getsource(ocr_evaluation).lower()
    assert "panimalar" not in source
