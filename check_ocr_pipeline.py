"""
End-to-end OCR pipeline check.

Tests both the single-layer (existing) and two-layer (new) pipelines
on a real COMPANY_DC document.
"""
import asyncio
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

STORAGE_ROOT = os.path.join(
    os.path.dirname(__file__), "storage", "documents", "documents",
)

# Test documents to run — list of (pdf_path, doc_type) tuples
TEST_DOCS = [
    (
        os.path.join(STORAGE_ROOT, "TEST-BRT001", "BRUTAL-PO-001", "CUSTOMER_PO", "9bc66021_brutal_test.pdf"),
        "CUSTOMER_PO",
    ),
    (
        os.path.join(STORAGE_ROOT, "TEST-BRT001", "BRUTAL-PO-001", "VENDOR_INVOICE", "1c30e1bd_test2.pdf"),
        "VENDOR_INVOICE",
    ),
]

# Will be set per-document in main()
PDF_PATH = TEST_DOCS[0][0]
DOC_TYPE = TEST_DOCS[0][1]


def hr():
    print("=" * 60)


async def test_single_layer():
    from backend.app.services.extraction.pdf_converter import PDFConverter
    from backend.app.services.extraction.ocr_client import OCRClient
    from backend.app.services.extraction.prompts import EXTRACTION_PROMPTS, build_prompt
    from backend.app.services.extraction.response_parser import ResponseParser

    hr()
    print("  SINGLE-LAYER PIPELINE (existing: glm-ocr)")
    hr()
    print()

    # 1. PDF → images
    print("[1] Converting PDF to images...")
    converter = PDFConverter(dpi=200, max_pages=10)
    images = converter.convert_to_images(PDF_PATH)
    sizes = [len(img) // 1024 for img in images]
    print(f"    Pages: {len(images)}, sizes: {sizes} KB")

    # 2. OCR each page
    print("[2] Running GLM-OCR...")
    client = OCRClient("http://localhost:11434", "glm-ocr", timeout=120, max_retries=2)
    prompt = build_prompt(DOC_TYPE)

    raw_texts = []
    total_ms = 0
    for i, img in enumerate(images):
        t0 = time.time()
        result = await client.extract_from_image(img, prompt)
        ms = int((time.time() - t0) * 1000)
        total_ms += ms
        raw_texts.append(result["text"])
        chars = len(result["text"])
        print(f"    Page {i+1}: {ms}ms, {chars} chars")
        if i < len(images) - 1:
            await client.release_model()
            await asyncio.sleep(2)

    # 3. Parse + merge
    print("[3] Parsing and merging...")
    parser = ResponseParser()
    merged = parser.parse_and_merge(raw_texts, DOC_TYPE)
    schema_fields = list(EXTRACTION_PROMPTS[DOC_TYPE]["schema"].keys())
    confidence = parser.calculate_confidence(merged, schema_fields)

    print(f"    Confidence: {confidence}%")
    print(f"    Total time: {total_ms}ms")
    print("    Fields extracted:")
    for k, v in merged.items():
        if v is not None:
            print(f"      {k}: {v}")

    await client.release_model()
    print()
    return merged


async def test_two_layer():
    from backend.app.services.extraction.pdf_converter import PDFConverter
    from backend.app.services.extraction.two_layer_client import TwoLayerClient
    from backend.app.services.extraction.glm_ocr_prompts import EXTRACTION_SCHEMAS

    hr()
    print("  TWO-LAYER PIPELINE (new: glm-ocr:latest -> gemma3:12b cloud)")
    hr()
    print()

    # 1. PDF → images
    print("[1] Converting PDF to images...")
    converter = PDFConverter(dpi=200, max_pages=10)
    images = converter.convert_to_images(PDF_PATH)
    sizes = [len(img) // 1024 for img in images]
    print(f"    Pages: {len(images)}, sizes: {sizes} KB")

    # 2. Two-layer extraction
    print("[2] Running two-layer pipeline...")
    client = TwoLayerClient(
        base_url="http://localhost:11434",
        ocr_model="glm-ocr:latest",
        extractor_model="gemma3:12b",
        timeout=300,
        max_retries=3,
        save_debug_markdown=True,
        debug_markdown_dir=os.path.join(os.path.dirname(__file__), "debug_markdown"),
    )

    all_fields = {}
    raw_texts = []
    total_ocr_ms = 0
    total_extract_ms = 0

    for i, img in enumerate(images):
        try:
            result = await client.extract(img, DOC_TYPE, f"page_{i+1}")
            raw_texts.append(result["text"])
            total_ocr_ms += result["ocr_ms"]
            total_extract_ms += result["extract_ms"]

            chars = len(result["text"])
            n_fields = len([v for k, v in result["fields"].items() if v is not None and not str(k).startswith("_")])
            print(f"    Page {i+1}: OCR {result['ocr_ms']}ms, Extract {result['extract_ms']}ms, {chars} chars, {n_fields} fields")

            # Merge fields (first non-null wins)
            for k, v in result["fields"].items():
                if k not in all_fields or all_fields[k] is None:
                    all_fields[k] = v
        except Exception as e:
            err_msg = str(e)[:120]
            print(f"    Page {i+1}: FAILED -- {type(e).__name__}: {err_msg}")
            # Reset circuit breaker so next page can try
            client._consecutive_failures = 0

    # 3. Confidence
    schema_fields = list(EXTRACTION_SCHEMAS.get(DOC_TYPE, {}).keys())
    filled = sum(1 for f in schema_fields if all_fields.get(f) is not None)
    confidence = round((filled / len(schema_fields)) * 100) if schema_fields else 0

    print()
    print(f"    Confidence: {confidence}%")
    print(f"    OCR time: {total_ocr_ms}ms, Extract time: {total_extract_ms}ms")
    print(f"    Total time: {total_ocr_ms + total_extract_ms}ms")
    print("    Fields extracted:")
    for k, v in all_fields.items():
        if v is not None and not str(k).startswith("_"):
            print(f"      {k}: {v}")

    # Validation metadata
    if "_validation" in all_fields:
        print("    Validation flags:")
        for k, v in all_fields["_validation"].items():
            print(f"      {k}: {v}")

    try:
        await client.release_model()
    except Exception:
        pass
    print()
    return all_fields


async def main():
    global PDF_PATH, DOC_TYPE

    for doc_idx, (pdf_path, doc_type) in enumerate(TEST_DOCS):
        PDF_PATH = pdf_path
        DOC_TYPE = doc_type

        if not os.path.exists(PDF_PATH):
            print(f"ERROR: Test PDF not found: {PDF_PATH}")
            continue

        print()
        print("#" * 70)
        print(f"  DOCUMENT {doc_idx+1}/{len(TEST_DOCS)}: {os.path.basename(PDF_PATH)}")
        print(f"  Type: {DOC_TYPE}")
        print("#" * 70)
        print()

        # Test 1: Single-layer
        single_result = await test_single_layer()

        # Test 2: Two-layer
        two_layer_result = await test_two_layer()

        # Compare
        hr()
        print("  COMPARISON")
        hr()
        print()
        all_keys = set()
        for k in single_result:
            if not str(k).startswith("_"):
                all_keys.add(k)
        for k in two_layer_result:
            if not str(k).startswith("_"):
                all_keys.add(k)

        print(f"  {'Field':<25} {'Single-Layer':<30} {'Two-Layer':<30}")
        print(f"  {'-'*25} {'-'*30} {'-'*30}")
        for k in sorted(all_keys):
            v1 = single_result.get(k, "-")
            v2 = two_layer_result.get(k, "-")
            if v1 is None:
                v1 = "(null)"
            if v2 is None:
                v2 = "(null)"
            marker = " *" if str(v1) != str(v2) else ""
            print(f"  {k:<25} {str(v1):<30} {str(v2):<30}{marker}")

        print()
        print("  * = values differ between pipelines")
        print()


if __name__ == "__main__":
    asyncio.run(main())
