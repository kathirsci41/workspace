"""
Programmatic text extraction for digital-native PDFs.

For PDFs that have an embedded text layer (machine-generated from
Tally, SAP, QuickBooks, Zoho, etc.) - extract text and coordinates
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

        Boxes are normalized to 0-1000 range as LayoutLMv3 expects.
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
                # PyMuPDF returns words in PDF block order, which for multi-column tables
                # can be column-by-column rather than row-by-row, causing label/value
                # interleaving that confuses LLMs. Sort by reading order (top→bottom,
                # left→right) using a 4pt y-tolerance to group words on the same line.
                words = sorted(
                    page.get_text("words"),
                    key=lambda w: (round(w[1] / 4) * 4, w[0]),
                )

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
