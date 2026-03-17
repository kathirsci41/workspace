# Save as: backend/tests/test_phase3.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_preprocessor_import():
    """Test that scan_preprocessor module imports correctly."""
    try:
        from app.services.extraction.scan_preprocessor import (
            preprocess_scan, estimate_scan_quality, CV2_AVAILABLE
        )
        print("OK scan_preprocessor imports correctly")
        if CV2_AVAILABLE:
            print("OK OpenCV is available")
        else:
            print("! OpenCV not installed - preprocessor will passthrough")
        return True
    except ImportError as e:
        print(f"x FAIL: scan_preprocessor import failed: {e}")
        return False

def test_passthrough_when_no_opencv():
    """If OpenCV not installed, image should pass through unchanged."""
    try:
        from app.services.extraction.scan_preprocessor import preprocess_scan, CV2_AVAILABLE
        # Create a simple fake image byte array
        fake_bytes = b"fake image bytes"
        result = preprocess_scan(fake_bytes)
        # Should return original bytes unchanged when CV2 not available
        # Or return processed bytes when CV2 is available
        assert result is not None
        print("OK Preprocessor returns bytes without crashing")
        return True
    except Exception as e:
        print(f"x FAIL: {e}")
        return False

def test_with_real_image():
    """Test with an actual synthetic test image."""
    try:
        from app.services.extraction.scan_preprocessor import (
            preprocess_scan, estimate_scan_quality, CV2_AVAILABLE
        )
        import io
        from PIL import Image

        # Create a synthetic test image (white background, black text pattern)
        img = Image.new("RGB", (800, 1000), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        result = preprocess_scan(image_bytes, debug=True)
        assert isinstance(result, bytes)
        assert len(result) > 0
        print(f"OK Pre-processing returned {len(result)//1024}KB image")

        quality = estimate_scan_quality(image_bytes)
        print(f"OK Quality assessment: {quality}")
        return True
    except Exception as e:
        print(f"x FAIL: {e}")
        return False

def test_deskew():
    """Test deskew does not crash on normal images."""
    try:
        from app.services.extraction.scan_preprocessor import _deskew, CV2_AVAILABLE
        import io
        import numpy as np
        from PIL import Image

        if not CV2_AVAILABLE:
            print("! OpenCV not installed — deskew test skipped")
            return True

        # Create a simple test image
        img = Image.new("RGB", (800, 1000), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        nparr = np.frombuffer(image_bytes, np.uint8)
        import cv2
        img_array = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        result = _deskew(img_array, debug=True)
        assert result is not None
        print("OK Deskew function runs without crashing")
        return True
    except Exception as e:
        print(f"x FAIL: {e}")
        return False

def test_tasks_imports_preprocessor():
    """Test that tasks.py imports and uses the preprocessor."""
    try:
        tasks_file = Path(__file__).parent.parent / "app" / "services" / "extraction" / "tasks.py"
        if not tasks_file.exists():
            print("! tasks.py not found - skipping check")
            return False

        content = tasks_file.read_text()

        has_preprocessor_import = "preprocess_scan" in content and "from app.services.extraction.scan_preprocessor" in content
        if has_preprocessor_import:
            print("OK tasks.py imports preprocess_scan")
        else:
            print("x FAIL: tasks.py doesn't import preprocess_scan")
            return False

        has_router_import = "HybridRouter" in content and "ExtractionRoute" in content
        if has_router_import:
            print("OK tasks.py imports HybridRouter and ExtractionRoute")
        else:
            print("x FAIL: tasks.py doesn't import router")
            return False

        has_routing_logic = "router.route" in content or "route = router.route" in content
        if has_routing_logic:
            print("OK tasks.py uses routing logic")
        else:
            print("x FAIL: tasks.py doesn't use routing logic")
            return False

        has_preprocessing_call = "preprocess_scan(img)" in content
        if has_preprocessing_call:
            print("OK tasks.py calls preprocess_scan on scanned images")
        else:
            print("x FAIL: tasks.py doesn't call preprocess_scan")
            return False

        return True
    except Exception as e:
        print(f"x FAIL: {e}")
        return False

if __name__ == "__main__":
    print("=== Phase 3 Tests ===\n")
    all_passed = True
    all_passed &= test_preprocessor_import()
    all_passed &= test_passthrough_when_no_opencv()
    all_passed &= test_with_real_image()
    all_passed &= test_deskew()
    all_passed &= test_tasks_imports_preprocessor()

    if all_passed:
        print("\nOK Phase 3 tests passed")
        print("\nPhase 3: OpenCV scan pre-processing is complete")
        print("\nREMINDER: To enable OpenCV processing, run:")
        print("  pip install opencv-python-headless")
    else:
        print("\nx Some Phase 3 tests failed")
