"""
Raw OCR text extraction for document analysis.
Usage: python extract_raw.py <pdf_path> [page_number]
"""

import sys, os, base64, json, io, time
import fitz  # PyMuPDF
from PIL import Image
import httpx

RAW_PROMPT = "Extract ALL text from this document image exactly as it appears. Include every label, number, header, footer, table content, and any printed text. Preserve the layout structure. Output the raw text only, no JSON."


def pdf_page_to_b64(pdf_path: str, page_num: int = 0, max_dim: int = 1024) -> tuple:
    doc = fitz.open(pdf_path)
    if page_num >= len(doc):
        page_num = len(doc) - 1
    page = doc.load_page(page_num)
    zoom = 200 / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    total_pages = len(doc)
    doc.close()
    return base64.b64encode(buf.getvalue()).decode(), total_pages


def extract_text(pdf_path: str, page_num: int = 0) -> dict:
    b64, total_pages = pdf_page_to_b64(pdf_path, page_num)
    payload = {
        "model": "glm-ocr",
        "messages": [
            {"role": "user", "content": RAW_PROMPT, "images": [b64]}
        ],
        "stream": False,
        "options": {"temperature": 0.01, "num_predict": 4096},
    }
    t0 = time.time()
    r = httpx.post("http://localhost:11434/api/chat", json=payload, timeout=300)
    elapsed = time.time() - t0
    
    if r.status_code != 200:
        return {"error": f"Ollama HTTP {r.status_code}", "body": r.text[:500]}
    
    content = r.json().get("message", {}).get("content", "")
    return {
        "text": content,
        "page": page_num + 1,
        "total_pages": total_pages,
        "elapsed_sec": round(elapsed, 1),
        "chars": len(content)
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_raw.py <pdf_path> [page_number]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    fname = os.path.basename(pdf_path)
    
    # Get total pages
    doc = fitz.open(pdf_path)
    total = len(doc)
    doc.close()
    
    if len(sys.argv) > 2:
        pages = [int(sys.argv[2]) - 1]
    else:
        pages = list(range(min(total, 3)))  # Max 3 pages
    
    print(f"\n{'='*70}")
    print(f"FILE: {fname}  ({total} pages)")
    print(f"{'='*70}")
    
    for p in pages:
        print(f"\n--- PAGE {p+1}/{total} ---")
        result = extract_text(pdf_path, p)
        if "error" in result:
            print(f"ERROR: {result['error']}")
        else:
            print(f"[{result['elapsed_sec']}s, {result['chars']} chars]")
            print(result["text"])
        print()
