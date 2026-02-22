"""
Compare OCR Layer 1 quality across all available vision models using real client PDFs.

Models tested as Layer 1 (image → text):
  glm-ocr:latest  — specialized 1.1B OCR model, /api/generate
  qwen2.5vl:3b   — Qwen 2.5 VL 3B, /api/chat
  qwen2.5vl:7b   — Qwen 2.5 VL 7B, /api/chat
  qwen3-vl:8b    — Qwen 3 VL 8B,   /api/chat
  qwen3-vl:30b   — Qwen 3 VL 30B,  /api/chat
  qwen3.5:cloud  — cloud-routed model, /api/chat (may not support images)

Each OCR output is fed through qwen2.5:7b (Layer 2) for JSON extraction.

Usage (from backend/ dir):
    python compare_ocr_layer.py [--docs N]   (default: all 5 docs)
    python compare_ocr_layer.py --docs 2     (first 2 docs only — faster)
"""

import asyncio
import base64
import io
import json
import re
import sys
import time
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import fitz  # PyMuPDF
import httpx

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL = "https://8wqtl9oxz84vo6-11434.proxy.runpod.net"
EXTRACTOR_MODEL = "qwen2.5:7b"
TIMEOUT = 300
NUM_CTX = 8192
PDF_DPI = 200

ELITE_ROOT = Path("E:/PROJECTS/Experiments/Logistic/Phase 2.1.0/.testdo/Elite")

# All OCR models to compare.
# glm-ocr uses /api/generate; all others use /api/chat with image in message.
OCR_MODELS = [
    "glm-ocr:latest",
    "qwen2.5vl:3b",
    "qwen2.5vl:7b",
    "qwen3-vl:8b",
    "qwen3-vl:30b",
    "qwen3.5:cloud",
]

# Test documents — one per doc_type, Elite client real PDFs (.testdo/Elite/)
TEST_DOCS = [
    {
        "path": ELITE_ROOT / "Skylark PO.pdf",
        "doc_type": "COMPANY_PO",
        "label": "Skylark PO",
    },
    {
        "path": ELITE_ROOT / "C240847449 1OTM2526001448-Vendor Invoice.pdf",
        "doc_type": "VENDOR_INVOICE",
        "label": "Redington Tax Invoice",
    },
    {
        "path": ELITE_ROOT / "PO (2).pdf",
        "doc_type": "CUSTOMER_PO",
        "label": "Elite Customer PO",
    },
    {
        "path": ELITE_ROOT / "1DNT2526DC2865.pdf",
        "doc_type": "COMPANY_DC",
        "label": "Company DC 1DNT2526DC2865",
    },
    {
        "path": ELITE_ROOT / "1ITR2526001748.pdf",
        "doc_type": "COMPANY_INVOICE",
        "label": "Company Invoice 1ITR2526001748",
    },
]

# ── Add app to path ───────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from app.services.extraction.glm_ocr_prompts import (  # noqa: E402
    get_ocr_prompt,
    build_extraction_prompt,
)


# ── PDF → PNG ─────────────────────────────────────────────────────────────────

def pdf_first_page_png(pdf_path: Path) -> bytes:
    doc = fitz.open(str(pdf_path))
    page = doc[0]
    mat = fitz.Matrix(PDF_DPI / 72, PDF_DPI / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    return pix.tobytes("png")


# ── OCR callers ───────────────────────────────────────────────────────────────

async def ocr_model(
    client: httpx.AsyncClient, model: str, image_bytes: bytes, doc_type: str
) -> tuple[str, int]:
    """Call any OCR model. Detects glm-ocr vs vision-language automatically."""
    prompt = get_ocr_prompt(doc_type)
    b64 = base64.b64encode(image_bytes).decode()
    t0 = time.time()

    if "glm-ocr" in model:
        # GLM-OCR: custom RENDERER/PARSER, must use /api/generate
        payload = {
            "model": model,
            "prompt": prompt,
            "images": [b64],
            "stream": False,
            "options": {"temperature": 0.0, "num_ctx": NUM_CTX},
        }
        try:
            resp = await client.post(
                f"{BASE_URL}/api/generate",
                json=payload,
                timeout=httpx.Timeout(TIMEOUT, connect=10),
            )
            resp.raise_for_status()
            text = resp.json().get("response", "")
            return text, int((time.time() - t0) * 1000)
        except Exception as e:
            return f"ERROR: {e}", int((time.time() - t0) * 1000)
    else:
        # Vision-language model: /api/chat with image in message
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt, "images": [b64]}],
            "stream": False,
            "options": {"temperature": 0.0, "num_ctx": NUM_CTX},
        }
        try:
            resp = await client.post(
                f"{BASE_URL}/api/chat",
                json=payload,
                timeout=httpx.Timeout(TIMEOUT, connect=10),
            )
            resp.raise_for_status()
            text = resp.json().get("message", {}).get("content", "")
            return text, int((time.time() - t0) * 1000)
        except Exception as e:
            return f"ERROR: {e}", int((time.time() - t0) * 1000)


