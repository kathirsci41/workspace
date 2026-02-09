import os
import logging
import tempfile

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# DPI for conversion — 200 balances quality vs size for OCR
DEFAULT_DPI = 200


def pdf_to_images(pdf_path: str, dpi: int = DEFAULT_DPI) -> list[str]:
    """
    Convert a PDF file to a list of JPEG image file paths using PyMuPDF.

    For single-page PDFs (most documents), returns a single image.
    For multi-page PDFs, returns one image per page.

    Args:
        pdf_path: Path to the PDF file
        dpi: Resolution for conversion (default 200)

    Returns:
        List of temporary image file paths (JPEG)
    """
    # Normalize path separators for cross-platform compatibility
    # Handles mixed paths like "/path\\to\\file" from database
    pdf_path = pdf_path.replace('\\', '/')

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # Create temp directory for images
    temp_dir = tempfile.mkdtemp(prefix="ocr_")

    try:
        doc = fitz.open(pdf_path)
        image_paths = []

        for page_num in range(doc.page_count):
            page = doc[page_num]
            # Set zoom level based on DPI (72 is base DPI for PyMuPDF)
            zoom = dpi / 72
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))

            image_path = os.path.join(temp_dir, f"page_{page_num + 1}.jpg")
            pix.save(image_path, "JPEG")
            image_paths.append(image_path)
            logger.info(f"Converted page {page_num + 1} -> {image_path}")

        doc.close()
        return image_paths

    except Exception as e:
        logger.error(f"PDF conversion failed for {pdf_path}: {e}")
        raise


def cleanup_temp_images(image_paths: list[str]):
    """Remove temporary image files after extraction."""
    for path in image_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            logger.warning(f"Failed to cleanup {path}: {e}")

    # Also remove the temp directory
    if image_paths:
        temp_dir = os.path.dirname(image_paths[0])
        try:
            os.rmdir(temp_dir)
        except Exception:
            pass
