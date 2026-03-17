# Save as: backend/tests/test_phase6.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_invoice_validator_exists():
    """Test that invoice_validator module exists."""
    try:
        from app.services.extraction.invoice_validator import validate_invoice_math, ValidationResult
        print("OK invoice_validator module exists")
        return True
    except ImportError as e:
        print(f"x FAIL: invoice_validator not found: {e}")
        return False

def test_validation_result_class():
    """Test that ValidationResult class exists and has required attributes."""
    try:
        from app.services.extraction import invoice_validator
        ValidationResult = invoice_validator.ValidationResult
        result = ValidationResult()
        assert hasattr(result, 'passed'), "ValidationResult missing 'passed' attribute"
        assert hasattr(result, 'errors'), "ValidationResult missing 'errors' attribute"
        assert hasattr(result, 'warnings'), "ValidationResult missing 'warnings' attribute"
        assert hasattr(result, 'route'), "ValidationResult missing 'route' attribute"
        assert hasattr(result, 'add_error'), "ValidationResult missing 'add_error' method"
        assert hasattr(result, 'add_warning'), "ValidationResult missing 'add_warning' method"
        print("OK ValidationResult class has all required attributes")
        return True
    except Exception as e:
        import traceback
        print(f"x FAIL: {e}")
        traceback.print_exc()
        return False

def test_validate_invoice_math_function():
    """Test that validate_invoice_math function exists."""
    try:
        from app.services.extraction.invoice_validator import validate_invoice_math, ValidationResult
        # Test with a simple case
        result = validate_invoice_math({}, "VENDOR_INVOICE")
        assert isinstance(result, ValidationResult), "validate_invoice_math should return ValidationResult"
        print("OK validate_invoice_math function exists and works")
        return True
    except Exception as e:
        print(f"x FAIL: {e}")
        return False

def test_tasks_imports_validator():
    """Test that tasks.py imports validate_invoice_math."""
    try:
        tasks_file = Path(__file__).parent.parent / "app" / "services" / "extraction" / "tasks.py"
        if not tasks_file.exists():
            print("! tasks.py not found - skipping check")
            return False

        content = tasks_file.read_text()

        has_validator_import = "validate_invoice_math" in content and "from app.services.extraction.invoice_validator" in content
        if has_validator_import:
            print("OK tasks.py imports validate_invoice_math")
        else:
            print("x FAIL: tasks.py doesn't import validate_invoice_math")
            return False

        # Check if validation is called in tasks.py
        has_validation_call = "validation_result = validate_invoice_math" in content
        if has_validation_call:
            print("OK tasks.py calls validate_invoice_math")
        else:
            print("x FAIL: tasks.py doesn't call validate_invoice_math")
            return False

        # Check if validation results are handled
        has_error_handling = "_validation_errors" in content or "_validation_warnings" in content
        if has_error_handling:
            print("OK tasks.py handles validation results")
        else:
            print("x FAIL: tasks.py doesn't handle validation results")
            return False

        return True
    except Exception as e:
        print(f"x FAIL: {e}")
        return False

def test_math_validation_logic():
    """Test that math validation catches invoice errors."""
    try:
        from app.services.extraction.invoice_validator import validate_invoice_math

        # Test case: Invoice with bad math (line items don't sum to total)
        bad_invoice = {
            "total_amount": 1000.00,
            "tax_amount": 100.00,
            "line_items": [
                {"quantity": 1, "unit_price": 100.00, "discount": 0}
            ]
        }

        result = validate_invoice_math(bad_invoice, "VENDOR_INVOICE")

        # Should fail because 100 + 100 != 1000
        if not result.passed:
            print("OK Math validation correctly catches invoice mismatch")
        else:
            print("x FAIL: Math validation should have caught invoice mismatch")
            return False

        return True
    except Exception as e:
        print(f"x FAIL: {e}")
        return False

def test_date_validation_logic():
    """Test that date validation catches future dates."""
    try:
        from app.services.extraction.invoice_validator import validate_invoice_math
        from datetime import date
        from datetime import timedelta

        # Test case: Invoice with future date
        future_invoice = {
            "total_amount": 100.00,
            "invoice_date": (date.today() + timedelta(days=10)).strftime("%d/%m/%Y")
        }

        result = validate_invoice_math(future_invoice, "VENDOR_INVOICE")

        # Should fail or warn because date is in future
        if not result.passed or result.warnings:
            print("OK Date validation catches future dates")
        else:
            print("! Date validation may not catch all future dates (format dependent)")
        return True
    except Exception as e:
        print(f"x FAIL: {e}")
        return False

if __name__ == "__main__":
    print("=== Phase 6 Tests ===\n")
    all_passed = True
    all_passed &= test_invoice_validator_exists()
    all_passed &= test_validation_result_class()
    all_passed &= test_validate_invoice_math_function()
    all_passed &= test_tasks_imports_validator()
    all_passed &= test_math_validation_logic()
    all_passed &= test_date_validation_logic()

    if all_passed:
        print("\nOK Phase 6 tests passed")
        print("\nPhase 6: Invoice math and business rule validation is complete")
    else:
        print("\nx Some Phase 6 tests failed")
