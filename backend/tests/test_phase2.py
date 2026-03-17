# Save as: backend/tests/test_phase2.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test the validation logic directly
from fastapi import HTTPException

def test_jpeg_rejected():
    try:
        from app.api.v1.purchase_orders import validate_upload_file
        try:
            validate_upload_file("invoice.jpg", "image/jpeg")
            print("x FAIL: JPEG was not rejected")
            return False
        except HTTPException as e:
            assert e.status_code == 415
            assert "JPEG" in e.detail
            print("OK JPEG correctly rejected with 415 and clear message")
            return True
    except ImportError:
        print("! validate_upload_file not found - add it to your upload router")
        return False

def test_jpeg_extension_rejected():
    try:
        from app.api.v1.purchase_orders import validate_upload_file
        try:
            validate_upload_file("document.jpeg", "image/jpeg")
            print("x FAIL: .jpeg extension was not rejected")
            return False
        except HTTPException as e:
            assert e.status_code == 415
            print("OK .jpeg extension correctly rejected")
            return True
    except ImportError:
        print("! validate_upload_file not found")
        return False

def test_pdf_accepted():
    try:
        from app.api.v1.purchase_orders import validate_upload_file
        try:
            validate_upload_file("invoice.pdf", "application/pdf")
            print("OK PDF accepted")
            return True
        except HTTPException:
            print("x FAIL: PDF was incorrectly rejected")
            return False
    except ImportError:
        print("! validate_upload_file not found")
        return False

def test_png_accepted():
    try:
        from app.api.v1.purchase_orders import validate_upload_file
        try:
            validate_upload_file("invoice.png", "image/png")
            print("OK PNG accepted")
            return True
        except HTTPException:
            print("x FAIL: PNG was incorrectly rejected")
            return False
    except ImportError:
        print("! validate_upload_file not found")
        return False

def test_tiff_accepted():
    try:
        from app.api.v1.purchase_orders import validate_upload_file
        try:
            validate_upload_file("scan.tiff", "image/tiff")
            print("OK TIFF accepted")
            return True
        except HTTPException:
            print("x FAIL: TIFF was incorrectly rejected")
            return False
    except ImportError:
        print("! validate_upload_file not found")
        return False

def test_unsupported_rejected():
    try:
        from app.api.v1.purchase_orders import validate_upload_file
        try:
            validate_upload_file("document.docx", "application/msword")
            print("x FAIL: .docx was not rejected")
            return False
        except HTTPException as e:
            assert e.status_code == 415
            print("OK Unsupported .docx correctly rejected")
            return True
    except ImportError:
        print("! validate_upload_file not found")
        return False

if __name__ == "__main__":
    print("=== Phase 2 Tests ===\n")
    all_passed = True
    all_passed &= test_jpeg_rejected()
    all_passed &= test_jpeg_extension_rejected()
    all_passed &= test_pdf_accepted()
    all_passed &= test_png_accepted()
    all_passed &= test_tiff_accepted()
    all_passed &= test_unsupported_rejected()
    if all_passed:
        print("\nOK Phase 2 tests passed")
    else:
        print("\nx Some Phase 2 tests failed")
