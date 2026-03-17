# Save as: backend/tests/test_phase8.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_correction_item_schema_exists():
    """Test that CorrectionItem schema exists."""
    try:
        from app.api.v1.extraction import CorrectionItem
        print("OK CorrectionItem schema exists")
        return True
    except ImportError as e:
        print(f"x FAIL: CorrectionItem not found: {e}")
        return False

def test_corrections_endpoint_exists():
    """Test that corrections endpoint exists in extraction API."""
    try:
        from app.api.v1 import extraction
        # Check if the router has the corrections route
        route_exists = False
        for route in extraction.router.routes:
            if hasattr(route, 'path') and '/corrections' in route.path:
                route_exists = True
                break

        if route_exists:
            print("OK POST /corrections endpoint exists in extraction router")
            return True
        else:
            print("x FAIL: POST /corrections endpoint not found")
            return False
    except Exception as e:
        print(f"x FAIL: {e}")
        return False

def test_extraction_correction_importable():
    """Test that ExtractionCorrection model is importable."""
    try:
        from app.models import ExtractionCorrection
        assert ExtractionCorrection is not None
        print("OK ExtractionCorrection model is importable")
        return True
    except Exception as e:
        print(f"x FAIL: {e}")
        return False

def test_endpoint_uses_extraction_correction():
    """Test that the endpoint uses ExtractionCorrection model."""
    try:
        extraction_file = Path(__file__).parent.parent / "app" / "api" / "v1" / "extraction.py"
        if not extraction_file.exists():
            print("! extraction.py not found - skipping check")
            return False

        content = extraction_file.read_text()

        # Check that the endpoint creates ExtractionCorrection records
        has_correction_model = "ExtractionCorrection(" in content
        has_endpoint_logic = "save_corrections" in content and "@router.post" in content

        if has_endpoint_logic:
            print("OK save_corrections endpoint exists")
        else:
            print("x FAIL: save_corrections endpoint not found")
            return False

        if has_correction_model:
            print("OK Endpoint uses ExtractionCorrection model")
        else:
            print("x FAIL: Endpoint doesn't use ExtractionCorrection model")
            return False

        return True
    except Exception as e:
        print(f"x FAIL: {e}")
        return False

if __name__ == "__main__":
    print("=== Phase 8 Tests ===\n")
    all_passed = True
    all_passed &= test_correction_item_schema_exists()
    all_passed &= test_corrections_endpoint_exists()
    all_passed &= test_extraction_correction_importable()
    all_passed &= test_endpoint_uses_extraction_correction()

    if all_passed:
        print("\nOK Phase 8 tests passed")
        print("\nREMINDER: Run the migration to update the database:")
        print("  cd backend")
        print("  alembic upgrade head")
    else:
        print("\nx Some Phase 8 tests failed")
