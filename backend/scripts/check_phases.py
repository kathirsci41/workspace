#!/usr/bin/env python3
"""
DocPlatform V3 — Pipeline Phase Checker
Run from project root: python backend/scripts/check_phases.py
"""

import os
import re
import sys
import json
import subprocess
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent  # backend/
APP  = ROOT / "app"
EXT  = APP / "services" / "extraction"

RESET  = "\033[0m"
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"

def ok(msg):    print(f"  {GREEN}#{RESET} {msg}")
def fail(msg):  print(f"  {RED}x{RESET} {msg}")
def warn(msg):  print(f"  {YELLOW}!{RESET} {msg}")
def info(msg):  print(f"  {CYAN}~{RESET} {msg}")
def header(msg):print(f"\n{BOLD}{msg}{RESET}")

results = {}

# ─────────────────────────────────────────────────────────────
# PHASE 0: Critical config fixes
# ─────────────────────────────────────────────────────────────
def check_phase0():
    header("PHASE 0 - Critical Config Fixes (target: 35 min)")
    passed = 0
    total  = 3

    # Check 1: 768px cap removed
    conv_file = EXT / "pdf_converter.py"
    if conv_file.exists():
        src = conv_file.read_text()
        if "MAX_IMAGE_DIM = 768" in src:
            fail("768px cap still present in pdf_converter.py - KILLS accuracy")
            info("Fix: delete lines with MAX_IMAGE_DIM = 768 and img.thumbnail()")
        elif "img.thumbnail" in src:
            fail("img.thumbnail() resize block still present")
            info("Fix: remove the entire resize block (keep PATCH_SIZE snapping)")
        else:
            ok("768px cap removed - full resolution preserved")
            passed += 1
    else:
        fail(f"pdf_converter.py not found at {conv_file}")

    # Check 2: DPI >= 300
    env_file = ROOT / ".env"
    dpi_ok = False
    pages_ok = False
    if env_file.exists():
        env_text = env_file.read_text()
        dpi_match = re.search(r"OCR_PDF_DPI\s*=\s*(\d+)", env_text)
        pages_match = re.search(r"OCR_MAX_PAGES\s*=\s*(\d+)", env_text)
        if dpi_match:
            dpi = int(dpi_match.group(1))
            if dpi >= 300:
                ok(f"OCR_PDF_DPI = {dpi} #")
                dpi_ok = True
            else:
                fail(f"OCR_PDF_DPI = {dpi} - must be >= 300")
                info("Fix: set OCR_PDF_DPI=300 in backend/.env")
        else:
            warn("OCR_PDF_DPI not found in .env - checking config.py default")
        if pages_match:
            pages = int(pages_match.group(1))
            if pages >= 10:
                ok(f"OCR_MAX_PAGES = {pages} #")
                pages_ok = True
            else:
                fail(f"OCR_MAX_PAGES = {pages} - only first {pages} page(s) processed")
                info("Fix: set OCR_MAX_PAGES=10 in backend/.env")
        else:
            warn("OCR_MAX_PAGES not found in .env")
    else:
        warn(".env not found - checking config.py defaults")

    if dpi_ok:
        passed += 1
    if pages_ok:
        passed += 1

    results["phase0"] = passed == total
    print(f"  Phase 0: {passed}/{total} checks passed")
    return passed == total


# ─────────────────────────────────────────────────────────────
# PHASE 1: Hybrid Router + Digital Fast Path
# ─────────────────────────────────────────────────────────────
def check_phase1():
    header("PHASE 1 - Hybrid Router + Digital Fast Path")
    passed = 0
    total  = 4

    # Check: hybrid_router.py exists
    router_file = EXT / "hybrid_router.py"
    if router_file.exists():
        ok("hybrid_router.py exists")
        passed += 1
        src = router_file.read_text()
        if "detect_and_route" in src or "is_digital" in src:
            ok("Router detection logic present")
            passed += 1
        else:
            fail("Router missing detect_and_route / is_digital function")
    else:
        fail("hybrid_router.py not found")
        info("Fix: create backend/app/services/extraction/hybrid_router.py (see Phase 1)")

    # Check: digital_extractor.py exists
    digital_file = EXT / "digital_extractor.py"
    if digital_file.exists():
        ok("digital_extractor.py exists")
        passed += 1
        src = digital_file.read_text()
        if "get_text" in src or "pdfplumber" in src:
            ok("Digital extraction logic (PyMuPDF / pdfplumber) present")
            passed += 1
        else:
            fail("digital_extractor.py missing PyMuPDF extraction logic")
    else:
        fail("digital_extractor.py not found")
        info("Fix: create backend/app/services/extraction/digital_extractor.py (see Phase 1)")

    results["phase1"] = passed == total
    print(f"  Phase 1: {passed}/{total} checks passed")
    return passed == total


