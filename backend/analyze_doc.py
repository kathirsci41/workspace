"""
Document field inventory analyzer.
Usage: python analyze_doc.py <pdf_path> [page_number]
Sends each page to glm-ocr with a field-inventory prompt (no real values leaked).
"""

import sys, os, base64, json, io, time
import fitz  # PyMuPDF
from PIL import Image
import httpx

ANALYSIS_PROMPT = r'''You are analyzing a confidential business document image/text. DO NOT output any sensitive values:
- Do NOT output names, addresses, phone/email, bank details, IDs (GSTIN/PAN/etc), invoice/PO/DC/SO numbers, amounts, dates, or any other real values.

You must output ONLY:
- field labels you see (exact label text)
- where the label/value appears (header/body/table/summary/footer)
- masked value SHAPES (letters->A, digits->#, keep separators like "-", "/", ".", ":", spaces)

Masking rules (strict):
- Replace every letter with "A" and every digit with "#", but keep punctuation and spaces.
  Examples:
  - "INV-2024/0912" -> "AAA-####/####"
  - "12/03/2025" -> "##/##/####"
  - "₹1,23,456.78" -> "₹#,##,###.##"
- For any person/company name: "<NAME>"
- Address: "<ADDRESS>"
- Email: "<EMAIL>"
- Phone: "<PHONE>"
- Any identifier (GSTIN/PAN/IRN/E-way/Account/IFSC/etc): "<ID>"

Document types (choose one):
- purchase_order
- vendor_invoice
- vendor_delivery_challan
- company_invoice
- company_delivery_challan
- acknowledgement
- unknown

Task:
1) Classify document_type_guess from the list above.
2) Describe layout regions briefly (header/body/table/summary/footer).
3) Build a field inventory. For each field:
   - field_key (snake_case you propose)
   - label_variants_found (exact label text(s) you see)
   - location (header/body/table/summary/footer)
   - value_shape_examples (1-3 masked shapes only; never raw)
   - disambiguation_notes (how to choose if multiple candidates)
4) If there is a line-items table:
   - capture table_headers (exact strings)
   - row_pattern_notes (how rows look; multi-line descriptions; merged cells)
   - totals_rows_keywords (e.g., Subtotal/Total/Grand Total/Round Off)
5) Note OCR risks: rotation, stamps, signatures, faded scan, watermark, handwriting, skew, etc.

Important cross-doc reference numbers to watch for (may appear in only some docs):
PO No, SO No (Sales Order / S.O. / SO#), Invoice No, Delivery Challan No (DC No), GRN, Gate Pass, LR No, E-way Bill, IRN/QR.

Output STRICT JSON only with this schema:
{
  "document_type_guess": "",
  "layout": {
    "has_table": false,
    "regions": [
      {"region":"header|body|table|summary|footer","description":""}
    ]
  },
  "fields": [
    {
      "field_key": "",
      "label_variants_found": [],
      "location": "",
      "value_shape_examples": [],
      "disambiguation_notes": ""
    }
  ],
  "table": {
    "table_presence": false,
    "table_headers": [],
    "row_pattern_notes": "",
    "totals_rows_keywords": []
  },
  "ocr_risks": []
}

Return ONLY the JSON.'''


def pdf_page_to_b64(pdf_path: str, page_num: int = 0, max_dim: int = 1024) -> str:
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


def analyze_page(pdf_path: str, page_num: int = 0) -> dict:
    b64, total_pages = pdf_page_to_b64(pdf_path, page_num)
    payload = {
        "model": "glm-ocr",
        "messages": [
            {"role": "user", "content": ANALYSIS_PROMPT, "images": [b64]}
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
    # Try to parse JSON from response
    try:
        # Find JSON block
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(content[start:end])
            result["_meta"] = {
                "page": page_num + 1,
                "total_pages": total_pages,
                "elapsed_sec": round(elapsed, 1),
                "response_chars": len(content)
            }
            return result
    except json.JSONDecodeError:
        pass
    
    return {
        "raw_response": content[:3000],
        "_meta": {
            "page": page_num + 1,
            "total_pages": total_pages,
            "elapsed_sec": round(elapsed, 1),
            "parse_error": True
        }
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_doc.py <pdf_path> [page_number]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    page = int(sys.argv[2]) - 1 if len(sys.argv) > 2 else 0
    
    fname = os.path.basename(pdf_path)
    print(f"\n{'='*70}")
    print(f"ANALYZING: {fname}")
    print(f"{'='*70}")
    
    result = analyze_page(pdf_path, page)
    print(json.dumps(result, indent=2, ensure_ascii=False))
