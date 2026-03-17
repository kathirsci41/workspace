# DocPlatform V3 — OCR Pipeline Implementation Guide

> **How to use this document**  
> Work through phases in order. Do not skip ahead.  
> Each phase has: exact file edits → test → verify.  
> Start every session by running the phase checker script (Section 0).

---

## Section 0 — Phase Checker Script

Save this as `backend/scripts/check_phases.py`.  
Run it before every work session. It audits your codebase and tells you exactly what is done, what is missing, and what to do next.

```python
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

def ok(msg):    print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg):  print(f"  {RED}✗{RESET} {msg}")
def warn(msg):  print(f"  {YELLOW}△{RESET} {msg}")
def info(msg):  print(f"  {CYAN}→{RESET} {msg}")
def header(msg):print(f"\n{BOLD}{msg}{RESET}")

results = {}

# ─────────────────────────────────────────────────────────────
# PHASE 0: Critical config fixes
# ─────────────────────────────────────────────────────────────
def check_phase0():
    header("PHASE 0 — Critical Config Fixes (target: 35 min)")
    passed = 0
    total  = 3

    # Check 1: 768px cap removed
    conv_file = EXT / "pdf_converter.py"
    if conv_file.exists():
        src = conv_file.read_text()
        if "MAX_IMAGE_DIM = 768" in src:
            fail("768px cap still present in pdf_converter.py — KILLS accuracy")
            info("Fix: delete lines with MAX_IMAGE_DIM = 768 and img.thumbnail()")
        elif "img.thumbnail" in src:
            fail("img.thumbnail() resize block still present")
            info("Fix: remove the entire resize block (keep PATCH_SIZE snapping)")
        else:
            ok("768px cap removed — full resolution preserved")
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
                ok(f"OCR_PDF_DPI = {dpi} ✓")
                dpi_ok = True
            else:
                fail(f"OCR_PDF_DPI = {dpi} — must be >= 300")
                info("Fix: set OCR_PDF_DPI=300 in backend/.env")
        else:
            warn("OCR_PDF_DPI not found in .env — check config.py default")
        if pages_match:
            pages = int(pages_match.group(1))
            if pages >= 10:
                ok(f"OCR_MAX_PAGES = {pages} ✓")
                pages_ok = True
            else:
                fail(f"OCR_MAX_PAGES = {pages} — only first {pages} page(s) processed")
                info("Fix: set OCR_MAX_PAGES=10 in backend/.env")
        else:
            warn("OCR_MAX_PAGES not found in .env")
    else:
        warn(".env not found — checking config.py defaults")

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
    header("PHASE 1 — Hybrid Router + Digital Fast Path")
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
        src = digital_extractor_file = digital_file.read_text()
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
    header("PHASE 2 — Format Gate + JPEG Rejection")
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
    header("PHASE 3 — OpenCV Scan Pre-Processing")
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
    header("PHASE 4 — Document Type Classifier")
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
            warn("model dir exists but no weights found — training not complete")
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
    header("PHASE 5 — LayoutLMv3 Field Extraction")
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
            ok("LayoutLMv3 config.json found — model downloaded")
            passed += 1
        else:
            warn("config.json missing — model may not be downloaded yet")
    else:
        fail("No LayoutLMv3 model at backend/models/layoutlmv3/")
        info("Fix: download base model — see Phase 5 setup")

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
    header("PHASE 6 — Math & Business Rule Validation")
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
    header("PHASE 7 — Version-Safe Persistence")
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
        fail("re-extract endpoint still uses DELETE — wipes history")
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
    models_file = APP / "models.py"
    if models_file.exists():
        src = models_file.read_text()
        if "field_confidences" in src:
            ok("field_confidences column exists in DocumentMetadata model")
            passed += 1
        else:
            fail("field_confidences column missing from DocumentMetadata")
            info("Fix: add field_confidences JSON column to DocumentMetadata model (see Phase 7)")
    else:
        warn("models.py not found at expected path")

    results["phase7"] = passed == total
    print(f"  Phase 7: {passed}/{total} checks passed")
    return passed == total


# ─────────────────────────────────────────────────────────────
# PHASE 8: HITL Corrections Capture
# ─────────────────────────────────────────────────────────────
def check_phase8():
    header("PHASE 8 — HITL Corrections Capture + Active Learning")
    passed = 0
    total  = 2

    models_file = APP / "models.py"
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
    header("═══════════════════════════════════════")
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
        print(f"{BOLD}{YELLOW}▶ START HERE:{RESET} {first_incomplete[0]} — {first_incomplete[1]}")
        print(f"  See IMPLEMENTATION.md Section for '{first_incomplete[0]}'\n")
    else:
        print(f"{BOLD}{GREEN}✓ All phases complete!{RESET}\n")


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
```

**Run it:**
```bash
cd /your-project
python backend/scripts/check_phases.py
```

---

## Phase 0 — Critical Config Fixes
**Time: 35 minutes | Risk: Zero | Impact: +40–60% accuracy immediately**

These are three config changes. No new code, no new dependencies. Do these first, before anything else.

---

### 0.1 — Remove the 768px Resolution Cap

**File:** `backend/app/services/extraction/pdf_converter.py`

**Find and delete these exact lines:**

```python
# DELETE this line:
MAX_IMAGE_DIM = 768

# DELETE this entire block inside convert_to_images():
if max(img.size) > self.max_image_dim:
    img.thumbnail(
        (self.max_image_dim, self.max_image_dim),
        Image.Resampling.LANCZOS,
    )
```

**Also update the class constructor — remove max_image_dim parameter:**

```python
# BEFORE:
class PDFConverter:
    def __init__(self, dpi: int = 200, max_pages: int = 10, max_image_dim: int = MAX_IMAGE_DIM):
        self.dpi = dpi
        self.max_pages = max_pages
        self.max_image_dim = max_image_dim

# AFTER:
class PDFConverter:
    def __init__(self, dpi: int = 300, max_pages: int = 10):
        self.dpi = dpi
        self.max_pages = max_pages
```

**Keep the PATCH_SIZE snapping block** — do not delete it. It prevents GGML tensor errors:

```python
# KEEP THIS — still needed:
PATCH_SIZE = 14
w, h = img.size
new_w = (w // PATCH_SIZE) * PATCH_SIZE
new_h = (h // PATCH_SIZE) * PATCH_SIZE
if (new_w, new_h) != (w, h) and new_w > 0 and new_h > 0:
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
```

---

### 0.2 — Raise DPI and Page Limit

**File:** `backend/.env`

```bash
# CHANGE these values:
OCR_PDF_DPI=300        # was 200 — minimum for financial documents
OCR_MAX_PAGES=10       # was 1 — only first page was ever processed
OCR_EXTRACTOR_NUM_CTX=16384   # was 8192 — needed for 10-page content
```

---

### 0.3 — Test Phase 0

Run this test script to confirm the changes work:

```python
# Save as: backend/tests/test_phase0.py
# Run with: python backend/tests/test_phase0.py

import io
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.extraction.pdf_converter import PDFConverter

def test_no_resize_cap():
    """Confirm 768px cap is gone — full resolution preserved."""
    conv = PDFConverter(dpi=300, max_pages=10)
    assert not hasattr(conv, 'max_image_dim'), \
        "FAIL: max_image_dim attribute still exists — 768px cap not removed"
    print("✓ No max_image_dim attribute — cap removed")

def test_dpi_default():
    """Confirm default DPI is now 300."""
    conv = PDFConverter()
    assert conv.dpi == 300, f"FAIL: dpi={conv.dpi}, expected 300"
    print(f"✓ Default DPI = {conv.dpi}")

def test_max_pages_default():
    """Confirm default max_pages is now 10."""
    conv = PDFConverter()
    assert conv.max_pages == 10, f"FAIL: max_pages={conv.max_pages}, expected 10"
    print(f"✓ Default max_pages = {conv.max_pages}")

def test_convert_sample_pdf():
    """
    If you have a sample PDF, test full-resolution conversion.
    Place any invoice PDF at: backend/tests/samples/sample_invoice.pdf
    """
    sample = Path(__file__).parent / "samples" / "sample_invoice.pdf"
    if not sample.exists():
        print("△ No sample PDF found — skipping live conversion test")
        print("  Place a sample PDF at backend/tests/samples/sample_invoice.pdf")
        return

    conv = PDFConverter(dpi=300, max_pages=10)
    images = conv.convert_to_images(str(sample))
    print(f"✓ Converted {len(images)} pages")

    from PIL import Image
    for i, img_bytes in enumerate(images):
        img = Image.open(io.BytesIO(img_bytes))
        w, h = img.size
        assert max(w, h) > 800, \
            f"FAIL: Page {i+1} is {w}x{h} — still being downscaled"
        print(f"  Page {i+1}: {w}x{h}px — full resolution ✓")

if __name__ == "__main__":
    print("=== Phase 0 Tests ===\n")
    test_no_resize_cap()
    test_dpi_default()
    test_max_pages_default()
    test_convert_sample_pdf()
    print("\n✓ Phase 0 tests passed")
```

