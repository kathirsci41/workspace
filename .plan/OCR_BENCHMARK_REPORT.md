# OCR Model Benchmark Report

**Date:** 2026-02-15  
**Platform:** DocPlatform V3.0  
**Test Documents:** 5 PDFs from `.test/` folder  
**Hardware:** Local Ollama inference (CPU/GPU)

---

## Models Tested

| Model | Size | Type |
|---|---|---|
| glm-ocr | 2.2 GB | Vision-Language (production) |
| granite3.2-vision | 2.4 GB | Vision-Language |
| minicpm-v | 5.5 GB | Vision-Language |
| deepseek-ocr | 6.7 GB | Vision OCR |
| Chandra OCR (GGUF Q4_K_M) | 6.2 GB | Vision-Language (Qwen3-VL based) |

## Test Documents

| File | Document Type | Known Reference |
|---|---|---|
| Skylark PO.pdf | CUSTOMER_PO | 18TB252000460 |
| C DC.pdf | COMPANY_DC | 1DNT2526DC2871 |
| C Invoice 0.pdf | VENDOR_INVOICE | 11SR2526000166 |
| C Invoice 1.pdf | COMPANY_INVOICE | 11TR2526001751 |
| Vendor invoice.pdf | VENDOR_INVOICE | (new document) |

---

## Test 1: Structured JSON Extraction

Each model was given the production prompt (system prompt + document-type-specific fields) and asked to return structured JSON.

### Results Summary

| Model | JSON Parse | Primary Match | Similarity | Fill Rate | Avg Speed | Total |
|---|---|---|---|---|---|---|
| **glm-ocr** | **5/5 (100%)** | 0/4 | **80%** | **95.1%** | **7.2s** | **35.9s** |
| granite3.2-vision | 5/5 (100%) | **1/4** | 52% | 93.3% | 9.3s | 46.3s |
| minicpm-v | 4/5 (80%) | 0/4 | 26% | 69.0% | 35.2s | 176.0s |
| deepseek-ocr | 0/5 (0%) | 0/4 | 0% | 0% | 17.5s | 87.5s |
| chandra-ocr | 0/5 (0%) | 0/4 | 0% | 0% | 28.3s | 141.7s |

### Per-Document Primary Reference Extraction

| Document | Expected | glm-ocr | granite3.2 | minicpm-v |
|---|---|---|---|---|
| Skylark PO.pdf | `18TB252000460` | `18PBT252000460` (86%) | `1PBT2R32604040` (43%) | `18AC532064` (38%) |
| C DC.pdf | `1DNT2526DC2871` | `10T2526D2C2871` (79%) | `33AAECM825172B` (0%) | JSON FAIL |
| C Invoice 0.pdf | `11SR2526000166` | `ISR252600166` (79%) | `15PR2520R00168` (64%) | `1825064` (36%) |
| C Invoice 1.pdf | `11TR2526001751` | `IT1R2526001751` (79%) | `11TR2526001751` (100%) | `1825036` (29%) |
| Vendor invoice.pdf | — | `TCH02329119140` | `ITCH0523116410` | `SA23546A-18H` |

---

## Test 2: Raw OCR (No JSON, Pure Text Extraction)

Prompt: *"Read all the text in this document image. Extract every word and number exactly as printed."*

### Results Summary

| Model | Has Output | Ref Found in Text | Avg Chars | Avg Speed | Total |
|---|---|---|---|---|---|
| **glm-ocr** | 4/5 | 0/4 | 1,714 | 20.3s | 101.6s |
| granite3.2-vision | 5/5 | 0/4 | 4,303 | 36.8s | 184.0s |
| minicpm-v | 5/5 | 0/4 | 1,871 | 25.1s | 125.6s |
| deepseek-ocr | 0/5 | 0/4 | 0 | 14.7s | 73.3s |
| chandra-ocr | 0/5 | 0/4 | 0 | 28.4s | 142.0s |

### Per-Document Reference Search in Raw Text

| Document | Expected | glm-ocr | granite3.2 | minicpm-v |
|---|---|---|---|---|
| Skylark PO.pdf | `18TB252000460` | NOT-FOUND (31%) | NOT-FOUND (38%) | NOT-FOUND (38%) |
| C DC.pdf | `1DNT2526DC2871` | NOT-FOUND (50%) | NOT-FOUND (57%) | NOT-FOUND (29%) |
| C Invoice 0.pdf | `11SR2526000166` | NOT-FOUND (64%) | NOT-FOUND (43%) | NOT-FOUND (36%) |
| C Invoice 1.pdf | `11TR2526001751` | NEAR 79%: `IT1R2526001751` | NOT-FOUND (57%) | NOT-FOUND (43%) |

---

## Key Findings

1. **glm-ocr is the clear production winner** — fastest (7.2s/doc), 100% JSON parse rate, highest fill rate (95.1%), highest character similarity (80%).

2. **granite3.2-vision** is second — got 1 exact match on C Invoice 1 but performed worse overall (52% similarity). Some fields extracted completely wrong values (GST number as DC number).

3. **minicpm-v hallucinates** — fabricates reference numbers entirely. Slow at 35s/doc. Not viable.

4. **deepseek-ocr is non-functional** — returns empty/echo of prompt. 0% success across both test modes.

5. **Chandra OCR GGUF does not work via Ollama** — generates 0 tokens (eval_count=0) for every prompt. The GGUF conversion for Qwen3-VL architecture is incompatible with Ollama's inference pipeline.

6. **Structured JSON prompts outperform raw OCR** — glm-ocr achieved 80% character similarity with JSON prompt vs only 31-64% in raw text mode. The structured prompt focuses the model's attention on specific fields.

7. **Character confusion is fundamental** — all models struggle with similar characters (I/1, T/P, 0/O/D). This is a limitation of small vision models on dense document text.

---

## Recommendation

**Production model: glm-ocr** (2.2 GB)
- Configuration: temperature=0.0, num_predict=4096, image max_dim=768, DPI=200
- Strengths: Fast, reliable JSON output, high fill rate
- Weakness: Character confusion on reference numbers (~80% similarity)
- Future improvement: Post-processing pattern correction for known reference formats

---

## Previous Benchmark (9-document suite from storage)

Run on the full 9-document set stored in the platform:

| Metric | Result |
|---|---|
| JSON parse success | 9/9 (100%) |
| Primary ref match | 5/9 (56%) |
| Total field fill rate | 94.2% |
| Avg OCR time/doc | 6.07s |

The 4 mismatches were the same character-confusion patterns seen in the 5-doc benchmark above.
