# Extraction & Verification Research — Order Assurance
*Caveman research report | June 2026*

---

## 0. Current State (baseline)

```
PDF input
  ├─ digital: PyMuPDF text layer
  └─ scanned: PP-OCRv4 GPU (PP-OCRv4_server_det + rec)
        └─ fallback: GLM-OCR (Ollama vision LLM)
               └─ regex parser → structured fields
                     └─ verifier (hard-coded ±2 tolerance, header-only, no line items)
```

Gaps: PP-OCRv4 outdated, GLM-OCR slot underused, no table structure parse, no line-item matching, hard-coded tolerance, no vendor master.

---

## 1. PaddleOCR Family — What Launched (2025–2026)

### PaddleOCR 3.0 (May/July 2025) — arXiv 2507.05595

Three pillars:

| Model | Role | Params | Key feature |
|---|---|---|---|
| **PP-OCRv5** | Text detection + recognition | <100M | Beats PP-OCRv4; best non-VLM multilingual OCR |
| **PP-StructureV3** | Document layout + table parse | pipeline | Layout → tables → markdown/JSON |
| **PP-ChatOCRv4** | Key information extraction | pipeline | 15pp better than v3; uses PP-DocBee2 + ERNIE 4.5 |

**PP-StructureV3 sub-models:**
- `PP-DocLayout-plus` — layout detection (text blocks, tables, figures)
- `PP-TableMagic` — table structure recognition (cells, rows, cols)
- `PP-FormulaNet_plus` — formula
- `PP-Chart2Table` — chart → table conversion
- Outputs: JSON + Markdown from full document

