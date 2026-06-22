"""OCR auto-rotation: probe 4 orientations and choose the best one.

Used as a pre-pass before the main OCR extraction when
OCR_AUTO_ROTATE_ENABLED=true. Does NOT modify the original PDF file.
Temporary page images (for PaddleOCR) are written to the system temp
directory and removed after scoring.
"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any


AUTO_ROTATE_ORIENTATIONS: tuple[int, ...] = (0, 90, 180, 270)

AUTO_ROTATE_KEYWORDS = (
    "tax invoice",
    "invoice no",
    "invoice date",
    "gstin",
    "purchase order",
    "po",
    "delivery challan",
    "total",
    "amount",
    "cgst",
    "sgst",
    "igst",
    "bill to",
    "ship to",
)


def score_ocr_text(text: str) -> float:
    """Score OCR text quality for orientation selection.

    Combines keyword hits (high weight) with useful text length (low weight).
    Higher score is better orientation.
    """
    if not text.strip():
        return 0.0
    text_lower = text.lower()
    keyword_hits = sum(1 for kw in AUTO_ROTATE_KEYWORDS if kw in text_lower)
    return keyword_hits * 100.0 + len(text.strip()) * 0.01


def find_best_rotation_glm(
    file_path: str,
    *,
    max_pages: int,
    dpi: int,
    timeout_seconds: int,
) -> tuple[int, dict[str, Any]]:
    """Probe 4 orientations using GLM OCR; return (best_rotation_degrees, diagnostics).

    Calls extract_text_with_ocr at each of 0/90/180/270 with rotation_degrees.
    Falls back to rotation=0 if all probes fail. Does not raise.
    """
    from app.services.extraction.glm_ocr_client import extract_text_with_ocr  # noqa: PLC0415

    started = time.perf_counter()
    candidate_scores: dict[str, Any] = {}
    best_rotation = 0
    best_score = -1.0
    first_error: str | None = None

    for rotation in AUTO_ROTATE_ORIENTATIONS:
        try:
            result = extract_text_with_ocr(
                file_path,
                max_pages=max_pages,
                dpi=dpi,
                timeout_seconds=timeout_seconds,
                rotation_degrees=rotation,
            )
            text = result.text.strip()
            score = score_ocr_text(text)
            candidate_scores[str(rotation)] = {
                "text_length": len(text),
                "score": round(score, 2),
            }
            if score > best_score:
                best_score = score
                best_rotation = rotation
        except Exception as exc:
            candidate_scores[str(rotation)] = {
                "text_length": 0,
                "score": 0.0,
                "error": str(exc)[:200],
            }
            if first_error is None:
                first_error = str(exc)[:200]

    diagnostics: dict[str, Any] = {
        "auto_rotation_enabled": True,
        "selected_rotation_degrees": best_rotation,
        "orientation_score": round(best_score, 2),
        "candidate_scores": candidate_scores,
        "provider": "glm_ocr",
        "fallback_used": best_score <= 0.0,
        "timeout_used": False,
        "auto_rotate_duration_ms": round((time.perf_counter() - started) * 1000),
    }
    if first_error:
        diagnostics["auto_rotate_probe_error"] = first_error

    return best_rotation, diagnostics


def render_pdf_pages_at_rotation(
    file_path: str,
    rotation: int,
    dpi: int,
    max_pages: int,
    out_dir: str,
) -> list[str]:
    """Render up to max_pages of a PDF at `rotation` degrees as PNG files.

    Returns list of temp PNG paths. Uses PyMuPDF (fitz). Never raises.
    """
    import fitz  # noqa: PLC0415

    png_paths: list[str] = []
    try:
        doc = fitz.open(file_path)
        n = min(max_pages, doc.page_count)
        for i in range(n):
            page = doc.load_page(i)
            matrix = fitz.Matrix(dpi / 72, dpi / 72).prerotate(rotation)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            out_path = str(Path(out_dir) / f"page_{i:03d}_rot{rotation}.png")
            pixmap.save(out_path)
            png_paths.append(out_path)
        doc.close()
    except Exception:
        pass
    return png_paths


def find_best_rotation_paddle(
    file_path: str,
    *,
    device: str | None,
    max_pages: int,
    dpi: int,
    timeout_seconds: int,
) -> tuple[int, dict[str, Any]]:
    """Probe 4 orientations using PaddleOCR; return (best_rotation_degrees, diagnostics).

    Renders page 0 of the PDF at each orientation as a temp PNG and runs
    PaddleOCR in a subprocess. Temp files are always cleaned up. Falls back
    to rotation=0 if all probes fail. Does not raise.
    """
    from app.services.extraction.ocr_providers.paddle_provider import (  # noqa: PLC0415
        _run_paddle_ocr_in_subprocess,
    )

    started = time.perf_counter()
    candidate_scores: dict[str, Any] = {}
    best_rotation = 0
    best_score = -1.0
    first_error: str | None = None
    timeout_used = False

    with tempfile.TemporaryDirectory() as tmpdir:
        for rotation in AUTO_ROTATE_ORIENTATIONS:
            png_paths = render_pdf_pages_at_rotation(file_path, rotation, dpi, 1, tmpdir)
            if not png_paths:
                candidate_scores[str(rotation)] = {
                    "text_length": 0,
                    "score": 0.0,
                    "error": "render failed",
                }
                if first_error is None:
                    first_error = "render failed"
                continue

            try:
                result_dict = _run_paddle_ocr_in_subprocess(png_paths[0], device, timeout_seconds)
                err = result_dict.get("error") or ""
                if "timed out" in err:
                    timeout_used = True
                raw_text = (result_dict.get("raw_text") or "").strip()
                score = score_ocr_text(raw_text)
                entry: dict[str, Any] = {
                    "text_length": len(raw_text),
                    "score": round(score, 2),
                    "success": result_dict.get("success", False),
                }
                if err:
                    entry["error"] = err[:200]
                candidate_scores[str(rotation)] = entry
                if score > best_score:
                    best_score = score
                    best_rotation = rotation
            except Exception as exc:
                candidate_scores[str(rotation)] = {
                    "text_length": 0,
                    "score": 0.0,
                    "error": str(exc)[:200],
                }
                if first_error is None:
                    first_error = str(exc)[:200]

    diagnostics: dict[str, Any] = {
        "auto_rotation_enabled": True,
        "selected_rotation_degrees": best_rotation,
        "orientation_score": round(best_score, 2),
        "candidate_scores": candidate_scores,
        "provider": "paddleocr",
        "fallback_used": best_score <= 0.0,
        "timeout_used": timeout_used,
        "auto_rotate_duration_ms": round((time.perf_counter() - started) * 1000),
    }
    if first_error:
        diagnostics["auto_rotate_probe_error"] = first_error

    return best_rotation, diagnostics


def run_paddle_full_page_at_rotation(
    file_path: str,
    rotation: int,
    *,
    device: str | None,
    max_pages: int,
    dpi: int,
    timeout_seconds: int,
) -> tuple[bool, str, str | None, int]:
    """Run PaddleOCR on all pages of a PDF at the given rotation.

    Renders pages as temp PNGs, runs PaddleOCR subprocess per page,
    concatenates results. Returns (success, raw_text, error, duration_ms).
    """
    from app.services.extraction.ocr_providers.paddle_provider import (  # noqa: PLC0415
        _run_paddle_ocr_in_subprocess,
    )

    started = time.perf_counter()
    page_texts: list[str] = []
    last_error: str | None = None

    with tempfile.TemporaryDirectory() as tmpdir:
        png_paths = render_pdf_pages_at_rotation(file_path, rotation, dpi, max_pages, tmpdir)
        if not png_paths:
            return (
                False,
                "",
                "Failed to render PDF pages for rotation",
                round((time.perf_counter() - started) * 1000),
            )
        for png_path in png_paths:
            result_dict = _run_paddle_ocr_in_subprocess(png_path, device, timeout_seconds)
            text = (result_dict.get("raw_text") or "").strip()
            if text:
                page_texts.append(text)
            if not result_dict.get("success"):
                last_error = result_dict.get("error")

    combined = "\n".join(page_texts)
    duration_ms = round((time.perf_counter() - started) * 1000)
    success = bool(combined.strip())
    return success, combined, last_error if not success else None, duration_ms
