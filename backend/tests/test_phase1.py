# Save as: backend/tests/test_phase1.py
# Run with: python backend/tests/test_phase1.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.extraction.hybrid_router import HybridRouter, ExtractionRoute
from app.services.extraction.digital_extractor import DigitalExtractor

def test_router_exists():
    router = HybridRouter()
    assert router is not None
    print("OK HybridRouter instantiated")

def test_digital_extractor_exists():
    ext = DigitalExtractor()
    assert ext is not None
    print("OK DigitalExtractor instantiated")

def test_image_routes_to_scanned():
    router = HybridRouter()
    # Image files must always go to scanned route
    assert router.route("test.png") == ExtractionRoute.SCANNED
    assert router.route("test.tiff") == ExtractionRoute.SCANNED
    print("OK Image files correctly routed to SCANNED")

def test_jpeg_routes_to_scanned():
    router = HybridRouter()
    assert router.route("test.jpg") == ExtractionRoute.SCANNED
    assert router.route("test.jpeg") == ExtractionRoute.SCANNED
    print("OK JPEG files correctly routed to SCANNED")

def test_with_sample_pdfs():
    """
    Place test files in backend/tests/samples/:
      digital_invoice.pdf  - machine-generated (from Tally/SAP)
      scanned_invoice.pdf  - photographed/scanned physical document
    """
    samples = Path(__file__).parent / "samples"
    router = HybridRouter()
    extractor = DigitalExtractor()

    digital = samples / "digital_invoice.pdf"
    scanned = samples / "scanned_invoice.pdf"

    if digital.exists():
        route = router.route(str(digital))
        assert route == ExtractionRoute.DIGITAL, f"Expected DIGITAL, got {route}"
        print(f"OK Digital PDF routed correctly: {route}")

        result = extractor.extract(str(digital))
        assert result.is_digital
        assert len(result.word_blocks) > 0
        print(f"  Extracted {len(result.word_blocks)} words from digital PDF")

        lm_input = result.to_layoutlm_input()
        assert len(lm_input["words"]) == len(lm_input["boxes"])
        print(f"  LayoutLM input: {len(lm_input['words'])} tokens with boxes OK")
    else:
        print("! No digital_invoice.pdf sample - add one for full test")

    if scanned.exists():
        route = router.route(str(scanned))
        assert route == ExtractionRoute.SCANNED, f"Expected SCANNED, got {route}"
        print(f"OK Scanned PDF routed correctly: {route}")
    else:
        print("! No scanned_invoice.pdf sample - add one for full test")

if __name__ == "__main__":
    print("=== Phase 1 Tests ===\n")
    test_router_exists()
    test_digital_extractor_exists()
    test_image_routes_to_scanned()
    test_jpeg_routes_to_scanned()
    test_with_sample_pdfs()
    print("\nOK Phase 1 tests passed")
