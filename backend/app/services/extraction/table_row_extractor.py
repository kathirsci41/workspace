"""
Table row extractor for line items in invoice PDFs.

Two paths:
  PATH A (digital PDF — primary): LiteParse Y-band grouping.
    Bboxes within ROW_TOLERANCE pt → same row.
    Column bands detected from header row (Description, Qty, Rate, Amount).
    Output: list of line item dicts.

  PATH B (scanned / optional): PP-StructureV3 PP-TableMagic via PaddleOCR HTTP server.
    Called only if PADDLEOCR_SERVER_URL is set and PATH A finds zero rows.
    Returns HTML table structure — parse with html.parser.
    Better accuracy on rendered/scanned images. Lower priority for digital PDFs.

Output schema (mirrors LlamaExtract line_items for consistency):
    {
        "description": str,
        "product_code": str | None,
        "hsn_sac": str | None,
        "qty": str | None,
        "uom": str | None,
        "unit_rate": str | None,
        "taxable_value": str | None,
        "tax_amount": str | None,
        "amount": str | None,
        "serial_numbers": list[str],
        "_raw": str,   # raw row text for diagnostics
    }

Storage: extracted_data["line_items"] = [list of above dicts]  (Option J — no migration)
"""
from __future__ import annotations

import logging
import os
import re
from html.parser import HTMLParser
from typing import Any

logger = logging.getLogger(__name__)

ROW_TOLERANCE = 5   # pt — bboxes within this ΔY are on same row
TABLE_HEADER_LABELS = {
    "description": ["description", "particulars", "item", "product name", "item description"],
    "product_code": ["product code", "part no", "part number", "item code", "model", "sku"],
    "hsn_sac":      ["hsn", "hsn/sac", "hsn sac", "sac", "hsn code"],
    "qty":          ["qty", "quantity", "nos", "pcs", "units"],
    "uom":          ["uom", "unit", "u.o.m.", "u/m"],
    "unit_rate":    ["rate", "unit rate", "unit price", "price", "mrp"],
    "taxable_value":["taxable", "taxable value", "taxable amount", "net value"],
    "tax_amount":   ["tax amount", "gst amount", "igst", "cgst", "sgst"],
    "amount":       ["amount", "total", "net amount", "value"],
}


def _group_rows(bboxes: list[dict]) -> list[list[dict]]:
    """Group bboxes into rows by Y proximity."""
    if not bboxes:
        return []
    sorted_bboxes = sorted(bboxes, key=lambda b: (b["y"], b["x"]))
    rows: list[list[dict]] = []
    current_row: list[dict] = [sorted_bboxes[0]]
    ref_y = sorted_bboxes[0]["y"]
    for bbox in sorted_bboxes[1:]:
        if abs(bbox["y"] - ref_y) < ROW_TOLERANCE:
            current_row.append(bbox)
        else:
            rows.append(sorted(current_row, key=lambda b: b["x"]))
            current_row = [bbox]
            ref_y = bbox["y"]
    rows.append(sorted(current_row, key=lambda b: b["x"]))
    return rows


def _detect_header_row(rows: list[list[dict]]) -> tuple[int, dict[str, float]]:
    """
    Find the table header row and build column_name → x_center mapping.
    Returns (row_index, col_map). col_map empty if no header found.
    """
    for i, row in enumerate(rows):
        row_text = " ".join(b["text"].lower() for b in row)
        # Header row must contain at least 2 of: description/qty/rate/amount
        hits = sum(1 for kw in ["description", "qty", "quantity", "rate", "amount", "hsn"]
                   if kw in row_text)
        if hits >= 2:
            col_map: dict[str, float] = {}
            for bbox in row:
                norm = bbox["text"].lower().strip()
                # Exact match first, then substring fallback — avoids "Amount"
                # being absorbed by "taxable_value"'s "taxable amount" variant.
                field = next(
                    (f for f, variants in TABLE_HEADER_LABELS.items() if norm in variants),
                    None,
                )
                if field is None:
                    field = next(
                        (f for f, variants in TABLE_HEADER_LABELS.items()
                         if any(v in norm or norm in v for v in variants)),
                        None,
                    )
                if field is not None:
                    col_map[field] = bbox["x"] + bbox["w"] / 2  # x_center
            return i, col_map
    return -1, {}


def _assign_columns(row: list[dict], col_map: dict[str, float]) -> dict[str, str]:
    """Assign each bbox in a data row to the nearest column."""
    result: dict[str, str] = {}
    if not col_map:
        # No header detected — return raw left-to-right text
        result["description"] = " | ".join(b["text"] for b in row)
        return result
    for bbox in row:
        x_center = bbox["x"] + bbox["w"] / 2
        nearest_col = min(col_map.items(), key=lambda kv: abs(kv[1] - x_center))
        col_name, _ = nearest_col
        # Append if multiple bboxes map to same column (e.g. long description)
        existing = result.get(col_name, "")
        result[col_name] = (existing + " " + bbox["text"]).strip() if existing else bbox["text"]
    return result


