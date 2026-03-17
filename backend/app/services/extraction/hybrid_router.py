"""
Hybrid Router - decides whether a document goes through:
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

        # Unknown format - default to scanned (safer)
        logger.warning(f"Unknown format {suffix}, defaulting to scanned route")
        return ExtractionRoute.SCANNED
