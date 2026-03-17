"""
Unit tests for PDF upload validation logic.

Rules (from purchase_orders.py upload endpoint):
  - Only PDF files accepted (MIME: application/pdf)
  - Magic bytes must start with %PDF-
  - Max file size: 25MB
  - Filename must end with .pdf (case-insensitive)
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))

import pytest


# ── Pure validation helpers (mirrors purchase_orders.py upload logic) ─────────

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB
PDF_MAGIC = b"%PDF-"


def validate_pdf_upload(
    filename: str,
    content_type: str,
    file_bytes: bytes,
) -> list[str]:
    """Returns list of validation error strings. Empty = valid."""
    errors = []

    if not filename.lower().endswith(".pdf"):
        errors.append("Only PDF files are accepted.")

    if content_type not in ("application/pdf", "application/octet-stream"):
        errors.append(f"Invalid content type: {content_type}. Expected application/pdf.")

    if not file_bytes.startswith(PDF_MAGIC):
        errors.append("File does not appear to be a valid PDF (missing %PDF- header).")

    if len(file_bytes) > MAX_FILE_SIZE:
        errors.append(f"File size exceeds 25MB limit ({len(file_bytes) / 1024 / 1024:.1f}MB).")

    return errors


# ── Valid PDF ─────────────────────────────────────────────────────────────────

class TestValidPdf:

    def test_valid_pdf_passes(self):
        errors = validate_pdf_upload(
            filename="invoice.pdf",
            content_type="application/pdf",
            file_bytes=b"%PDF-1.4 content here",
        )
        assert errors == []

    def test_uppercase_extension_passes(self):
        errors = validate_pdf_upload(
            filename="INVOICE.PDF",
            content_type="application/pdf",
            file_bytes=b"%PDF-1.7 content",
        )
        assert errors == []


# ── File type validation ───────────────────────────────────────────────────────

class TestFileTypeValidation:

    def test_jpg_rejected(self):
        errors = validate_pdf_upload(
            filename="scan.jpg",
            content_type="image/jpeg",
            file_bytes=b"\xff\xd8\xff\xe0 jpeg content",
        )
        assert any("PDF" in e for e in errors)
        assert any("jpeg" in e.lower() or "content type" in e.lower() for e in errors)

    def test_png_rejected(self):
        errors = validate_pdf_upload(
            filename="scan.png",
            content_type="image/png",
            file_bytes=b"\x89PNG\r\n content",
        )
        assert any("PDF" in e for e in errors)

    def test_word_doc_rejected(self):
        errors = validate_pdf_upload(
            filename="document.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            file_bytes=b"PK\x03\x04 zip content",
        )
        assert len(errors) > 0

    def test_fake_pdf_extension_real_jpg_rejected(self):
        """File named .pdf but actually contains JPEG bytes."""
        errors = validate_pdf_upload(
            filename="fake.pdf",
            content_type="application/pdf",
            file_bytes=b"\xff\xd8\xff\xe0 jpeg bytes",
        )
        assert any("PDF" in e and "header" in e.lower() for e in errors)


# ── File size validation ───────────────────────────────────────────────────────

class TestFileSizeValidation:

    def test_exactly_25mb_passes(self):
        """25MB exactly is the boundary — should pass."""
        errors = validate_pdf_upload(
            filename="large.pdf",
            content_type="application/pdf",
            file_bytes=b"%PDF-1.4 " + b"x" * (MAX_FILE_SIZE - 9),
        )
        assert errors == []

    def test_one_byte_over_25mb_rejected(self):
        errors = validate_pdf_upload(
            filename="toobig.pdf",
            content_type="application/pdf",
            file_bytes=b"%PDF-1.4 " + b"x" * (MAX_FILE_SIZE - 9 + 1),
        )
        assert any("25MB" in e or "size" in e.lower() for e in errors)

    def test_small_file_passes(self):
        errors = validate_pdf_upload(
            filename="tiny.pdf",
            content_type="application/pdf",
            file_bytes=b"%PDF-1.4 small content",
        )
        assert errors == []


# ── Magic bytes check ─────────────────────────────────────────────────────────

class TestMagicBytes:

    def test_correct_magic_bytes_passes(self):
        for version in [b"%PDF-1.0", b"%PDF-1.4", b"%PDF-1.7", b"%PDF-2.0"]:
            errors = validate_pdf_upload(
                filename="doc.pdf",
                content_type="application/pdf",
                file_bytes=version + b" content",
            )
            assert errors == [], f"Failed for version {version}"

    def test_wrong_magic_bytes_rejected(self):
        errors = validate_pdf_upload(
            filename="doc.pdf",
            content_type="application/pdf",
            file_bytes=b"PK\x03\x04 not a pdf",
        )
        assert any("header" in e.lower() for e in errors)

    def test_empty_file_rejected(self):
        errors = validate_pdf_upload(
            filename="empty.pdf",
            content_type="application/pdf",
            file_bytes=b"",
        )
        assert len(errors) > 0