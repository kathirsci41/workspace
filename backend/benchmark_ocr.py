"""OCR Benchmark & Accuracy Test for DocPlatform V3"""
import os, base64, httpx, json, time, io, re
import fitz
from PIL import Image
from app.config import settings
from app.services.extraction.prompts import build_prompt, get_primary_field, EXTRACTION_PROMPTS

DOCS = [
    {"type": "CUSTOMER_PO",    "path": "documents/SKY-KA424/PO 10AK123456/CUSTOMER_PO/5f9dc4e3_Skylark_PO.pdf",                    "expected_primary": "18TB252000460"},
    {"type": "CUSTOMER_PO",    "path": "documents/SKY-AB321/1PTR2526000405/CUSTOMER_PO/8269a613_Skylark_PO.pdf",                    "expected_primary": "1PTR2526000405"},
    {"type": "VENDOR_DC",      "path": "documents/SKY-AB321/1PTR2526000405/VENDOR_DC/6a0b0a6d_1DNT2526DC2865.pdf",                  "expected_primary": "10TN252GDC2865"},
    {"type": "VENDOR_INVOICE", "path": "documents/SKY-KA424/PO 10AK123456/VENDOR_INVOICE/01b15915_C_Invoice_0.pdf",                 "expected_primary": "11SR2526000166"},
    {"type": "VENDOR_INVOICE", "path": "documents/SKY-AB321/1PTR2526000405/VENDOR_INVOICE/ef116881_C240847449_1OTM2526001448-Vendor_Invoice.pdf", "expected_primary": "C240847449"},
    {"type": "COMPANY_DC",     "path": "documents/SKY-KA424/PO 10AK123456/COMPANY_DC/2adc06ed_C_DC.pdf",                            "expected_primary": "1DNT2526DC2871"},
    {"type": "COMPANY_DC",     "path": "documents/SKY-AB321/1PTR2526000405/COMPANY_DC/f666b5cb_1DNT2526DC2865.pdf",                  "expected_primary": "10TN252GDC2865"},
    {"type": "COMPANY_INVOICE","path": "documents/SKY-KA424/PO 10AK123456/COMPANY_INVOICE/aff16e28_C_Invoice_1.pdf",                 "expected_primary": "11TR2526001751"},
    {"type": "COMPANY_INVOICE","path": "documents/SKY-AB321/1PTR2526000405/COMPANY_INVOICE/806da99e_1ITR2526001748.pdf",              "expected_primary": "IT12526001748"},
]


def render_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    page = doc.load_page(0)
    zoom = 200 / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    img.thumbnail((768, 768), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    doc.close()
    return buf.getvalue()


def call_ollama(img_bytes, prompt):
    b64 = base64.b64encode(img_bytes).decode()
    payload = {
        "model": "glm-ocr",
        "messages": [{"role": "user", "content": prompt, "images": [b64]}],
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 4096},
    }
    r = httpx.post("http://localhost:11434/api/chat", json=payload, timeout=180)
    return r.json().get("message", {}).get("content", "")


def parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
    # Clean comma-formatted numbers (e.g. 86,678.5 -> 86678.5)
    def clean_commas(t):
        t = re.sub(
            r'("\s*:\s*)(\d{1,3}(?:,\d{3})+(?:\.\d+)?)',
            lambda m: m.group(1) + m.group(2).replace(',', ''),
            t,
        )
        # Remove trailing commas before } or ]
        t = re.sub(r",\s*([}\]])", r"\1", t)
        return t
    try:
        return json.loads(text)
    except Exception:
        text = clean_commas(text)
        try:
            return json.loads(text)
        except Exception:
            pass
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            candidate = clean_commas(m.group())
            try:
                return json.loads(candidate)
            except Exception:
                pass
    return None


