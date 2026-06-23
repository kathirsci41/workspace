"""
PP-StructureV3 table extraction service (Sprint 2, Task 2.2).

Purpose: extract line-item tables from SCANNED invoice images using
PP-StructureV3 (PPStructure).  For DIGITAL PDFs the existing LiteParse
Y-band path (table_row_extractor.py) is preferred and faster; this service
is the scanned-doc fallback.

Integration:
  Called by extraction_service.py after PP-OCRv5 text extraction for
  VENDOR_INVOICE and COMPANY_INVOICE document types.
  Result is merged into extracted_data["line_items"].

Model: PP-StructureV3 (PPStructure, table=True) — part of paddleocr package.
  Lazy-loaded on first call.  Requires paddleocr >= 3.0 and GPU ≥ 4 GB VRAM.
  Falls back gracefully when unavailable.

Output: list of LineItem dicts matching the schema used by line_item_matcher.py:
  {
    "description": str,
    "hsn_sac": str,
    "quantity": float,
    "unit": str,
    "unit_price": float,
    "taxable_amount": float,
    "gst_rate": float,
    "igst": float,
    "cgst": float,
    "sgst": float,
    "total": float,
    "raw": dict,   # original row dict for diagnostics
  }
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from typing import Any

logger = logging.getLogger(__name__)

_structure_model = None


def _ppstructure_available() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec("paddleocr") is not None
    except Exception:
        return False


def _init_structure():
    """Lazy-initialise PPStructure model (GPU, table mode)."""
    from paddleocr import PPStructure  # noqa: PLC0415
    return PPStructure(table=True, ocr=True, show_log=False, use_gpu=True)


@dataclass
class LineItem:
    description: str = ""
    hsn_sac: str = ""
    quantity: float = 0.0
    unit: str = ""
    unit_price: float = 0.0
    taxable_amount: float = 0.0
    gst_rate: float = 0.0
    igst: float = 0.0
    cgst: float = 0.0
    sgst: float = 0.0
    total: float = 0.0
    raw: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# HTML table parsing
# ---------------------------------------------------------------------------

class _TableParser(HTMLParser):
    """Parse an HTML table returned by PP-StructureV3 into a list of row lists."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] = []
        self._cell: list[str] = []
        self._in_cell = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("td", "th"):
            self._in_cell = True
            self._cell = []
        elif tag == "tr":
            self._row = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th"):
            self._row.append(" ".join(self._cell).strip())
            self._in_cell = False
        elif tag == "tr":
            if self._row:
                self.rows.append(self._row)

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell.append(data.strip())


def _parse_html_table(html: str) -> list[dict]:
    """Convert PP-StructureV3 HTML table → list of row dicts."""
    try:
        parser = _TableParser()
        parser.feed(html)
        if not parser.rows:
            return []
        headers = parser.rows[0]
        return [
            {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
            for row in parser.rows[1:]
        ]
    except Exception as exc:
        logger.warning("table_extraction_service: HTML parse failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# PPStructure inference
# ---------------------------------------------------------------------------

def extract_tables(image_path: str) -> list[list[dict]]:
    """
    Run PP-StructureV3 on image_path (PNG/JPG page image).

    Returns list of tables, each table is a list of row-dicts.
    Returns [] on any failure — callers must handle empty gracefully.
    Safe: never raises.
    """
    global _structure_model

    if not _ppstructure_available():
        logger.debug("table_extraction_service: paddleocr not installed — skipping")
        return []

    try:
        if _structure_model is None:
            _structure_model = _init_structure()

        result = _structure_model(image_path)
        tables: list[list[dict]] = []
        for region in result or []:
            if region.get("type") != "table":
                continue
            html = region.get("res", {}).get("html", "")
            if html:
                rows = _parse_html_table(html)
                if rows:
                    tables.append(rows)
        return tables

    except Exception as exc:
        logger.warning("table_extraction_service: PPStructure failed on %s: %s", image_path, exc)
        return []


# ---------------------------------------------------------------------------
# Row → LineItem mapping
# ---------------------------------------------------------------------------

def _to_float(s: str) -> float:
    try:
        return float(str(s).replace(",", "").replace("₹", "").replace(" ", "").strip() or 0)
    except (ValueError, TypeError):
        return 0.0


def parse_line_items(table_rows: list[dict]) -> list[LineItem]:
    """
    Map raw table row-dicts (from PP-StructureV3 HTML) → LineItem objects.

    Handles common Indian invoice column name variants.
    Rows that have neither description nor taxable_amount are skipped.
    """
    items: list[LineItem] = []
    for row in table_rows:
        # Normalise keys: strip, lowercase, spaces → underscores
        norm = {k.strip().lower().replace(" ", "_"): v for k, v in row.items()}

        def get(*keys: str) -> str:
            for k in keys:
                v = norm.get(k, "")
                if v:
                    return str(v)
            return ""

        item = LineItem(
            description=get("description", "item_description", "particulars", "product_name", "item"),
            hsn_sac=get("hsn/sac", "hsn_sac", "hsn", "sac", "hsn_code", "sac_code"),
            quantity=_to_float(get("qty", "quantity", "nos", "pcs", "units")),
            unit=get("unit", "uom", "u/m", "u.o.m."),
            unit_price=_to_float(get("rate", "unit_price", "unit_rate", "price", "mrp")),
            taxable_amount=_to_float(get("taxable_amount", "taxable_value", "taxable", "net_value", "amount")),
            gst_rate=_to_float(get("gst_rate", "gst_%", "gst_rate_%", "tax_rate", "rate_%")),
            igst=_to_float(get("igst", "igst_amount")),
            cgst=_to_float(get("cgst", "cgst_amount")),
            sgst=_to_float(get("sgst", "sgst_amount", "utgst")),
            total=_to_float(get("total", "total_amount", "net_amount", "gross_amount", "value")),
            raw=row,
        )
        if item.description or item.taxable_amount:
            items.append(item)
    return items


def extract_line_items_from_image(image_path: str) -> list[dict[str, Any]]:
    """
    High-level entry point: run PP-StructureV3 on image_path and return
    line items as plain dicts (suitable for JSON / extracted_data storage).

    Uses the first table found that contains at least one line item.
    Returns [] if no table found or paddleocr not available.
    """
    tables = extract_tables(image_path)
    for table_rows in tables:
        items = parse_line_items(table_rows)
        if items:
            return [asdict(item) for item in items]
    return []
