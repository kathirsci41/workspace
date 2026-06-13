"""TDD tests for OCR DPI × mode matrix evaluation harness.

Phase 1n covers:
  - Matrix builds expected combinations (providers × DPI values)
  - MatrixEntry contains required fields (provider, dpi, score, extracted_fields, match_flags, duration_ms)
  - score_fields returns 0-3 based on exact matches against expected dict
  - Provider errors are recorded without crashing the matrix
  - render_matrix_report includes score and exact-match fields in output
  - summarize_matrix returns best entry and any_perfect flag
  - No PaddleOCR dependency required
  - No production extraction mutation
  - No Panimalar-specific hardcoding in ocr_matrix module

Phase 1o adds:
  - classify_field returns failure classification per field
  - MatrixEntry has normalized_text_preview and field_classifications fields
  - Markdown report contains field classification table and text preview section
  - JSON report contains field_classifications and normalized_text_preview keys

Phase 1w adds:
  - Matrix accepts paddleocr_gpu provider key
  - paddleocr_gpu records result without crashing
  - Scoring works for paddleocr_gpu extracted fields
  - Renderer includes paddleocr_gpu, duration, text_len, extracted fields
  - paddleocr_gpu does not mutate production extraction
"""
from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import app.services.extraction.ocr_matrix as ocr_matrix
from app.services.extraction.ocr_matrix import (
    MatrixEntry,
    classify_field,
    render_matrix_report,
    run_matrix,
    score_fields,
    summarize_matrix,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Generic expected values — not Panimalar-specific
_EXPECTED = {
    "vendor_invoice_no": "INV001",
    "vendor_invoice_date": "01-01-2026",
    "po_reference": "PO001",
}

_PROVIDERS = ["glm_full_page", "glm_header"]
_DPI_VALUES = [72, 150, 200, 300]


def _make_ocr_result(
    *,
    provider_name: str = "glm_full_page",
    success: bool = True,
    extracted_fields: dict | None = None,
    duration_ms: int = 100,
    raw_text_length: int = 500,
    error: str | None = None,
    normalized_text_preview: str = "Invoice No: INV001\nInvoice Date: 01-01-2026",
    parse_mode: str = "raw",
) -> SimpleNamespace:
    """Minimal fake OcrProviderResult for patching run_glm_*_evaluation."""
    return SimpleNamespace(
        provider_name=provider_name,
        success=success,
        extracted_fields=extracted_fields if extracted_fields is not None else {},
        duration_ms=duration_ms,
        raw_text_length=raw_text_length,
        error=error,
        normalized_text_preview=normalized_text_preview,
        parse_mode=parse_mode,
    )


def _all_match_result(provider_name: str) -> SimpleNamespace:
    return _make_ocr_result(
        provider_name=provider_name,
        extracted_fields={
            "vendor_invoice_no": "INV001",
            "vendor_invoice_date": "01-01-2026",
            "po_reference": "PO001",
        },
    )


def _no_match_result(provider_name: str) -> SimpleNamespace:
    return _make_ocr_result(
        provider_name=provider_name,
        extracted_fields={
            "vendor_invoice_no": None,
            "vendor_invoice_date": None,
            "po_reference": None,
        },
    )


def _patch_providers(full_page_fn, header_fn):
    """Context manager patching both provider fns on the matrix module."""
    return (
        patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=full_page_fn),
        patch.object(ocr_matrix, "run_glm_header_evaluation", side_effect=header_fn),
    )


# ---------------------------------------------------------------------------
# Matrix combination building
# ---------------------------------------------------------------------------

