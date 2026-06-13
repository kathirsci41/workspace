"""TDD tests for Phase 1m: OCR provider evaluation harness.

Covers:
  - GLM full-page provider result has correct shape
  - GLM header provider result has correct shape
  - Unavailable optional provider returns provider_status="unavailable" without crashing
  - Evaluation records duration_ms, success, error, raw_text_length
  - Evaluation does not mutate production extraction output
  - Evaluation does not require PaddleOCR installed
  - No Panimalar-specific hardcoding in evaluation module

Phase 1w adds:
  - run_paddleocr_evaluation: unavailable path, mock-available path, GPU device setting
  - Records provider_name, success, error, duration_ms, raw_text_length, extracted_fields
  - Device setting failure does not abort evaluation when OCR itself succeeds
"""
from __future__ import annotations

import inspect
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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


# ---------------------------------------------------------------------------
# Phase 1q — parse_mode support
# ---------------------------------------------------------------------------

class TestHeaderNormalizedParseMode:
    """Phase 1q: header_normalized parse mode applies production normalization."""

    def test_ocr_provider_result_has_parse_mode_field(self, tmp_path: Path):
        """OcrProviderResult must expose parse_mode so callers know what was applied."""
        pdf = tmp_path / "pm.pdf"
        _make_blank_pdf(pdf)
        with patch.object(ocr_evaluation, "extract_header_text_with_ocr", return_value=_mock_header_result("Invoice No: X001")):
            result = run_glm_header_evaluation(str(pdf), dpi=72, timeout_seconds=5, parse_mode="raw")
        assert hasattr(result, "parse_mode")

    def test_raw_mode_keeps_existing_behavior(self, tmp_path: Path):
        """raw parse_mode must produce same result as current default (no normalization)."""
        pdf = tmp_path / "raw.pdf"
        _make_blank_pdf(pdf)
        json_ocr = '```json\n{\n    "Invoice No": "RAW001"\n}\n```'
        with patch.object(ocr_evaluation, "extract_header_text_with_ocr", return_value=_mock_header_result(json_ocr)):
            result = run_glm_header_evaluation(str(pdf), dpi=72, timeout_seconds=5, parse_mode="raw")
        assert result.parse_mode == "raw"
        assert result.extracted_fields.get("vendor_invoice_no") is None

    def test_header_normalized_mode_converts_json_ocr_to_fields(self, tmp_path: Path):
        """header_normalized must recover fields from JSON-style header OCR."""
        pdf = tmp_path / "norm.pdf"
        _make_blank_pdf(pdf)
        json_ocr = '```json\n{\n    "Invoice No": "NORM001",\n    "Invoice Date": "01-06-2026",\n    "PO Reference": "PO 1ABC2026000001"\n}\n```'
        with patch.object(ocr_evaluation, "extract_header_text_with_ocr", return_value=_mock_header_result(json_ocr)):
            result = run_glm_header_evaluation(str(pdf), dpi=72, timeout_seconds=5, parse_mode="header_normalized")
        assert result.parse_mode == "header_normalized"
        assert result.extracted_fields.get("vendor_invoice_no") == "NORM001"
        assert result.extracted_fields.get("vendor_invoice_date") == "01-06-2026"
        assert result.extracted_fields.get("po_reference") == "1ABC2026000001"

    def test_header_normalized_strips_po_prefix_when_digit_present(self, tmp_path: Path):
        """PO prefix must be stripped when the remainder contains a digit."""
        pdf = tmp_path / "po.pdf"
        _make_blank_pdf(pdf)
        json_ocr = '```json\n{\n    "Invoice No": "POTEST001",\n    "Invoice Date": "01-06-2026",\n    "PO Reference": "PO 9ZXY2026000099"\n}\n```'
        with patch.object(ocr_evaluation, "extract_header_text_with_ocr", return_value=_mock_header_result(json_ocr)):
            result = run_glm_header_evaluation(str(pdf), dpi=72, timeout_seconds=5, parse_mode="header_normalized")
        assert result.extracted_fields.get("po_reference") == "9ZXY2026000099"

    def test_header_normalized_mode_only_applies_to_header_provider(self, tmp_path: Path):
        """full-page provider ignores header_normalized and always uses raw behavior."""
        pdf = tmp_path / "fp.pdf"
        _make_blank_pdf(pdf)
        json_ocr = '```json\n{\n    "Invoice No": "FPTEST001"\n}\n```'
        with patch.object(ocr_evaluation, "extract_text_with_ocr", return_value=_mock_ocr_result(json_ocr)):
            result = run_glm_full_page_evaluation(str(pdf), dpi=72, timeout_seconds=5, parse_mode="header_normalized")
        assert result.parse_mode == "raw"
        assert result.extracted_fields.get("vendor_invoice_no") is None

    def test_wrong_ocr_values_remain_wrong_in_header_normalized_mode(self, tmp_path: Path):
        """Normalization must NOT correct wrong OCR values — missing is better than wrong.

        - Wrong invoice numbers that parse are forwarded as-is (not corrected).
        - Values the parser rejects (bad date/PO formats) return None — not guessed-at values.
        - In both cases, normalization never injects a "correct" value it does not have.
        """
        pdf = tmp_path / "wrong.pdf"
        _make_blank_pdf(pdf)
        json_ocr = '```json\n{\n    "Invoice No": "WRONG999",\n    "Invoice Date": "BADDATE",\n    "PO Reference": "PO BADREF"\n}\n```'
        with patch.object(ocr_evaluation, "extract_header_text_with_ocr", return_value=_mock_header_result(json_ocr)):
            result = run_glm_header_evaluation(str(pdf), dpi=72, timeout_seconds=5, parse_mode="header_normalized")
        # Wrong invoice number is forwarded exactly as-is — not corrected
        assert result.extracted_fields.get("vendor_invoice_no") == "WRONG999"
        # BADDATE and PO BADREF are rejected by the parser (None is correct: missing > wrong)
        # The key invariant: normalization never injects the real/expected value
        assert result.extracted_fields.get("vendor_invoice_date") is None
        assert result.extracted_fields.get("po_reference") is None

    def test_malformed_json_does_not_crash_in_header_normalized_mode(self, tmp_path: Path):
        """Malformed JSON OCR must not crash header_normalized mode."""
        pdf = tmp_path / "malform.pdf"
        _make_blank_pdf(pdf)
        malformed = '{"Invoice No": "X001", "Invoice Date":   '
        with patch.object(ocr_evaluation, "extract_header_text_with_ocr", return_value=_mock_header_result(malformed)):
            result = run_glm_header_evaluation(str(pdf), dpi=72, timeout_seconds=5, parse_mode="header_normalized")
        assert isinstance(result, OcrProviderResult)

    def test_header_normalized_result_parse_mode_stored_on_result(self, tmp_path: Path):
        """The applied parse_mode must be stored on the result object."""
        pdf = tmp_path / "stored.pdf"
        _make_blank_pdf(pdf)
        with patch.object(ocr_evaluation, "extract_header_text_with_ocr", return_value=_mock_header_result("Invoice No: STORE001")):
            result = run_glm_header_evaluation(str(pdf), dpi=72, timeout_seconds=5, parse_mode="header_normalized")
        assert result.parse_mode == "header_normalized"

    def test_evaluation_with_parse_mode_does_not_call_extract_document(self, tmp_path: Path):
        """parse_mode must not cause evaluation to touch the production extractor."""
        pdf = tmp_path / "nodoc.pdf"
        _make_blank_pdf(pdf)
        with (
            patch.object(ocr_evaluation, "extract_header_text_with_ocr", return_value=_mock_header_result("Invoice No: NODOC001")),
            patch("app.services.extraction_service.extract_document") as mock_extract,
        ):
            run_glm_header_evaluation(str(pdf), dpi=72, timeout_seconds=5, parse_mode="header_normalized")
        mock_extract.assert_not_called()