**PP-ChatOCRv4 pipeline stages:**
1. PP-StructureV3 (layout)
2. Vector retrieval module
3. PP-DocBee2 (PaddlePaddle's own document VLM)
4. ERNIE 4.5 Turbo (LLM — needs Baidu API unless self-hosted)
5. Result fusion

> Problem for Order Assurance: ERNIE 4.5 is Baidu cloud. Can swap with local Ollama model (Qwen2.5-VL or GLM-OCR) as LLM step.

---

### PaddleOCR-VL (Jan 2026 → May 2026)

| Version | OmniDocBench | Notes |
|---|---|---|
| PaddleOCR-VL 1.0 | 91.76 | Oct 2025 |
| **PaddleOCR-VL 1.5** | **94.5** | Jan 2026 — 0.9B, beat GPT-4o |
| **PaddleOCR-VL 1.6** | **96.33** | May 2026 — current leader |

0.9B param VLM. Image → markdown. Outperforms GPT-4o, Gemini 2.5 Pro, Mistral OCR3 on document benchmarks. Apache-licensed. Replaces both PP-OCRv4 AND the GLM-OCR fallback in one shot.

---

### OmniDocBench Leaderboard (June 2026)

```
PaddleOCR-VL-1.6     96.33  ← best open-source, 0.9B
MinerU2.5-Pro        95.69
GLM-OCR              ~95.0
PaddleOCR-VL-1.5     94.5
Mistral OCR3         85.20
GPT-4o               ~86
Gemini 2.5 Pro       ~85
```

GLM-OCR already present in Order Assurance stack — already at tier 3. PaddleOCR-VL-1.6 is the upgrade path.

---

## 2. Extraction Model Spectrum

### 2a. Deterministic / Rule-Based

**invoice2data** (github.com/invoice-x/invoice2data)
- YAML template per vendor → regex field map
- Best: fixed vendor set, known layouts, zero latency
- Worst: new vendor = new template; scanned PDFs fail
- Relevance: perfect for known vendor subset (Panimalar, Trade, AMC templates already implied)

**PyMuPDF text layer** (already in stack)
- Fastest. Zero inference. Perfect for digital PDFs.
- Fails: scanned, rotated, photo invoices

**Verdict for Order Assurance:** keep PyMuPDF for digital. invoice2data patterns usable for known vendors.

---

### 2b. ML — Layout-Aware Multimodal

**LayoutLMv3** (Microsoft, HuggingFace)
- Jointly models text + bounding boxes + image patches
- Fine-tuned on annotated invoices → near-perfect KIE for trained document types
- Needs labeled training data (100–1000 annotated docs)
- Good for: stable invoice formats from fixed vendor set
- Bad for: variable layouts, new vendors without retraining
- Fine-tuning guide: towardsdatascience.com/fine-tuning-layoutlm-v3

**DocLayout-YOLO** (opendatalab, github.com/opendatalab/DocLayout-YOLO)
- YOLO-v10 based, real-time layout detection
- Detects: text blocks, tables, figures, headings — bounding boxes + confidence
- Does NOT parse table internals — detection only
- Pair with PP-TableMagic or TableMaster for full table extraction
- pip: `doclayout-yolo`

**SynJAC** (arXiv 2410.01609)
- Synthetic data approach for domain-specific scanned document KIE
- Relevant if building training data for Indian GST invoice fine-tuning

---

### 2c. DL — End-to-End (OCR-Free)

**Donut** (ClovaAI, HuggingFace)
- Image → JSON, no OCR step
- Trained on synthetic document images
- Slower, needs GPU, good zero-shot but fine-tuning for specific docs helps
- Works on scanned and digital

**Nanonets-OCR-s** (github.com/inferless/nanonets-ocr-s)
- 3B model, Qwen2.5-VL-3B backbone fine-tuned on 3M+ document pages
- Image → Markdown with semantic understanding (tables, signatures, watermarks)
- Free for self-hosted. Markdown output → parse to JSON.
- Strong for invoices, receipts, passports

**Nanonets-OCR-3** (nanonets.com/research/nanonets-ocr-3)
- Newer version, OCR-free structured extraction with confidence scoring
- Purpose-built for AI agents with structured outputs

---

### 2d. VLM / VLLM

**Qwen2.5-VL** (7B, 72B — Ollama available)
- Best open VLM for invoice/form structured JSON extraction
- Supports: tables, multilingual (Hindi/English mixed), complex layouts
- Can run on existing Ollama setup in Order Assurance
- Prompt → structured JSON output enforced
- Fine-tuning guide: ubiai.tools/fine-tune-qwen2.5-vl

**Qwen3-VL** (latest — 2B to 235B)
- Dense and MoE variants, reasoning + structured output editions
- Structured JSON enforced output for invoice fields

**PaddleOCR-VL-1.6** (0.9B, PaddlePaddle)
- Current benchmark leader (96.33 OmniDocBench)
- Sub-1B: GPU inference feasible on existing hardware
- Replaces PP-OCRv4 + GLM-OCR in one model
- Apache licensed

**PP-DocBee2** (PaddlePaddle)
- PaddleOCR's specialized document VLM
- Used internally by PP-ChatOCRv4 pipeline
- Handles: printed text, handwriting, seals, tables, charts

**InternVL3-78B** (OmniDocBench top-tier, large)
- 78B — needs multi-GPU, overkill for production unless cloud

---

### 2e. Document Parsing Pipelines (full stack)

**MinerU 2.5** (github.com/opendatalab/MinerU, 2nd on OmniDocBench)
- 5 specialized models: layout detect, formula detect, table recognize, formula recog, OCR
- Stage 1: thumbnail global layout analysis
- Stage 2: high-resolution crop processing
- Output: Markdown + JSON. PDF/image/Office input.
- Strong for complex multi-page docs

**Docling** (IBM Research, github.com/docling-project/docling, 61k stars)
- MIT licensed. PDF, Office, images → unified DoclingDocument format
- Native integrations: LangChain, LlamaIndex, Haystack, CrewAI
- Built-in table detection, formula, reading order, OCR
- Best for AI pipeline integration; structured output ready for LLM consumption

**PP-StructureV3** (already in PaddleOCR 3.0 above)
- Closest to Order Assurance's existing stack
- Drop-in upgrade path

---

## 3. Indian GST / Multilingual Specifics

**UNI BILL** (ijsrset.com/paper/14224.pdf)
- Multilingual invoice extraction: English + Hindi + Marathi
- Extracts: invoice items, tax items (GST/SGST/CGST), totals → structured JSON
- Evaluates on varying layouts and noise

**TrustBill AI** (IJERT, Indian GST focus)
- GST invoice fraud detection + verification
- OCR + regex domain knowledge (GST number format, HSN codes) + ML
- Validates GSTIN format, checks consistency

**arXiv 2602.16430** — "Designing Production-Scale OCR for India"
- Multilingual Indian languages, domain-specific systems
- Covers script diversity challenges (Devanagari, Tamil, etc.)

**Key Indian-specific fields to handle:**
- GSTIN: `[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}`
- HSN/SAC codes: 4-8 digit numeric
- GST components: IGST / (CGST + SGST) depending on inter/intra state
- E-way bill number, LR number, DC number — logistics-specific
- Bilingual headers common (English field labels, Indian language values)

PP-OCRv5 explicitly targets multilingual including Indian scripts. PaddleOCR-VL handles mixed-language docs.

---

## 4. Verification Engine Research

### Current gap
```python
# backend/app/services/order_bundle_verifier.py ~line 339
elif abs(left_value - right_value) <= 2:  # hard-coded ±2 absolute
```

No line-item comparison. Header-only amounts. No vendor master.

### Industry patterns

**Three-way match in production:**
- PO line items ↔ GRN/DC quantities ↔ Invoice line items
- Tolerance: percentage-based (1–3%) OR absolute (±₹50) — never both hardcoded to ±2
- Exception routing: if mismatch → flag, not fail-hard
- Partial receipt handling: DC may cover subset of PO lines

**AI agent invoice matching** (saxon.ai/blogs)
- Agent receives PO + DC + Invoice
- Extracts line items from each
- Normalizes: item codes, UOM (pieces vs dozen), GST-inclusive vs exclusive amounts
- Matches by HSN code or description similarity (fuzzy)
- Flags: quantity shortfall, price variance, tax calculation error
- Output: approved / flagged-for-review / rejected

**Tolerance config pattern:**
```python
class ToleranceConfig:
    percentage: float = 0.02          # 2% default
    absolute_floor: float = 5.0       # ≤₹5 always pass regardless of %
    per_field_overrides: dict[str, float] = {}  # field-level override
```

### Verification improvements needed for Order Assurance:

1. **Line-item extraction**: PP-StructureV3 / MinerU → table → line items as list of dicts
2. **HSN-based matching**: primary key for item reconciliation (DC + Invoice HSN must match)
3. **GST computation check**: verify IGST = taxable_amount × igst_rate; flag if disagree
4. **GSTIN validation**: regex + checksum (last digit Luhn-like)
5. **Percentage tolerance**: replace ±2 with configurable %
6. **SO→DC→Invoice chain**: SO number must appear in DC must appear in Invoice
7. **Vendor master lookup**: GSTIN → vendor record → flag if Invoice GSTIN ≠ registered GSTIN

---

## 5. Recommended Extraction Pipeline Upgrade

### Option A — Minimal (same stack, better models)

```
PDF
  ├─ digital: PyMuPDF (unchanged)
  └─ scanned: PP-OCRv5 (upgrade from PP-OCRv4)
        └─ table regions: PP-StructureV3 / PP-TableMagic
        └─ fallback KIE: Qwen2.5-VL-7B via Ollama (already present, replaces GLM-OCR)
               └─ structured regex parser (enhanced with line-item patterns)
                     └─ verifier (ToleranceConfig + line-item + GSTIN validation)
```

Cost: low. PP-OCRv5 is drop-in upgrade. PP-StructureV3 adds table parse.

### Option B — Modern VLM (best accuracy)

```
PDF
  ├─ digital: PyMuPDF (unchanged)
  └─ scanned/complex: PaddleOCR-VL-1.6 (0.9B, replaces both PP-OCRv4 + GLM-OCR)
        └─ structured output → JSON fields + table rows
               └─ rule-based validation layer (GSTIN regex, HSN check, GST math)
                     └─ verifier (ToleranceConfig + line-item reconciliation)
```

Cost: GPU inference for 0.9B model — runs on existing GPU setup. Eliminates two model hops.

### Option C — Full pipeline (highest accuracy, most complex)

```
PDF → MinerU 2.5 / PP-StructureV3
    → Layout JSON (text blocks + table cells)
    → Regex KIE for known fields
    → PaddleOCR-VL for ambiguous/fallback fields
    → Structured field dict + line_items list
    → Verifier (tolerance + line-item + vendor master)
    → Export
```

---

## 6. Model Selection Matrix — Order Assurance Context

| Model | Speed | Accuracy | GPU RAM | Indian GST | Table | Self-hosted | Verdict |
|---|---|---|---|---|---|---|---|
| PP-OCRv4 (current) | fast | good | 2GB | partial | no | yes | **replace** |
| **PP-OCRv5** | fast | better | 2GB | yes | no | yes | **upgrade OCR** |
| **PaddleOCR-VL-1.6** | medium | best (96.33) | 4GB | yes | yes | yes | **best single model** |
| **PP-StructureV3** | medium | high | 3GB | yes | yes | yes | **add for tables** |
| GLM-OCR (current fallback) | slow | high | 8GB+ | yes | partial | yes | **replace with PaddleOCR-VL** |
| Qwen2.5-VL-7B | slow | high | 14GB | yes | yes | yes | **good KIE fallback, already in Ollama** |
| LayoutLMv3 fine-tuned | fast | very high | 4GB | needs training | yes | yes | **long-term option after data collected** |
| MinerU2.5 | slow | 95.69 | 4GB | yes | yes | yes | **alternative full pipeline** |
| Docling | medium | high | CPU | yes | yes | yes | **best for AI pipeline integration** |
| invoice2data templates | instant | perfect(known) | none | yes | no | yes | **use for known vendors** |

---

## 7. Specific GitHub Repos

| Repo | Purpose | Stars |
|---|---|---|
| github.com/PaddlePaddle/PaddleOCR | PP-OCRv5, PP-StructureV3, PP-ChatOCRv4 | 50k+ |
| github.com/opendatalab/MinerU | Full doc parse pipeline | 30k+ |
| github.com/docling-project/docling | IBM doc parser, AI pipeline ready | 61k |
| github.com/opendatalab/DocLayout-YOLO | Layout detection YOLO-v10 | 5k+ |
| github.com/invoice-x/invoice2data | Template-based extraction | 2k+ |
| github.com/NanoNets/docext | OCR-free extraction, IDP leaderboard | active |
| github.com/NanoNets/docstrange | Doc → Markdown/JSON/CSV/HTML | active |
| github.com/opendatalab/OmniDocBench | CVPR 2025 benchmark | reference |

---

## 8. Priority Actions for Order Assurance

### Extraction (priority order)

1. **Upgrade PP-OCRv4 → PP-OCRv5** (1 line change in config). Immediate improvement, no arch change.
2. **Add PP-StructureV3 table detection** on Vendor Invoice document type. Prerequisite for line-item matching.
3. **Replace GLM-OCR fallback → PaddleOCR-VL-1.6** (0.9B, same GPU footprint, 96.33 accuracy).
4. **Add invoice2data templates** for known vendors (Panimalar, Trade, AMC) as fast-path before OCR.
5. **GSTIN regex validation** in parser — zero inference cost, catch bad extractions immediately.

### Verification (priority order)

1. **Replace ±2 hardcode → ToleranceConfig** (ADR-003 already designed, implement).
2. **Line-item parser** on table output from PP-StructureV3 → produce `line_items: List[LineItemRecord]`.
3. **GST math check**: taxable_amount × rate = component_tax. Flag if diff > tolerance.
4. **SO→DC→Invoice chain validation**: cross-check SO number presence across documents.
5. **GSTIN vendor master**: store GSTIN on first successful extraction; flag future mismatches.

---

## 9. Key Papers

| Paper | Relevance |
|---|---|
| arXiv 2507.05595 — PaddleOCR 3.0 | PP-OCRv5, PP-StructureV3, PP-ChatOCRv4 |
| arXiv 2601.21957 — PaddleOCR-VL 1.5 | 0.9B beats GPT-4o |
| arXiv 2412.07626 — OmniDocBench | Benchmark for all models |
| arXiv 2510.15727 — Invoice Information Extraction | Methods comparison |
| arXiv 2602.16430 — Indian OCR Production | Indian multilingual specifics |
| arXiv 2409.18839 — MinerU | Full pipeline architecture |
| arXiv 2410.12628 — DocLayout-YOLO | Layout detection |

---

*End of research report.*
