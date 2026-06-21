"""
LiteParse digital text + bbox extractor.
Runs alongside PyMuPDF — does NOT replace OCR providers.
For digital PDFs only (ocr_enabled=False).
Scanned docs: returns empty result, existing OCR path handles them.

LiteParse: https://github.com/run-llama/liteparse (Apache 2.0, PDFium-based)
Benchmark: 50-111% more text than PyMuPDF; 222-242 bboxes on our fixtures.
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from liteparse import LiteParse, ParseError
    _LITEPARSE_AVAILABLE = True
except ImportError:
    _LITEPARSE_AVAILABLE = False
    logger.warning("liteparse not installed — bbox extraction disabled. pip install liteparse")


def _is_available() -> bool:
    return _LITEPARSE_AVAILABLE


def extract_bboxes(pdf_path: str) -> dict[str, Any]:
    """
    Extract text items with bounding boxes from a digital PDF.

    Returns:
        {
            "bboxes": list[{page, text, x, y, w, h}],
            "text": str,        # full concatenated text
            "pages": int,
            "is_digital": bool, # False = scanned, skip bbox extraction
            "error": str | None,
        }

    Safe: never raises. Returns {"bboxes": [], "is_digital": False} on any failure.
    """
    empty = {"bboxes": [], "text": "", "pages": 0, "is_digital": False, "error": None}

    if not _is_available():
        return {**empty, "error": "liteparse not installed"}

    try:
        # ocr_enabled=False: digital text only — no Tesseract/PaddleOCR needed.
        # Tesseract offline: set TESSDATA_PREFIX env var to dir with eng.traineddata.
        parser = LiteParse(ocr_enabled=False)
        result = parser.parse(pdf_path)

        bboxes: list[dict] = []
        for page in result.pages:
            for item in page.text_items:
                bboxes.append({
                    "page": page.page_num,
                    "text": item.text,
                    "x": round(item.x, 1),
                    "y": round(item.y, 1),
                    "w": round(item.width, 1),
                    "h": round(item.height, 1),
                })

        is_digital = len(result.text.strip()) > 30
        return {
            "bboxes": bboxes,
            "text": result.text,
            "pages": len(result.pages),
            "is_digital": is_digital,
            "error": None,
        }

    except ParseError as exc:
        logger.warning("LiteParse parse error on %s: %s", pdf_path, exc)
        return {**empty, "error": str(exc)}
    except Exception as exc:
        logger.warning("LiteParse unexpected error on %s: %s", pdf_path, exc)
        return {**empty, "error": str(exc)}


def extract_bboxes_from_bytes(pdf_bytes: bytes) -> dict[str, Any]:
    """Convenience wrapper — writes bytes to temp file, calls extract_bboxes."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    try:
        return extract_bboxes(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
