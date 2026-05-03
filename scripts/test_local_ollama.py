"""
test_local_ollama.py
--------------------
Temporary script to verify whether the local Ollama instance can run
both pipeline models simultaneously on the RTX 3050 6 GB VRAM.

Layer 1  →  glm-ocr:latest   (image → markdown OCR)
Layer 2  →  qwen2.5:7b       (markdown → structured JSON extraction)

Usage:
    python test_local_ollama.py
    python test_local_ollama.py --url http://localhost:11434
    python test_local_ollama.py --l1 glm-ocr:latest --l2 qwen2.5:3b

Delete this file when done testing.
"""

import argparse
import asyncio
import json
import subprocess
import sys
import time
from datetime import datetime

# Force UTF-8 on Windows console (handles box-drawing, arrows, tick marks)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    import httpx
except ImportError:
    print("httpx not installed. Run:  pip install httpx")
    sys.exit(1)

# ── defaults ──────────────────────────────────────────────────────────────────
DEFAULT_URL = "http://localhost:11434"
DEFAULT_L1  = "glm-ocr:latest"
DEFAULT_L2  = "qwen2.5:7b"

# Minimal prompts — just enough to force each model to load into VRAM
L1_PROMPT = "Describe this document in one sentence."   # text-only fallback (no image)
L2_PROMPT = (
    "Extract the following fields as JSON from this text:\n\n"
    "Invoice #INV-001  Date: 2025-01-15  Total: ₹12,500\n\n"
    "Fields: invoice_number, date, total_amount"
)


# ── helpers ───────────────────────────────────────────────────────────────────