def _is_data_row(row: list[dict]) -> bool:
    """Filter out header rows, totals rows, blank rows."""
    if len(row) < 2:
        return False
    row_text = " ".join(b["text"].lower() for b in row)
    skip_patterns = [
        "total", "grand total", "sub total", "subtotal",
        "amount in words", "bank details", "terms", "declaration",
        "description", "particulars", "qty", "quantity",  # header row labels
    ]
    if any(p in row_text for p in skip_patterns):
        return False
    # Must have at least one numeric token (amount or quantity)
    if not re.search(r"\d[\d,]*\.?\d*", row_text):
        return False
    return True


def extract_line_items_from_bboxes(bboxes: list[dict]) -> list[dict[str, Any]]:
    """
    PATH A: Extract line items from LiteParse bboxes (digital PDF).
    Returns list of line item dicts. Empty list if no table found.
    """
    rows = _group_rows(bboxes)
    if not rows:
        return []

    header_idx, col_map = _detect_header_row(rows)
    data_start = header_idx + 1 if header_idx >= 0 else 0

    items: list[dict[str, Any]] = []
    for row in rows[data_start:]:
        if not _is_data_row(row):
            continue
        assigned = _assign_columns(row, col_map)
        item: dict[str, Any] = {
            "description":   assigned.get("description", ""),
            "product_code":  assigned.get("product_code"),
            "hsn_sac":       assigned.get("hsn_sac"),
            "qty":           assigned.get("qty"),
            "uom":           assigned.get("uom"),
            "unit_rate":     assigned.get("unit_rate"),
            "taxable_value": assigned.get("taxable_value"),
            "tax_amount":    assigned.get("tax_amount"),
            "amount":        assigned.get("amount"),
            "serial_numbers": [],
            "_raw": " | ".join(b["text"] for b in row),
        }
        # Only include rows with at least a description or amount
        if item["description"] or item["amount"]:
            items.append(item)

    return items


# ── PATH B: PP-StructureV3 table via PaddleOCR HTTP server (scanned docs) ────

class _TableHTMLParser(HTMLParser):
    """Parse PP-TableMagic HTML output into rows of cell strings."""
    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self._current_row: list[str] = []
        self._current_cell: str = ""
        self._in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._current_row = []
        elif tag in ("td", "th"):
            self._current_cell = ""
            self._in_cell = True

    def handle_endtag(self, tag):
        if tag == "tr" and self._current_row:
            self.rows.append(self._current_row)
        elif tag in ("td", "th"):
            self._current_row.append(self._current_cell.strip())
            self._in_cell = False

    def handle_data(self, data):
        if self._in_cell:
            self._current_cell += data


def _parse_table_html(html: str) -> list[list[str]]:
    """Parse PP-TableMagic HTML → list of rows (each row = list of cell strings)."""
    parser = _TableHTMLParser()
    parser.feed(html)
    return parser.rows


def extract_line_items_from_table_html(html: str) -> list[dict[str, Any]]:
    """
    PATH B: Convert PP-TableMagic HTML table to line_items list.
    Used when PaddleOCR HTTP server returns PP-StructureV3 table output.
    """
    rows = _parse_table_html(html)
    if not rows:
        return []

    # First row = header
    headers = [h.lower().strip() for h in rows[0]]
    col_index: dict[str, int] = {}
    for field, variants in TABLE_HEADER_LABELS.items():
        for i, h in enumerate(headers):
            if any(v in h or h in v for v in variants):
                col_index[field] = i
                break

    items: list[dict[str, Any]] = []
    for row in rows[1:]:
        if not row or all(c.strip() == "" for c in row):
            continue
        def cell(field: str) -> str | None:
            i = col_index.get(field)
            return row[i].strip() if i is not None and i < len(row) else None

        item: dict[str, Any] = {
            "description":   cell("description") or "",
            "product_code":  cell("product_code"),
            "hsn_sac":       cell("hsn_sac"),
            "qty":           cell("qty"),
            "uom":           cell("uom"),
            "unit_rate":     cell("unit_rate"),
            "taxable_value": cell("taxable_value"),
            "tax_amount":    cell("tax_amount"),
            "amount":        cell("amount"),
            "serial_numbers": [],
            "_raw": " | ".join(row),
        }
        if item["description"] or item["amount"]:
            items.append(item)

    return items