# ─────────────────────────────────────────────────────────────
# PHASE 2: Format Gate + JPEG Rejection
# ─────────────────────────────────────────────────────────────
def check_phase2():
    header("PHASE 2 - Format Gate + JPEG Rejection")
    passed = 0
    total  = 2

    # Check upload router for JPEG rejection
    routers_dir = APP / "api"
    jpeg_rejected = False
    for f in routers_dir.glob("*.py"):
        src = f.read_text()
        if "jpeg" in src.lower() or "jpg" in src.lower():
            if "reject" in src.lower() or "not allowed" in src.lower() or "unsupported" in src.lower():
                jpeg_rejected = True
                break
            if ".jpg" in src and "raise" in src:
                jpeg_rejected = True
                break

    if jpeg_rejected:
        ok("JPEG rejection found in upload router")
        passed += 1
    else:
        fail("No JPEG rejection in upload router")
        info("Fix: add ALLOWED_TYPES check in upload endpoint (see Phase 2)")

    # Check format_gate.py or similar
    gate_file = EXT / "format_gate.py"
    if gate_file.exists():
        ok("format_gate.py exists")
        passed += 1
    else:
        warn("format_gate.py not found (acceptable if rejection is inline in router)")
        passed += 1  # Not a hard requirement

    results["phase2"] = passed == total
    print(f"  Phase 2: {passed}/{total} checks passed")
    return passed == total


# ─────────────────────────────────────────────────────────────
# PHASE 3: OpenCV Pre-Processing
# ─────────────────────────────────────────────────────────────
def check_phase3():
    header("PHASE 3 - OpenCV Scan Pre-Processing")
    passed = 0
    total  = 2

    preproc_file = EXT / "scan_preprocessor.py"
    if preproc_file.exists():
        ok("scan_preprocessor.py exists")
        passed += 1
        src = preproc_file.read_text()
        checks = {"deskew": "HoughLines" in src or "deskew" in src.lower(),
                  "binarize": "adaptiveThreshold" in src or "threshold" in src.lower(),
                  "denoise": "medianBlur" in src or "denoise" in src.lower()}
        for name, found in checks.items():
            if found:
                ok(f"  {name} step present")
            else:
                warn(f"  {name} step not found")
        if all(checks.values()):
            passed += 1
    else:
        fail("scan_preprocessor.py not found")
        info("Fix: create backend/app/services/extraction/scan_preprocessor.py (see Phase 3)")

    results["phase3"] = passed == total
    print(f"  Phase 3: {passed}/{total} checks passed")
    return passed == total


# ─────────────────────────────────────────────────────────────
# PHASE 4: Document Type Classifier
# ─────────────────────────────────────────────────────────────
def check_phase4():
    header("PHASE 4 - Document Type Classifier")
    passed = 0
    total  = 3

    classifier_file = EXT / "doc_classifier.py"
    if classifier_file.exists():
        ok("doc_classifier.py exists")
        passed += 1
    else:
        fail("doc_classifier.py not found")
        info("Fix: create backend/app/services/extraction/doc_classifier.py (see Phase 4)")

    model_dir = ROOT / "models" / "doc_classifier"
    if model_dir.exists():
        weights = list(model_dir.glob("*.pth")) + list(model_dir.glob("*.bin")) + list(model_dir.glob("*.pt"))
        if weights:
            ok(f"Classifier model weights found: {weights[0].name}")
            passed += 1
        else:
            warn("model dir exists but no weights found - training not complete")
    else:
        fail("No trained classifier model found at backend/models/doc_classifier/")
        info("Fix: train classifier (see Phase 4 training instructions)")

    # Check if classify endpoint or pre-upload hook exists
    routers_dir = APP / "api"
    classify_found = False
    for f in routers_dir.glob("*.py"):
        src = f.read_text()
        if "classify" in src or "doc_classifier" in src:
            classify_found = True
            break
    if classify_found:
        ok("Classifier integrated into upload/API flow")
        passed += 1
    else:
        warn("Classifier not yet wired into upload flow")
        info("Fix: integrate doc_classifier into document upload router (see Phase 4)")

    results["phase4"] = passed == total
    print(f"  Phase 4: {passed}/{total} checks passed")
    return passed == total


