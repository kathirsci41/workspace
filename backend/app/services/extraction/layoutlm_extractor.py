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