# ── Layer 2: extraction ───────────────────────────────────────────────────────

async def extract_fields(
    client: httpx.AsyncClient, ocr_text: str, doc_type: str
) -> tuple[dict, int]:
    if not ocr_text or ocr_text.startswith("ERROR"):
        return {}, 0
    prompt = build_extraction_prompt(doc_type, ocr_text)
    if not prompt:
        return {}, 0
    payload = {
        "model": EXTRACTOR_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.0, "num_ctx": NUM_CTX, "num_predict": 1024},
    }
    t0 = time.time()
    try:
        resp = await client.post(
            f"{BASE_URL}/api/chat",
            json=payload,
            timeout=httpx.Timeout(TIMEOUT, connect=10),
        )
        resp.raise_for_status()
        raw = resp.json().get("message", {}).get("content", "")
        return parse_json_safe(raw), int((time.time() - t0) * 1000)
    except Exception as e:
        return {"_error": str(e)}, int((time.time() - t0) * 1000)


# ── JSON helpers ──────────────────────────────────────────────────────────────

def parse_json_safe(text: str) -> dict:
    def _clean(t: str) -> str:
        t = re.sub(r"[\x00-\x1f\x7f]", "", t)
        t = re.sub(r",\s*([}\]])", r"\1", t)
        return t
    for attempt in [
        lambda: json.loads(text),
        lambda: json.loads(_clean(re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL).group(1))),  # type: ignore
        lambda: json.loads(_clean(re.search(r"\{.*\}", text, re.DOTALL).group(0))),  # type: ignore
    ]:
        try:
            result = attempt()
            if isinstance(result, dict):
                return result
        except Exception:
            pass
    return {}


def score_ocr_text(text: str) -> dict:
    if not text or text.startswith("ERROR"):
        return {"chars": 0, "lines": 0, "has_table": False, "error": True, "msg": text[:80]}
    lines = [l for l in text.splitlines() if l.strip()]
    return {
        "chars": len(text),
        "lines": len(lines),
        "has_table": "<table" in text.lower() or "|" in text,
        "error": False,
        "msg": "",
    }


# ── Main comparison ───────────────────────────────────────────────────────────