# ─────────────────────────────────────────────────────────────
# PHASE 5: LayoutLMv3 Integration
# ─────────────────────────────────────────────────────────────
def check_phase5():
    header("PHASE 5 - LayoutLMv3 Field Extraction")
    passed = 0
    total  = 4

    layoutlm_file = EXT / "layoutlm_extractor.py"
    if layoutlm_file.exists():
        ok("layoutlm_extractor.py exists")
        passed += 1
    else:
        fail("layoutlm_extractor.py not found")
        info("Fix: create backend/app/services/extraction/layoutlm_extractor.py (see Phase 5)")

    model_dir = ROOT / "models" / "layoutlmv3"
    if model_dir.exists():
        ok("LayoutLMv3 model directory exists")
        passed += 1
        config = model_dir / "config.json"
        if config.exists():
            ok("LayoutLMv3 config.json found - model downloaded")
            passed += 1
        else:
            warn("config.json missing - model may not be downloaded yet")
    else:
        fail("No LayoutLMv3 model at backend/models/layoutlmv3/")
        info("Fix: download base model - see Phase 5 setup")

    # Check tasks.py uses layoutlm_extractor
    tasks_file = EXT / "tasks.py"
    if tasks_file.exists():
        src = tasks_file.read_text()
        if "layoutlm_extractor" in src or "LayoutLMExtractor" in src:
            ok("tasks.py imports LayoutLM extractor")
            passed += 1
        else:
            fail("tasks.py still using qwen2.5:7b for Layer 2")
            info("Fix: replace TwoLayerClient extraction call in tasks.py (see Phase 5)")

    results["phase5"] = passed == total
    print(f"  Phase 5: {passed}/{total} checks passed")
    return passed == total


# ─────────────────────────────────────────────────────────────
# PHASE 6: Math + Business Rule Validation
# ─────────────────────────────────────────────────────────────
def check_phase6():
    header("PHASE 6 - Math & Business Rule Validation")
    passed = 0
    total  = 2

    validator_file = EXT / "invoice_validator.py"
    if validator_file.exists():
        ok("invoice_validator.py exists")
        passed += 1
        src = validator_file.read_text()
        if "validate_invoice_math" in src or "total_amount" in src:
            ok("Invoice math validation logic present")
            passed += 1
        else:
            fail("invoice_validator.py missing math validation function")
    else:
        fail("invoice_validator.py not found")
        info("Fix: create backend/app/services/extraction/invoice_validator.py (see Phase 6)")

    results["phase6"] = passed == total
    print(f"  Phase 6: {passed}/{total} checks passed")
    return passed == total


