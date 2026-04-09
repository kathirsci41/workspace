"""Tests for PDFConverter (PDF → PNG conversion and page selection)."""
import io
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image

from app.services.extraction.pdf_converter import PDFConverter, PDFConversionError, PATCH_SIZE


# ── Helpers ──────────────────────────────────────────────────────────────

def make_fake_pixmap(width=100, height=100):
    """Create a mock pixmap that returns a real PNG bytes."""
    img = Image.new("RGB", (width, height), color=255)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    pix = MagicMock()
    pix.tobytes.return_value = png_bytes
    return pix


def make_mock_doc(page_count, page_width=100, page_height=100):
    """Create a mock fitz document."""
    doc = MagicMock()
    doc.page_count = page_count
    doc.__len__ = MagicMock(return_value=page_count)

    def load_page(i):
        page = MagicMock()
        page.get_pixmap.return_value = make_fake_pixmap(page_width, page_height)
        return page

    doc.load_page = load_page
    doc.close = MagicMock()
    return doc


# ── Constructor ──────────────────────────────────────────────────────────

class TestInit:
    def test_default_dpi(self):
        c = PDFConverter()
        assert c.dpi == 300

    def test_default_max_pages(self):
        c = PDFConverter()
        assert c.max_pages == 10

    def test_custom_values(self):
        c = PDFConverter(dpi=200, max_pages=5)
        assert c.dpi == 200
        assert c.max_pages == 5


# ── Page selection logic ─────────────────────────────────────────────────

class TestPageSelection:
    @patch("app.services.extraction.pdf_converter.fitz")
    def test_all_pages_when_under_max(self, mock_fitz):
        mock_fitz.open.return_value = make_mock_doc(5)
        mock_fitz.Matrix = MagicMock()

        converter = PDFConverter(max_pages=10)
        images = converter.convert_to_images("test.pdf")
        assert len(images) == 5

    @patch("app.services.extraction.pdf_converter.fitz")
    def test_all_pages_when_equal_max(self, mock_fitz):
        mock_fitz.open.return_value = make_mock_doc(10)
        mock_fitz.Matrix = MagicMock()

        converter = PDFConverter(max_pages=10)
        images = converter.convert_to_images("test.pdf")
        assert len(images) == 10

    @patch("app.services.extraction.pdf_converter.fitz")
    def test_first_half_last_half_when_over_max(self, mock_fitz):
        mock_fitz.open.return_value = make_mock_doc(20)
        mock_fitz.Matrix = MagicMock()

        converter = PDFConverter(max_pages=6)
        images = converter.convert_to_images("test.pdf")
        # 6 // 2 = 3 from first, 3 from last = 6 total
        assert len(images) == 6

    @patch("app.services.extraction.pdf_converter.fitz")
    def test_single_page_pdf(self, mock_fitz):
        mock_fitz.open.return_value = make_mock_doc(1)
        mock_fitz.Matrix = MagicMock()

        converter = PDFConverter()
        images = converter.convert_to_images("test.pdf")
        assert len(images) == 1


# ── Error handling ───────────────────────────────────────────────────────

class TestErrors:
    @patch("app.services.extraction.pdf_converter.fitz")
    def test_cannot_open_pdf(self, mock_fitz):
        mock_fitz.open.side_effect = Exception("corrupt file")

        converter = PDFConverter()
        with pytest.raises(PDFConversionError, match="Cannot open PDF"):
            converter.convert_to_images("bad.pdf")

    @patch("app.services.extraction.pdf_converter.fitz")
    def test_zero_page_pdf(self, mock_fitz):
        mock_fitz.open.return_value = make_mock_doc(0)

        converter = PDFConverter()
        with pytest.raises(PDFConversionError, match="no pages"):
            converter.convert_to_images("empty.pdf")

    @patch("app.services.extraction.pdf_converter.fitz")
    def test_all_pages_fail_conversion(self, mock_fitz):
        doc = MagicMock()
        doc.page_count = 2
        page = MagicMock()
        page.get_pixmap.side_effect = Exception("render fail")
        doc.load_page.return_value = page
        doc.close = MagicMock()
        mock_fitz.open.return_value = doc
        mock_fitz.Matrix = MagicMock()

        converter = PDFConverter()
        with pytest.raises(PDFConversionError, match="No pages could be converted"):
            converter.convert_to_images("fail.pdf")


# ── Image resizing ───────────────────────────────────────────────────────

class TestImageResizing:
    @patch("app.services.extraction.pdf_converter.fitz")
    def test_small_images_returned(self, mock_fitz):
        mock_fitz.open.return_value = make_mock_doc(1, page_width=100, page_height=100)
        mock_fitz.Matrix = MagicMock()

        converter = PDFConverter()
        images = converter.convert_to_images("test.pdf")
        assert len(images) == 1
        assert images[0][:4] == b"\x89PNG"

    @patch("app.services.extraction.pdf_converter.fitz")
    def test_large_images_returned(self, mock_fitz):
        mock_fitz.open.return_value = make_mock_doc(1, page_width=2000, page_height=1500)
        mock_fitz.Matrix = MagicMock()

        converter = PDFConverter()
        images = converter.convert_to_images("test.pdf")
        assert len(images) == 1
        assert images[0][:4] == b"\x89PNG"


# ── get_page_count ───────────────────────────────────────────────────────