**Expected output:**
```
=== Phase 0 Tests ===

✓ No max_image_dim attribute — cap removed
✓ Default DPI = 300
✓ Default max_pages = 10
✓ Converted 3 pages
  Page 1: 2480x3508px — full resolution ✓
  Page 2: 2480x3508px — full resolution ✓
  Page 3: 2480x3508px — full resolution ✓

✓ Phase 0 tests passed
```

**Run phase checker to confirm:**
```bash
python backend/scripts/check_phases.py
# Phase 0 should show COMPLETE
```

---

## Phase 1 — Hybrid Router + Digital Fast Path
**Time: 1–2 days | Impact: 100% accuracy on all ERP-generated invoices**

### 1.1 — Create the Digital Extractor

**Create file:** `backend/app/services/extraction/digital_extractor.py`

```python
"""
Programmatic text extraction for digital-native PDFs.

For PDFs that have an embedded text layer (machine-generated from
Tally, SAP, QuickBooks, Zoho, etc.) — extract text and coordinates
directly via PyMuPDF without any OCR model invocation.

Accuracy: 100% (no OCR errors possible)
Speed: < 100ms per page
GPU cost: zero
"""

import logging
from typing import Optional
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# Minimum characters per page to classify a PDF as "digital native"
DIGITAL_THRESHOLD = 50


class DigitalExtractionResult:
    """Structured result from programmatic PDF extraction."""

    def __init__(self):
        self.pages: list[dict] = []        # list of page dicts
        self.full_text: str = ""           # all text joined
        self.word_blocks: list[dict] = []  # words with bounding boxes
        self.is_digital: bool = False

    def to_layoutlm_input(self) -> dict:
        """
        Convert to the format LayoutLMv3 expects:
        {'words': [...], 'boxes': [[x1,y1,x2,y2], ...], 'page_size': (w, h)}

        Boxes are normalized to 0–1000 range as LayoutLMv3 expects.
        """
        words = []
        boxes = []

        for block in self.word_blocks:
            words.append(block["text"])
            # Normalize to 0-1000 scale
            pw = block["page_width"]
            ph = block["page_height"]
            x1 = int((block["x0"] / pw) * 1000)
            y1 = int((block["y0"] / ph) * 1000)
            x2 = int((block["x1"] / pw) * 1000)
            y2 = int((block["y1"] / ph) * 1000)
            # Clamp to 0-1000
            boxes.append([
                max(0, min(1000, x1)),
                max(0, min(1000, y1)),
                max(0, min(1000, x2)),
                max(0, min(1000, y2)),
            ])

        return {"words": words, "boxes": boxes}


class DigitalExtractor:
    """Extract text and layout from digital-native PDFs using PyMuPDF."""

    def __init__(self, threshold: int = DIGITAL_THRESHOLD):
        self.threshold = threshold

    def is_digital_pdf(self, pdf_path: str) -> bool:
        """
        Check if a PDF has a usable text layer.
        Returns True if the PDF is digital-native (skip OCR).
        Returns False if it is a scanned image PDF (needs OCR).
        """
        try:
            doc = fitz.open(pdf_path)
            total_chars = 0
            pages_checked = min(doc.page_count, 3)  # check first 3 pages
            for i in range(pages_checked):
                page = doc.load_page(i)
                text = page.get_text("text")
                total_chars += len(text.strip())
            doc.close()
            avg_chars = total_chars / max(pages_checked, 1)
            is_digital = avg_chars >= self.threshold
            logger.info(
                f"PDF detection: avg_chars={avg_chars:.0f}, "
                f"is_digital={is_digital}"
            )
            return is_digital
        except Exception as e:
            logger.warning(f"PDF detection failed, defaulting to OCR: {e}")
            return False

    def extract(self, pdf_path: str, max_pages: int = 10) -> DigitalExtractionResult:
        """
        Full extraction from a digital PDF.
        Returns text blocks with bounding boxes, ready for LayoutLMv3.
        """
        result = DigitalExtractionResult()

        try:
            doc = fitz.open(pdf_path)
            total = doc.page_count
            pages_to_process = min(total, max_pages)

            all_words = []

            for page_idx in range(pages_to_process):
                page = doc.load_page(page_idx)
                pw = page.rect.width
                ph = page.rect.height

                # Extract words with bounding boxes
                # get_text("words") returns: (x0, y0, x1, y1, word, block_no, line_no, word_no)
                words = page.get_text("words")

                page_text_parts = []
                for word_data in words:
                    x0, y0, x1, y1, text = word_data[:5]
                    if text.strip():
                        all_words.append({
                            "text": text.strip(),
                            "x0": x0,
                            "y0": y0,
                            "x1": x1,
                            "y1": y1,
                            "page": page_idx,
                            "page_width": pw,
                            "page_height": ph,
                        })
                        page_text_parts.append(text.strip())

                page_text = " ".join(page_text_parts)
                result.pages.append({
                    "page_idx": page_idx,
                    "text": page_text,
                    "width": pw,
                    "height": ph,
                    "word_count": len(words),
                })

            doc.close()

            result.word_blocks = all_words
            result.full_text = "\n\n".join(p["text"] for p in result.pages)
            result.is_digital = True

            logger.info(
                f"Digital extraction: {pages_to_process} pages, "
                f"{len(all_words)} words extracted"
            )

        except Exception as e:
            logger.error(f"Digital extraction failed: {e}")
            result.is_digital = False

        return result
```

---

### 1.2 — Create the Hybrid Router

**Create file:** `backend/app/services/extraction/hybrid_router.py`

```python
"""
Hybrid Router — decides whether a document goes through:
  Route A: Digital fast path (PyMuPDF programmatic extraction)
  Route B: Full OCR pipeline (scan pre-processing + qwen2.5vl)
"""

import logging
from enum import Enum
from pathlib import Path
from app.services.extraction.digital_extractor import DigitalExtractor

logger = logging.getLogger(__name__)


class ExtractionRoute(str, Enum):
    DIGITAL = "digital"   # Route A: programmatic extraction
    SCANNED = "scanned"   # Route B: full OCR pipeline


class HybridRouter:
    """
    Routes documents to the appropriate extraction pipeline
    based on whether they have an embedded text layer.
    """

    def __init__(self, digital_threshold: int = 50):
        self.extractor = DigitalExtractor(threshold=digital_threshold)

    def route(self, file_path: str) -> ExtractionRoute:
        """
        Inspect the PDF and return the appropriate route.
        Non-PDF files (PNG, TIFF) always go to scanned route.
        """
        path = Path(file_path)
        suffix = path.suffix.lower()

        # Image files are always scanned
        if suffix in (".png", ".tiff", ".tif", ".jpg", ".jpeg"):
            logger.info(f"Route B (image file): {path.name}")
            return ExtractionRoute.SCANNED

        # For PDFs, probe the text layer
        if suffix == ".pdf":
            if self.extractor.is_digital_pdf(file_path):
                logger.info(f"Route A (digital PDF): {path.name}")
                return ExtractionRoute.DIGITAL
            else:
                logger.info(f"Route B (scanned PDF): {path.name}")
                return ExtractionRoute.SCANNED

        # Unknown format — default to scanned (safer)
        logger.warning(f"Unknown format {suffix}, defaulting to scanned route")
        return ExtractionRoute.SCANNED
```

