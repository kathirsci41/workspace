"""
PaddleOCR-VL-1.6 fallback OCR service (Sprint 2, Task 2.3).

Model:     PaddlePaddle/PaddleOCR-VL-1.6 (0.9B VLM, HuggingFace)
Benchmark: 96.33 OmniDocBench — #1 open-source document VLM (benchmarked 2025)
Source:    https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6

NOT available via Ollama — loaded directly via transformers library.
Requires GPU with ≥ 4 GB VRAM.  ~1.8 GB model download on first call.

Usage:
  Called by extraction_service.py when PP-OCRv5 (PaddleOCR GPU route) fails
  or returns low-confidence / empty text.  Replaces the cloud-based GLM-OCR
  fallback for scanned documents on GPU machines.

Integration:
  - Registered as OCR provider "paddleocr_vl" in the provider registry.
  - OCR_PROVIDER=paddleocr_vl  →  use as primary (no PaddleOCR needed)
  - Used automatically as fallback when OCR_PADDLE_VL_FALLBACK=true (default
    on GPU machines when transformers + torch are installed).

Safe: never raises.  Returns empty string on failure so callers keep
PP-OCRv5 result.
"""
from __future__ import annotations

import importlib.util
import logging
import time
from pathlib import Path

from app.services.extraction.ocr_providers.base import OcrProviderBase, OcrProviderResult

logger = logging.getLogger(__name__)

_MODEL_ID = "PaddlePaddle/PaddleOCR-VL-1.6"

_model = None
_processor = None
_load_error: str | None = None   # cached failure reason


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

def _transformers_available() -> bool:
    return (
        importlib.util.find_spec("transformers") is not None
        and importlib.util.find_spec("torch") is not None
    )


# ---------------------------------------------------------------------------
# Model loading (lazy, once per process)
# ---------------------------------------------------------------------------

def _load_model() -> None:
    """Load PaddleOCR-VL-1.6 from HuggingFace.  Idempotent — only loads once."""
    global _model, _processor, _load_error

    if _model is not None:
        return
    if _load_error is not None:
        return  # already tried and failed — don't retry

    if not _transformers_available():
        _load_error = "transformers or torch not installed"
        logger.warning("PaddleOCR-VL-1.6: %s", _load_error)
        return

    logger.info(
        "Loading PaddleOCR-VL-1.6 from HuggingFace (first call — may take ~30 s)..."
    )
    try:
        from transformers import AutoModelForCausalLM, AutoProcessor  # noqa: PLC0415
        import torch  # noqa: PLC0415

        _processor = AutoProcessor.from_pretrained(_MODEL_ID, trust_remote_code=True)
        _model = AutoModelForCausalLM.from_pretrained(
            _MODEL_ID,
            trust_remote_code=True,
            torch_dtype=torch.float16,
            device_map="auto",
        )
        logger.info("PaddleOCR-VL-1.6 loaded successfully.")
    except Exception as exc:
        _load_error = str(exc)
        _model = None
        _processor = None
        logger.error("Failed to load PaddleOCR-VL-1.6: %s", exc)


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

_OCR_PROMPT = (
    "Extract all text from this document image exactly as it appears. "
    "Preserve the original layout, numbers, and structure. "
    "Return plain text only."
)


def extract_text_vl(image_path: str) -> str:
    """
    Run PaddleOCR-VL-1.6 on image_path and return extracted text.

    Returns empty string on failure — caller falls back to PP-OCRv5 result.
    Safe: never raises.
    """
    _load_model()
    if _model is None or _processor is None:
        logger.debug(
            "PaddleOCR-VL-1.6 not available (%s) — skipping VLM fallback",
            _load_error or "unknown",
        )
        return ""

    try:
        from PIL import Image  # noqa: PLC0415
        import torch  # noqa: PLC0415

        image = Image.open(image_path).convert("RGB")

        inputs = _processor(
            text=_OCR_PROMPT,
            images=image,
            return_tensors="pt",
        ).to(_model.device)

        with torch.no_grad():
            output_ids = _model.generate(
                **inputs,
                max_new_tokens=2048,
                do_sample=False,
            )

        # Decode only the newly generated tokens (skip the prompt tokens)
        input_len = inputs["input_ids"].shape[1]
        generated = output_ids[0][input_len:]
        text = _processor.decode(generated, skip_special_tokens=True)
        return text.strip()

    except Exception as exc:
        logger.warning("PaddleOCR-VL-1.6 inference failed on %s: %s", image_path, exc)
        return ""


# ---------------------------------------------------------------------------
# OcrProviderBase adapter
# ---------------------------------------------------------------------------

class PaddleOcrVlProvider(OcrProviderBase):
    """
    OcrProviderBase adapter for PaddleOCR-VL-1.6.

    Registered as "paddleocr_vl" in the provider registry.
    Can be used as OCR_PROVIDER=paddleocr_vl or as automatic fallback.
    """

    @property
    def provider_name(self) -> str:
        return "paddleocr_vl"

    @property
    def supports_header(self) -> bool:
        return True  # VLM reads full page including header region

    def is_available(self) -> bool:
        return _transformers_available()

    def run_full_page(
        self,
        file_path: str,
        *,
        max_pages: int,
        dpi: int,
        timeout_seconds: int,
    ) -> OcrProviderResult:
        if not _transformers_available():
            return OcrProviderResult(
                provider_name=self.provider_name,
                source_type="ocr",
                raw_text="",
                success=False,
                error="transformers or torch not installed",
                duration_ms=0,
                model=_MODEL_ID,
            )

        started = time.perf_counter()
        text = extract_text_vl(file_path)
        elapsed_ms = round((time.perf_counter() - started) * 1000)

        if text:
            return OcrProviderResult(
                provider_name=self.provider_name,
                source_type="ocr",
                raw_text=text,
                success=True,
                error=None,
                duration_ms=elapsed_ms,
                model=_MODEL_ID,
            )

        return OcrProviderResult(
            provider_name=self.provider_name,
            source_type="ocr",
            raw_text="",
            success=False,
            error=_load_error or "PaddleOCR-VL-1.6 returned empty text",
            duration_ms=elapsed_ms,
            model=_MODEL_ID,
        )
