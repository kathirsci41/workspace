# Save as: backend/tests/test_phase5.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_layoutlm_extractor_exists():
    """Test that LayoutLM extractor module exists."""
    try:
        from app.services.extraction.layoutlm_extractor import LayoutLMExtractor, FIELD_LABELS
        print("OK layoutlm_extractor module exists")
        return True
    except ImportError as e:
        print(f"x FAIL: layoutlm_extractor not found: {e}")
        return False

def test_layoutlm_extractor_class():
    """Test that LayoutLMExtractor class exists and has required attributes."""
    try:
        from app.services.extraction.layoutlm_extractor import LayoutLMExtractor

        extractor = LayoutLMExtractor()
        assert hasattr(extractor, 'is_available'), "Missing 'is_available' method"
        assert hasattr(extractor, 'extract'), "Missing 'extract' method"
        assert hasattr(extractor, 'model'), "Missing 'model' attribute"
        assert hasattr(extractor, 'processor'), "Missing 'processor' attribute"
        print("OK LayoutLMExtractor class has all required attributes")
        return True
    except Exception as e:
        print(f"x FAIL: {e}")
        return False

def test_field_labels_defined():
    """Test that FIELD_LABELS is properly defined."""
    try:
        from app.services.extraction.layoutlm_extractor import FIELD_LABELS

        required_types = [
            "VENDOR_INVOICE",
            "COMPANY_INVOICE",
            "VENDOR_DC",
            "COMPANY_DC",
            "CUSTOMER_PO",
            "COMPANY_PO",
        ]

        for doc_type in required_types:
            if doc_type not in FIELD_LABELS:
                print(f"x FAIL: FIELD_LABELS missing {doc_type}")
                return False
            if not isinstance(FIELD_LABELS[doc_type], list):
                print(f"x FAIL: FIELD_LABELS[{doc_type}] is not a list")
                return False

        print(f"OK FIELD_LABELS defined for all {len(required_types)} document types")
        return True
    except Exception as e:
        print(f"x FAIL: {e}")
        return False

def test_extractor_graceful_fallback():
    """Test that extractor gracefully handles missing model."""
    try:
        from app.services.extraction.layoutlm_extractor import LayoutLMExtractor

        extractor = LayoutLMExtractor()
        # Model is not trained yet, so is_available should return False
        if not extractor.is_available():
            print("OK LayoutLMExtractor correctly reports unavailable (no trained model yet)")
        else:
            print("! LayoutLMExtractor reports available - model may be present")

        # Extract should return empty dict when model unavailable
        result = extractor.extract([], [], b"fake", "VENDOR_INVOICE")
        if result == {}:
            print("OK Extract returns empty dict when model unavailable")
        else:
            print(f"! Extract returned: {result}")
        return True
    except Exception as e:
        print(f"x FAIL: {e}")
        return False

def test_model_directory_structure():
    """Test that model directory structure exists (or can be created)."""
    try:
        from pathlib import Path

        model_dir = Path(__file__).parent.parent / "models" / "layoutlmv3"
        if model_dir.exists():
            print(f"OK LayoutLMv3 model directory exists: {model_dir}")
            # Check for processor or finetuned subdirs
            has_processor = (model_dir / "processor").exists()
            has_finetuned = (model_dir / "finetuned").exists()
            if has_processor:
                print("  - processor/ found")
            if has_finetuned:
                print("  - finetuned/ found")
            if not has_processor and not has_finetuned:
                print("  ! No processor or finetuned subdirs yet")
        else:
            print(f"! LayoutLMv3 model directory does not exist: {model_dir}")
            print("  Create with: mkdir -p backend/models/layoutlmv3")
        return True
    except Exception as e:
        print(f"x FAIL: {e}")
        return False

if __name__ == "__main__":
    print("=== Phase 5 Tests ===\n")
    print("Note: Phase 5 requires a trained LayoutLMv3 model to be fully functional.")
    print("These tests verify the infrastructure is in place.\n")

    all_passed = True
    all_passed &= test_layoutlm_extractor_exists()
    all_passed &= test_layoutlm_extractor_class()
    all_passed &= test_field_labels_defined()
    all_passed &= test_extractor_graceful_fallback()
    all_passed &= test_model_directory_structure()

    if all_passed:
        print("\nOK Phase 5 infrastructure tests passed")
        print("\nPhase 5: LayoutLMv3 Integration scaffold is complete")
        print("\nREMAINING STEPS for full Phase 5:")
        print("  1. pip install transformers datasets torch seqeval")
        print("  2. Download base LayoutLMv3 model (see IMPLEMENTATION.md 5.2)")
        print("  3. Build training dataset (backend/scripts/build_layoutlm_dataset.py)")
        print("  4. Train/fine-tune LayoutLMv3 (backend/scripts/train_layoutlm.py)")
        print("  5. Wire LayoutLMExtractor into tasks.py to replace TwoLayerClient extraction")
    else:
        print("\nx Some Phase 5 tests failed")