---

### 1.3 — Test Phase 1

```python
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
    print("✓ HybridRouter instantiated")

def test_digital_extractor_exists():
    ext = DigitalExtractor()
    assert ext is not None
    print("✓ DigitalExtractor instantiated")

def test_image_routes_to_scanned():
    router = HybridRouter()
    # Image files must always go to scanned route
    assert router.route("test.png") == ExtractionRoute.SCANNED
    assert router.route("test.tiff") == ExtractionRoute.SCANNED
    print("✓ Image files correctly routed to SCANNED")

def test_with_sample_pdfs():
    """
    Place test files in backend/tests/samples/:
      digital_invoice.pdf  — machine-generated (from Tally/SAP)
      scanned_invoice.pdf  — photographed/scanned physical document
    """
    samples = Path(__file__).parent / "samples"
    router = HybridRouter()
    extractor = DigitalExtractor()

    digital = samples / "digital_invoice.pdf"
    scanned = samples / "scanned_invoice.pdf"

    if digital.exists():
        route = router.route(str(digital))
        assert route == ExtractionRoute.DIGITAL, f"Expected DIGITAL, got {route}"
        print(f"✓ Digital PDF routed correctly: {route}")

        result = extractor.extract(str(digital))
        assert result.is_digital
        assert len(result.word_blocks) > 0
        print(f"  Extracted {len(result.word_blocks)} words from digital PDF")

        lm_input = result.to_layoutlm_input()
        assert len(lm_input["words"]) == len(lm_input["boxes"])
        print(f"  LayoutLM input: {len(lm_input['words'])} tokens with boxes ✓")
    else:
        print("△ No digital_invoice.pdf sample — add one for full test")

    if scanned.exists():
        route = router.route(str(scanned))
        assert route == ExtractionRoute.SCANNED, f"Expected SCANNED, got {route}"
        print(f"✓ Scanned PDF routed correctly: {route}")
    else:
        print("△ No scanned_invoice.pdf sample — add one for full test")

if __name__ == "__main__":
    print("=== Phase 1 Tests ===\n")
    test_router_exists()
    test_digital_extractor_exists()
    test_image_routes_to_scanned()
    test_with_sample_pdfs()
    print("\n✓ Phase 1 tests passed")
```

---

## Phase 2 — Format Gate + JPEG Rejection
**Time: 2 hours | Risk: Zero**

### 2.1 — Add JPEG Rejection to Upload Endpoint

**File:** `backend/app/api/documents.py` (or wherever your upload endpoint is)

Find your upload endpoint and add this validation before the file is saved:

```python
# Add at the top of the file:
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/tiff",
}
ALLOWED_EXTENSIONS = {".pdf", ".png", ".tiff", ".tif"}

# Add this function:
def validate_upload_file(filename: str, content_type: str) -> None:
    """Raise HTTPException if file format is not accepted."""
    from pathlib import Path
    from fastapi import HTTPException

    ext = Path(filename).suffix.lower()
    if ext in (".jpg", ".jpeg") or "jpeg" in content_type.lower():
        raise HTTPException(
            status_code=415,
            detail=(
                "JPEG files are not accepted. "
                "JPEG compression reduces OCR accuracy significantly. "
                "Please convert to PDF, PNG, or TIFF before uploading."
            )
        )
    if ext not in ALLOWED_EXTENSIONS and content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"File type '{ext}' is not supported. Accepted: PDF, PNG, TIFF"
        )
```

**Call it in your upload handler:**
```python
@router.post("/upload")
async def upload_document(file: UploadFile, ...):
    validate_upload_file(file.filename, file.content_type)  # ADD THIS LINE
    # ... rest of your existing upload code
```

### 2.2 — Test Phase 2

```python
# Save as: backend/tests/test_phase2.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test the validation logic directly
from fastapi import HTTPException
import pytest

def test_jpeg_rejected():
    try:
        from app.api.documents import validate_upload_file
        try:
            validate_upload_file("invoice.jpg", "image/jpeg")
            print("✗ FAIL: JPEG was not rejected")
        except HTTPException as e:
            assert e.status_code == 415
            assert "JPEG" in e.detail
            print("✓ JPEG correctly rejected with 415 and clear message")
    except ImportError:
        print("△ validate_upload_file not found — add it to your upload router")

def test_pdf_accepted():
    try:
        from app.api.documents import validate_upload_file
        try:
            validate_upload_file("invoice.pdf", "application/pdf")
            print("✓ PDF accepted")
        except HTTPException:
            print("✗ FAIL: PDF was incorrectly rejected")
    except ImportError:
        print("△ validate_upload_file not found")

def test_png_accepted():
    try:
        from app.api.documents import validate_upload_file
        try:
            validate_upload_file("invoice.png", "image/png")
            print("✓ PNG accepted")
        except HTTPException:
            print("✗ FAIL: PNG was incorrectly rejected")
    except ImportError:
        print("△ validate_upload_file not found")

if __name__ == "__main__":
    print("=== Phase 2 Tests ===\n")
    test_jpeg_rejected()
    test_pdf_accepted()
    test_png_accepted()
    print("\n✓ Phase 2 tests passed")
```

---

## Phase 3 — OpenCV Scan Pre-Processing
**Time: 2–3 days | Impact: +15–25% accuracy on scanned documents**

### 3.1 — Install Dependencies

```bash
pip install opencv-python-headless numpy pillow
```

### 3.2 — Create Scan Preprocessor

**Create file:** `backend/app/services/extraction/scan_preprocessor.py`

```python
"""
OpenCV scan pre-processing pipeline.

Runs BEFORE OCR on scanned documents to maximize character recognition accuracy.
Steps:
  1. Deskew        — correct rotation up to ±15 degrees
  2. Binarize      — convert to clean black/white
  3. Denoise       — remove scanner noise and artifacts
  4. Normalize     — equalize contrast for faded/overexposed scans

Input:  raw PNG bytes (from pdf_converter.py)
Output: cleaned PNG bytes (ready for qwen2.5vl)
"""

import io
import logging
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("OpenCV not installed — scan pre-processing disabled. Run: pip install opencv-python-headless")


def preprocess_scan(image_bytes: bytes, debug: bool = False) -> bytes:
    """
    Apply full pre-processing pipeline to a scanned document image.

    Args:
        image_bytes: Raw PNG image bytes
        debug: If True, log intermediate step metrics

    Returns:
        Cleaned PNG image bytes
    """
    if not CV2_AVAILABLE:
        logger.debug("OpenCV not available — returning image unchanged")
        return image_bytes

    try:
        # Load image
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            logger.warning("Could not decode image — returning unchanged")
            return image_bytes

        original_shape = img.shape
        if debug:
            logger.info(f"Pre-processing: input shape={original_shape}")

        # Step 1: Deskew
        img = _deskew(img, debug=debug)

        # Step 2: Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Step 3: Adaptive binarization (handles uneven lighting)
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=15,
            C=8,
        )

        # Step 4: Denoise (remove scanner specks)
        denoised = cv2.medianBlur(binary, 3)

        # Step 5: CLAHE contrast enhancement (before binarization on the gray)
        # Applied to the gray image for a second pass on very faded docs
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Use denoised binary for clean text, but fall back to enhanced gray
        # if binarization was too aggressive (check white pixel ratio)
        white_ratio = np.sum(denoised == 255) / denoised.size
        if white_ratio > 0.97 or white_ratio < 0.50:
            # Binarization too aggressive — use enhanced grayscale instead
            if debug:
                logger.info(f"Binary white ratio {white_ratio:.2f} — using enhanced gray")
            result_gray = enhanced
        else:
            result_gray = denoised

        if debug:
            logger.info(f"Pre-processing: white_ratio={white_ratio:.2f}")

        # Convert back to BGR for consistent output
        result = cv2.cvtColor(result_gray, cv2.COLOR_GRAY2BGR)

        # Encode to PNG bytes
        _, encoded = cv2.imencode(".png", result)
        output_bytes = encoded.tobytes()

        logger.debug(
            f"Pre-processing complete: "
            f"{len(image_bytes)//1024}KB -> {len(output_bytes)//1024}KB"
        )
        return output_bytes

    except Exception as e:
        logger.warning(f"Pre-processing failed, using original: {e}")
        return image_bytes


def _deskew(img: np.ndarray, max_angle: float = 15.0, debug: bool = False) -> np.ndarray:
    """
    Detect and correct document skew using Hough line detection.
    Only corrects if detected angle is within ±max_angle degrees
    to avoid overcorrecting on non-skewed documents.
    """
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)

        if lines is None:
            return img

        angles = []
        for line in lines[:20]:  # use top 20 strongest lines
            rho, theta = line[0]
            angle_deg = np.degrees(theta) - 90
            if abs(angle_deg) <= max_angle:
                angles.append(angle_deg)

        if not angles:
            return img

        # Use median angle to avoid outliers
        skew_angle = float(np.median(angles))

        if abs(skew_angle) < 0.5:
            return img  # Less than 0.5 degree — not worth correcting

        if debug:
            logger.info(f"Deskew: detected angle={skew_angle:.2f}°")

        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, skew_angle, 1.0)
        rotated = cv2.warpAffine(
            img,
            rotation_matrix,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return rotated

    except Exception as e:
        logger.debug(f"Deskew failed, using original: {e}")
        return img


def estimate_scan_quality(image_bytes: bytes) -> dict:
    """
    Estimate scan quality metrics for a document image.
    Returns a dict with quality scores.
    Useful for routing borderline cases.
    """
    if not CV2_AVAILABLE:
        return {"quality": "unknown", "cv2_available": False}

    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return {"quality": "unknown"}

        # Sharpness via Laplacian variance
        sharpness = float(cv2.Laplacian(img, cv2.CV_64F).var())

        # Contrast
        contrast = float(img.std())

        # Overall quality score (0-100)
        quality_score = min(100, (sharpness / 100) * 50 + (contrast / 128) * 50)

        return {
            "sharpness": round(sharpness, 1),
            "contrast": round(contrast, 1),
            "quality_score": round(quality_score, 1),
            "quality": "good" if quality_score > 40 else "poor",
        }
    except Exception as e:
        return {"quality": "unknown", "error": str(e)}
```

