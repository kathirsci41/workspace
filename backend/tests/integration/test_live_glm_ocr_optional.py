from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.services.extraction.glm_ocr_client import extract_text_with_ocr


pytestmark = pytest.mark.skipif(os.getenv("OCR_LIVE_TESTS", "").lower() not in {"1", "true", "yes"}, reason="Live glm-ocr smoke requires OCR_LIVE_TESTS=true and local Ollama model")


def test_live_glm_ocr_smoke(tmp_path: Path):
    import fitz

    pdf_path = tmp_path / "ocr-smoke.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Invoice No TEST-12345\nPO No PO-778899\nTotal 12345", fontsize=18)
    document.save(pdf_path)
    document.close()

    result = extract_text_with_ocr(str(pdf_path), max_pages=1, dpi=72, timeout_seconds=90)

    if not result.text.strip() and any(page.get("error") for page in result.pages):
        pytest.skip(f"Live glm-ocr provider returned an error: {result.pages[0].get('error')}")
    assert len(result.text.strip()) > 0
    assert result.provider == "glm_ocr"
    assert result.model == "glm-ocr:latest"