class TestGetPageCount:
    @patch("app.services.extraction.pdf_converter.fitz")
    def test_returns_page_count(self, mock_fitz):
        doc = MagicMock()
        doc.page_count = 7
        doc.close = MagicMock()
        mock_fitz.open.return_value = doc

        converter = PDFConverter()
        assert converter.get_page_count("test.pdf") == 7

    @patch("app.services.extraction.pdf_converter.fitz")
    def test_raises_on_error(self, mock_fitz):
        mock_fitz.open.side_effect = Exception("bad file")

        converter = PDFConverter()
        with pytest.raises(PDFConversionError, match="Cannot read PDF"):
            converter.get_page_count("bad.pdf")


# ── Output format ────────────────────────────────────────────────────────

class TestOutputFormat:
    @patch("app.services.extraction.pdf_converter.fitz")
    def test_output_is_list_of_bytes(self, mock_fitz):
        mock_fitz.open.return_value = make_mock_doc(2)
        mock_fitz.Matrix = MagicMock()

        converter = PDFConverter()
        images = converter.convert_to_images("test.pdf")
        assert isinstance(images, list)
        for img_bytes in images:
            assert isinstance(img_bytes, bytes)

    @patch("app.services.extraction.pdf_converter.fitz")
    def test_output_is_valid_png(self, mock_fitz):
        mock_fitz.open.return_value = make_mock_doc(1)
        mock_fitz.Matrix = MagicMock()

        converter = PDFConverter()
        images = converter.convert_to_images("test.pdf")
        # PNG magic bytes
        assert images[0][:4] == b"\x89PNG"


# ── PATCH_SIZE constant ──────────────────────────────────────────────────

class TestPatchSizeConstant:
    def test_patch_size_is_14(self):
        assert PATCH_SIZE == 14


# ── Patch-size dimension alignment ───────────────────────────────────────

class TestPatchSizeAlignment:
    """Verify images are snapped to multiples of PATCH_SIZE=14."""

    @patch("app.services.extraction.pdf_converter.fitz")
    def test_unaligned_dims_snapped_down(self, mock_fitz):
        """543x768 → 532x756 (nearest multiples of 14 below)."""
        mock_fitz.open.return_value = make_mock_doc(1, page_width=543, page_height=768)
        mock_fitz.Matrix = MagicMock()

        converter = PDFConverter()
        images = converter.convert_to_images("test.pdf")
        img = Image.open(io.BytesIO(images[0]))
        w, h = img.size
        assert w % PATCH_SIZE == 0, f"width {w} not aligned to {PATCH_SIZE}"
        assert h % PATCH_SIZE == 0, f"height {h} not aligned to {PATCH_SIZE}"

    @patch("app.services.extraction.pdf_converter.fitz")
    def test_already_aligned_dims_unchanged(self, mock_fitz):
        """560x784 — already multiples of 14 → no resize needed."""
        mock_fitz.open.return_value = make_mock_doc(1, page_width=560, page_height=784)
        mock_fitz.Matrix = MagicMock()

        converter = PDFConverter()
        images = converter.convert_to_images("test.pdf")
        img = Image.open(io.BytesIO(images[0]))
        assert img.size == (560, 784)

    @patch("app.services.extraction.pdf_converter.fitz")
    def test_large_image_patch_aligned(self, mock_fitz):
        """Large image dimensions are snapped to patch grid."""
        mock_fitz.open.return_value = make_mock_doc(1, page_width=2000, page_height=1500)
        mock_fitz.Matrix = MagicMock()

        converter = PDFConverter()
        images = converter.convert_to_images("test.pdf")
        img = Image.open(io.BytesIO(images[0]))
        w, h = img.size
        assert w % PATCH_SIZE == 0
        assert h % PATCH_SIZE == 0

    @patch("app.services.extraction.pdf_converter.fitz")
    def test_small_unaligned_image_gets_aligned(self, mock_fitz):
        """Small image (< max_dim) but unaligned → still snapped."""
        mock_fitz.open.return_value = make_mock_doc(1, page_width=99, page_height=101)
        mock_fitz.Matrix = MagicMock()

        converter = PDFConverter()
        images = converter.convert_to_images("test.pdf")
        img = Image.open(io.BytesIO(images[0]))
        w, h = img.size
        assert w % PATCH_SIZE == 0
        assert h % PATCH_SIZE == 0

    @patch("app.services.extraction.pdf_converter.fitz")
    def test_specific_snap_values(self, mock_fitz):
        """Verify exact snap math: 543 → 532 (38*14), 768 → 756 (54*14)."""
        mock_fitz.open.return_value = make_mock_doc(1, page_width=543, page_height=768)
        mock_fitz.Matrix = MagicMock()

        converter = PDFConverter()
        images = converter.convert_to_images("test.pdf")
        img = Image.open(io.BytesIO(images[0]))
        assert img.size == (532, 756)

    @patch("app.services.extraction.pdf_converter.fitz")
    def test_width_aligned_height_not(self, mock_fitz):
        """Only height needs alignment."""
        mock_fitz.open.return_value = make_mock_doc(1, page_width=140, page_height=145)
        mock_fitz.Matrix = MagicMock()

        converter = PDFConverter()
        images = converter.convert_to_images("test.pdf")
        img = Image.open(io.BytesIO(images[0]))
        w, h = img.size
        assert w % PATCH_SIZE == 0
        assert h % PATCH_SIZE == 0
        assert w == 140  # already aligned
        assert h == 140  # 145 → 140