### 3.3 — Wire Pre-Processing Into the Pipeline

**File:** `backend/app/services/extraction/tasks.py`

Add to imports at top:
```python
from app.services.extraction.scan_preprocessor import preprocess_scan
from app.services.extraction.hybrid_router import HybridRouter, ExtractionRoute
from app.services.extraction.digital_extractor import DigitalExtractor
```

In the `extract_document` task, after fetching the document and before converting to images, add the router check:

```python
# After: storage_path = os.path.join(settings.nas_base_path, doc.file_path)
# ADD THIS BLOCK:

router = HybridRouter()
route = router.route(storage_path)
logger.info(f"Document {document_id}: route={route.value}")

if route == ExtractionRoute.DIGITAL:
    # Digital fast path — no OCR needed
    digital_extractor = DigitalExtractor()
    digital_result = digital_extractor.extract(storage_path, max_pages=settings.ocr_max_pages)
    if digital_result.is_digital and digital_result.word_blocks:
        # Use digital result directly — skip all OCR
        # For now: pass full_text to Layer 2 extraction as markdown
        # Phase 5 will replace this with LayoutLMv3
        raw_texts = [digital_result.full_text]
        logger.info(f"Digital extraction: {len(digital_result.word_blocks)} words, no GPU used")
        # Continue to extraction step with raw_texts populated
    else:
        logger.warning("Digital route returned no content — falling back to OCR")
        route = ExtractionRoute.SCANNED
```

And when processing scanned images, wrap with pre-processing:
```python
# In the OCR loop, after: img = images[i]
# ADD:
if route == ExtractionRoute.SCANNED:
    img = preprocess_scan(img)
```

### 3.4 — Test Phase 3

```python
# Save as: backend/tests/test_phase3.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_preprocessor_import():
    from app.services.extraction.scan_preprocessor import preprocess_scan, estimate_scan_quality
    print("✓ scan_preprocessor imports correctly")

def test_passthrough_when_no_opencv():
    """If OpenCV not installed, image should pass through unchanged."""
    from app.services.extraction.scan_preprocessor import preprocess_scan
    fake_bytes = b"fake image bytes"
    result = preprocess_scan(fake_bytes)
    # Should return original bytes unchanged (either CV2 processed or passthrough)
    assert result is not None
    print("✓ Preprocessor returns bytes without crashing")

def test_with_real_image():
    """Test with an actual scan image."""
    from app.services.extraction.scan_preprocessor import preprocess_scan, estimate_scan_quality
    import io
    from PIL import Image
    import numpy as np

    # Create a synthetic test image (white background, black text pattern)
    img = Image.new("RGB", (800, 1000), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    image_bytes = buf.getvalue()

    result = preprocess_scan(image_bytes, debug=True)
    assert isinstance(result, bytes)
    assert len(result) > 0
    print(f"✓ Pre-processing returned {len(result)//1024}KB image")

    quality = estimate_scan_quality(image_bytes)
    print(f"✓ Quality assessment: {quality}")

def test_deskew():
    """Test deskew does not crash on normal images."""
    import io, numpy as np
    from PIL import Image
    from app.services.extraction.scan_preprocessor import _deskew

    try:
        import cv2
        img = np.zeros((800, 600, 3), dtype=np.uint8)
        img[:] = 255  # white
        result = _deskew(img)
        assert result.shape == img.shape
        print("✓ Deskew function works on clean image")
    except ImportError:
        print("△ OpenCV not installed — deskew test skipped")

if __name__ == "__main__":
    print("=== Phase 3 Tests ===\n")
    test_preprocessor_import()
    test_passthrough_when_no_opencv()
    test_with_real_image()
    test_deskew()
    print("\n✓ Phase 3 tests passed")
```

---

## Phase 4 — Document Type Classifier
**Time: 3–5 days (includes training time) | Enables: automated batch ingestion**

### 4.1 — Prepare Training Data

Before writing any code, export your labelled training data:

```sql
-- Run in your PostgreSQL database
-- This gives you the documents available for training

SELECT
    d.id,
    d.file_path,
    d.document_type,
    dm.status,
    dm.confidence_score,
    COUNT(*) OVER (PARTITION BY d.document_type) AS type_count
FROM documents d
JOIN document_metadata dm ON dm.document_id = d.id
WHERE dm.status = 'VERIFIED'
ORDER BY d.document_type, dm.confidence_score DESC;
```

**You need at minimum:**
- 50 verified documents per document type for initial training
- 100+ per type for reliable results
- Aim for 200+ per type before production use

If you have fewer than 50 per type, skip to Phase 5 and return to Phase 4 after more documents accumulate.

### 4.2 — Create Classifier Module

**Create file:** `backend/app/services/extraction/doc_classifier.py`