def main():
    print("=" * 80)
    print("DOCPLATFORM V3 - OCR BENCHMARK & ACCURACY TEST")
    print(f"Model: glm-ocr | Date: 2026-02-15 | Documents: {len(DOCS)}")
    print("=" * 80)

    results = []
    total_start = time.time()

    for i, doc in enumerate(DOCS):
        full_path = os.path.join(settings.nas_base_path, doc["path"])
        fname = os.path.basename(doc["path"])
        file_size = os.path.getsize(full_path) / 1024

        print(f"\n[{i+1}/{len(DOCS)}] {doc['type']} - {fname} ({file_size:.0f} KB)")

        # Render
        t0 = time.time()
        img_bytes = render_pdf(full_path)
        render_time = time.time() - t0

        # OCR
        prompt = build_prompt(doc["type"])
        t1 = time.time()
        raw = call_ollama(img_bytes, prompt)
        ocr_time = time.time() - t1

        # Parse
        data = parse_json(raw)
        total_time = render_time + ocr_time

        expected_fields = list(EXTRACTION_PROMPTS[doc["type"]]["schema"].keys())
        primary_field = get_primary_field(doc["type"])

        if data:
            filled = sum(
                1
                for f in expected_fields
                if data.get(f) is not None and str(data.get(f, "")).strip() != ""
            )
            total_f = len(expected_fields)
            fill_rate = filled / total_f * 100

            primary_val = data.get(primary_field, "")
            primary_match = str(primary_val).strip() == doc["expected_primary"]

            print(f"  Render: {render_time:.2f}s | OCR: {ocr_time:.2f}s | Total: {total_time:.2f}s")
            print(f"  Fields: {filled}/{total_f} filled ({fill_rate:.0f}%)")
            match_str = "MATCH" if primary_match else "MISMATCH"
            print(f'  Primary [{primary_field}]: "{primary_val}" vs "{doc["expected_primary"]}" -> {match_str}')

            for f in expected_fields:
                v = data.get(f)
                status = "+" if v is not None and str(v).strip() != "" else "-"
                val_str = str(v)[:60] if v else "null"
                print(f"    {status} {f}: {val_str}")

            results.append({
                "doc": fname, "type": doc["type"],
                "render_s": render_time, "ocr_s": ocr_time, "total_s": total_time,
                "filled": filled, "total_fields": total_f, "fill_rate": fill_rate,
                "primary_match": primary_match, "primary_extracted": str(primary_val),
                "primary_expected": doc["expected_primary"],
                "json_parsed": True,
            })
        else:
            print("  FAILED TO PARSE JSON")
            print(f"  Raw: {raw[:200]}")
            results.append({
                "doc": fname, "type": doc["type"],
                "render_s": render_time, "ocr_s": ocr_time, "total_s": total_time,
                "filled": 0, "total_fields": len(expected_fields), "fill_rate": 0,
                "primary_match": False, "primary_extracted": "",
                "primary_expected": doc["expected_primary"],
                "json_parsed": False,
            })

    total_elapsed = time.time() - total_start

    # Summary
    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY")
    print("=" * 80)

    json_success = sum(1 for r in results if r["json_parsed"])
    primary_matches = sum(1 for r in results if r["primary_match"])
    avg_fill = sum(r["fill_rate"] for r in results) / len(results) if results else 0
    avg_ocr = sum(r["ocr_s"] for r in results) / len(results) if results else 0
    avg_total = sum(r["total_s"] for r in results) / len(results) if results else 0
    total_filled = sum(r["filled"] for r in results)
    total_possible = sum(r["total_fields"] for r in results)

    print(f"Documents tested:       {len(DOCS)}")
    print(f"JSON parse success:     {json_success}/{len(DOCS)} ({json_success/len(DOCS)*100:.0f}%)")
    print(f"Primary ref match:      {primary_matches}/{len(DOCS)} ({primary_matches/len(DOCS)*100:.0f}%)")
    print(f"Total fields extracted: {total_filled}/{total_possible} ({total_filled/total_possible*100:.1f}%)")
    print(f"Avg field fill rate:    {avg_fill:.1f}%")
    print(f"Avg OCR time/doc:       {avg_ocr:.2f}s")
    print(f"Avg total time/doc:     {avg_total:.2f}s")
    print(f"Total benchmark time:   {total_elapsed:.1f}s")

    # Per-type breakdown
    print(f"\nPER-TYPE BREAKDOWN:")
    print(f"{'Type':<20} {'Docs':>4} {'JSON%':>6} {'PrimMatch':>10} {'FillRate':>9} {'AvgOCR':>8}")
    print("-" * 60)
    types = sorted(set(r["type"] for r in results))
    for t in types:
        tr = [r for r in results if r["type"] == t]
        j = sum(1 for r in tr if r["json_parsed"])
        pm = sum(1 for r in tr if r["primary_match"])
        fr = sum(r["fill_rate"] for r in tr) / len(tr)
        ao = sum(r["ocr_s"] for r in tr) / len(tr)
        print(f"{t:<20} {len(tr):>4} {j/len(tr)*100:>5.0f}% {pm}/{len(tr):>8} {fr:>8.1f}% {ao:>7.2f}s")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