# ─────────────────────────────────────────────────────────────
# PHASE 7: Version-Safe Persistence
# ─────────────────────────────────────────────────────────────
def check_phase7():
    header("PHASE 7 - Version-Safe Persistence")
    passed = 0
    total  = 3

    # Check re-extract endpoint does not DELETE
    routers_dir = APP / "api"
    delete_found = False
    versioned_found = False
    for f in routers_dir.glob("*.py"):
        src = f.read_text()
        if "re.extract" in src.lower() or "re_extract" in src.lower() or "reextract" in src.lower():
            if "DELETE" in src or ".delete()" in src:
                delete_found = True
            if "extraction_version" in src or "version" in src.lower():
                versioned_found = True

    if delete_found:
        fail("re-extract endpoint still uses DELETE - wipes history")
        info("Fix: replace DELETE with version increment (see Phase 7)")
    else:
        ok("No DELETE in re-extract flow")
        passed += 1

    if versioned_found:
        ok("extraction_version logic found")
        passed += 1
    else:
        warn("extraction_version not found in re-extract flow")
        info("Fix: add extraction_version increment (see Phase 7)")

    # Check DB model has field_confidences column
    models_file = APP / "models" / "__init__.py"
    if models_file.exists():
        src = models_file.read_text()
        if "field_confidences" in src or "extraction_version" in src:
            ok("field_confidences / extraction_version columns exist in DocumentMetadata model")
            passed += 1
        else:
            fail("field_confidences/extraction_version columns missing from DocumentMetadata")
            info("Fix: add field_confidences JSON column to DocumentMetadata model (see Phase 7)")
    else:
        warn("models/__init__.py not found at expected path")

    results["phase7"] = passed == total
    print(f"  Phase 7: {passed}/{total} checks passed")
    return passed == total


# ─────────────────────────────────────────────────────────────
# PHASE 8: HITL Corrections Capture
# ─────────────────────────────────────────────────────────────
def check_phase8():
    header("PHASE 8 - HITL Corrections Capture + Active Learning")
    passed = 0
    total  = 2

    models_file = APP / "models" / "__init__.py"
    if models_file.exists():
        src = models_file.read_text()
        if "ExtractionCorrection" in src or "corrections" in src:
            ok("ExtractionCorrection model / corrections table found")
            passed += 1
        else:
            fail("No corrections capture table in models.py")
            info("Fix: add ExtractionCorrection model (see Phase 8)")

    # Check corrections endpoint
    routers_dir = APP / "api"
    corrections_endpoint = False
    for f in routers_dir.glob("*.py"):
        src = f.read_text()
        if "correction" in src.lower() and ("post" in src.lower() or "patch" in src.lower()):
            corrections_endpoint = True
            break
    if corrections_endpoint:
        ok("Corrections API endpoint found")
        passed += 1
    else:
        fail("No corrections save endpoint in API routers")
        info("Fix: add POST /corrections endpoint (see Phase 8)")

    results["phase8"] = passed == total
    print(f"  Phase 8: {passed}/{total} checks passed")
    return passed == total


# ─────────────────────────────────────────────────────────────
# SUMMARY + NEXT ACTION
# ─────────────────────────────────────────────────────────────
def print_summary():
    header("=" * 40)
    header("SUMMARY")
    print()
    phases = [
        ("Phase 0", "Critical config fixes",          "results" in dir() and results.get("phase0")),
        ("Phase 1", "Hybrid router + digital path",   results.get("phase1")),
        ("Phase 2", "Format gate + JPEG rejection",   results.get("phase2")),
        ("Phase 3", "OpenCV pre-processing",          results.get("phase3")),
        ("Phase 4", "Document type classifier",       results.get("phase4")),
        ("Phase 5", "LayoutLMv3 integration",         results.get("phase5")),
        ("Phase 6", "Math validation",                results.get("phase6")),
        ("Phase 7", "Version-safe persistence",       results.get("phase7")),
        ("Phase 8", "HITL corrections capture",       results.get("phase8")),
    ]

    first_incomplete = None
    for name, desc, done in phases:
        status = f"{GREEN}COMPLETE{RESET}" if done else f"{RED}MISSING {RESET}"
        print(f"  {status}  {name}: {desc}")
        if not done and first_incomplete is None:
            first_incomplete = (name, desc)

    print()
    if first_incomplete:
        print(f"{BOLD}{YELLOW}> START HERE:{RESET} {first_incomplete[0]} - {first_incomplete[1]}")
        print(f"  See IMPLEMENTATION.md Section for '{first_incomplete[0]}'\n")
    else:
        print(f"{BOLD}{GREEN}# All phases complete!{RESET}\n")


if __name__ == "__main__":
    check_phase0()
    check_phase1()
    check_phase2()
    check_phase3()
    check_phase4()
    check_phase5()
    check_phase6()
    check_phase7()
    check_phase8()
    print_summary()
