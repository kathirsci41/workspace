"""
BBox spatial field extractor for digital invoice PDFs.
Uses label-proximity rules on LiteParse bboxes.

Algorithm:
  1. Find label bbox matching known label text (e.g. "Invoice No", "GSTIN", "Date")
  2. Value = nearest bbox to the RIGHT of label on same row (ΔY < ROW_TOLERANCE)
     OR nearest bbox BELOW label within BELOW_MAX_Y distance if right is empty
  3. Row detection: bboxes with |y_a - y_b| < ROW_TOLERANCE are on the same row.
  4. Table detection: bboxes where x-positions form consistent column bands = table region.
     Header fields extracted OUTSIDE table region only; line items extracted separately.

Tuning constants — adjust if fixtures regress:
  ROW_TOLERANCE = 5    # pt — same row if ΔY < 5
  BELOW_MAX_Y   = 25   # pt — value "below" label if ΔY < 25
  RIGHT_MAX_X   = 300  # pt — value is "right of label" if ΔX < 300
"""
from __future__ import annotations

import re
from typing import Any

# ── Spatial tolerances (pt) ──────────────────────────────────────────────────
ROW_TOLERANCE = 5
BELOW_MAX_Y   = 25
RIGHT_MAX_X   = 300

# ── Label → field_name mapping (canonical, document-type-agnostic) ───────────
# Multiple label variants per field — first match wins.
LABEL_MAP: dict[str, list[str]] = {
    # Buyer / Customer
    "customer_name":      ["bill to", "buyer", "sold to", "customer name", "billed to"],
    "customer_gstin":     ["buyer gstin", "bill to gstin", "gstin of recipient"],
    # Vendor
    "vendor_name":        ["sold by", "from", "vendor", "seller", "supplier"],
    "vendor_gstin":       ["gstin", "supplier gstin", "seller gstin", "vendor gstin"],
    # Order references
    "po_reference":       ["po no", "p.o. no", "purchase order no", "po number", "po #"],
    "so_no":              ["so no", "s.o. no", "sales order no", "so number"],
    "customer_po_no":     ["your po", "customer po", "customer order no", "order no"],
    "vendor_invoice_no":  ["invoice no", "invoice number", "bill no", "tax invoice no"],
    "dc_number":          ["dc no", "challan no", "delivery challan no", "dc number"],
    # Dates
    "invoice_date":       ["invoice date", "bill date", "date of invoice", "date"],
    "dc_date":            ["challan date", "dc date", "delivery date"],
    "po_date":            ["po date", "order date", "purchase order date"],
    # Financial header (line totals handled by table extractor)
    "taxable_amount":     ["taxable amount", "taxable value", "subtotal", "sub total", "net amount before tax"],
    "igst_amount":        ["igst", "igst amount", "integrated tax"],
    "cgst_amount":        ["cgst", "cgst amount", "central tax"],
    "sgst_amount":        ["sgst", "sgst amount", "state tax", "utgst"],
    "total_amount":       ["total amount", "grand total", "invoice total", "net amount", "total payable"],
    "gst_rate":           ["gst %", "gst rate", "tax rate", "rate %"],
    # Vendor invoice specific
    "irn_number":         ["irn", "irn no", "invoice reference number"],
    "hsn_sac":            ["hsn", "hsn/sac", "hsn sac", "sac code", "hsn code"],
    # Shipping
    "ship_to":            ["ship to", "consignee", "delivery address"],
    "place_of_supply":    ["place of supply", "supply state"],
}


def _normalize(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation for label matching."""
    return re.sub(r"[:\-–•|]+$", "", text.lower().strip()).strip()


def _same_row(bbox_a: dict, bbox_b: dict) -> bool:
    return abs(bbox_a["y"] - bbox_b["y"]) < ROW_TOLERANCE


def _right_of(label: dict, candidate: dict) -> bool:
    return (
        candidate["x"] > label["x"] + label["w"] - 5
        and candidate["x"] - (label["x"] + label["w"]) < RIGHT_MAX_X
    )


def _below(label: dict, candidate: dict) -> bool:
    return (
        candidate["y"] > label["y"] + label["h"] - 2
        and candidate["y"] - (label["y"] + label["h"]) < BELOW_MAX_Y
        and abs(candidate["x"] - label["x"]) < 80  # roughly same x-column
    )


def _is_value_candidate(text: str) -> bool:
    """Reject empty/punctuation-only bboxes (e.g. a lone ':' separator) as values."""
    return bool(re.sub(r"[:\-–•|.\s]+", "", text))


def _clean_value(text: str) -> str:
    """Strip leading separator punctuation a label's own ':' sometimes leaks into the next bbox."""
    return re.sub(r"^[:\-–•|\s]+", "", text.strip())


def _find_value(label_bbox: dict, all_bboxes: list[dict]) -> str:
    """Find value bbox for a given label bbox. Right-of wins over below."""
    same_row_right = [
        b for b in all_bboxes
        if _same_row(label_bbox, b) and _right_of(label_bbox, b) and _is_value_candidate(b["text"])
    ]
    if same_row_right:
        # Nearest right
        nearest = min(same_row_right, key=lambda b: b["x"])
        return _clean_value(nearest["text"])

    below_bboxes = [
        b for b in all_bboxes
        if _below(label_bbox, b) and _is_value_candidate(b["text"])
    ]
    if below_bboxes:
        nearest = min(below_bboxes, key=lambda b: b["y"])
        return _clean_value(nearest["text"])

    return ""


def extract_header_fields(bboxes: list[dict]) -> dict[str, Any]:
    """
    Extract header fields from LiteParse bboxes using label-proximity rules.

    Args:
        bboxes: list of {page, text, x, y, w, h} from liteparse_extractor

    Returns:
        dict of field_name → value (same key names as existing regex parser)
        Only includes fields where a non-empty value was found.
    """
    result: dict[str, Any] = {}

    # Build normalized label → bbox lookup (first occurrence wins per label variant)
    label_bbox_map: dict[str, dict] = {}
    for bbox in bboxes:
        norm = _normalize(bbox["text"])
        if norm and norm not in label_bbox_map:
            label_bbox_map[norm] = bbox

    # Resolve each field
    for field_name, label_variants in LABEL_MAP.items():
        for variant in label_variants:
            label_norm = variant.lower().strip()
            # Exact match first
            if label_norm in label_bbox_map:
                value = _find_value(label_bbox_map[label_norm], bboxes)
                if value:
                    result[field_name] = value
                    break
            # Prefix/substring match — skip for single-word variants (e.g. "vendor",
            # "from", "date"), which collide with unrelated multi-word labels like
            # "Vendor GSTIN" or "Invoice Date" and grab the wrong nearby value.
            if " " not in label_norm:
                continue
            for norm_text, bbox in label_bbox_map.items():
                # Skip long sentences (>5 words) — they are body text, not labels.
                # Guards against e.g. "All Invoices needs to contain PO Number & PO Date"
                # or footer disclaimers containing "order no".
                if len(norm_text.split()) > 5:
                    continue
                if norm_text.startswith(label_norm) or label_norm in norm_text:
                    value = _find_value(bbox, bboxes)
                    if value:
                        result[field_name] = value
                        break
            if field_name in result:
                break

    return result