class TestMatrixCombinations:
    def test_matrix_produces_correct_number_of_entries(self, tmp_path: Path):
        pdf = str(tmp_path / "doc.pdf")
        full_page = lambda *a, **kw: _make_ocr_result(provider_name="glm_full_page")
        header = lambda *a, **kw: _make_ocr_result(provider_name="glm_header")
        with patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=full_page), \
             patch.object(ocr_matrix, "run_glm_header_evaluation", side_effect=header):
            entries = run_matrix(
                pdf,
                providers=_PROVIDERS,
                dpi_values=_DPI_VALUES,
                expected=_EXPECTED,
                timeout_seconds=5,
            )
        assert len(entries) == len(_PROVIDERS) * len(_DPI_VALUES)

    def test_matrix_entries_cover_all_providers(self, tmp_path: Path):
        pdf = str(tmp_path / "doc.pdf")
        full_page = lambda *a, **kw: _make_ocr_result(provider_name="glm_full_page")
        header = lambda *a, **kw: _make_ocr_result(provider_name="glm_header")
        with patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=full_page), \
             patch.object(ocr_matrix, "run_glm_header_evaluation", side_effect=header):
            entries = run_matrix(
                pdf,
                providers=_PROVIDERS,
                dpi_values=_DPI_VALUES,
                expected=_EXPECTED,
                timeout_seconds=5,
            )
        providers_seen = {e.provider for e in entries}
        assert providers_seen == set(_PROVIDERS)

    def test_matrix_entries_cover_all_dpi_values(self, tmp_path: Path):
        pdf = str(tmp_path / "doc.pdf")
        full_page = lambda *a, **kw: _make_ocr_result(provider_name="glm_full_page")
        header = lambda *a, **kw: _make_ocr_result(provider_name="glm_header")
        with patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=full_page), \
             patch.object(ocr_matrix, "run_glm_header_evaluation", side_effect=header):
            entries = run_matrix(
                pdf,
                providers=_PROVIDERS,
                dpi_values=_DPI_VALUES,
                expected=_EXPECTED,
                timeout_seconds=5,
            )
        dpis_seen = {e.dpi for e in entries}
        assert dpis_seen == set(_DPI_VALUES)

    def test_single_provider_single_dpi_produces_one_entry(self, tmp_path: Path):
        pdf = str(tmp_path / "doc.pdf")
        full_page = lambda *a, **kw: _make_ocr_result(provider_name="glm_full_page")
        with patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=full_page):
            entries = run_matrix(
                pdf,
                providers=["glm_full_page"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=5,
            )
        assert len(entries) == 1
        assert entries[0].provider == "glm_full_page"
        assert entries[0].dpi == 150


# ---------------------------------------------------------------------------
# MatrixEntry shape
# ---------------------------------------------------------------------------

class TestMatrixEntryShape:
    def _get_single_entry(self, tmp_path: Path) -> MatrixEntry:
        pdf = str(tmp_path / "shape.pdf")
        full_page = lambda *a, **kw: _make_ocr_result(provider_name="glm_full_page", duration_ms=42, raw_text_length=123)
        with patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=full_page):
            entries = run_matrix(
                pdf,
                providers=["glm_full_page"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=5,
            )
        return entries[0]

    def test_entry_is_matrix_entry_instance(self, tmp_path: Path):
        entry = self._get_single_entry(tmp_path)
        assert isinstance(entry, MatrixEntry)

    def test_entry_has_provider_field(self, tmp_path: Path):
        entry = self._get_single_entry(tmp_path)
        assert entry.provider == "glm_full_page"

    def test_entry_has_dpi_field(self, tmp_path: Path):
        entry = self._get_single_entry(tmp_path)
        assert entry.dpi == 150

    def test_entry_has_duration_ms_field(self, tmp_path: Path):
        entry = self._get_single_entry(tmp_path)
        assert isinstance(entry.duration_ms, int)
        assert entry.duration_ms == 42

    def test_entry_has_raw_text_length_field(self, tmp_path: Path):
        entry = self._get_single_entry(tmp_path)
        assert entry.raw_text_length == 123

    def test_entry_has_success_field(self, tmp_path: Path):
        entry = self._get_single_entry(tmp_path)
        assert isinstance(entry.success, bool)

    def test_entry_has_extracted_fields_dict(self, tmp_path: Path):
        entry = self._get_single_entry(tmp_path)
        assert isinstance(entry.extracted_fields, dict)

    def test_entry_has_match_flags_dict(self, tmp_path: Path):
        entry = self._get_single_entry(tmp_path)
        assert isinstance(entry.match_flags, dict)

    def test_entry_has_score_int(self, tmp_path: Path):
        entry = self._get_single_entry(tmp_path)
        assert isinstance(entry.score, int)
        assert 0 <= entry.score <= 3


# ---------------------------------------------------------------------------
# score_fields
# ---------------------------------------------------------------------------

class TestScoreFields:
    def test_returns_0_when_extracted_is_empty(self):
        assert score_fields({}, _EXPECTED) == 0

    def test_returns_0_when_all_fields_none(self):
        extracted = {k: None for k in _EXPECTED}
        assert score_fields(extracted, _EXPECTED) == 0

    def test_returns_0_when_all_fields_wrong(self):
        extracted = {k: "WRONG" for k in _EXPECTED}
        assert score_fields(extracted, _EXPECTED) == 0

    def test_returns_3_when_all_fields_match_exactly(self):
        extracted = dict(_EXPECTED)
        assert score_fields(extracted, _EXPECTED) == 3

    def test_returns_1_when_one_field_matches(self):
        extracted = {
            "vendor_invoice_no": "INV001",
            "vendor_invoice_date": None,
            "po_reference": None,
        }
        assert score_fields(extracted, _EXPECTED) == 1

    def test_returns_2_when_two_fields_match(self):
        extracted = {
            "vendor_invoice_no": "INV001",
            "vendor_invoice_date": "01-01-2026",
            "po_reference": "WRONG",
        }
        assert score_fields(extracted, _EXPECTED) == 2

    def test_strips_whitespace_before_comparing(self):
        extracted = {
            "vendor_invoice_no": "  INV001  ",
            "vendor_invoice_date": "01-01-2026",
            "po_reference": "PO001",
        }
        assert score_fields(extracted, _EXPECTED) == 3

    def test_returns_int_type(self):
        result = score_fields({}, _EXPECTED)
        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# Scoring and match flags in entries
# ---------------------------------------------------------------------------

class TestMatrixEntryScoring:
    def test_score_is_3_when_all_fields_match(self, tmp_path: Path):
        pdf = str(tmp_path / "score3.pdf")
        full_page = lambda *a, **kw: _all_match_result("glm_full_page")
        with patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=full_page):
            entries = run_matrix(
                pdf,
                providers=["glm_full_page"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=5,
            )
        assert entries[0].score == 3

    def test_score_is_0_when_no_fields_match(self, tmp_path: Path):
        pdf = str(tmp_path / "score0.pdf")
        full_page = lambda *a, **kw: _no_match_result("glm_full_page")
        with patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=full_page):
            entries = run_matrix(
                pdf,
                providers=["glm_full_page"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=5,
            )
        assert entries[0].score == 0

    def test_match_flags_are_true_when_fields_match(self, tmp_path: Path):
        pdf = str(tmp_path / "flagstrue.pdf")
        full_page = lambda *a, **kw: _all_match_result("glm_full_page")
        with patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=full_page):
            entries = run_matrix(
                pdf,
                providers=["glm_full_page"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=5,
            )
        flags = entries[0].match_flags
        assert flags["vendor_invoice_no"] is True
        assert flags["vendor_invoice_date"] is True
        assert flags["po_reference"] is True

    def test_match_flags_are_false_when_fields_missing(self, tmp_path: Path):
        pdf = str(tmp_path / "flagsfalse.pdf")
        full_page = lambda *a, **kw: _no_match_result("glm_full_page")
        with patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=full_page):
            entries = run_matrix(
                pdf,
                providers=["glm_full_page"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=5,
            )
        flags = entries[0].match_flags
        assert flags["vendor_invoice_no"] is False
        assert flags["vendor_invoice_date"] is False
        assert flags["po_reference"] is False

    def test_extracted_fields_stored_in_entry(self, tmp_path: Path):
        pdf = str(tmp_path / "stored.pdf")
        full_page = lambda *a, **kw: _all_match_result("glm_full_page")
        with patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=full_page):
            entries = run_matrix(
                pdf,
                providers=["glm_full_page"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=5,
            )
        ef = entries[0].extracted_fields
        assert ef.get("vendor_invoice_no") == "INV001"


# ---------------------------------------------------------------------------
# Error handling — provider errors must not crash run_matrix
# ---------------------------------------------------------------------------

class TestMatrixErrorHandling:
    def test_provider_exception_recorded_without_crash(self, tmp_path: Path):
        pdf = str(tmp_path / "err.pdf")
        full_page = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("connection refused"))
        with patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=RuntimeError("connection refused")):
            entries = run_matrix(
                pdf,
                providers=["glm_full_page"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=5,
            )
        assert len(entries) == 1
        assert entries[0].success is False
        assert entries[0].error is not None
        assert "connection refused" in entries[0].error

    def test_provider_error_entry_has_score_0(self, tmp_path: Path):
        pdf = str(tmp_path / "err_score.pdf")
        with patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=RuntimeError("boom")):
            entries = run_matrix(
                pdf,
                providers=["glm_full_page"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=5,
            )
        assert entries[0].score == 0

    def test_one_provider_error_does_not_block_other_providers(self, tmp_path: Path):
        pdf = str(tmp_path / "partial_err.pdf")
        header = lambda *a, **kw: _all_match_result("glm_header")
        with patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=RuntimeError("bad")), \
             patch.object(ocr_matrix, "run_glm_header_evaluation", side_effect=header):
            entries = run_matrix(
                pdf,
                providers=["glm_full_page", "glm_header"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=5,
            )
        assert len(entries) == 2
        fp_entry = next(e for e in entries if e.provider == "glm_full_page")
        hdr_entry = next(e for e in entries if e.provider == "glm_header")
        assert fp_entry.success is False
        assert hdr_entry.success is True
        assert hdr_entry.score == 3


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

class TestMatrixReporting:
    def _make_entries(self) -> list[MatrixEntry]:
        return [
            MatrixEntry(
                provider="glm_full_page",
                dpi=150,
                duration_ms=500,
                success=True,
                error=None,
                raw_text_length=300,
                extracted_fields={"vendor_invoice_no": "INV001", "vendor_invoice_date": None, "po_reference": None},
                match_flags={"vendor_invoice_no": True, "vendor_invoice_date": False, "po_reference": False},
                score=1,
            ),
            MatrixEntry(
                provider="glm_header",
                dpi=300,
                duration_ms=200,
                success=True,
                error=None,
                raw_text_length=100,
                extracted_fields={"vendor_invoice_no": "INV001", "vendor_invoice_date": "01-01-2026", "po_reference": "PO001"},
                match_flags={"vendor_invoice_no": True, "vendor_invoice_date": True, "po_reference": True},
                score=3,
            ),
        ]

    def test_markdown_report_contains_score(self):
        report = render_matrix_report(self._make_entries(), format="markdown")
        assert "score" in report.lower()

    def test_markdown_report_contains_provider_names(self):
        report = render_matrix_report(self._make_entries(), format="markdown")
        assert "glm_full_page" in report
        assert "glm_header" in report

    def test_markdown_report_contains_dpi_values(self):
        report = render_matrix_report(self._make_entries(), format="markdown")
        assert "150" in report
        assert "300" in report

    def test_markdown_report_contains_score_values(self):
        report = render_matrix_report(self._make_entries(), format="markdown")
        # score=3 should appear
        assert "3" in report

    def test_json_report_is_parseable(self):
        import json
        report = render_matrix_report(self._make_entries(), format="json")
        data = json.loads(report)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_json_report_contains_score_field(self):
        import json
        report = render_matrix_report(self._make_entries(), format="json")
        data = json.loads(report)
        for item in data:
            assert "score" in item

    def test_json_report_contains_match_flags(self):
        import json
        report = render_matrix_report(self._make_entries(), format="json")
        data = json.loads(report)
        for item in data:
            assert "match_flags" in item

    def test_report_renders_without_unicode_encode_error(self):
        """Report must be ASCII-safe for Windows cp1252 console."""
        report = render_matrix_report(self._make_entries(), format="markdown")
        report.encode("cp1252")  # must not raise


# ---------------------------------------------------------------------------
# summarize_matrix
# ---------------------------------------------------------------------------

class TestMatrixSummary:
    def _make_mixed_entries(self) -> list[MatrixEntry]:
        def _entry(provider, dpi, score, duration_ms=100):
            return MatrixEntry(
                provider=provider,
                dpi=dpi,
                duration_ms=duration_ms,
                success=True,
                error=None,
                raw_text_length=100,
                extracted_fields={},
                match_flags={},
                score=score,
            )
        return [
            _entry("glm_full_page", 72, 0),
            _entry("glm_full_page", 150, 1),
            _entry("glm_full_page", 200, 2),
            _entry("glm_full_page", 300, 3, duration_ms=500),
            _entry("glm_header", 72, 1),
            _entry("glm_header", 150, 2),
            _entry("glm_header", 200, 3, duration_ms=200),
            _entry("glm_header", 300, 3, duration_ms=300),
        ]

    def test_summary_is_dict(self):
        summary = summarize_matrix(self._make_mixed_entries())
        assert isinstance(summary, dict)

    def test_summary_contains_best_entry(self):
        summary = summarize_matrix(self._make_mixed_entries())
        assert "best_entry" in summary
        assert isinstance(summary["best_entry"], MatrixEntry)

    def test_best_entry_has_highest_score(self):
        summary = summarize_matrix(self._make_mixed_entries())
        assert summary["best_entry"].score == 3

    def test_best_entry_tiebreaks_by_lowest_duration(self):
        """When multiple entries share the max score, pick the fastest."""
        summary = summarize_matrix(self._make_mixed_entries())
        # glm_header@200 scores 3 with 200ms vs glm_full_page@300 with 500ms and glm_header@300 with 300ms
        best = summary["best_entry"]
        assert best.score == 3
        assert best.duration_ms == 200

    def test_any_perfect_true_when_score_3_exists(self):
        summary = summarize_matrix(self._make_mixed_entries())
        assert summary["any_perfect"] is True

    def test_any_perfect_false_when_no_score_3(self):
        entries = [
            MatrixEntry("glm_full_page", 150, 100, True, None, 100, {}, {}, 1),
            MatrixEntry("glm_header", 150, 100, True, None, 100, {}, {}, 2),
        ]
        summary = summarize_matrix(entries)
        assert summary["any_perfect"] is False

    def test_summary_contains_max_score(self):
        summary = summarize_matrix(self._make_mixed_entries())
        assert summary["max_score"] == 3

    def test_summary_contains_total_entries_count(self):
        entries = self._make_mixed_entries()
        summary = summarize_matrix(entries)
        assert summary["total_entries"] == len(entries)


# ---------------------------------------------------------------------------
# Production isolation
# ---------------------------------------------------------------------------

class TestMatrixDoesNotMutateProduction:
    def test_run_matrix_does_not_call_extract_document(self, tmp_path: Path):
        pdf = str(tmp_path / "iso.pdf")
        full_page = lambda *a, **kw: _make_ocr_result(provider_name="glm_full_page")
        with patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=full_page), \
             patch("app.services.extraction_service.extract_document") as mock_extract:
            run_matrix(
                pdf,
                providers=["glm_full_page"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=5,
            )
        mock_extract.assert_not_called()

    def test_run_matrix_does_not_require_paddleocr(self, tmp_path: Path):
        """Matrix harness must run without PaddleOCR installed."""
        import importlib.util
        spec = importlib.util.find_spec("paddleocr")
        if spec is not None:
            pytest.skip("PaddleOCR is installed — unavailability path not testable")
        # Import succeeds without paddleocr
        import app.services.extraction.ocr_matrix  # noqa: F401


# ---------------------------------------------------------------------------
# No Panimalar-specific hardcoding
# ---------------------------------------------------------------------------

def test_ocr_matrix_module_has_no_panimalar_hardcoding():
    source = inspect.getsource(ocr_matrix).lower()
    assert "panimalar" not in source


def test_ocr_matrix_module_has_no_hardcoded_expected_values():
    """Expected invoice/PO values must be injected, never baked in."""
    source = inspect.getsource(ocr_matrix)
    # These are the Panimalar-specific expected values from the evaluation spec
    assert "2526PSI25087738" not in source
    assert "1PTR2526000467" not in source
    assert "12-02-2026" not in source


# ---------------------------------------------------------------------------
# classify_field — Phase 1o
# ---------------------------------------------------------------------------

class TestClassifyField:
    def test_ocr_error_when_not_success(self):
        result = classify_field(
            success=False,
            raw_text_length=400,
            extracted_value=None,
            expected_value="INV001",
        )
        assert result == "ocr_error"

    def test_no_text_when_raw_text_length_zero_and_success(self):
        result = classify_field(
            success=True,
            raw_text_length=0,
            extracted_value=None,
            expected_value="INV001",
        )
        assert result == "no_text"

    def test_exact_match_when_values_equal(self):
        result = classify_field(
            success=True,
            raw_text_length=400,
            extracted_value="INV001",
            expected_value="INV001",
        )
        assert result == "exact_match"

    def test_exact_match_strips_whitespace(self):
        result = classify_field(
            success=True,
            raw_text_length=400,
            extracted_value="  INV001  ",
            expected_value="INV001",
        )
        assert result == "exact_match"

    def test_value_mismatch_when_extracted_exists_but_differs(self):
        result = classify_field(
            success=True,
            raw_text_length=400,
            extracted_value="WRONG999",
            expected_value="INV001",
        )
        assert result == "value_mismatch"

    def test_parser_no_match_when_extracted_none_and_text_exists(self):
        result = classify_field(
            success=True,
            raw_text_length=400,
            extracted_value=None,
            expected_value="INV001",
        )
        assert result == "parser_no_match"

    def test_ocr_error_priority_over_no_text(self):
        """success=False takes priority even when raw_text_length is 0."""
        result = classify_field(
            success=False,
            raw_text_length=0,
            extracted_value=None,
            expected_value="INV001",
        )
        assert result == "ocr_error"

    def test_no_text_priority_over_parser_no_match(self):
        """raw_text_length=0 with success=True yields no_text, not parser_no_match."""
        result = classify_field(
            success=True,
            raw_text_length=0,
            extracted_value=None,
            expected_value="INV001",
        )
        assert result == "no_text"

    def test_returns_string(self):
        result = classify_field(
            success=True,
            raw_text_length=400,
            extracted_value="INV001",
            expected_value="INV001",
        )
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# MatrixEntry new fields — Phase 1o
# ---------------------------------------------------------------------------

class TestMatrixEntryNewFields:
    def _get_entry(self, tmp_path: Path, preview: str = "Sample preview") -> MatrixEntry:
        pdf = str(tmp_path / "new_fields.pdf")
        full_page = lambda *a, **kw: _make_ocr_result(
            provider_name="glm_full_page",
            normalized_text_preview=preview,
            extracted_fields={"vendor_invoice_no": "INV001", "vendor_invoice_date": "01-01-2026", "po_reference": "PO001"},
        )
        with patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=full_page):
            entries = run_matrix(
                pdf,
                providers=["glm_full_page"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=5,
            )
        return entries[0]

    def test_entry_has_normalized_text_preview_field(self, tmp_path: Path):
        entry = self._get_entry(tmp_path)
        assert hasattr(entry, "normalized_text_preview")

    def test_entry_preview_matches_provider_result(self, tmp_path: Path):
        entry = self._get_entry(tmp_path, preview="My preview text")
        assert entry.normalized_text_preview == "My preview text"

    def test_entry_has_field_classifications_field(self, tmp_path: Path):
        entry = self._get_entry(tmp_path)
        assert hasattr(entry, "field_classifications")
        assert isinstance(entry.field_classifications, dict)

    def test_entry_field_classifications_keys_match_expected(self, tmp_path: Path):
        entry = self._get_entry(tmp_path)
        assert set(entry.field_classifications.keys()) == set(_EXPECTED.keys())

    def test_entry_exact_match_classification_for_matching_field(self, tmp_path: Path):
        entry = self._get_entry(tmp_path)
        assert entry.field_classifications["vendor_invoice_no"] == "exact_match"
        assert entry.field_classifications["vendor_invoice_date"] == "exact_match"
        assert entry.field_classifications["po_reference"] == "exact_match"

    def test_entry_parser_no_match_when_field_not_extracted(self, tmp_path: Path):
        pdf = str(tmp_path / "no_match.pdf")
        full_page = lambda *a, **kw: _make_ocr_result(
            provider_name="glm_full_page",
            raw_text_length=400,
            extracted_fields={"vendor_invoice_no": None, "vendor_invoice_date": None, "po_reference": None},
        )
        with patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=full_page):
            entries = run_matrix(
                pdf,
                providers=["glm_full_page"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=5,
            )
        entry = entries[0]
        assert entry.field_classifications["vendor_invoice_no"] == "parser_no_match"
        assert entry.field_classifications["vendor_invoice_date"] == "parser_no_match"

    def test_entry_value_mismatch_when_extracted_wrong(self, tmp_path: Path):
        pdf = str(tmp_path / "mismatch.pdf")
        full_page = lambda *a, **kw: _make_ocr_result(
            provider_name="glm_full_page",
            raw_text_length=400,
            extracted_fields={"vendor_invoice_no": "WRONG", "vendor_invoice_date": "WRONG", "po_reference": "WRONG"},
        )
        with patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=full_page):
            entries = run_matrix(
                pdf,
                providers=["glm_full_page"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=5,
            )
        entry = entries[0]
        assert entry.field_classifications["vendor_invoice_no"] == "value_mismatch"

    def test_entry_error_gets_ocr_error_classification(self, tmp_path: Path):
        pdf = str(tmp_path / "err_cls.pdf")
        with patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=RuntimeError("boom")):
            entries = run_matrix(
                pdf,
                providers=["glm_full_page"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=5,
            )
        entry = entries[0]
        assert entry.field_classifications["vendor_invoice_no"] == "ocr_error"
        assert entry.field_classifications["vendor_invoice_date"] == "ocr_error"
        assert entry.field_classifications["po_reference"] == "ocr_error"


# ---------------------------------------------------------------------------
# Report rendering — Phase 1o additions
# ---------------------------------------------------------------------------

class TestMatrixReportingPhase1o:
    def _make_entries(self) -> list[MatrixEntry]:
        return [
            MatrixEntry(
                provider="glm_header",
                dpi=72,
                duration_ms=300,
                success=True,
                error=None,
                raw_text_length=398,
                extracted_fields={
                    "vendor_invoice_no": "WRONG123",
                    "vendor_invoice_date": "01-01-2026",
                    "po_reference": None,
                },
                match_flags={
                    "vendor_invoice_no": False,
                    "vendor_invoice_date": True,
                    "po_reference": False,
                },
                score=1,
                normalized_text_preview="Invoice No: WRONG123\nInvoice Date: 01-01-2026\nPO Reference: PO ABC1",
                field_classifications={
                    "vendor_invoice_no": "value_mismatch",
                    "vendor_invoice_date": "exact_match",
                    "po_reference": "parser_no_match",
                },
            ),
        ]

    def test_markdown_report_contains_field_classification_section(self):
        report = render_matrix_report(self._make_entries(), format="markdown")
        assert "classification" in report.lower()

    def test_markdown_report_contains_value_mismatch_label(self):
        report = render_matrix_report(self._make_entries(), format="markdown")
        assert "value_mismatch" in report

    def test_markdown_report_contains_exact_match_label(self):
        report = render_matrix_report(self._make_entries(), format="markdown")
        assert "exact_match" in report

    def test_markdown_report_contains_parser_no_match_label(self):
        report = render_matrix_report(self._make_entries(), format="markdown")
        assert "parser_no_match" in report

    def test_markdown_report_contains_text_preview_section(self):
        report = render_matrix_report(self._make_entries(), format="markdown")
        assert "preview" in report.lower()

    def test_markdown_report_contains_preview_text_content(self):
        report = render_matrix_report(self._make_entries(), format="markdown")
        assert "Invoice No: WRONG123" in report

    def test_json_report_contains_field_classifications_key(self):
        import json
        report = render_matrix_report(self._make_entries(), format="json")
        data = json.loads(report)
        assert "field_classifications" in data[0]

    def test_json_report_contains_normalized_text_preview_key(self):
        import json
        report = render_matrix_report(self._make_entries(), format="json")
        data = json.loads(report)
        assert "normalized_text_preview" in data[0]

    def test_json_field_classifications_values_are_correct(self):
        import json
        report = render_matrix_report(self._make_entries(), format="json")
        data = json.loads(report)
        cls = data[0]["field_classifications"]
        assert cls["vendor_invoice_no"] == "value_mismatch"
        assert cls["vendor_invoice_date"] == "exact_match"
        assert cls["po_reference"] == "parser_no_match"

    def test_markdown_report_ascii_safe_with_classification_section(self):
        """Classification labels must remain ASCII-safe."""
        report = render_matrix_report(self._make_entries(), format="markdown")
        report.encode("cp1252")  # must not raise


# ---------------------------------------------------------------------------
# Phase 1q — parse_mode in MatrixEntry and run_matrix
# ---------------------------------------------------------------------------

class TestParseModePhase1q:
    """Phase 1q: parse_mode propagates from run_matrix through MatrixEntry to report."""

    def test_matrix_entry_has_parse_mode_field(self):
        """MatrixEntry must have a parse_mode field defaulting to 'raw'."""
        entry = MatrixEntry(
            provider="glm_header",
            dpi=150,
            duration_ms=100,
            success=True,
            error=None,
            raw_text_length=200,
            extracted_fields={},
            match_flags={},
            score=0,
        )
        assert hasattr(entry, "parse_mode")
        assert entry.parse_mode == "raw"

    def test_matrix_entry_parse_mode_can_be_set_to_header_normalized(self):
        """MatrixEntry must accept parse_mode='header_normalized'."""
        entry = MatrixEntry(
            provider="glm_header",
            dpi=150,
            duration_ms=100,
            success=True,
            error=None,
            raw_text_length=200,
            extracted_fields={},
            match_flags={},
            score=0,
            parse_mode="header_normalized",
        )
        assert entry.parse_mode == "header_normalized"

    def test_run_matrix_accepts_parse_mode_parameter(self, tmp_path: Path):
        """run_matrix must accept parse_mode kwarg without TypeError."""
        pdf = str(tmp_path / "doc.pdf")
        full_page = lambda *a, **kw: _make_ocr_result(provider_name="glm_full_page")
        header = lambda *a, **kw: _make_ocr_result(provider_name="glm_header")
        with patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=full_page), \
             patch.object(ocr_matrix, "run_glm_header_evaluation", side_effect=header):
            entries = run_matrix(
                pdf,
                providers=["glm_header"],
                dpi_values=[72],
                expected=_EXPECTED,
                timeout_seconds=5,
                parse_mode="raw",
            )
        assert len(entries) == 1

    def test_run_matrix_propagates_parse_mode_to_entries(self, tmp_path: Path):
        """parse_mode passed to run_matrix must appear on each MatrixEntry."""
        pdf = str(tmp_path / "doc.pdf")
        full_page = lambda *a, **kw: _make_ocr_result(provider_name="glm_full_page", parse_mode="header_normalized")
        header = lambda *a, **kw: _make_ocr_result(provider_name="glm_header", parse_mode="header_normalized")
        with patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=full_page), \
             patch.object(ocr_matrix, "run_glm_header_evaluation", side_effect=header):
            entries = run_matrix(
                pdf,
                providers=["glm_header"],
                dpi_values=[72],
                expected=_EXPECTED,
                timeout_seconds=5,
                parse_mode="header_normalized",
            )
        assert entries[0].parse_mode == "header_normalized"

    def test_run_matrix_passes_parse_mode_to_header_provider(self, tmp_path: Path):
        """run_matrix must forward parse_mode to run_glm_header_evaluation."""
        pdf = str(tmp_path / "doc.pdf")
        captured_kwargs: list[dict] = []

        def header_spy(*a, **kw):
            captured_kwargs.append(kw)
            return _make_ocr_result(provider_name="glm_header", parse_mode=kw.get("parse_mode", "raw"))

        with patch.object(ocr_matrix, "run_glm_header_evaluation", side_effect=header_spy):
            run_matrix(
                pdf,
                providers=["glm_header"],
                dpi_values=[72],
                expected=_EXPECTED,
                timeout_seconds=5,
                parse_mode="header_normalized",
            )
        assert captured_kwargs[0].get("parse_mode") == "header_normalized"

    def test_run_matrix_default_parse_mode_is_raw(self, tmp_path: Path):
        """Omitting parse_mode from run_matrix must default to 'raw'."""
        pdf = str(tmp_path / "doc.pdf")
        full_page = lambda *a, **kw: _make_ocr_result(provider_name="glm_full_page")
        header = lambda *a, **kw: _make_ocr_result(provider_name="glm_header")
        with patch.object(ocr_matrix, "run_glm_full_page_evaluation", side_effect=full_page), \
             patch.object(ocr_matrix, "run_glm_header_evaluation", side_effect=header):
            entries = run_matrix(
                pdf,
                providers=["glm_header"],
                dpi_values=[72],
                expected=_EXPECTED,
                timeout_seconds=5,
            )
        assert entries[0].parse_mode == "raw"

    def test_markdown_report_includes_parse_mode(self):
        """Markdown report must mention parse_mode."""
        entries = [
            MatrixEntry(
                provider="glm_header",
                dpi=150,
                duration_ms=100,
                success=True,
                error=None,
                raw_text_length=200,
                extracted_fields={"vendor_invoice_no": "INV001", "vendor_invoice_date": "01-01-2026", "po_reference": "PO001"},
                match_flags={"vendor_invoice_no": True, "vendor_invoice_date": True, "po_reference": True},
                score=3,
                parse_mode="header_normalized",
            )
        ]
        report = render_matrix_report(entries, format="markdown")
        assert "header_normalized" in report

    def test_json_report_includes_parse_mode(self):
        """JSON report must include parse_mode key in each entry."""
        import json
        entries = [
            MatrixEntry(
                provider="glm_header",
                dpi=150,
                duration_ms=100,
                success=True,
                error=None,
                raw_text_length=200,
                extracted_fields={},
                match_flags={},
                score=0,
                parse_mode="raw",
            )
        ]
        report = render_matrix_report(entries, format="json")
        data = json.loads(report)
        assert "parse_mode" in data[0]
        assert data[0]["parse_mode"] == "raw"

    def test_matrix_does_not_mutate_production_extractor_with_parse_mode(self, tmp_path: Path):
        """parse_mode support must not cause run_matrix to call extract_document."""
        pdf = str(tmp_path / "nodoc.pdf")
        header = lambda *a, **kw: _make_ocr_result(provider_name="glm_header", parse_mode="header_normalized")
        with patch.object(ocr_matrix, "run_glm_header_evaluation", side_effect=header), \
             patch("app.services.extraction_service.extract_document") as mock_extract:
            run_matrix(
                pdf,
                providers=["glm_header"],
                dpi_values=[72],
                expected=_EXPECTED,
                timeout_seconds=5,
                parse_mode="header_normalized",
            )
        mock_extract.assert_not_called()