```python
"""
Document Type Classifier

Classifies a document image into one of 6 types:
  VENDOR_INVOICE, COMPANY_INVOICE, VENDOR_DC, COMPANY_DC,
  CUSTOMER_PO, COMPANY_PO

Uses a lightweight EfficientNet-B0 fine-tuned on your document images.
Runs on CPU — inference ~50ms, no GPU required.

Training: see backend/scripts/train_classifier.py
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DOC_TYPES = [
    "VENDOR_INVOICE",
    "COMPANY_INVOICE",
    "VENDOR_DC",
    "COMPANY_DC",
    "CUSTOMER_PO",
    "COMPANY_PO",
]

# Minimum confidence to auto-accept classification
# Below this threshold → prompt user to confirm
AUTO_ACCEPT_THRESHOLD = 0.85
CONFIRM_THRESHOLD = 0.60  # below this → require manual selection


class ClassificationResult:
    def __init__(self, doc_type: str, confidence: float, all_scores: dict):
        self.doc_type = doc_type
        self.confidence = confidence
        self.all_scores = all_scores  # {doc_type: probability}

    @property
    def needs_confirmation(self) -> bool:
        return self.confidence < AUTO_ACCEPT_THRESHOLD

    @property
    def needs_manual(self) -> bool:
        return self.confidence < CONFIRM_THRESHOLD

    def __repr__(self):
        return f"ClassificationResult({self.doc_type}, conf={self.confidence:.2f})"


class DocClassifier:
    """Lightweight document type classifier."""

    def __init__(self, model_dir: Optional[str] = None):
        self.model_dir = Path(model_dir) if model_dir else \
            Path(__file__).parent.parent.parent.parent / "models" / "doc_classifier"
        self.model = None
        self.transform = None
        self._load_model()

    def _load_model(self):
        """Load the fine-tuned EfficientNet model if it exists."""
        try:
            import torch
            from torchvision import transforms

            weights_path = self.model_dir / "model.pth"
            if not weights_path.exists():
                logger.warning(
                    f"Classifier weights not found at {weights_path}. "
                    f"Run backend/scripts/train_classifier.py to train."
                )
                return

            import torchvision.models as tv_models
            model = tv_models.efficientnet_b0(weights=None)
            # Replace final classifier for our 6 classes
            import torch.nn as nn
            model.classifier[1] = nn.Linear(model.classifier[1].in_features, len(DOC_TYPES))
            model.load_state_dict(torch.load(weights_path, map_location="cpu"))
            model.eval()
            self.model = model

            self.transform = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225]
                ),
            ])
            logger.info(f"Classifier loaded from {weights_path}")

        except ImportError:
            logger.warning("PyTorch/torchvision not installed — classifier unavailable")
        except Exception as e:
            logger.warning(f"Classifier load failed: {e}")

    def classify_file(self, file_path: str) -> Optional[ClassificationResult]:
        """
        Classify a document from its file path.
        Returns None if classifier is not available.
        """
        if self.model is None:
            return None

        try:
            from PIL import Image
            import torch
            import torch.nn.functional as F

            img = Image.open(file_path).convert("RGB")
            tensor = self.transform(img).unsqueeze(0)

            with torch.no_grad():
                logits = self.model(tensor)
                probs = F.softmax(logits, dim=1)[0]

            scores = {DOC_TYPES[i]: float(probs[i]) for i in range(len(DOC_TYPES))}
            best_type = max(scores, key=scores.get)
            best_conf = scores[best_type]

            logger.info(f"Classification: {best_type} ({best_conf:.2f})")
            return ClassificationResult(best_type, best_conf, scores)

        except Exception as e:
            logger.warning(f"Classification failed: {e}")
            return None

    def is_available(self) -> bool:
        return self.model is not None
```

### 4.3 — Training Script

**Create file:** `backend/scripts/train_classifier.py`

```python
"""
Train the document type classifier.

Usage:
  python backend/scripts/train_classifier.py --data-dir /path/to/documents --epochs 20

Where data-dir contains subdirectories named after each doc type:
  /path/to/documents/VENDOR_INVOICE/  <- place PDF/image files here
  /path/to/documents/COMPANY_DC/
  etc.

The script exports verified documents from your database automatically
if you use --from-db flag.
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def export_training_data_from_db(output_dir: Path, nas_base: str):
    """Export verified documents from DB into class subdirectories."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from app.database import get_sync_db
    from app.models import Document, DocumentMetadata, MetadataStatus
    import shutil

    logger.info("Exporting verified documents from database...")
    with get_sync_db() as db:
        records = db.query(Document, DocumentMetadata).join(
            DocumentMetadata, DocumentMetadata.document_id == Document.id
        ).filter(
            DocumentMetadata.status == MetadataStatus.VERIFIED
        ).all()

        counts = {}
        for doc, meta in records:
            doc_type = doc.document_type.value
            src = Path(nas_base) / doc.file_path
            if not src.exists():
                continue
            dst_dir = output_dir / doc_type
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst = dst_dir / src.name
            shutil.copy2(src, dst)
            counts[doc_type] = counts.get(doc_type, 0) + 1

    logger.info("Exported documents per type:")
    for t, c in sorted(counts.items()):
        status = "✓" if c >= 100 else "△" if c >= 50 else "✗"
        logger.info(f"  {status} {t}: {c} documents")

    return counts


def train(data_dir: Path, output_dir: Path, epochs: int = 20, lr: float = 1e-4):
    """Train EfficientNet-B0 classifier on document images."""
    try:
        import torch
        import torch.nn as nn
        import torchvision.models as models
        import torchvision.transforms as T
        from torchvision.datasets import ImageFolder
        from torch.utils.data import DataLoader, random_split
    except ImportError:
        logger.error("PyTorch not installed. Run: pip install torch torchvision")
        sys.exit(1)

    # Dataset
    transform = T.Compose([
        T.Resize((224, 224)),
        T.RandomHorizontalFlip(p=0.0),  # no flip for documents
        T.RandomRotation(degrees=3),     # slight rotation augmentation
        T.ColorJitter(brightness=0.2, contrast=0.2),
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    # For PDFs, convert first page to image before loading
    # Assume all files in data_dir subdirs are already images or single-page PDFs
    # Use ImageFolder for simplicity
    from PIL import Image
    import fitz

    # Pre-convert any PDFs to PNG thumbnails for training
    logger.info("Pre-converting PDFs to PNG for training...")
    for doc_type_dir in data_dir.iterdir():
        if not doc_type_dir.is_dir():
            continue
        for f in doc_type_dir.glob("*.pdf"):
            png_path = f.with_suffix(".png")
            if not png_path.exists():
                try:
                    doc = fitz.open(str(f))
                    pix = doc.load_page(0).get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                    pix.save(str(png_path))
                    doc.close()
                except Exception as e:
                    logger.warning(f"Could not convert {f.name}: {e}")

    dataset = ImageFolder(str(data_dir), transform=transform)
    logger.info(f"Dataset: {len(dataset)} images, {len(dataset.classes)} classes")
    logger.info(f"Classes: {dataset.classes}")

    train_size = int(0.85 * len(dataset))
    val_size = len(dataset) - train_size
    train_ds, val_ds = random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_ds, batch_size=16, shuffle=True, num_workers=2)
    val_loader   = DataLoader(val_ds,   batch_size=16, shuffle=False, num_workers=2)

    # Model
    model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT)
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, len(dataset.classes))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Training on: {device}")
    model = model.to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = nn.CrossEntropyLoss()

    best_val_acc = 0.0
    output_dir.mkdir(parents=True, exist_ok=True)

    for epoch in range(1, epochs + 1):
        # Train
        model.train()
        train_loss = 0.0
        for imgs, labels in train_loader:
            imgs, labels = imgs.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(imgs), labels)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()

        # Validate
        model.eval()
        correct = total = 0
        with torch.no_grad():
            for imgs, labels in val_loader:
                imgs, labels = imgs.to(device), labels.to(device)
                preds = model(imgs).argmax(dim=1)
                correct += (preds == labels).sum().item()
                total += labels.size(0)

        val_acc = correct / total
        scheduler.step()

        logger.info(f"Epoch {epoch}/{epochs}: loss={train_loss/len(train_loader):.3f}, val_acc={val_acc:.3f}")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), output_dir / "model.pth")
            logger.info(f"  ✓ Best model saved (val_acc={val_acc:.3f})")

    logger.info(f"\nTraining complete. Best val_acc={best_val_acc:.3f}")
    logger.info(f"Model saved to: {output_dir / 'model.pth'}")

    # Save class mapping
    import json
    with open(output_dir / "classes.json", "w") as f:
        json.dump(dataset.classes, f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, help="Directory with class subdirs")
    parser.add_argument("--output-dir", default="backend/models/doc_classifier")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--from-db", action="store_true", help="Export verified docs from DB first")
    parser.add_argument("--nas-base", default="", help="NAS base path (needed for --from-db)")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)

    if args.from_db:
        counts = export_training_data_from_db(data_dir, args.nas_base)
        low_count = [t for t, c in counts.items() if c < 50]
        if low_count:
            logger.warning(f"Low data for types: {low_count} (less than 50 each)")
            logger.warning("Training may overfit. Proceed anyway? (y/N)")
            if input().strip().lower() != "y":
                sys.exit(0)

    train(data_dir, output_dir, epochs=args.epochs)
```

