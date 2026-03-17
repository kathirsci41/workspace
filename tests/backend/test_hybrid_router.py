"""
Unit tests for HybridRouter — PDF routing logic.

Covers:
  - Image files always route to SCANNED
  - Unknown formats route to SCANNED (safe default)
  - PDFs route based on DigitalExtractor.is_digital_pdf result
  - ExtractionRoute enum values
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))

import pytest
from unittest.mock import patch, MagicMock
from app.services.extraction.hybrid_router import HybridRouter, ExtractionRoute


def make_router():
    return HybridRouter(digital_threshold=50)


# ── Image files ───────────────────────────────────────────────────────────────

class TestImageFiles:

    @pytest.mark.parametrize("ext", [".png", ".tiff", ".tif", ".jpg", ".jpeg"])
    def test_image_always_scanned(self, ext, tmp_path):
        f = tmp_path / f"doc{ext}"
        f.write_bytes(b"fake image content")
        router = make_router()
        assert router.route(str(f)) == ExtractionRoute.SCANNED

    @pytest.mark.parametrize("ext", [".PNG", ".TIFF", ".JPG"])
    def test_uppercase_image_ext_scanned(self, ext, tmp_path):
        f = tmp_path / f"doc{ext}"
        f.write_bytes(b"fake image content")
        router = make_router()
        assert router.route(str(f)) == ExtractionRoute.SCANNED


# ── Unknown file formats ──────────────────────────────────────────────────────

class TestUnknownFormats:

    @pytest.mark.parametrize("ext", [".docx", ".xlsx", ".txt", ".xml", ""])
    def test_unknown_format_defaults_to_scanned(self, ext, tmp_path):
        f = tmp_path / f"doc{ext}"
        f.write_bytes(b"some content")
        router = make_router()
        assert router.route(str(f)) == ExtractionRoute.SCANNED


# ── PDF routing ───────────────────────────────────────────────────────────────

class TestPdfRouting:

    def test_digital_pdf_routes_to_digital(self, tmp_path):
        f = tmp_path / "invoice.pdf"
        f.write_bytes(b"%PDF-1.4 content")
        router = make_router()
        with patch.object(router.extractor, 'is_digital_pdf', return_value=True):
            assert router.route(str(f)) == ExtractionRoute.DIGITAL

    def test_scanned_pdf_routes_to_scanned(self, tmp_path):
        f = tmp_path / "scan.pdf"
        f.write_bytes(b"%PDF-1.4 content")
        router = make_router()
        with patch.object(router.extractor, 'is_digital_pdf', return_value=False):
            assert router.route(str(f)) == ExtractionRoute.SCANNED

    def test_uppercase_pdf_ext_handled(self, tmp_path):
        f = tmp_path / "invoice.PDF"
        f.write_bytes(b"%PDF-1.4 content")
        router = make_router()
        with patch.object(router.extractor, 'is_digital_pdf', return_value=True):
            assert router.route(str(f)) == ExtractionRoute.DIGITAL


# ── ExtractionRoute enum ──────────────────────────────────────────────────────

class TestExtractionRouteEnum:

    def test_digital_value(self):
        assert ExtractionRoute.DIGITAL == "digital"

    def test_scanned_value(self):
        assert ExtractionRoute.SCANNED == "scanned"

    def test_is_string(self):
        assert isinstance(ExtractionRoute.DIGITAL, str)
        assert isinstance(ExtractionRoute.SCANNED, str)
