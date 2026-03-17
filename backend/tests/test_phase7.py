# Save as: backend/tests/test_phase7.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_extraction_version_column_exists():
    """Test that extraction_version column exists in DocumentMetadata model."""
    try:
        from app.models.document_metadata import DocumentMetadata
        # Check if the class has the attribute
        assert hasattr(DocumentMetadata, 'extraction_version'), \
            "FAIL: extraction_version column not found in DocumentMetadata"
        print("OK extraction_version column exists in DocumentMetadata model")
        return True
    except Exception as e:
        print(f"x FAIL: {e}")
        return False

def test_field_confidences_column_exists():
    """Test that field_confidences column exists in DocumentMetadata model."""
    try:
        from app.models.document_metadata import DocumentMetadata
        assert hasattr(DocumentMetadata, 'field_confidences'), \
            "FAIL: field_confidences column not found in DocumentMetadata"
        print("OK field_confidences column exists in DocumentMetadata model")
        return True
    except Exception as e:
        print(f"x FAIL: {e}")
        return False

def test_extraction_correction_model_exists():
    """Test that ExtractionCorrection model exists."""
    try:
        from app.models import ExtractionCorrection
        assert ExtractionCorrection is not None
        print("OK ExtractionCorrection model exists")

        # Check key attributes
        required_attrs = [
            'document_id', 'field_name', 'original_value',
            'corrected_value', 'operator_id', 'corrected_at',
            'extraction_version', 'used_for_training'
        ]
        for attr in required_attrs:
            assert hasattr(ExtractionCorrection, attr), \
                f"FAIL: ExtractionCorrection missing attribute: {attr}"
        print(f"OK ExtractionCorrection has all required attributes: {required_attrs}")
        return True
    except ImportError as e:
        print(f"x FAIL: ExtractionCorrection not found: {e}")
        return False

def test_re_extract_uses_version_increment():
    """Test that re-extract endpoint uses version increment, not DELETE."""
    try:
        # Read the extraction.py file to check for version increment logic
        extraction_file = Path(__file__).parent.parent / "app" / "api" / "v1" / "extraction.py"
        if not extraction_file.exists():
            print("! extraction.py not found - skipping check")
            return False

        content = extraction_file.read_text()

        # Check that we have version increment logic
        has_version_increment = "extraction_version" in content and "new_version" in content
        # Check that we're NOT deleting the metadata record
        has_delete = "delete(DocumentMetadata)" in content

        if has_version_increment:
            print("OK re-extract endpoint uses version increment")
        else:
            print("x FAIL: re-extract endpoint missing version increment logic")
            return False

        if has_delete:
            print("x FAIL: re-extract endpoint still uses DELETE on DocumentMetadata")
            return False

        print("OK re-extract endpoint does NOT DELETE DocumentMetadata")
        return True

    except Exception as e:
        print(f"x FAIL: {e}")
        return False

def test_document_has_corrections_relationship():
    """Test that Document model has corrections relationship."""
    try:
        from app.models.document import Document
        assert hasattr(Document, 'corrections'), \
            "FAIL: Document model missing 'corrections' relationship"
        print("OK Document model has corrections relationship")
        return True
    except Exception as e:
        print(f"x FAIL: {e}")
        return False

if __name__ == "__main__":
    print("=== Phase 7 Tests ===\n")
    all_passed = True
    all_passed &= test_extraction_version_column_exists()
    all_passed &= test_field_confidences_column_exists()
    all_passed &= test_extraction_correction_model_exists()
    all_passed &= test_re_extract_uses_version_increment()
    all_passed &= test_document_has_corrections_relationship()

    if all_passed:
        print("\nOK Phase 7 tests passed")
        print("\nREMINDER: Run the migration to update the database:")
        print("  cd backend")
        print("  alembic upgrade head")
    else:
        print("\nx Some Phase 7 tests failed")
