"""Phase 1xK-B: OCR auto-rotation unit tests.

Covers:
1. score_ocr_text returns higher score for text with more keywords
2. find_best_rotation_glm chooses the orientation with the highest score
3. find_best_rotation_glm falls back to rotation=0 when all probes fail
4. find_best_rotation_glm includes all required diagnostic fields
5. find_best_rotation_paddle chooses the orientation with the highest score
6. find_best_rotation_paddle falls back to rotation=0 when subprocess fails
7. find_best_rotation_paddle reports timeout_used=True on timeout
8. Original file path is not modified by any auto-rotation function
9. Auto-rotation disabled by default (OCR_AUTO_ROTATE_ENABLED=false)
10. render_pdf_pages_at_rotation produces PNG files and respects max_pages
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import fitz
import pytest

from app.services.extraction.ocr_auto_rotate import (
    AUTO_ROTATE_KEYWORDS,
    AUTO_ROTATE_ORIENTATIONS,
    find_best_rotation_glm,
    find_best_rotation_paddle,
    render_pdf_pages_at_rotation,
    score_ocr_text,
)


# ---------------------------------------------------------------------------
# score_ocr_text
# ---------------------------------------------------------------------------

def test_score_ocr_text_empty_returns_zero():
    assert score_ocr_text("") == 0.0
    assert score_ocr_text("   ") == 0.0


def test_score_ocr_text_keywords_increase_score():
    score_plain = score_ocr_text("some random text with no keywords here")
    score_with_kw = score_ocr_text("TAX INVOICE\nInvoice No: 12345\nTotal: 5000\nCGST: 450")
    assert score_with_kw > score_plain


def test_score_ocr_text_longer_text_scores_higher_than_short_when_same_keywords():
    short = "invoice no 1"
    long_text = "invoice no 1 " + "x" * 500
    assert score_ocr_text(long_text) > score_ocr_text(short)


def test_score_ocr_text_all_keywords_score_maximum_among_test_cases():
    all_kw_text = " ".join(AUTO_ROTATE_KEYWORDS)
    some_kw_text = "tax invoice total amount"
    assert score_ocr_text(all_kw_text) > score_ocr_text(some_kw_text)


# ---------------------------------------------------------------------------
# find_best_rotation_glm  (patch extract_text_with_ocr at its origin module)
# ---------------------------------------------------------------------------

def _make_glm_result(text: str):
    from app.services.extraction.glm_ocr_client import OcrResult
    return OcrResult(
        text=text,
        pages=[{"page_number": 1}],
        provider="glm_ocr",
        model="glm-ocr:latest",
        diagnostics={"ocr_duration_ms": 10},
    )


def test_find_best_rotation_glm_picks_highest_scoring_orientation():
    """Rotation 90 returns the richest text; should be chosen."""
    rotation_results = {
        0: _make_glm_result("some unrecognized text"),
        90: _make_glm_result("TAX INVOICE\nInvoice No: 100\nTotal: 5000\nGSTIN: 12345\nBill To: ABC Ltd"),
        180: _make_glm_result("garbage"),
        270: _make_glm_result(""),
    }

    def fake_extract(fp, *, max_pages, dpi, timeout_seconds, rotation_degrees=0):
        return rotation_results[rotation_degrees]

    with patch("app.services.extraction.glm_ocr_client.extract_text_with_ocr", side_effect=fake_extract):
        best_rotation, diag = find_best_rotation_glm(
            "dummy.pdf", max_pages=5, dpi=200, timeout_seconds=10
        )

    assert best_rotation == 90
    assert diag["selected_rotation_degrees"] == 90
    assert diag["candidate_scores"]["90"]["score"] > diag["candidate_scores"]["0"]["score"]
    assert diag["auto_rotation_enabled"] is True


def test_find_best_rotation_glm_falls_back_to_zero_when_all_fail():
    def raise_exc(fp, **kw):
        raise RuntimeError("network error")

    with patch("app.services.extraction.glm_ocr_client.extract_text_with_ocr", side_effect=raise_exc):
        best_rotation, diag = find_best_rotation_glm(
            "dummy.pdf", max_pages=5, dpi=200, timeout_seconds=10
        )

    assert best_rotation == 0
    assert diag["fallback_used"] is True
    assert "auto_rotate_probe_error" in diag
    for rot in AUTO_ROTATE_ORIENTATIONS:
        assert str(rot) in diag["candidate_scores"]
        assert "error" in diag["candidate_scores"][str(rot)]


def test_find_best_rotation_glm_diagnostics_include_required_fields():
    def trivial_result(fp, **kw):
        return _make_glm_result("invoice no total amount")

    with patch("app.services.extraction.glm_ocr_client.extract_text_with_ocr", side_effect=trivial_result):
        best_rotation, diag = find_best_rotation_glm(
            "dummy.pdf", max_pages=5, dpi=200, timeout_seconds=10
        )

    required = {
        "auto_rotation_enabled",
        "selected_rotation_degrees",
        "orientation_score",
        "candidate_scores",
        "provider",
        "fallback_used",
        "timeout_used",
        "auto_rotate_duration_ms",
    }
    for field in required:
        assert field in diag, f"Missing diagnostic field: {field}"
    for rot in AUTO_ROTATE_ORIENTATIONS:
        assert str(rot) in diag["candidate_scores"]


def test_find_best_rotation_glm_does_not_modify_original_file(tmp_path: Path):
    pdf_path = tmp_path / "original.pdf"
    doc = fitz.open()
    doc.new_page(width=400, height=600)
    doc.save(str(pdf_path))
    doc.close()
    original_bytes = pdf_path.read_bytes()
    original_mtime = pdf_path.stat().st_mtime

    def trivial_result(fp, **kw):
        return _make_glm_result("hello")

    with patch("app.services.extraction.glm_ocr_client.extract_text_with_ocr", side_effect=trivial_result):
        find_best_rotation_glm(str(pdf_path), max_pages=1, dpi=100, timeout_seconds=5)

    assert pdf_path.read_bytes() == original_bytes, "Original PDF bytes were modified"
    assert pdf_path.stat().st_mtime == original_mtime, "Original PDF mtime changed"


# ---------------------------------------------------------------------------
# find_best_rotation_paddle
# (patch _run_paddle_ocr_in_subprocess at its origin module)
# ---------------------------------------------------------------------------

_PADDLE_SUBPROCESS_PATH = (
    "app.services.extraction.ocr_providers.paddle_provider._run_paddle_ocr_in_subprocess"
)


def _make_subprocess_result(text: str = "", *, success: bool = True, error: str | None = None):
    return {
        "success": success and bool(text),
        "raw_text": text,
        "error": error,
        "duration_ms": 100,
    }


def test_find_best_rotation_paddle_picks_highest_scoring_orientation(tmp_path: Path):
    pdf_path = tmp_path / "scan.pdf"
    doc = fitz.open()
    doc.new_page(width=400, height=600)
    doc.save(str(pdf_path))
    doc.close()

    rotation_texts = {
        0: "random noise",
        90: "TAX INVOICE\nInvoice No: 999\nTotal: 12000\nGSTIN: 99ZZ\nBill To: Corp",
        180: "",
        270: "garbage",
    }

    def fake_subprocess(png_path: str, device, timeout):
        for rot in (0, 90, 180, 270):
            if f"rot{rot}" in png_path:
                return _make_subprocess_result(rotation_texts[rot])
        return _make_subprocess_result("")

    with patch(_PADDLE_SUBPROCESS_PATH, side_effect=fake_subprocess):
        best_rotation, diag = find_best_rotation_paddle(
            str(pdf_path), device=None, max_pages=1, dpi=72, timeout_seconds=10
        )

    assert best_rotation == 90
    assert diag["selected_rotation_degrees"] == 90
    assert diag["candidate_scores"]["90"]["score"] > diag["candidate_scores"]["0"]["score"]


def test_find_best_rotation_paddle_falls_back_to_zero_when_all_fail(tmp_path: Path):
    pdf_path = tmp_path / "scan.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()

    with patch(
        _PADDLE_SUBPROCESS_PATH,
        return_value={"success": False, "raw_text": "", "error": "GPU error", "duration_ms": 10},
    ):
        best_rotation, diag = find_best_rotation_paddle(
            str(pdf_path), device=None, max_pages=1, dpi=72, timeout_seconds=10
        )

    assert best_rotation == 0
    assert diag["fallback_used"] is True


def test_find_best_rotation_paddle_reports_timeout_used(tmp_path: Path):
    pdf_path = tmp_path / "scan.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()

    with patch(
        _PADDLE_SUBPROCESS_PATH,
        return_value={
            "success": False,
            "raw_text": "",
            "error": "PaddleOCR subprocess timed out after 10s",
            "duration_ms": 10010,
        },
    ):
        best_rotation, diag = find_best_rotation_paddle(
            str(pdf_path), device=None, max_pages=1, dpi=72, timeout_seconds=10
        )

    assert diag["timeout_used"] is True


def test_find_best_rotation_paddle_does_not_modify_original_file(tmp_path: Path):
    pdf_path = tmp_path / "original_scan.pdf"
    doc = fitz.open()
    doc.new_page(width=400, height=600)
    doc.save(str(pdf_path))
    doc.close()
    original_bytes = pdf_path.read_bytes()

    with patch(
        _PADDLE_SUBPROCESS_PATH,
        return_value={"success": True, "raw_text": "hello", "error": None, "duration_ms": 50},
    ):
        find_best_rotation_paddle(str(pdf_path), device=None, max_pages=1, dpi=72, timeout_seconds=10)

    assert pdf_path.read_bytes() == original_bytes, "Original PDF bytes were modified"


def test_find_best_rotation_paddle_diagnostics_include_required_fields(tmp_path: Path):
    pdf_path = tmp_path / "scan.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()

    with patch(
        _PADDLE_SUBPROCESS_PATH,
        return_value={"success": True, "raw_text": "invoice total", "error": None, "duration_ms": 50},
    ):
        best_rotation, diag = find_best_rotation_paddle(
            str(pdf_path), device=None, max_pages=1, dpi=72, timeout_seconds=10
        )

    required = {
        "auto_rotation_enabled",
        "selected_rotation_degrees",
        "orientation_score",
        "candidate_scores",
        "provider",
        "fallback_used",
        "timeout_used",
        "auto_rotate_duration_ms",
    }
    for field in required:
        assert field in diag, f"Missing diagnostic field: {field}"
    for rot in AUTO_ROTATE_ORIENTATIONS:
        assert str(rot) in diag["candidate_scores"]


# ---------------------------------------------------------------------------
# render_pdf_pages_at_rotation
# ---------------------------------------------------------------------------

def test_render_pdf_pages_at_rotation_produces_png_files(tmp_path: Path):
    pdf_path = tmp_path / "doc.pdf"
    doc = fitz.open()
    doc.new_page(width=400, height=600)
    doc.new_page(width=400, height=600)
    doc.save(str(pdf_path))
    doc.close()

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    paths = render_pdf_pages_at_rotation(str(pdf_path), rotation=90, dpi=72, max_pages=2, out_dir=str(out_dir))

    assert len(paths) == 2
    for p in paths:
        assert os.path.exists(p)
        assert p.endswith(".png")


def test_render_pdf_pages_at_rotation_respects_max_pages(tmp_path: Path):
    pdf_path = tmp_path / "doc.pdf"
    doc = fitz.open()
    for _ in range(5):
        doc.new_page()
    doc.save(str(pdf_path))
    doc.close()

    out_dir = tmp_path / "out2"
    out_dir.mkdir()
    paths = render_pdf_pages_at_rotation(str(pdf_path), rotation=0, dpi=72, max_pages=2, out_dir=str(out_dir))
    assert len(paths) == 2


def test_render_pdf_pages_at_rotation_returns_empty_on_bad_path(tmp_path: Path):
    out_dir = tmp_path / "out3"
    out_dir.mkdir()
    paths = render_pdf_pages_at_rotation("does_not_exist.pdf", rotation=0, dpi=72, max_pages=1, out_dir=str(out_dir))
    assert paths == []


# ---------------------------------------------------------------------------
# Config: auto-rotation off by default
# ---------------------------------------------------------------------------

def test_auto_rotate_disabled_by_default():
    from app.config import Settings
    s = Settings()
    assert s.ocr_auto_rotate_enabled is False


def test_auto_rotate_timeout_default():
    from app.config import Settings
    s = Settings()
    assert s.ocr_auto_rotate_timeout_seconds == 30
