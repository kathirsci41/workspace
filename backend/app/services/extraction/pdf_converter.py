import io
import logging
import fitz  # PyMuPDF
from PIL import Image

logger = logging.getLogger(__name__)

# Maximum image dimension (width or height) for OCR models.
# glm-ocr (1.1B) crashes with GGML tensor errors on large images.
# 768 gives enough headroom — 1024 still triggers intermittent 500s.
MAX_IMAGE_DIM = 768

# Vision-model patch size.  Ensuring both width and height are
# multiples of this prevents GGML tensor-dimension assertions
# ("a->ne[2]*4 == b->ne[0]") inside the CogVLM vision encoder.
PATCH_SIZE = 14


class PDFConversionError(Exception):
    pass


class PDFConverter:
    def __init__(self, dpi: int = 200, max_pages: int = 10, max_image_dim: int = MAX_IMAGE_DIM):
        self.dpi = dpi
        self.max_pages = max_pages
        self.max_image_dim = max_image_dim

    def convert_to_images(self, pdf_path: str) -> list[bytes]:
        """Convert PDF pages to PNG images, resized to fit OCR model limits."""
        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            raise PDFConversionError(f"Cannot open PDF: {e}")

        total_pages = doc.page_count
        if total_pages == 0:
            doc.close()
            raise PDFConversionError("PDF has no pages")

        # Determine which pages to process
        if total_pages <= self.max_pages:
            page_indices = list(range(total_pages))
        elif self.max_pages == 1:
            page_indices = [0]  # first page only
        else:
            # First half + last half to capture headers and totals
            half = self.max_pages // 2
            first_half = list(range(half))
            last_half = list(range(total_pages - half, total_pages))
            page_indices = first_half + last_half

        images = []
        zoom = self.dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)

        for i in page_indices:
            try:
                page = doc.load_page(i)
                pix = page.get_pixmap(matrix=mat)  # type: ignore[attr-defined]
                raw_png = pix.tobytes("png")

                # Resize if exceeds max dimension for the OCR model
                img = Image.open(io.BytesIO(raw_png))
                if max(img.size) > self.max_image_dim:
                    img.thumbnail(
                        (self.max_image_dim, self.max_image_dim),
                        Image.Resampling.LANCZOS,
                    )

                # Snap both dimensions down to the nearest multiple
                # of the vision-model patch size to avoid GGML
                # tensor assertion failures.
                w, h = img.size
                new_w = (w // PATCH_SIZE) * PATCH_SIZE
                new_h = (h // PATCH_SIZE) * PATCH_SIZE
                if (new_w, new_h) != (w, h) and new_w > 0 and new_h > 0:
                    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                if img.size != Image.open(io.BytesIO(raw_png)).size:
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    raw_png = buf.getvalue()
                    logger.info(
                        f"Page {i}: resized to {img.size} "
                        f"({len(raw_png)/1024:.0f} KB)"
                    )

                images.append(raw_png)
            except Exception as e:
                logger.warning(f"Failed to convert page {i}: {e}")
                continue

        doc.close()

        if not images:
            raise PDFConversionError("No pages could be converted")

        return images

    def get_page_count(self, pdf_path: str) -> int:
        """Get page count of a PDF."""
        try:
            doc = fitz.open(pdf_path)
            count = doc.page_count
            doc.close()
            return count
        except Exception as e:
            raise PDFConversionError(f"Cannot read PDF: {e}")
