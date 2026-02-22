"""
Compare extraction quality between two models using existing debug_markdown files.

Usage (from backend/ dir):
    python compare_extractors.py

Reads all debug_markdown/*.md files, sends each through both models, prints side-by-side.
Skips the slow GLM-OCR Layer 1 — uses already-captured OCR output.
"""

import asyncio
import io
import json
import re
import sys
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import httpx

# ── Config ───────────────────────────────────────────────────────────────────
BASE_URL = "https://8wqtl9oxz84vo6-11434.proxy.runpod.net"
MODEL_A = "qwen2.5:7b"
MODEL_B = "qwen2.5vl:3b"
TIMEOUT = 120
NUM_CTX = 8192
DEBUG_DIR = Path("debug_markdown")

# ── Add app to path so we can import the schemas ─────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from app.services.extraction.glm_ocr_prompts import build_extraction_prompt  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_doc_type(filename: str) -> str:
    """Extract doc_type from filename like doc{uuid}_p1_COMPANY_DC.md"""
    m = re.search(r"_p\d+_([A-Z_]+)\.md$", filename)
    return m.group(1) if m else ""


def clean_json(text: str) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]", "", text)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    # Remove comma-formatted numbers: 86,678.50 → 86678.50
    text = re.sub(r'(\d),(\d{3})', r'\1\2', text)
    return text


def parse_json_safe(text: str) -> dict:
    # Try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass
    # Try extracting JSON from code fences
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(clean_json(m.group(1)))
        except Exception:
            pass
    # Try bare JSON object
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(clean_json(m.group(0)))
        except Exception:
            pass
    return {}


async def call_model(client: httpx.AsyncClient, model: str, prompt: str) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_ctx": NUM_CTX,
            "num_predict": 1024,
        },
    }
    try:
        resp = await client.post(
            f"{BASE_URL}/api/chat",
            json=payload,
            timeout=httpx.Timeout(TIMEOUT, connect=10),
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")
    except Exception as e:
        return f"ERROR: {e}"


async def run_comparison():
    files = sorted(DEBUG_DIR.glob("*.md"))
    if not files:
        print(f"No .md files found in {DEBUG_DIR}/")
        return

    print(f"Found {len(files)} debug_markdown files")
    print(f"Comparing: {MODEL_A}  vs  {MODEL_B}\n")
    print("=" * 100)

    async with httpx.AsyncClient() as client:
        for md_file in files:
            doc_type = parse_doc_type(md_file.name)
            if not doc_type:
                continue

            markdown = md_file.read_text(encoding="utf-8")
            prompt = build_extraction_prompt(doc_type, markdown)
            if not prompt:
                continue

            print(f"\n{'-' * 100}")
            print(f"FILE : {md_file.name}")
            print(f"TYPE : {doc_type}")
            print()

            # Run both models concurrently
            raw_a, raw_b = await asyncio.gather(
                call_model(client, MODEL_A, prompt),
                call_model(client, MODEL_B, prompt),
            )

            fields_a = parse_json_safe(raw_a)
            fields_b = parse_json_safe(raw_b)

            all_keys = sorted(set(list(fields_a.keys()) + list(fields_b.keys())))
            # exclude internal keys
            all_keys = [k for k in all_keys if not k.startswith("_")]

            # Header
            print(f"{'FIELD':<25}  {'qwen2.5:7b':<40}  {'qwen2.5vl:3b':<40}  MATCH")
            print(f"{'─' * 25}  {'─' * 40}  {'─' * 40}  {'─' * 5}".replace("─", "-"))

            for key in all_keys:
                val_a = str(fields_a.get(key, "-"))[:40]
                val_b = str(fields_b.get(key, "-"))[:40]
                match = "OK" if fields_a.get(key) == fields_b.get(key) else "!!"
                print(f"{key:<25}  {val_a:<40}  {val_b:<40}  {match}")

            # Flag if either model errored
            if raw_a.startswith("ERROR"):
                print(f"  ⚠️  {MODEL_A}: {raw_a}")
            if raw_b.startswith("ERROR"):
                print(f"  ⚠️  {MODEL_B}: {raw_b}")

    print("\n" + "=" * 100)  # noqa
    print("Done.")


if __name__ == "__main__":
    asyncio.run(run_comparison())
