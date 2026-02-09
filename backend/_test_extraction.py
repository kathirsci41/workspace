"""Quick test: PDF->Image->Ollama OCR pipeline (no timeout)."""
import os, sys, base64, tempfile, asyncio, time

import fitz  # PyMuPDF
import httpx

PDF_PATH = r"E:\PROJECTS\Experiments\Logistic\Phases-2\backend\storage\cases\CASE-2026-0001\2026-01\SO-10AK1234556\VENDOR_DC\431737a0_ITICHG0325119410_1OTM2526001428-vendor_invoice.pdf"

def main():
    t0 = time.perf_counter()

    # Step 1: PDF to image
    print("Step 1: Converting PDF to image (PyMuPDF)...")
    doc = fitz.open(PDF_PATH)
    print(f"  -> {doc.page_count} page(s)")
    page = doc[0]
    zoom = 200 / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    temp_path = os.path.join(tempfile.gettempdir(), "test_ocr_page.jpg")
    pix.save(temp_path, "JPEG")
    doc.close()
    pdf_time = time.perf_counter() - t0
    print(f"  -> Saved: {temp_path} ({os.path.getsize(temp_path)} bytes) [{pdf_time:.2f}s]")

    # Step 2: Encode
    with open(temp_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    print(f"Step 2: Base64 encoded ({len(img_b64)} chars)")

    # Step 3: Call Ollama (NO TIMEOUT)
    print("Step 3: Calling Ollama glm-ocr with image (no timeout - waiting for completion)...")

    async def call_ocr():
        ocr_start = time.perf_counter()
        async with httpx.AsyncClient(timeout=None) as client:
            resp = await client.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": "glm-ocr",
                    "messages": [{
                        "role": "user",
                        "content": "Extract text from this document image. Return JSON.",
                        "images": [img_b64]
                    }],
                    "stream": False,
                    "options": {"temperature": 0.01, "num_predict": 4096, "num_ctx": 8192}
                }
            )
            ocr_time = time.perf_counter() - ocr_start
            print(f"  -> Status: {resp.status_code} [{ocr_time:.2f}s]")
            if resp.status_code == 200:
                data = resp.json()
                content = data["message"]["content"]
                print(f"  -> OCR Output ({len(content)} chars):")
                print(content[:1000])
            else:
                print(f"  -> ERROR: {resp.text[:500]}")

    asyncio.run(call_ocr())

    total = time.perf_counter() - t0
    print(f"\nTotal time: {total:.2f}s")

    os.remove(temp_path)
    print("Done.")

if __name__ == "__main__":
    main()
