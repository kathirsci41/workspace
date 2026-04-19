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

import logging
import numpy as np

logger = logging.getLogger(__name__)

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning(
        "OpenCV not installed — scan pre-processing disabled. "
        "Run: pip install opencv-python-headless"
    )


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
        return {"quality": "unknown", "cv2_available": False, "quality_score": 0}

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