async def run_comparison(num_docs: int):
    docs = TEST_DOCS[:num_docs]
    models = OCR_MODELS

    print("=" * 120)
    print(f"  OCR LAYER 1 COMPARISON — {len(models)} models × {len(docs)} documents")
    print(f"  Models: {', '.join(models)}")
    print(f"  Client: Elite (.testdo/Elite/)")
    print("=" * 120)

    # Summary table accumulated across all docs
    summary: dict[str, dict[str, list]] = {m: {"ocr_ms": [], "ext_ms": [], "fields_filled": []} for m in models}

    async with httpx.AsyncClient() as client:
        for doc in docs:
            pdf_path = Path(doc["path"])  # already absolute Path objects
            doc_type = doc["doc_type"]
            label = doc["label"]

            print(f"\n{'─' * 120}")
            print(f"  DOC   : {label}  [{doc_type}]")
            print(f"  FILE  : {pdf_path.name}")

            if not pdf_path.exists():
                print(f"  ERROR : File not found — {pdf_path}")
                continue

            try:
                image_bytes = pdf_first_page_png(pdf_path)
                print(f"  IMAGE : {len(image_bytes) // 1024} KB PNG at {PDF_DPI} DPI")
            except Exception as e:
                print(f"  ERROR : PDF conversion failed — {e}")
                continue

            # ── Run each OCR model sequentially (avoid VRAM contention) ──────
            results: dict[str, tuple[str, int]] = {}
            for m in models:
                print(f"  OCR   : {m} ...", end=" ", flush=True)
                text, ms = await ocr_model(client, m, image_bytes, doc_type)
                results[m] = (text, ms)
                q = score_ocr_text(text)
                status = f"ERROR({q['msg'][:40]})" if q["error"] else f"{ms}ms  {q['chars']}ch  {q['lines']}ln"
                print(status)

            # ── OCR quality table ─────────────────────────────────────────────
            print()
            print(f"  {'MODEL':<20}  {'TIME':>6}  {'CHARS':>6}  {'LINES':>5}  {'TABLE':>5}  STATUS")
            print(f"  {'─' * 20}  {'─' * 6}  {'─' * 6}  {'─' * 5}  {'─' * 5}  {'─' * 8}")
            for m in models:
                text, ms = results[m]
                q = score_ocr_text(text)
                if q["error"]:
                    print(f"  {m:<20}  {'':>6}  {'':>6}  {'':>5}  {'':>5}  ERROR: {q['msg'][:50]}")
                else:
                    tbl = "YES" if q["has_table"] else "no"
                    print(f"  {m:<20}  {ms:>5}ms  {q['chars']:>6}  {q['lines']:>5}  {tbl:>5}  OK")
                summary[m]["ocr_ms"].append(ms if not q["error"] else 0)

            # ── Layer 2 extraction ────────────────────────────────────────────
            print()
            print("  Extracting fields (qwen2.5:7b) from each OCR output...")
            extracted: dict[str, tuple[dict, int]] = {}
            for m in models:
                text, _ = results[m]
                fields, ext_ms = await extract_fields(client, text, doc_type)
                extracted[m] = (fields, ext_ms)
                summary[m]["ext_ms"].append(ext_ms)
                filled = len([v for k, v in fields.items() if v and not k.startswith("_")])
                summary[m]["fields_filled"].append(filled)

            # ── Field comparison table ────────────────────────────────────────
            all_keys = sorted(set(
                k for m in models for k in extracted[m][0].keys() if not k.startswith("_")
            ))

            if all_keys:
                print()
                W = 22
                header = f"  {'FIELD':<18}"
                for m in models:
                    short = m.replace("qwen2.5vl:", "q25vl:").replace("qwen3-vl:", "q3vl:").replace("qwen3.5:", "q35:").replace("glm-ocr:", "glm:")
                    header += f"  {short[:W]:<{W}}"
                print(header)
                sep = f"  {'─' * 18}" + f"  {'─' * W}" * len(models)
                print(sep)
                for key in all_keys:
                    row = f"  {key:<18}"
                    vals = [str(extracted[m][0].get(key, "—"))[:W] for m in models]
                    all_same = len(set(vals)) == 1
                    for v in vals:
                        row += f"  {v:<{W}}"
                    row += "  ✓" if all_same else ""
                    print(row)

            print()
            ext_times = "  ".join(
                f"{m.split(':')[0][-8:]}:{extracted[m][1]}ms" for m in models
            )
            print(f"  Extraction times: {ext_times}")

            # ── Raw OCR preview ───────────────────────────────────────────────
            print()
            print("  RAW OCR PREVIEW (first 300 chars):")
            for m in models:
                text, _ = results[m]
                preview = (text or "")[:300].replace("\n", " ↵ ")
                short_m = m
                print(f"  [{short_m}]  {preview}")
                print()

    # ── Summary scorecard ─────────────────────────────────────────────────────
    print("=" * 120)
    print("  SUMMARY SCORECARD")
    print(f"  {'MODEL':<20}  {'AVG OCR':>8}  {'AVG EXT':>8}  {'TOTAL':>8}  {'AVG FIELDS':>10}")
    print(f"  {'─' * 20}  {'─' * 8}  {'─' * 8}  {'─' * 8}  {'─' * 10}")
    for m in models:
        ocr_ms_list = [x for x in summary[m]["ocr_ms"] if x > 0]
        ext_ms_list = [x for x in summary[m]["ext_ms"] if x > 0]
        fields_list = summary[m]["fields_filled"]
        avg_ocr = int(sum(ocr_ms_list) / len(ocr_ms_list)) if ocr_ms_list else 0
        avg_ext = int(sum(ext_ms_list) / len(ext_ms_list)) if ext_ms_list else 0
        avg_total = avg_ocr + avg_ext
        avg_fields = f"{sum(fields_list) / len(fields_list):.1f}" if fields_list else "0"
        print(f"  {m:<20}  {avg_ocr:>6}ms  {avg_ext:>6}ms  {avg_total:>6}ms  {avg_fields:>10}")
    print("=" * 120)
    print("Done.")


if __name__ == "__main__":
    num_docs = 5
    if "--docs" in sys.argv:
        idx = sys.argv.index("--docs")
        if idx + 1 < len(sys.argv):
            num_docs = int(sys.argv[idx + 1])
    asyncio.run(run_comparison(num_docs))