# ---------------------------------------------------------------------------
# Phase 1w — run_paddleocr_evaluation
# ---------------------------------------------------------------------------

def _make_paddle_provider(
    *,
    available: bool = True,
    success: bool = True,
    text: str = "Invoice No: INV001\nDate: 01-01-2026\n",
    error: str | None = None,
    duration_ms: int = 500,
) -> MagicMock:
    """Return a minimal mock PaddleOcrProvider."""
    provider = MagicMock()
    provider.provider_name = "paddleocr"
    provider.is_available.return_value = available
    provider.run_full_page.return_value = SimpleNamespace(
        success=success,
        error=error,
        duration_ms=duration_ms,
        raw_text=text if success else "",
    )
    return provider


class TestPaddleOcrEvaluation:
    """Phase 1w: run_paddleocr_evaluation covers unavailable, mocked-available, and GPU device."""

    def test_unavailable_provider_returns_unavailable_without_crash(self):
        from app.services.extraction.ocr_evaluation import run_paddleocr_evaluation
        with patch("app.services.extraction.ocr_evaluation.get_ocr_provider") as mock_get:
            mock_get.return_value = _make_paddle_provider(available=False)
            result = run_paddleocr_evaluation("fake.pdf", dpi=150, timeout_seconds=30)
        assert result.provider_status == "unavailable"
        assert result.success is False

    def test_unavailable_provider_does_not_raise(self):
        from app.services.extraction.ocr_evaluation import run_paddleocr_evaluation
        with patch("app.services.extraction.ocr_evaluation.get_ocr_provider") as mock_get:
            mock_get.return_value = _make_paddle_provider(available=False)
            try:
                run_paddleocr_evaluation("fake.pdf", dpi=150, timeout_seconds=30)
            except Exception as exc:
                pytest.fail(f"run_paddleocr_evaluation raised unexpectedly: {exc}")

    def test_available_provider_mocked_without_importing_real_paddleocr(self):
        """Must run successfully using only mocks — real paddleocr not required."""
        from app.services.extraction.ocr_evaluation import run_paddleocr_evaluation
        with patch("app.services.extraction.ocr_evaluation.get_ocr_provider") as mock_get:
            mock_get.return_value = _make_paddle_provider(available=True)
            result = run_paddleocr_evaluation("fake.pdf", dpi=150, timeout_seconds=30)
        assert result.provider_name == "paddleocr"

    def test_records_provider_name(self):
        from app.services.extraction.ocr_evaluation import run_paddleocr_evaluation
        with patch("app.services.extraction.ocr_evaluation.get_ocr_provider") as mock_get:
            mock_get.return_value = _make_paddle_provider()
            result = run_paddleocr_evaluation("fake.pdf", dpi=150, timeout_seconds=30)
        assert result.provider_name == "paddleocr"

    def test_records_success_true(self):
        from app.services.extraction.ocr_evaluation import run_paddleocr_evaluation
        with patch("app.services.extraction.ocr_evaluation.get_ocr_provider") as mock_get:
            mock_get.return_value = _make_paddle_provider(success=True)
            result = run_paddleocr_evaluation("fake.pdf", dpi=150, timeout_seconds=30)
        assert result.success is True

    def test_records_success_false_when_provider_fails(self):
        from app.services.extraction.ocr_evaluation import run_paddleocr_evaluation
        with patch("app.services.extraction.ocr_evaluation.get_ocr_provider") as mock_get:
            mock_get.return_value = _make_paddle_provider(success=False, error="PIR crash")
            result = run_paddleocr_evaluation("fake.pdf", dpi=150, timeout_seconds=30)
        assert result.success is False

    def test_records_error_message_from_provider(self):
        from app.services.extraction.ocr_evaluation import run_paddleocr_evaluation
        with patch("app.services.extraction.ocr_evaluation.get_ocr_provider") as mock_get:
            mock_get.return_value = _make_paddle_provider(success=False, error="OCR crashed hard")
            result = run_paddleocr_evaluation("fake.pdf", dpi=150, timeout_seconds=30)
        assert "OCR crashed hard" in (result.error or "")

    def test_records_duration_ms_as_non_negative_int(self):
        from app.services.extraction.ocr_evaluation import run_paddleocr_evaluation
        with patch("app.services.extraction.ocr_evaluation.get_ocr_provider") as mock_get:
            mock_get.return_value = _make_paddle_provider(duration_ms=11154)
            result = run_paddleocr_evaluation("fake.pdf", dpi=150, timeout_seconds=30)
        assert isinstance(result.duration_ms, int)
        assert result.duration_ms >= 0

    def test_records_raw_text_length(self):
        from app.services.extraction.ocr_evaluation import run_paddleocr_evaluation
        text = "Invoice No: INV001\nDate: 01-01-2026\n"
        with patch("app.services.extraction.ocr_evaluation.get_ocr_provider") as mock_get:
            mock_get.return_value = _make_paddle_provider(text=text)
            result = run_paddleocr_evaluation("fake.pdf", dpi=150, timeout_seconds=30)
        assert result.raw_text_length == len(text)

    def test_records_extracted_fields_dict(self):
        from app.services.extraction.ocr_evaluation import run_paddleocr_evaluation
        with patch("app.services.extraction.ocr_evaluation.get_ocr_provider") as mock_get:
            mock_get.return_value = _make_paddle_provider()
            result = run_paddleocr_evaluation("fake.pdf", dpi=150, timeout_seconds=30, run_parser=False)
        assert isinstance(result.extracted_fields, dict)

    def test_calls_set_device_when_device_provided(self):
        from app.services.extraction.ocr_evaluation import run_paddleocr_evaluation
        with (
            patch("app.services.extraction.ocr_evaluation.get_ocr_provider") as mock_get,
            patch("app.services.extraction.ocr_evaluation._set_paddle_device") as mock_set,
        ):
            mock_get.return_value = _make_paddle_provider()
            mock_set.return_value = None
            run_paddleocr_evaluation("fake.pdf", dpi=150, timeout_seconds=30, device="gpu:0")
        mock_set.assert_called_once_with("gpu:0")

    def test_no_set_device_when_device_is_none(self):
        from app.services.extraction.ocr_evaluation import run_paddleocr_evaluation
        with (
            patch("app.services.extraction.ocr_evaluation.get_ocr_provider") as mock_get,
            patch("app.services.extraction.ocr_evaluation._set_paddle_device") as mock_set,
        ):
            mock_get.return_value = _make_paddle_provider()
            mock_set.return_value = None
            run_paddleocr_evaluation("fake.pdf", dpi=150, timeout_seconds=30)
        mock_set.assert_not_called()

    def test_device_error_does_not_fail_evaluation_when_ocr_succeeds(self):
        from app.services.extraction.ocr_evaluation import run_paddleocr_evaluation
        with (
            patch("app.services.extraction.ocr_evaluation.get_ocr_provider") as mock_get,
            patch("app.services.extraction.ocr_evaluation._set_paddle_device", return_value="CUDA unavailable"),
        ):
            mock_get.return_value = _make_paddle_provider(success=True)
            result = run_paddleocr_evaluation("fake.pdf", dpi=150, timeout_seconds=30, device="gpu:0")
        assert result.success is True

    def test_result_is_ocr_provider_result_instance(self):
        from app.services.extraction.ocr_evaluation import run_paddleocr_evaluation
        with patch("app.services.extraction.ocr_evaluation.get_ocr_provider") as mock_get:
            mock_get.return_value = _make_paddle_provider()
            result = run_paddleocr_evaluation("fake.pdf", dpi=150, timeout_seconds=30)
        assert isinstance(result, OcrProviderResult)

    def test_does_not_call_extract_document(self):
        from app.services.extraction.ocr_evaluation import run_paddleocr_evaluation
        with (
            patch("app.services.extraction.ocr_evaluation.get_ocr_provider") as mock_get,
            patch("app.services.extraction_service.extract_document") as mock_extract,
        ):
            mock_get.return_value = _make_paddle_provider()
            run_paddleocr_evaluation("fake.pdf", dpi=150, timeout_seconds=30)
        mock_extract.assert_not_called()