# ---------------------------------------------------------------------------
# Phase 1w — paddleocr_gpu provider in matrix
# ---------------------------------------------------------------------------

def _paddle_gpu_result(
    *,
    success: bool = True,
    extracted_fields: dict | None = None,
    raw_text_length: int = 2897,
    duration_ms: int = 11154,
    error: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        provider_name="paddleocr",
        success=success,
        error=error if not success else None,
        duration_ms=duration_ms,
        raw_text_length=raw_text_length,
        extracted_fields=extracted_fields if extracted_fields is not None else {},
        normalized_text_preview="Invoice No: INV001",
        parse_mode="raw",
    )


class TestPaddleOcrGpuMatrix:
    """Phase 1w: matrix accepts paddleocr_gpu provider, scores and renders correctly."""

    def test_matrix_accepts_paddleocr_gpu_provider(self, tmp_path: Path):
        pdf = str(tmp_path / "doc.pdf")
        with patch.object(ocr_matrix, "run_paddleocr_evaluation", return_value=_paddle_gpu_result()):
            entries = run_matrix(
                pdf,
                providers=["paddleocr_gpu"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=30,
            )
        assert len(entries) == 1
        assert entries[0].provider == "paddleocr_gpu"

    def test_matrix_records_paddleocr_gpu_result_without_crashing(self, tmp_path: Path):
        pdf = str(tmp_path / "doc.pdf")
        with patch.object(ocr_matrix, "run_paddleocr_evaluation", return_value=_paddle_gpu_result(success=False, error="GPU error")):
            entries = run_matrix(
                pdf,
                providers=["paddleocr_gpu"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=30,
            )
        assert isinstance(entries[0], MatrixEntry)
        assert entries[0].success is False

    def test_matrix_scoring_works_for_paddleocr_gpu(self, tmp_path: Path):
        pdf = str(tmp_path / "doc.pdf")
        result = _paddle_gpu_result(
            extracted_fields={
                "vendor_invoice_no": "INV001",
                "vendor_invoice_date": "01-01-2026",
                "po_reference": "PO001",
            }
        )
        with patch.object(ocr_matrix, "run_paddleocr_evaluation", return_value=result):
            entries = run_matrix(
                pdf,
                providers=["paddleocr_gpu"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=30,
            )
        assert entries[0].score == 3

    def test_renderer_includes_paddleocr_gpu_provider(self, tmp_path: Path):
        pdf = str(tmp_path / "doc.pdf")
        with patch.object(ocr_matrix, "run_paddleocr_evaluation", return_value=_paddle_gpu_result()):
            entries = run_matrix(
                pdf,
                providers=["paddleocr_gpu"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=30,
            )
        report = render_matrix_report(entries, format="markdown")
        assert "paddleocr_gpu" in report

    def test_renderer_includes_duration_and_text_length(self, tmp_path: Path):
        pdf = str(tmp_path / "doc.pdf")
        with patch.object(ocr_matrix, "run_paddleocr_evaluation", return_value=_paddle_gpu_result(duration_ms=11154, raw_text_length=2897)):
            entries = run_matrix(
                pdf,
                providers=["paddleocr_gpu"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=30,
            )
        report = render_matrix_report(entries, format="markdown")
        assert "11154" in report
        assert "2897" in report

    def test_renderer_includes_extracted_fields(self, tmp_path: Path):
        pdf = str(tmp_path / "doc.pdf")
        result = _paddle_gpu_result(
            extracted_fields={
                "vendor_invoice_no": "INV001",
                "vendor_invoice_date": "01-01-2026",
                "po_reference": "PO001",
            }
        )
        with patch.object(ocr_matrix, "run_paddleocr_evaluation", return_value=result):
            entries = run_matrix(
                pdf,
                providers=["paddleocr_gpu"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=30,
            )
        report = render_matrix_report(entries, format="markdown")
        assert "INV001" in report

    def test_paddleocr_gpu_does_not_mutate_production(self, tmp_path: Path):
        pdf = str(tmp_path / "doc.pdf")
        with patch.object(ocr_matrix, "run_paddleocr_evaluation", return_value=_paddle_gpu_result()), \
             patch("app.services.extraction_service.extract_document") as mock_extract:
            run_matrix(
                pdf,
                providers=["paddleocr_gpu"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=30,
            )
        mock_extract.assert_not_called()

    def test_paddleocr_gpu_passes_device_gpu0_to_evaluation(self, tmp_path: Path):
        """Matrix must pass device='gpu:0' when provider key is paddleocr_gpu."""
        pdf = str(tmp_path / "doc.pdf")
        captured: list[dict] = []

        def spy(*a, **kw):
            captured.append(kw)
            return _paddle_gpu_result()

        with patch.object(ocr_matrix, "run_paddleocr_evaluation", side_effect=spy):
            run_matrix(
                pdf,
                providers=["paddleocr_gpu"],
                dpi_values=[150],
                expected=_EXPECTED,
                timeout_seconds=30,
            )
        assert captured[0].get("device") == "gpu:0"

