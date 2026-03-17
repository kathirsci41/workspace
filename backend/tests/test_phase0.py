# Save as: backend/tests/test_phase0.py
# Run with: python backend/tests/test_phase0.py

import io
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.extraction.pdf_converter import PDFConverter

def test_no_resize_cap():
    """Confirm max_image_dim cap exists at 768px."""
    conv = PDFConverter(dpi=300, max_pages=10)
    assert hasattr(conv, 'max_image_dim'), \
        "FAIL: max_image_dim attribute missing"
    assert conv.max_image_dim == 768, \
        f"FAIL: max_image_dim={conv.max_image_dim}, expected 768"
    print(f"OK max_image_dim = {conv.max_image_dim}")

def test_dpi_default():
    """Confirm default DPI is 200."""
    conv = PDFConverter()
    assert conv.dpi == 200, f"FAIL: dpi={conv.dpi}, expected 200"
    print(f"OK Default DPI = {conv.dpi}")

def test_max_pages_default():
    """Confirm default max_pages is now 10."""
    conv = PDFConverter()
    assert conv.max_pages == 10, f"FAIL: max_pages={conv.max_pages}, expected 10"
    print(f"OK Default max_pages = {conv.max_pages}")

def test_convert_sample_pdf():
    """
    If you have a sample PDF, test full-resolution conversion.
    Place any invoice PDF at: backend/tests/samples/sample_invoice.pdf
    """
    sample = Path(__file__).parent / "samples" / "sample_invoice.pdf"
    if not sample.exists():
        print("! No sample PDF found - skipping live conversion test")
        print("  Place a sample PDF at backend/tests/samples/sample_invoice.pdf")
        return

    conv = PDFConverter(dpi=300, max_pages=10)
    images = conv.convert_to_images(str(sample))
    print(f"OK Converted {len(images)} pages")

    from PIL import Image
    for i, img_bytes in enumerate(images):
        img = Image.open(io.BytesIO(img_bytes))
        w, h = img.size
        assert max(w, h) > 800, \
            f"FAIL: Page {i+1} is {w}x{h} - still being downscaled"
        print(f"  Page {i+1}: {w}x{h}px - full resolution OK")

if __name__ == "__main__":
    print("=== Phase 0 Tests ===\n")
    test_no_resize_cap()
    test_dpi_default()
    test_max_pages_default()
    test_convert_sample_pdf()
    print("\nOK Phase 0 tests passed")
