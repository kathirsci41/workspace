"""Phase 1u/1v/1xA: PaddleOCR provider adapter tests.

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

Phase 1xA adds:
- Provider accepts optional device= and provider_name= constructor kwargs
- GPU device ("gpu:0") infers provider_name="paddleocr_gpu" by default
- CPU/no device keeps provider_name="paddleocr"
- _set_paddle_device called before OCR when device is set
- Device-setting failure returns a safe failed result (no crash)
- Timeout accepted but not enforced (limitation explicitly documented)
- Constructor does not import paddle at instantiation time
"""
from __future__ import annotations

import sys
import time
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


# ---------------------------------------------------------------------------
# Phase 1xA — device selection, GPU provenance, timeout documentation
# ---------------------------------------------------------------------------


class TestPaddleOcrProviderHardening:
    """Phase 1xA: optional device/provider_name constructor args, GPU provenance, timeout honesty."""

    # --- Constructor: backward compatibility ---

    def test_default_constructor_no_args_provider_name_is_paddleocr(self):
        assert PaddleOcrProvider().provider_name == "paddleocr"

    def test_accepts_device_kwarg_without_error(self):
        provider = PaddleOcrProvider(device="gpu:0")
        assert provider is not None

    def test_accepts_provider_name_kwarg_without_error(self):
        provider = PaddleOcrProvider(provider_name="my_name")
        assert provider is not None

    # --- Provider name inference ---

    def test_gpu_device_infers_provider_name_paddleocr_gpu(self):
        provider = PaddleOcrProvider(device="gpu:0")
        assert provider.provider_name == "paddleocr_gpu"

    def test_cpu_device_keeps_provider_name_paddleocr(self):
        provider = PaddleOcrProvider(device="cpu")
        assert provider.provider_name == "paddleocr"

    def test_none_device_keeps_provider_name_paddleocr(self):
        provider = PaddleOcrProvider(device=None)
        assert provider.provider_name == "paddleocr"

    def test_explicit_provider_name_overrides_device_inference_for_gpu(self):
        provider = PaddleOcrProvider(device="gpu:0", provider_name="custom_paddle")
        assert provider.provider_name == "custom_paddle"

    def test_explicit_provider_name_overrides_default_for_no_device(self):
        provider = PaddleOcrProvider(provider_name="evaluation_cpu")
        assert provider.provider_name == "evaluation_cpu"

    # --- Device-setting integration ---

    def test_set_device_called_before_ocr_when_device_provided(self):
        mock_module, _ = _make_mock_paddle_module()
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch("app.services.extraction.ocr_providers.paddle_provider._set_paddle_device") as mock_set, \
             patch.dict(sys.modules, {"paddleocr": mock_module}):
            mock_set.return_value = None
            PaddleOcrProvider(device="gpu:0").run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        mock_set.assert_called_once_with("gpu:0")

    def test_set_device_not_called_when_no_device(self):
        mock_module, _ = _make_mock_paddle_module()
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch("app.services.extraction.ocr_providers.paddle_provider._set_paddle_device") as mock_set, \
             patch.dict(sys.modules, {"paddleocr": mock_module}):
            mock_set.return_value = None
            PaddleOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        mock_set.assert_not_called()

    # --- Device failure: safe result, no crash ---

    def test_device_failure_returns_failed_result(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch("app.services.extraction.ocr_providers.paddle_provider._set_paddle_device", return_value="CUDA unavailable"):
            result = PaddleOcrProvider(device="gpu:0").run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.success is False

    def test_device_failure_error_contains_device_info(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch("app.services.extraction.ocr_providers.paddle_provider._set_paddle_device", return_value="CUDA unavailable"):
            result = PaddleOcrProvider(device="gpu:0").run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.error is not None
        assert len(result.error) > 0

    def test_device_failure_does_not_crash(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch("app.services.extraction.ocr_providers.paddle_provider._set_paddle_device", return_value="boom"):
            try:
                PaddleOcrProvider(device="gpu:0").run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
            except Exception as exc:
                pytest.fail(f"raised unexpectedly: {exc}")

    # --- Result provenance ---

    def test_gpu_run_result_has_provider_name_paddleocr_gpu(self):
        mock_module, _ = _make_mock_paddle_module()
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch("app.services.extraction.ocr_providers.paddle_provider._set_paddle_device", return_value=None), \
             patch.dict(sys.modules, {"paddleocr": mock_module}):
            result = PaddleOcrProvider(device="gpu:0").run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.provider_name == "paddleocr_gpu"

    def test_cpu_run_result_has_provider_name_paddleocr(self):
        mock_module, _ = _make_mock_paddle_module()
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch.dict(sys.modules, {"paddleocr": mock_module}):
            result = PaddleOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.provider_name == "paddleocr"

    def test_failed_unavailable_result_uses_provider_name_from_instance(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=False):
            result = PaddleOcrProvider(device="gpu:0").run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.provider_name == "paddleocr_gpu"

    # --- Timeout: accepted, not enforced ---

    def test_timeout_seconds_accepted_without_type_error(self):
        """timeout_seconds is accepted by the API — must not raise TypeError."""
        mock_module, _ = _make_mock_paddle_module()
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch.dict(sys.modules, {"paddleocr": mock_module}):
            result = PaddleOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=30)
        assert isinstance(result, OcrProviderResult)

    def test_timeout_not_enforced_fast_mock_still_succeeds(self):
        """Phase 1xA: timeout_seconds=1 does NOT abort a fast mock call.

        Limitation: timeout_seconds is accepted but not enforced at the process level.
        The PaddleOCR predict() call is synchronous — there is no process-level preemption.
        Thread-based timeout is unsafe (leaves OCR running in background). Phase 1xB must solve.
        This test records the limitation: a fast mock at timeout_seconds=1 still succeeds.
        """
        mock_module, _ = _make_mock_paddle_module()
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch.dict(sys.modules, {"paddleocr": mock_module}):
            result = PaddleOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=1)
        assert result.success is True

    # --- Lazy import: no paddle at constructor time ---

    def test_no_paddle_import_at_module_load_after_constructor(self):
        """Constructing PaddleOcrProvider(device='gpu:0') must not import paddle."""
        paddle_before = {k for k in sys.modules if "paddle" in k.lower()}
        PaddleOcrProvider(device="gpu:0")
        paddle_after = {k for k in sys.modules if "paddle" in k.lower()}
        new_paddle_mods = paddle_after - paddle_before
        assert new_paddle_mods == set(), f"unexpected paddle imports: {new_paddle_mods}"

    # --- Flatten still supports real API ---

    def test_flatten_result_handles_rec_texts_format(self):
        """_flatten_paddle_result handles PaddleOCR 3.7.0 rec_texts page format."""
        from app.services.extraction.ocr_providers.paddle_provider import _flatten_paddle_result
        pages = [{"rec_texts": ["LINE A", "LINE B"]}, {"rec_texts": ["LINE C"]}]
        text = _flatten_paddle_result(pages)
        assert "LINE A" in text
        assert "LINE B" in text
        assert "LINE C" in text


# ---------------------------------------------------------------------------
# Phase 1xB — process-level timeout enforcement
# ---------------------------------------------------------------------------
#
# Module-level worker functions for real multiprocessing.spawn tests below.
# Must stay module-level (not nested) so spawn can pickle/import them by reference.

def _fast_worker_for_test(payload, queue):
    """Returns immediately. Proves the subprocess helper's success path
    without requiring paddleocr to be installed."""
    queue.put({"success": True, "raw_text": "FAST WORKER TEXT", "error": None, "duration_ms": 1})


def _slow_worker_for_test(payload, queue):
    """Sleeps far longer than any timeout used in tests. Proves the parent
    terminates/kills a hung child rather than waiting or leaving it running."""
    import time as _time
    _time.sleep(payload.get("sleep_seconds", 30))
    queue.put({"success": True, "raw_text": "SHOULD NOT ARRIVE", "error": None, "duration_ms": 1})


def _large_payload_worker_for_test(payload, queue):
    """Returns immediately with a payload large enough to exceed the OS pipe
    buffer. Reproduces the multiprocessing.Queue join-before-drain deadlock: a
    child blocks until its buffered items are flushed to the pipe, so a parent
    that joins before reading hangs until the timeout. The helper must drain
    the queue first and return this result quickly."""
    queue.put({
        "success": True,
        "raw_text": "X" * 200_000,
        "error": None,
        "duration_ms": 1,
    })


class TestPaddleOcrProviderTimeoutEnforcement:
    """Phase 1xB: real process-level timeout via multiprocessing subprocess isolation."""

    # --- Constructor: backward compatibility ---

    def test_default_constructor_enforce_timeout_disabled(self):
        provider = PaddleOcrProvider()
        assert provider._enforce_timeout is False

    def test_accepts_enforce_timeout_true(self):
        provider = PaddleOcrProvider(enforce_timeout=True)
        assert provider._enforce_timeout is True

    def test_enforce_timeout_false_keeps_direct_path(self):
        """enforce_timeout=False (default) never calls the subprocess helper."""
        mock_module, _ = _make_mock_paddle_module()
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch("app.services.extraction.ocr_providers.paddle_provider._run_paddle_ocr_in_subprocess") as mock_run, \
             patch.dict(sys.modules, {"paddleocr": mock_module}):
            result = PaddleOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        mock_run.assert_not_called()
        assert result.success is True

    # --- enforce_timeout=True wiring ---

    def test_enforce_timeout_true_calls_subprocess_helper(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch("app.services.extraction.ocr_providers.paddle_provider._run_paddle_ocr_in_subprocess") as mock_run:
            mock_run.return_value = {"success": True, "raw_text": "TEXT", "error": None, "duration_ms": 100}
            PaddleOcrProvider(enforce_timeout=True).run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=45)
        mock_run.assert_called_once_with("f.pdf", None, 45)

    def test_enforce_timeout_true_passes_device_to_helper(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch("app.services.extraction.ocr_providers.paddle_provider._run_paddle_ocr_in_subprocess") as mock_run:
            mock_run.return_value = {"success": True, "raw_text": "TEXT", "error": None, "duration_ms": 100}
            PaddleOcrProvider(device="gpu:0", enforce_timeout=True).run_full_page(
                "f.pdf", max_pages=1, dpi=150, timeout_seconds=45
            )
        mock_run.assert_called_once_with("f.pdf", "gpu:0", 45)

    def test_enforce_timeout_true_success_result(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch("app.services.extraction.ocr_providers.paddle_provider._run_paddle_ocr_in_subprocess") as mock_run:
            mock_run.return_value = {"success": True, "raw_text": "HELLO WORLD", "error": None, "duration_ms": 1234}
            result = PaddleOcrProvider(enforce_timeout=True).run_full_page(
                "f.pdf", max_pages=1, dpi=150, timeout_seconds=45
            )
        assert result.success is True
        assert result.raw_text == "HELLO WORLD"
        assert result.error is None
        assert result.duration_ms == 1234

    def test_enforce_timeout_true_provider_error_result(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch("app.services.extraction.ocr_providers.paddle_provider._run_paddle_ocr_in_subprocess") as mock_run:
            mock_run.return_value = {"success": False, "raw_text": "", "error": "paddle internal error", "duration_ms": 500}
            result = PaddleOcrProvider(enforce_timeout=True).run_full_page(
                "f.pdf", max_pages=1, dpi=150, timeout_seconds=45
            )
        assert result.success is False
        assert result.error == "paddle internal error"
        assert result.raw_text == ""

    # --- timeout result shape ---

    def test_timeout_result_success_is_false(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch("app.services.extraction.ocr_providers.paddle_provider._run_paddle_ocr_in_subprocess") as mock_run:
            mock_run.return_value = {
                "success": False, "raw_text": "", "error": "PaddleOCR subprocess timed out after 60s", "duration_ms": 60000,
            }
            result = PaddleOcrProvider(enforce_timeout=True).run_full_page(
                "f.pdf", max_pages=1, dpi=150, timeout_seconds=60
            )
        assert result.success is False

    def test_timeout_result_error_mentions_timed_out_and_seconds(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch("app.services.extraction.ocr_providers.paddle_provider._run_paddle_ocr_in_subprocess") as mock_run:
            mock_run.return_value = {
                "success": False, "raw_text": "", "error": "PaddleOCR subprocess timed out after 60s", "duration_ms": 60000,
            }
            result = PaddleOcrProvider(enforce_timeout=True).run_full_page(
                "f.pdf", max_pages=1, dpi=150, timeout_seconds=60
            )
        assert "timed out" in result.error.lower()
        assert "60" in result.error

    def test_timeout_result_provider_name_preserved_for_gpu(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch("app.services.extraction.ocr_providers.paddle_provider._run_paddle_ocr_in_subprocess") as mock_run:
            mock_run.return_value = {
                "success": False, "raw_text": "", "error": "PaddleOCR subprocess timed out after 5s", "duration_ms": 5000,
            }
            result = PaddleOcrProvider(device="gpu:0", enforce_timeout=True).run_full_page(
                "f.pdf", max_pages=1, dpi=150, timeout_seconds=5
            )
        assert result.provider_name == "paddleocr_gpu"

    def test_timeout_result_raw_text_empty(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch("app.services.extraction.ocr_providers.paddle_provider._run_paddle_ocr_in_subprocess") as mock_run:
            mock_run.return_value = {
                "success": False, "raw_text": "", "error": "PaddleOCR subprocess timed out after 5s", "duration_ms": 5000,
            }
            result = PaddleOcrProvider(enforce_timeout=True).run_full_page(
                "f.pdf", max_pages=1, dpi=150, timeout_seconds=5
            )
        assert result.raw_text == ""

    def test_timeout_result_duration_ms_around_timeout(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch("app.services.extraction.ocr_providers.paddle_provider._run_paddle_ocr_in_subprocess") as mock_run:
            mock_run.return_value = {
                "success": False, "raw_text": "", "error": "PaddleOCR subprocess timed out after 5s", "duration_ms": 5000,
            }
            result = PaddleOcrProvider(enforce_timeout=True).run_full_page(
                "f.pdf", max_pages=1, dpi=150, timeout_seconds=5
            )
        assert result.duration_ms >= 5 * 1000 * 0.9

    # --- unavailable check happens before subprocess spawn ---

    def test_unavailable_with_enforce_timeout_does_not_spawn_subprocess(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=False), \
             patch("app.services.extraction.ocr_providers.paddle_provider._run_paddle_ocr_in_subprocess") as mock_run:
            result = PaddleOcrProvider(enforce_timeout=True).run_full_page(
                "f.pdf", max_pages=1, dpi=150, timeout_seconds=5
            )
        mock_run.assert_not_called()
        assert result.success is False
        assert "not installed" in (result.error or "").lower()

    # --- worker function: direct in-process calls (no real subprocess) ---

    def test_worker_puts_success_result(self):
        mock_module, _ = _make_mock_paddle_module(["WORKER LINE"])
        from app.services.extraction.ocr_providers.paddle_provider import _paddle_ocr_worker
        fake_queue = MagicMock()
        with patch.dict(sys.modules, {"paddleocr": mock_module}):
            _paddle_ocr_worker({"file_path": "f.pdf", "device": None}, fake_queue)
        payload = fake_queue.put.call_args[0][0]
        assert payload["success"] is True
        assert "WORKER LINE" in payload["raw_text"]
        assert payload["error"] is None

    def test_worker_puts_error_result_on_exception(self):
        mock_module = MagicMock()
        mock_module.PaddleOCR.side_effect = RuntimeError("worker boom")
        from app.services.extraction.ocr_providers.paddle_provider import _paddle_ocr_worker
        fake_queue = MagicMock()
        with patch.dict(sys.modules, {"paddleocr": mock_module}):
            _paddle_ocr_worker({"file_path": "f.pdf", "device": None}, fake_queue)
        payload = fake_queue.put.call_args[0][0]
        assert payload["success"] is False
        assert "worker boom" in payload["error"]

    def test_worker_device_failure_returns_clear_error(self):
        from app.services.extraction.ocr_providers.paddle_provider import _paddle_ocr_worker
        fake_queue = MagicMock()
        with patch("app.services.extraction.ocr_providers.paddle_provider._set_paddle_device", return_value="CUDA unavailable"):
            _paddle_ocr_worker({"file_path": "f.pdf", "device": "gpu:0"}, fake_queue)
        payload = fake_queue.put.call_args[0][0]
        assert payload["success"] is False
        assert "CUDA unavailable" in payload["error"]
        assert "gpu:0" in payload["error"]

    # --- real subprocess: prove process-level isolation (no paddleocr/GPU needed) ---

    def test_subprocess_helper_real_process_success(self):
        """Real spawned subprocess with a fast module-level worker."""
        from app.services.extraction.ocr_providers.paddle_provider import _run_paddle_ocr_in_subprocess
        result = _run_paddle_ocr_in_subprocess("f.pdf", None, 10, worker=_fast_worker_for_test)
        assert result["success"] is True
        assert result["raw_text"] == "FAST WORKER TEXT"

    def test_subprocess_helper_drains_large_payload_without_deadlock(self):
        """Regression: a worker returning a payload larger than the OS pipe
        buffer must not deadlock. With the previous join-before-drain logic this
        hung until the timeout and returned a failure; draining the queue first
        returns the result quickly. This is the exact condition that broke real
        PaddleOCR extraction (a multi-KB result deadlocked the subprocess)."""
        from app.services.extraction.ocr_providers.paddle_provider import _run_paddle_ocr_in_subprocess
        started = time.perf_counter()
        result = _run_paddle_ocr_in_subprocess("f.pdf", None, 30, worker=_large_payload_worker_for_test)
        wall_seconds = time.perf_counter() - started
        assert result["success"] is True, f"deadlocked or failed: {result.get('error')!r}"
        assert len(result["raw_text"]) == 200_000
        assert wall_seconds < 25  # must not hang until the 30s timeout

    def test_subprocess_helper_real_process_timeout_terminates_child(self):
        """Real spawned subprocess with a worker that sleeps past the timeout.

        Proves the parent terminates/kills the child instead of waiting for it
        or leaving it running in the background.
        """
        from app.services.extraction.ocr_providers.paddle_provider import _run_paddle_ocr_in_subprocess
        started = time.perf_counter()
        result = _run_paddle_ocr_in_subprocess("f.pdf", None, 1, worker=_slow_worker_for_test)
        wall_seconds = time.perf_counter() - started
        assert result["success"] is False
        assert "timed out" in result["error"].lower()
        assert "1" in result["error"]
        assert result["raw_text"] == ""
        assert wall_seconds < 10  # must not wait for the worker's 30s sleep

    # --- existing behaviors must remain intact ---

    def test_no_paddle_or_paddleocr_import_with_enforce_timeout_constructor(self):
        """Constructing PaddleOcrProvider(enforce_timeout=True) must not import paddle/paddleocr."""
        before = {k for k in sys.modules if "paddle" in k.lower()}
        PaddleOcrProvider(enforce_timeout=True, device="gpu:0")
        after = {k for k in sys.modules if "paddle" in k.lower()}
        assert after - before == set()

    def test_registry_default_still_glm(self):
        assert get_default_ocr_provider().provider_name == "glm"


# ---------------------------------------------------------------------------
# Phase 1xI — runtime/model diagnostics (Step 6)
# ---------------------------------------------------------------------------


class TestPaddleRuntimeInfo:
    def test_paddle_runtime_info_has_expected_keys(self):
        from app.services.extraction.ocr_providers.paddle_provider import paddle_runtime_info
        info = paddle_runtime_info()
        assert set(info.keys()) == {
            "paddleocr_available",
            "paddleocr_version",
            "paddlepaddle_version",
            "paddle_init_args",
        }

    def test_paddle_runtime_info_reflects_availability(self):
        from app.services.extraction.ocr_providers.paddle_provider import paddle_runtime_info
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=False):
            info = paddle_runtime_info()
        assert info["paddleocr_available"] is False

    def test_paddle_runtime_info_init_args_contains_lang_en(self):
        from app.services.extraction.ocr_providers.paddle_provider import paddle_runtime_info
        info = paddle_runtime_info()
        assert info["paddle_init_args"] == {"lang": "en"}

    def test_paddle_runtime_info_version_unknown_when_metadata_lookup_fails(self):
        from app.services.extraction.ocr_providers.paddle_provider import paddle_runtime_info
        with patch("importlib.metadata.version", side_effect=Exception("no metadata")):
            info = paddle_runtime_info()
        assert info["paddleocr_version"] == "unknown"
        assert info["paddlepaddle_version"] == "unknown"


# ---------------------------------------------------------------------------
# Phase 1xI — OCR text block capture (Step 7)
# ---------------------------------------------------------------------------


class TestExtractPaddleTextBlocks:
    def test_returns_text_and_page_for_each_block(self):
        from app.services.extraction.ocr_providers.paddle_provider import _extract_paddle_text_blocks
        results = [{"rec_texts": ["HELLO", "WORLD"]}]
        blocks = _extract_paddle_text_blocks(results)
        assert blocks[0]["text"] == "HELLO"
        assert blocks[0]["page"] == 1
        assert blocks[1]["text"] == "WORLD"
        assert blocks[1]["page"] == 1

    def test_includes_confidence_when_rec_scores_present(self):
        from app.services.extraction.ocr_providers.paddle_provider import _extract_paddle_text_blocks
        results = [{"rec_texts": ["HELLO"], "rec_scores": [0.97]}]
        blocks = _extract_paddle_text_blocks(results)
        assert blocks[0]["confidence"] == pytest.approx(0.97)

    def test_includes_bbox_when_rec_polys_present(self):
        from app.services.extraction.ocr_providers.paddle_provider import _extract_paddle_text_blocks
        results = [{"rec_texts": ["HELLO"], "rec_polys": [[[0, 0], [10, 0], [10, 5], [0, 5]]]}]
        blocks = _extract_paddle_text_blocks(results)
        assert "bbox" in blocks[0]

    def test_omits_optional_keys_when_not_present(self):
        from app.services.extraction.ocr_providers.paddle_provider import _extract_paddle_text_blocks
        results = [{"rec_texts": ["HELLO"]}]
        blocks = _extract_paddle_text_blocks(results)
        assert "confidence" not in blocks[0]
        assert "bbox" not in blocks[0]

    def test_empty_for_none_results(self):
        from app.services.extraction.ocr_providers.paddle_provider import _extract_paddle_text_blocks
        assert _extract_paddle_text_blocks(None) == []

    def test_page_numbers_increment_across_pages(self):
        from app.services.extraction.ocr_providers.paddle_provider import _extract_paddle_text_blocks
        results = [{"rec_texts": ["PAGE1"]}, {"rec_texts": ["PAGE2"]}]
        blocks = _extract_paddle_text_blocks(results)
        assert blocks[0]["page"] == 1
        assert blocks[1]["page"] == 2


class TestRunFullPageDiagnostics:
    def test_run_full_page_populates_model_info(self):
        mock_module, _ = _make_mock_paddle_module()
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch.dict(sys.modules, {"paddleocr": mock_module}):
            result = PaddleOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.model_info is not None
        assert "paddleocr_version" in result.model_info

    def test_run_full_page_populates_text_blocks(self):
        mock_module, _ = _make_mock_paddle_module(["HELLO"])
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch.dict(sys.modules, {"paddleocr": mock_module}):
            result = PaddleOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.text_blocks is not None
        assert result.text_blocks[0]["text"] == "HELLO"

    def test_unavailable_result_has_no_text_blocks(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=False):
            result = PaddleOcrProvider().run_full_page("f.pdf", max_pages=1, dpi=150, timeout_seconds=60)
        assert result.text_blocks is None

    def test_worker_includes_text_blocks_in_payload(self):
        mock_module, _ = _make_mock_paddle_module(["WORKER LINE"])
        from app.services.extraction.ocr_providers.paddle_provider import _paddle_ocr_worker
        fake_queue = MagicMock()
        with patch.dict(sys.modules, {"paddleocr": mock_module}):
            _paddle_ocr_worker({"file_path": "f.pdf", "device": None}, fake_queue)
        payload = fake_queue.put.call_args[0][0]
        assert "text_blocks" in payload
        assert payload["text_blocks"][0]["text"] == "WORKER LINE"

    def test_enforce_timeout_path_populates_text_blocks_from_subprocess_result(self):
        with patch("app.services.extraction.ocr_providers.paddle_provider._paddle_available", return_value=True), \
             patch("app.services.extraction.ocr_providers.paddle_provider._run_paddle_ocr_in_subprocess") as mock_run:
            mock_run.return_value = {
                "success": True, "raw_text": "HELLO", "error": None, "duration_ms": 10,
                "text_blocks": [{"text": "HELLO", "page": 1}],
            }
            result = PaddleOcrProvider(enforce_timeout=True).run_full_page(
                "f.pdf", max_pages=1, dpi=150, timeout_seconds=45
            )
        assert result.text_blocks == [{"text": "HELLO", "page": 1}]