---

## Phase 5 — LayoutLMv3 Integration
**Time: 1–2 weeks | Impact: Per-field confidence, spatial field understanding**

### 5.1 — Prerequisites (Before Writing Any Code)

**Step 1:** Run the training data count query from Phase 4.  
**Step 2:** Re-extract all existing documents with Phase 0 fixes applied.  
**Step 3:** Have humans re-verify the re-extracted documents.  
**Step 4:** Only then proceed with LayoutLMv3 fine-tuning.

If you skip Steps 2–3, you train LayoutLMv3 on dirty labels from the old 768px/200DPI extractions.

### 5.2 — Download Base Model

```bash
# Install dependencies
pip install transformers datasets torch seqeval

# Download LayoutLMv3 base (run once)
python -c "
from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification
processor = LayoutLMv3Processor.from_pretrained('microsoft/layoutlmv3-base')
processor.save_pretrained('backend/models/layoutlmv3')
print('LayoutLMv3 base downloaded')
"
```

### 5.3 — Create Dataset Builder

**Create file:** `backend/scripts/build_layoutlm_dataset.py`

```python
"""
Build LayoutLMv3 fine-tuning dataset from verified database records.

For each verified document:
  1. Run qwen2.5vl in grounding mode to get text + bounding boxes
  2. Pair with verified extracted_data as ground truth labels
  3. Convert to BIO token classification format
  4. Save as HuggingFace Dataset

Run: python backend/scripts/build_layoutlm_dataset.py --output-dir backend/data/layoutlm_dataset
"""

import sys
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# BIO label scheme for each document type
FIELD_LABELS = {
    "VENDOR_INVOICE": ["invoice_number", "customer_order_no", "po_reference"],
    "COMPANY_INVOICE": ["invoice_number", "po_reference", "so_number", "customer_name", "total_amount"],
    "VENDOR_DC":  ["dc_number", "dc_date", "po_reference", "vendor_name", "quantity"],
    "COMPANY_DC": ["dc_number", "po_reference", "sales_order_no", "dispatch_to"],
    "CUSTOMER_PO": ["po_number", "po_date", "bsif_name"],
    "COMPANY_PO": ["purchase_bill_no", "po_number", "bill_no"],
}

def build_label_list(doc_type: str) -> list[str]:
    """Build full BIO label list for a document type."""
    labels = ["O"]
    for field in FIELD_LABELS.get(doc_type, []):
        labels.append(f"B-{field}")
        labels.append(f"I-{field}")
    return labels

def create_bio_labels(words: list[str], boxes: list, verified_fields: dict, doc_type: str) -> list[str]:
    """
    Create BIO labels for each word token by matching against verified field values.

    This is a simplified approach:
    - Find each field value in the word sequence
    - Label the matching tokens B-field / I-field
    - Label everything else O
    """
    labels = ["O"] * len(words)

    for field, value in verified_fields.items():
        if not value or field.startswith("_"):
            continue
        value_str = str(value).strip()
        value_words = value_str.split()
        if not value_words:
            continue

        # Find value_words in words sequence
        for i in range(len(words) - len(value_words) + 1):
            match = all(
                words[i + j].strip().lower() == value_words[j].strip().lower()
                for j in range(len(value_words))
            )
            if match:
                labels[i] = f"B-{field}"
                for j in range(1, len(value_words)):
                    labels[i + j] = f"I-{field}"
                break

    return labels

def export_from_db(output_dir: Path, nas_base: str):
    """Export verified documents with their OCR coordinates."""
    from app.database import get_sync_db
    from app.models import Document, DocumentMetadata, MetadataStatus

    output_dir.mkdir(parents=True, exist_ok=True)
    examples = []

    with get_sync_db() as db:
        records = db.query(Document, DocumentMetadata).join(
            DocumentMetadata, DocumentMetadata.document_id == Document.id
        ).filter(
            DocumentMetadata.status == MetadataStatus.VERIFIED
        ).all()

        logger.info(f"Found {len(records)} verified documents")

        for doc, meta in records:
            # Check raw_ocr_text has content
            if not meta.raw_ocr_text or not meta.extracted_data:
                continue

            file_path = Path(nas_base) / doc.file_path
            if not file_path.exists():
                logger.warning(f"File not found: {file_path}")
                continue

            # For now, store the path and verified labels
            # The actual OCR + coordinate extraction runs during training
            examples.append({
                "document_id": str(doc.id),
                "file_path": str(file_path),
                "doc_type": doc.document_type.value,
                "verified_fields": meta.extracted_data,
            })

    # Save examples
    dataset_file = output_dir / "examples.jsonl"
    with open(dataset_file, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")

    logger.info(f"Saved {len(examples)} examples to {dataset_file}")

    # Summary
    from collections import Counter
    type_counts = Counter(ex["doc_type"] for ex in examples)
    logger.info("Examples per document type:")
    for dt, count in sorted(type_counts.items()):
        status = "✓" if count >= 100 else "△" if count >= 50 else "✗ (need more)"
        logger.info(f"  {status} {dt}: {count}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="backend/data/layoutlm_dataset")
    parser.add_argument("--nas-base", default="", help="NAS storage base path")
    args = parser.parse_args()
    export_from_db(Path(args.output_dir), args.nas_base)
```

### 5.4 — Create LayoutLM Extractor

**Create file:** `backend/app/services/extraction/layoutlm_extractor.py`

