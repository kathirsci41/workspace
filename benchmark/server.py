"""
LiteParse vs PyMuPDF Benchmark Server
--------------------------------------
Standalone FastAPI server on port 8001.
Does NOT modify any existing source file.
Imports existing parsers READ-ONLY via sys.path.

Run:
    cd order-assurance/benchmark
    python server.py          # or: python -B server.py (skip .pyc cache)

Then open: http://localhost:8001
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any

# ── read-only import of existing backend parsers ─────────────────────────────
_BACKEND = str(Path(__file__).parent.parent / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

os.environ.setdefault("DATABASE_URL", "sqlite:///./benchmark_temp.db")
os.environ.setdefault("APP_ENV", "benchmark")

try:
    from app.services.extraction.structured_text_parser import parse_structured_text
    PARSER_AVAILABLE = True
    _PARSER_ERR = ""
except Exception as exc:
    PARSER_AVAILABLE = False
    _PARSER_ERR = str(exc)

# ── third-party deps ─────────────────────────────────────────────────────────
import fitz  # PyMuPDF
from liteparse import LiteParse, ParseError
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

app = FastAPI(title="LiteParse Benchmark", docs_url=None, redoc_url=None)

DOC_TYPES = [
    "COMPANY_INVOICE",
    "COMPANY_DC",
    "COMPANY_PO",
    "CUSTOMER_PO",
    "VENDOR_INVOICE",
]

# ── extractors ────────────────────────────────────────────────────────────────

def extract_pymupdf(pdf_bytes: bytes) -> dict[str, Any]:
    t0 = time.perf_counter()
    pages_text: list[str] = []
    page_count = 0
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            page_count = doc.page_count
            for i in range(doc.page_count):
                pages_text.append(doc[i].get_text("text") or "")
    except Exception as e:
        return {"error": str(e), "text": "", "pages": 0, "ms": 0, "is_digital": False}
    elapsed = (time.perf_counter() - t0) * 1000
    full_text = "\n".join(pages_text)
    return {
        "text": full_text,
        "text_length": len(full_text.strip()),
        "pages": page_count,
        "ms": round(elapsed, 1),
        "is_digital": len(full_text.strip()) > 30,
        "bbox_count": 0,
        "bboxes": [],
    }


def extract_liteparse(pdf_bytes: bytes) -> dict[str, Any]:
    t0 = time.perf_counter()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        # ocr_enabled=False: digital text only — no Tesseract/PaddleOCR server needed.
        # Scanned docs will return empty text (reported honestly in UI).
        parser = LiteParse(ocr_enabled=False)
        result = parser.parse(tmp_path)

        bboxes = []
        for page in result.pages:
            for item in page.text_items:
                bboxes.append({
                    "page": page.page_num,
                    "text": item.text,
                    "x": round(item.x, 1),
                    "y": round(item.y, 1),
                    "w": round(item.width, 1),
                    "h": round(item.height, 1),
                })

        elapsed = (time.perf_counter() - t0) * 1000
        return {
            "text": result.text,
            "text_length": len(result.text.strip()),
            "pages": len(result.pages),
            "ms": round(elapsed, 1),
            "is_digital": len(result.text.strip()) > 30,
            "bbox_count": len(bboxes),
            "bboxes": bboxes[:50],
        }
    except ParseError as e:
        elapsed = (time.perf_counter() - t0) * 1000
        return {
            "text": "",
            "text_length": 0,
            "pages": 0,
            "ms": round(elapsed, 1),
            "is_digital": False,
            "bbox_count": 0,
            "bboxes": [],
            "error": str(e),
        }
    finally:
        os.unlink(tmp_path)


def run_parser(text: str, doc_type: str, route: str, filename: str) -> dict[str, Any]:
    if not PARSER_AVAILABLE:
        return {"fields": {}, "field_count": 0, "missing": [], "error": f"Parser not available: {_PARSER_ERR}"}
    if not text.strip():
        return {"fields": {}, "field_count": 0, "missing": [], "note": "no text to parse"}
    try:
        result = parse_structured_text(
            document_type=doc_type,
            raw_text=text,
            extraction_route=route,
            filename=filename,
        )
        # Key is "fields" in current codebase
        fields = result.get("fields") or result.get("extracted_data") or {}
        missing = result.get("missing_required_fields", [])
        return {
            "fields": fields,
            "field_count": len(fields),
            "missing": missing,
            "failure_code": result.get("failure_code"),
            "parser_route": result.get("parser_route"),
        }
    except Exception as e:
        return {"fields": {}, "field_count": 0, "missing": [], "error": str(e), "trace": traceback.format_exc()[-500:]}


# ── routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    html_path = Path(__file__).parent / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/health")
def health():
    return {"ok": True, "parser_available": PARSER_AVAILABLE, "parser_error": _PARSER_ERR}


@app.post("/benchmark")
async def benchmark(
    files: list[UploadFile] = File(...),
    doc_type: str = Form("VENDOR_INVOICE"),
):
    results = []
    for file in files:
        pdf_bytes = await file.read()
        filename = file.filename or "document.pdf"

        pm = extract_pymupdf(pdf_bytes)
        lp = extract_liteparse(pdf_bytes)

        route_pm = "digital" if pm["is_digital"] else "ocr_glm"
        route_lp = "digital" if lp["is_digital"] else "ocr_glm"

        pm_fields = run_parser(pm["text"], doc_type, route_pm, filename)
        lp_fields = run_parser(lp["text"], doc_type, route_lp, filename)

        pm_keys = set(pm_fields.get("fields", {}).keys())
        lp_keys = set(lp_fields.get("fields", {}).keys())
        only_lp = sorted(lp_keys - pm_keys)
        only_pm = sorted(pm_keys - lp_keys)
        both = sorted(pm_keys & lp_keys)

        disagreements = []
        for k in both:
            v_pm = str(pm_fields["fields"].get(k, ""))
            v_lp = str(lp_fields["fields"].get(k, ""))
            if v_pm != v_lp:
                disagreements.append({"field": k, "pymupdf": v_pm, "liteparse": v_lp})

        results.append({
            "filename": filename,
            "doc_type": doc_type,
            "pymupdf": {
                "text_length": pm["text_length"],
                "pages": pm["pages"],
                "ms": pm["ms"],
                "is_digital": pm["is_digital"],
                "bbox_count": 0,
                "field_count": pm_fields.get("field_count", 0),
                "fields": pm_fields.get("fields", {}),
                "missing": pm_fields.get("missing", []),
                "text_preview": pm["text"].strip()[:400],
                "error": pm.get("error") or pm_fields.get("error"),
            },
            "liteparse": {
                "text_length": lp["text_length"],
                "pages": lp["pages"],
                "ms": lp["ms"],
                "is_digital": lp["is_digital"],
                "bbox_count": lp["bbox_count"],
                "field_count": lp_fields.get("field_count", 0),
                "fields": lp_fields.get("fields", {}),
                "missing": lp_fields.get("missing", []),
                "text_preview": lp["text"].strip()[:400],
                "bboxes_sample": lp["bboxes"][:20],
                "error": lp.get("error") or lp_fields.get("error"),
            },
            "comparison": {
                "text_length_delta": lp["text_length"] - pm["text_length"],
                "text_length_pct": round(
                    (lp["text_length"] - pm["text_length"]) / max(pm["text_length"], 1) * 100, 1
                ),
                "speed_delta_ms": round(lp["ms"] - pm["ms"], 1),
                "fields_only_liteparse": only_lp,
                "fields_only_pymupdf": only_pm,
                "fields_both": both,
                "field_disagreements": disagreements,
                "liteparse_wins": len(only_lp) > len(only_pm),
                "scanned_doc": not pm["is_digital"] and not lp["is_digital"],
            },
        })

    return JSONResponse({"results": results, "parser_available": PARSER_AVAILABLE})


if __name__ == "__main__":
    print("=" * 60)
    print("LiteParse Benchmark Server")
    print("Open: http://localhost:8001")
    print(f"Backend parser: {'OK' if PARSER_AVAILABLE else 'NOT AVAILABLE - ' + _PARSER_ERR}")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="warning")