def vram_snapshot() -> str:
    """Return a one-line VRAM summary from nvidia-smi (Windows-safe)."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi",
             "--query-gpu=name,memory.used,memory.free,memory.total",
             "--format=csv,noheader,nounits"],
            timeout=5, stderr=subprocess.DEVNULL
        ).decode().strip()
        parts = [p.strip() for p in out.split(",")]
        name, used, free, total = parts[0], parts[1], parts[2], parts[3]
        pct = round(int(used) / int(total) * 100)
        return f"{name} — {used} MB used / {total} MB total  ({pct}% full, {free} MB free)"
    except Exception as e:
        return f"nvidia-smi unavailable: {e}"


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def header(text: str) -> None:
    print(f"\n{'-'*60}")
    print(f"  {text}")
    print('-'*60)


async def list_models(client: httpx.AsyncClient, base_url: str) -> list[str]:
    r = await client.get(f"{base_url}/api/tags", timeout=10)
    r.raise_for_status()
    return [m["name"] for m in r.json().get("models", [])]


async def generate(
    client: httpx.AsyncClient,
    base_url: str,
    model: str,
    prompt: str,
    label: str,
) -> dict:
    """Send a /api/generate request and return timing + first 120 chars of response."""
    payload = {"model": model, "prompt": prompt, "stream": False}
    t0 = time.perf_counter()
    print(f"  [{ts()}] {label}: sending request…")
    try:
        r = await client.post(
            f"{base_url}/api/generate",
            json=payload,
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
        elapsed = time.perf_counter() - t0
        snippet = data.get("response", "")[:120].replace("\n", " ")
        return {
            "label":   label,
            "model":   model,
            "ok":      True,
            "elapsed": round(elapsed, 2),
            "snippet": snippet,
            "eval_count": data.get("eval_count", "?"),
        }
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        return {
            "label":   label,
            "model":   model,
            "ok":      False,
            "elapsed": round(elapsed, 2),
            "error":   str(exc),
        }


# ── main ──────────────────────────────────────────────────────────────────────

async def run(base_url: str, l1_model: str, l2_model: str) -> None:

    async with httpx.AsyncClient() as client:

        # ── 0. Ping Ollama ────────────────────────────────────────────────────
        header("0. Ollama reachability")
        try:
            r = await client.get(base_url, timeout=5)
            print(f"  ✓  Ollama is up at {base_url}  (HTTP {r.status_code})")
        except Exception as e:
            print(f"  ✗  Cannot reach Ollama at {base_url}")
            print(f"     → {e}")
            print("\n  Make sure Ollama is running:  ollama serve")
            return

        # ── 1. Available models ───────────────────────────────────────────────
        header("1. Models available locally")
        models = await list_models(client, base_url)
        if models:
            for m in models:
                tag = ""
                if m == l1_model or m.startswith(l1_model.split(":")[0]):
                    tag = "  ← Layer 1"
                if m == l2_model or m.startswith(l2_model.split(":")[0]):
                    tag = "  ← Layer 2"
                print(f"  • {m}{tag}")
        else:
            print("  (no models found — pull them first)")
            print(f"\n  ollama pull {l1_model}")
            print(f"  ollama pull {l2_model}")

        # Warn if required models are missing
        missing = []
        for needed in [l1_model, l2_model]:
            base = needed.split(":")[0]
            if not any(m == needed or m.startswith(base) for m in models):
                missing.append(needed)
        if missing:
            print(f"\n  ⚠  Missing models: {', '.join(missing)}")
            print("  Pull them before running the full test.")

        # ── 2. VRAM before any model is loaded ───────────────────────────────
        header("2. VRAM baseline (before loading)")
        print(f"  {vram_snapshot()}")

        # ── 3. Layer 1 alone ─────────────────────────────────────────────────
        header(f"3. Layer 1 alone  →  {l1_model}")
        res1 = await generate(client, base_url, l1_model, L1_PROMPT, "L1")
        if res1["ok"]:
            print(f"  ✓  {res1['elapsed']}s | tokens: {res1['eval_count']}")
            print(f"     Response: {res1['snippet']}…")
        else:
            print(f"  ✗  FAILED: {res1['error']}")
        print(f"  VRAM after L1: {vram_snapshot()}")

        # ── 4. Layer 2 alone ─────────────────────────────────────────────────
        header(f"4. Layer 2 alone  →  {l2_model}")
        res2 = await generate(client, base_url, l2_model, L2_PROMPT, "L2")
        if res2["ok"]:
            print(f"  ✓  {res2['elapsed']}s | tokens: {res2['eval_count']}")
            print(f"     Response: {res2['snippet']}…")
        else:
            print(f"  ✗  FAILED: {res2['error']}")
        print(f"  VRAM after L2: {vram_snapshot()}")

        # ── 5. Both models in PARALLEL ───────────────────────────────────────
        header("5. BOTH MODELS IN PARALLEL  (the real VRAM test)")
        print(f"  Firing L1 ({l1_model}) and L2 ({l2_model}) simultaneously…")
        print(f"  VRAM before parallel: {vram_snapshot()}")

        t_start = time.perf_counter()
        results = await asyncio.gather(
            generate(client, base_url, l1_model, L1_PROMPT, "L1-parallel"),
            generate(client, base_url, l2_model, L2_PROMPT, "L2-parallel"),
        )
        total = round(time.perf_counter() - t_start, 2)

        print(f"\n  VRAM peak (after parallel): {vram_snapshot()}")
        print()
        for r in results:
            status = "✓" if r["ok"] else "✗"
            label  = r["label"]
            if r["ok"]:
                print(f"  {status}  {label}: {r['elapsed']}s  — {r['snippet'][:80]}…")
            else:
                print(f"  {status}  {label}: FAILED — {r['error']}")
        print(f"\n  Total wall-clock time (parallel): {total}s")

        # ── 6. Summary ───────────────────────────────────────────────────────
        header("6. Summary")
        l1_ok = results[0]["ok"]
        l2_ok = results[1]["ok"]

        if l1_ok and l2_ok:
            print("  ✓  Both models ran in parallel successfully.")
            print("  ✓  Local Ollama CAN handle the two-layer pipeline.")
            print()
            print("  To switch from RunPod → local, update backend/.env:")
            print(f"    OCR_BASE_URL=http://localhost:11434")
            print(f"    OCR_EXTRACTOR_BASE_URL=http://localhost:11434")
            if "7b" in l2_model:
                print()
                print("  Note: qwen2.5:7b + glm-ocr may be tight on 6 GB VRAM.")
                print("  If you see OOM errors under load, switch Layer 2 to qwen2.5:3b:")
                print("    OCR_EXTRACTOR_MODEL=qwen2.5:3b")
        else:
            print("  ✗  Parallel run failed. Likely VRAM exhaustion on 6 GB.")
            if not l1_ok:
                print(f"     L1 error: {results[0].get('error')}")
            if not l2_ok:
                print(f"     L2 error: {results[1].get('error')}")
            print()
            print("  Recommendation: use qwen2.5:3b for Layer 2 to fit in 6 GB:")
            print("    OCR_EXTRACTOR_MODEL=qwen2.5:3b")
            print("  Or run sequentially (set OCR_TWO_LAYER_ENABLED=false as fallback).")

        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Test local Ollama for two-layer OCR pipeline")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Ollama base URL (default: {DEFAULT_URL})")
    parser.add_argument("--l1",  default=DEFAULT_L1,  help=f"Layer 1 model  (default: {DEFAULT_L1})")
    parser.add_argument("--l2",  default=DEFAULT_L2,  help=f"Layer 2 model  (default: {DEFAULT_L2})")
    args = parser.parse_args()

    print(f"\nOllama Local Capability Test")
    print(f"  URL      : {args.url}")
    print(f"  Layer 1  : {args.l1}  (GLM-OCR -- image -> markdown)")
    print(f"  Layer 2  : {args.l2}  (Qwen2.5 -- markdown -> JSON)")
    print(f"  GPU      : {vram_snapshot()}")

    asyncio.run(run(args.url, args.l1, args.l2))


if __name__ == "__main__":
    main()