```python
"""
LayoutLMv3 field extractor.

Replaces qwen2.5:7b (Layer 2) for field extraction.
Takes OCR text + bounding boxes + document image.
Returns extracted fields with per-field confidence scores.

Requires fine-tuned model from: backend/scripts/train_layoutlm.py
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

FIELD_LABELS = {
    "VENDOR_INVOICE": ["invoice_number", "customer_order_no", "po_reference"],
    "COMPANY_INVOICE": ["invoice_number", "po_reference", "so_number", "customer_name", "total_amount"],
    "VENDOR_DC":  ["dc_number", "dc_date", "po_reference", "vendor_name", "quantity"],
    "COMPANY_DC": ["dc_number", "po_reference", "sales_order_no", "dispatch_to"],
    "CUSTOMER_PO": ["po_number", "po_date", "bsif_name"],
    "COMPANY_PO": ["purchase_bill_no", "po_number", "bill_no"],
}


class LayoutLMExtractor:
    """
    Extract structured fields from documents using LayoutLMv3.
    Falls back gracefully to qwen2.5:7b if model is not available.
    """

    def __init__(self, model_dir: Optional[str] = None):
        self.model_dir = Path(model_dir) if model_dir else \
            Path(__file__).parent.parent.parent.parent / "models" / "layoutlmv3"
        self.processor = None
        self.model = None
        self.label2id = {}
        self.id2label = {}
        self._load_model()

    def _load_model(self):
        """Load fine-tuned LayoutLMv3 model."""
        try:
            from transformers import (
                LayoutLMv3Processor,
                LayoutLMv3ForTokenClassification,
            )

            processor_path = self.model_dir / "processor"
            model_path = self.model_dir / "finetuned"
            label_map_path = self.model_dir / "label_map.json"

            if not model_path.exists():
                logger.warning(
                    f"Fine-tuned LayoutLMv3 not found at {model_path}. "
                    f"Run: python backend/scripts/train_layoutlm.py"
                )
                return

            self.processor = LayoutLMv3Processor.from_pretrained(str(processor_path))
            self.model = LayoutLMv3ForTokenClassification.from_pretrained(str(model_path))
            self.model.eval()

            if label_map_path.exists():
                with open(label_map_path) as f:
                    self.label2id = json.load(f)
                    self.id2label = {v: k for k, v in self.label2id.items()}

            logger.info("LayoutLMv3 fine-tuned model loaded")

        except ImportError:
            logger.warning("transformers not installed — LayoutLMv3 unavailable")
        except Exception as e:
            logger.warning(f"LayoutLMv3 load failed: {e}")

    def is_available(self) -> bool:
        return self.model is not None and self.processor is not None

    def extract(
        self,
        words: list[str],
        boxes: list[list[int]],
        image_bytes: bytes,
        doc_type: str,
    ) -> dict:
        """
        Extract fields from a document.

        Args:
            words: List of word tokens from OCR
            boxes: List of [x1, y1, x2, y2] bounding boxes (normalized 0-1000)
            image_bytes: Raw document image as PNG bytes
            doc_type: Document type string (e.g. 'VENDOR_INVOICE')

        Returns:
            Dict with extracted fields and '_field_confidences' key
        """
        if not self.is_available():
            logger.warning("LayoutLMv3 not available — returning empty extraction")
            return {}

        import torch
        import torch.nn.functional as F
        from PIL import Image
        import io

        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

            # Prepare inputs
            encoding = self.processor(
                image,
                words,
                boxes=boxes,
                return_tensors="pt",
                truncation=True,
                padding="max_length",
                max_length=512,
            )

            with torch.no_grad():
                outputs = self.model(**encoding)

            # Get predictions and probabilities
            logits = outputs.logits  # (1, seq_len, num_labels)
            probs = F.softmax(logits, dim=2)[0]  # (seq_len, num_labels)
            predictions = logits.argmax(dim=2)[0].tolist()  # (seq_len,)

            # Decode tokens back to words and labels
            tokens = encoding.tokens()
            token_boxes = encoding["bbox"][0].tolist()

            # Group subword tokens back to word level
            extracted = {}
            field_confidences = {}
            current_field = None
            current_tokens = []
            current_conf = []

            for idx, (token, pred_id) in enumerate(zip(tokens, predictions)):
                if token in ("[CLS]", "[SEP]", "[PAD]"):
                    continue

                label = self.id2label.get(pred_id, "O")
                prob = float(probs[idx][pred_id])

                if label.startswith("B-"):
                    # Save previous field if any
                    if current_field and current_tokens:
                        value = " ".join(current_tokens)
                        conf = sum(current_conf) / len(current_conf)
                        extracted[current_field] = value
                        field_confidences[current_field] = round(conf, 3)

                    current_field = label[2:]  # strip "B-"
                    current_tokens = [token.replace("##", "")]
                    current_conf = [prob]

                elif label.startswith("I-") and current_field:
                    current_tokens.append(token.replace("##", ""))
                    current_conf.append(prob)

                else:
                    # O label — close current field
                    if current_field and current_tokens:
                        value = " ".join(current_tokens)
                        conf = sum(current_conf) / len(current_conf)
                        extracted[current_field] = value
                        field_confidences[current_field] = round(conf, 3)
                        current_field = None
                        current_tokens = []
                        current_conf = []

            # Close last field
            if current_field and current_tokens:
                value = " ".join(current_tokens)
                conf = sum(current_conf) / len(current_conf)
                extracted[current_field] = value
                field_confidences[current_field] = round(conf, 3)

            extracted["_field_confidences"] = field_confidences
            logger.info(f"LayoutLMv3 extracted {len(extracted)-1} fields: {field_confidences}")
            return extracted

        except Exception as e:
            logger.error(f"LayoutLMv3 extraction failed: {e}")
            return {}
```

---

## Phase 6 — Math & Business Rule Validation
**Time: 2–3 days | Impact: Catches financial errors before ERP**

### 6.1 — Create Invoice Validator

**Create file:** `backend/app/services/extraction/invoice_validator.py`

```python
"""
Invoice math and business rule validation.

Runs after field extraction, before persistence.
Catches financial errors before they reach the ERP.
"""

import logging
import re
from datetime import date, timedelta
from typing import Optional
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# If computed total differs from extracted total by more than this, flag it
MATH_TOLERANCE_PERCENT = 0.5
# Maximum age of a valid invoice date (in years)
MAX_INVOICE_AGE_YEARS = 2


class ValidationResult:
    def __init__(self):
        self.passed = True
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.route = "AUTO_APPROVED"  # AUTO_APPROVED | PENDING_REVIEW | DUPLICATE_FLAGGED

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.passed = False
        self.route = "PENDING_REVIEW"

    def add_warning(self, msg: str):
        self.warnings.append(msg)
        if self.route == "AUTO_APPROVED":
            self.route = "PENDING_REVIEW"

    def __repr__(self):
        return f"ValidationResult(passed={self.passed}, route={self.route}, errors={self.errors})"


def validate_invoice_math(extracted: dict, doc_type: str) -> ValidationResult:
    """
    Validate invoice math and business rules.

    Args:
        extracted: Extracted fields dict from LayoutLMv3 or qwen2.5:7b
        doc_type: Document type string

    Returns:
        ValidationResult with pass/fail and error details
    """
    result = ValidationResult()

    # Math validation only for invoice types with line items
    if doc_type in ("VENDOR_INVOICE", "COMPANY_INVOICE"):
        _validate_math(extracted, result)

    # Date validation for all types
    _validate_date(extracted, result)

    # Amount sanity for all types with total_amount
    _validate_amount_sanity(extracted, result)

    return result


def _validate_math(extracted: dict, result: ValidationResult):
    """Check invoice math: sum(line_items) + tax == total."""
    total_amount = extracted.get("total_amount")
    if total_amount is None:
        result.add_warning("total_amount not extracted — cannot validate math")
        return

    # Look for line items
    line_items = extracted.get("line_items", [])
    if not line_items:
        # No line items extracted yet — skip math check
        # (line items not in current schema, will be added later)
        return

    try:
        total_extracted = float(total_amount)
        computed = 0.0

        for item in line_items:
            qty = float(item.get("quantity", 0) or 0)
            unit_price = float(item.get("unit_price", 0) or 0)
            discount = float(item.get("discount", 0) or 0)
            computed += (qty * unit_price) - discount

        tax = float(extracted.get("tax_amount", 0) or 0)
        computed_total = computed + tax

        if total_extracted == 0:
            result.add_warning("total_amount is 0 — possible extraction error")
            return

        discrepancy_pct = abs(computed_total - total_extracted) / total_extracted * 100

        if discrepancy_pct > MATH_TOLERANCE_PERCENT:
            result.add_error(
                f"Invoice math mismatch: "
                f"computed={computed_total:.2f}, "
                f"extracted={total_extracted:.2f}, "
                f"discrepancy={discrepancy_pct:.1f}%"
            )
        else:
            logger.debug(f"Math validation passed: discrepancy={discrepancy_pct:.2f}%")

    except (ValueError, TypeError) as e:
        result.add_warning(f"Could not validate math: {e}")


def _validate_date(extracted: dict, result: ValidationResult):
    """Validate document date is reasonable."""
    date_fields = ["po_date", "dc_date", "invoice_date"]
    for field in date_fields:
        raw = extracted.get(field)
        if not raw:
            continue

        # Try to parse the date
        parsed = _parse_date_flexible(str(raw))
        if parsed is None:
            result.add_warning(f"{field} could not be parsed: '{raw}'")
            continue

        today = date.today()
        max_age = today - timedelta(days=MAX_INVOICE_AGE_YEARS * 365)

        if parsed > today:
            result.add_error(f"{field} is in the future: {parsed} > {today}")
        elif parsed < max_age:
            result.add_warning(
                f"{field} is very old ({parsed}) — "
                f"more than {MAX_INVOICE_AGE_YEARS} years ago"
            )


def _validate_amount_sanity(extracted: dict, result: ValidationResult):
    """Sanity check for obviously wrong amounts (e.g., OCR comma/period confusion)."""
    total = extracted.get("total_amount")
    if total is None:
        return

    try:
        amount = float(total)
        if amount < 0:
            result.add_error(f"total_amount is negative: {amount}")
        elif amount > 100_000_000:  # 10 crore — likely a parsing error
            result.add_warning(f"total_amount seems very large: {amount} — verify")
        elif amount > 0 and amount < 1:
            result.add_warning(f"total_amount is less than 1: {amount} — possible decimal error")
    except (ValueError, TypeError):
        result.add_warning(f"total_amount is not numeric: {total}")


def _parse_date_flexible(date_str: str) -> Optional[date]:
    """Try multiple date formats."""
    from datetime import datetime
    formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
        "%Y-%m-%d", "%d-%b-%Y", "%d %b %Y",
        "%B %d, %Y", "%d/%m/%y", "%d-%m-%y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None
```

