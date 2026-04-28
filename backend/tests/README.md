# Backend Test Suite

## Benchmark Framework (Local-Only)

**IMPORTANT:** This benchmark uses **SYNTHETIC DATA ONLY**. No customer documents.

### Ground Truth (Immutable)

File: `fixtures/benchmark_ground_truth.csv`

- Contains expected values for 10 synthetic test documents
- Human-curated reference set (never programmatically modified)
- Committed to version control (permanent reference)
- Each row defines a test document's expected extraction outputs

Fields:
- `document_id` — unique ID for the test case
- `file_name` — synthetic test document name
- `document_type` — enum (CUSTOMER_PO, COMPANY_DC, etc.)
- `file_path` — path to PDF in fixtures
- `expected_po_number` — canonical expected value
- `expected_amount` — canonical expected value
- `source` — always "Synthetic template" (documents generated from templates, not real customer data)

### Model Output (Mutable, Timestamped)

Directory: `results/<ISO-timestamp>/`

When running the benchmark:

```bash
python backend/tests/local_benchmark_runner.py
```

Output files are written to a **new timestamped directory** each run:
- `results/2026-04-28T18:30:45.123456/candidates.csv` — model extraction output (only this run)
- Never overwrites previous results
- Never modifies `ground_truth.csv`

### Comparison Workflow

1. **Read** immutable ground truth: `fixtures/benchmark_ground_truth.csv`
2. **Run** extraction on synthetic test documents using local Ollama
3. **Write** model output to: `results/<timestamp>/candidates.csv`
4. **Compare** ground_truth vs candidates (manual or via test script)
5. **Document** accuracy deltas (reference_number match %, amount match %, etc.)
6. **Archive** results (timestamped, safe to delete old runs)

### Safety Gates

The benchmark runner enforces:

- ✅ **Local-only endpoints** — `http://localhost:11434` or `http://127.0.0.1:11434`
- ✅ **Blocks external endpoints** — prevents RunPod/cloud exfiltration
- ✅ **Synthetic data only** — no customer PDFs loaded
- ✅ **Never overwrites ground truth** — separate result files per run
- ✅ **Timestamped outputs** — prevents accidental data loss
- ✅ **Requires explicit opt-in** — `BENCHMARK_MODE=true` environment variable

### Running the Benchmark

#### Prerequisites

```bash
# Ensure Ollama is running locally
ollama serve

# In another terminal, pull models if needed
ollama pull glm-ocr
ollama pull gemma4:e4b
```

#### Run Benchmark

```bash
# Set environment variables
export OLLAMA_ENDPOINT=http://localhost:11434
export BENCHMARK_MODE=true
export OCR_MODEL=glm-ocr
export EXTRACTION_MODEL=gemma4:e4b

# Run benchmark
cd backend
python -m pytest tests/local_benchmark_runner.py
# or
python tests/local_benchmark_runner.py
```

#### Output

```
================================================================================
LOCAL BENCHMARK RUNNER — Synthetic Data Only
================================================================================
✓ Endpoint validated: http://localhost:11434
✓ Benchmark mode: enabled
✓ Using synthetic data only (no customer documents)

Loaded 10 synthetic test documents

[1/10] test_po_basic.pdf... OCR OK (8.2s) > Extract (13.4s)
[2/10] test_po_complex.pdf... OCR OK (21.3s) > Extract (12.8s)
...

================================================================================
BENCHMARK RESULTS (Synthetic Data)
================================================================================

Success rate: 10/10 documents (100.0%)

OCR (Layer 1):
  Average: 15.0 sec/doc

Extraction (Layer 2):
  Average: 13.4 sec/doc

Total Pipeline:
  Average: 28.4 sec/doc
  Throughput: 127 docs/hour

Results saved to: results/2026-04-28T18:30:45.123456/candidates.csv
NOTE: Ground truth (fixtures/benchmark_ground_truth.csv) NOT modified
```

### Directory Structure

```
backend/tests/
├── fixtures/
│   ├── benchmark_ground_truth.csv        # IMMUTABLE: canonical expected values
│   └── test_documents/                   # Synthetic PDFs (never customer data)
│       ├── test_po_basic.pdf
│       ├── test_dc_multipage.pdf
│       └── ...
├── results/                              # MUTABLE: timestamped model outputs
│   ├── 2026-04-28T18:30:45.123456/
│   │   └── candidates.csv                # This run's model output (read-only archive)
│   └── 2026-04-29T09:15:22.654321/
│       └── candidates.csv                # Previous run's output
├── local_benchmark_runner.py             # Benchmark runner (safe, local-only)
├── README.md                             # This file
└── ... other test files
```

### Never Do

❌ **Do NOT** check customer PDFs into version control  
❌ **Do NOT** programmatically modify `benchmark_ground_truth.csv`  
❌ **Do NOT** hardcode external endpoints (RunPod, cloud services)  
❌ **Do NOT** run benchmark with `BENCHMARK_MODE=false` (safety gate off)  
❌ **Do NOT** reuse result files across runs (timestamps prevent this)  

### Synthetic Test Documents

To create synthetic test PDFs:

1. Use a template (e.g., blank PO with placeholder numbers)
2. Generate 10 variations (different amounts, reference numbers, addresses)
3. Use **template data only**: `TEST-PO-001`, `100000`, `Test Address, Test City`
4. Never reference real customer data or company information
5. Commit to `fixtures/test_documents/` with clear naming

Example filenames:
- `test_po_basic.pdf` — simple single-page PO
- `test_po_complex.pdf` — multi-page with line items
- `test_dc_multipage.pdf` — delivery challan with multiple pages
- `test_invoice_multiitem.pdf` — invoice with 10+ line items

---

## Unit Tests

Run all unit tests:

```bash
pytest backend/tests/ -v
```

By document type:

```bash
pytest backend/tests/ -k "CUSTOMER_PO" -v
pytest backend/tests/ -k "VENDOR_INVOICE" -v
```

Coverage:

```bash
pytest backend/tests/ --cov=backend/app
```

---

## Integration Tests

See `.github/workflows/` for CI/CD integration tests.

---

## Notes for Contributors

- Always use synthetic data for benchmarks
- Never commit customer documents or real business data
- Document expected values clearly (source: "Synthetic template" or "Manual review")
- Archive old benchmark results (can be deleted after 30 days)
- Update this README if benchmark methodology changes