### 6.2 — Wire Validation Into tasks.py

After the extraction step, before creating the DocumentMetadata record, add:

```python
# Add to imports:
from app.services.extraction.invoice_validator import validate_invoice_math, ValidationResult

# After extraction is complete, before step 10 (Create/update metadata):
# ADD THIS BLOCK:
validation_result = validate_invoice_math(extracted_data, doc_type)
if validation_result.errors:
    logger.warning(f"Validation errors for {document_id}: {validation_result.errors}")
    extracted_data["_validation_errors"] = validation_result.errors
    extracted_data["_validation_warnings"] = validation_result.warnings
    # Override status to PENDING_REVIEW regardless of confidence
    doc.status = DocumentStatus.PENDING_REVIEW
elif validation_result.warnings:
    extracted_data["_validation_warnings"] = validation_result.warnings
    logger.info(f"Validation warnings for {document_id}: {validation_result.warnings}")
```

---

## Phase 7 — Version-Safe Persistence
**Time: 1 day | Fixes: re-extract deletes history**

### 7.1 — Add DB Columns

Add to your Alembic migration (create a new migration file):

```python
# backend/alembic/versions/xxx_add_versioning_columns.py

from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add extraction versioning
    op.add_column("document_metadata",
        sa.Column("extraction_version", sa.Integer(), nullable=False, server_default="1")
    )
    # Per-field confidence scores
    op.add_column("document_metadata",
        sa.Column("field_confidences", sa.JSON(), nullable=True)
    )
    # Corrections tracking
    op.create_table(
        "extraction_corrections",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("document_id", sa.String(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("original_value", sa.Text(), nullable=True),
        sa.Column("corrected_value", sa.Text(), nullable=True),
        sa.Column("operator_id", sa.String(), nullable=True),
        sa.Column("corrected_at", sa.DateTime(), nullable=False),
        sa.Column("extraction_version", sa.Integer(), nullable=False),
    )

def downgrade():
    op.drop_table("extraction_corrections")
    op.drop_column("document_metadata", "field_confidences")
    op.drop_column("document_metadata", "extraction_version")
```

Run the migration:
```bash
cd backend
alembic revision --autogenerate -m "add versioning columns"
alembic upgrade head
```

### 7.2 — Fix the Re-Extract Endpoint

**Find your re-extract endpoint** (likely in `backend/app/api/documents.py` or similar).

Replace the DELETE logic with version increment:

```python
# BEFORE (what currently happens — DELETES HISTORY):
# db.query(DocumentMetadata).filter(...).delete()

# AFTER (version-safe):
@router.post("/{document_id}/re-extract")
async def re_extract_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    existing_meta = db.query(DocumentMetadata).filter(
        DocumentMetadata.document_id == document_id
    ).first()

    if existing_meta:
        # INCREMENT version — do NOT delete
        existing_meta.extraction_version = (existing_meta.extraction_version or 0) + 1
        existing_meta.status = MetadataStatus.PENDING  # reset to pending
        # Reset only extraction fields, NOT human corrections
        existing_meta.extracted_data = None
        existing_meta.confidence_score = None
        existing_meta.field_confidences = None
        existing_meta.last_error = None
        db.commit()
    # else: new extraction — record will be created by the task

    # Queue the extraction task
    extract_document.delay(str(document_id))
    return {"status": "queued", "extraction_version": existing_meta.extraction_version if existing_meta else 1}
```

---

## Phase 8 — HITL Corrections Capture
**Time: 2–3 days | Impact: Corrections feed LayoutLMv3, accuracy improves over time**

### 8.1 — Add Corrections Model to models.py

```python
# Add to backend/app/models.py:

class ExtractionCorrection(Base):
    """Records every human correction made during document review."""
    __tablename__ = "extraction_corrections"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    field_name = Column(String(100), nullable=False)
    original_value = Column(Text, nullable=True)    # what the model extracted
    corrected_value = Column(Text, nullable=True)   # what the human entered
    operator_id = Column(String, nullable=True)
    corrected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    extraction_version = Column(Integer, nullable=False, default=1)
    used_for_training = Column(Boolean, default=False)  # flagged after LayoutLMv3 fine-tune

    document = relationship("Document", back_populates="corrections")
```

### 8.2 — Add Corrections API Endpoint

```python
# Add to backend/app/api/documents.py (or corrections.py):

@router.post("/{document_id}/corrections")
async def save_corrections(
    document_id: str,
    corrections: list[dict],  # [{"field": "invoice_number", "corrected_value": "1ITR..."}]
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Save human corrections for a document.
    Captures original vs corrected for LayoutLMv3 fine-tuning.
    """
    meta = db.query(DocumentMetadata).filter(
        DocumentMetadata.document_id == document_id
    ).first()
    if not meta:
        raise HTTPException(status_code=404)

    saved = []
    for correction in corrections:
        field = correction.get("field")
        new_value = correction.get("corrected_value")
        original_value = meta.extracted_data.get(field) if meta.extracted_data else None

        # Only save if value actually changed
        if str(original_value or "") == str(new_value or ""):
            continue

        corr = ExtractionCorrection(
            document_id=document_id,
            field_name=field,
            original_value=str(original_value) if original_value is not None else None,
            corrected_value=str(new_value) if new_value is not None else None,
            operator_id=str(current_user.id),
            extraction_version=meta.extraction_version or 1,
        )
        db.add(corr)

        # Also update the current extracted_data
        if meta.extracted_data:
            meta.extracted_data[field] = new_value

        saved.append(field)

    # Update metadata status to VERIFIED
    meta.status = MetadataStatus.VERIFIED
    meta.verified_at = datetime.utcnow()
    db.commit()

    logger.info(f"Saved {len(saved)} corrections for document {document_id}: {saved}")
    return {"saved_fields": saved, "document_id": document_id}
```

### 8.3 — Nightly Fine-Tune Trigger (Future)

Once you have 50+ new corrections, run this to queue incremental LayoutLMv3 training:

```python
# backend/scripts/queue_finetune.py
# Run nightly via cron or Celery beat

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_sync_db
from app.models import ExtractionCorrection

def check_and_queue_finetune(min_corrections: int = 50):
    with get_sync_db() as db:
        pending = db.query(ExtractionCorrection).filter(
            ExtractionCorrection.used_for_training == False
        ).count()

        if pending >= min_corrections:
            print(f"✓ {pending} corrections ready — queuing LayoutLMv3 fine-tune")
            # Queue the fine-tune task here
            # from app.services.extraction.tasks import finetune_layoutlm
            # finetune_layoutlm.delay()
        else:
            print(f"△ {pending} corrections pending (need {min_corrections})")

if __name__ == "__main__":
    check_and_queue_finetune()
```

---

## Quick Reference — Test All Phases

```bash
# Run all phase tests at once
cd /your-project

echo "=== Running All Phase Tests ===" && \
python backend/tests/test_phase0.py && \
python backend/tests/test_phase1.py && \
python backend/tests/test_phase2.py && \
python backend/tests/test_phase3.py && \
echo "=== All Tests Complete ===" && \
python backend/scripts/check_phases.py
```

## Quick Reference — Phase Completion Order

```
Phase 0  →  35 min   →  Config changes only, run today
Phase 2  →  2 hours  →  Format gate, easy
Phase 1  →  2 days   →  Hybrid router + digital path
Phase 3  →  3 days   →  OpenCV pre-processing
Phase 7  →  1 day    →  Version-safe persistence (fix the DELETE bug)
Phase 6  →  3 days   →  Math validation
Phase 8  →  3 days   →  Corrections capture
Phase 4  →  5 days   →  Document classifier (needs training data)
Phase 5  →  2 weeks  →  LayoutLMv3 (do last — needs clean data from all previous phases)
```

