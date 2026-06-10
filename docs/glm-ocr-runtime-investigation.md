# glm-ocr Local Runtime Investigation

Date: 2026-05-23  
Scope: `order-assurance` OCR Layer 1 only. Verification rules and manual fallback behavior were not changed.

## Summary

`glm-ocr:latest` is usable from Order Assurance on this workstation when each Ollama request explicitly bounds the context length. The HTTP 500 failures were caused by the model being loaded with an oversized context allocation on the CUDA backend, not by the OCR image payload format or application verification logic.

Order Assurance now sends `OCR_CONTEXT_LENGTH=8192` as `options.num_ctx` on both Ollama OCR request paths.

## Environment

| Item | Observed Value |
| --- | --- |
| OS | Microsoft Windows 11 Home Single Language, 64-bit, version 10.0.26200 |
| RAM | 15.6 GiB visible; approximately 5.0 GiB free during investigation |
| GPU | NVIDIA GeForce RTX 3050 6GB Laptop GPU |
| GPU driver | 32.0.15.9186 |
| Ollama version | 0.24.0 |
| Model | `glm-ocr:latest` |
| Model disk size | 2.2 GB |
| Architecture | `glmocr` |
| Parameters | 1.1B |
| Quantization | F16 |
| Trained context | 131072 |
| Model minimum Ollama version | 0.15.5 |

Installed Ollama models included `glm-ocr:latest`, `gemma4:31b-cloud`, `qwen2.5:3b`, `qwen2.5:0.5b`, `nomic-embed-text:latest`, and `gpt-oss:120b-cloud`.

## Reproduction

Before the fix, all of the following failed:

- `ollama run glm-ocr:latest "Return exactly OK."`
- Ollama `/api/generate` and `/api/chat` with text-only input.
- Synthetic image OCR calls through both endpoints.
- PNG and JPEG synthetic images at 72, 150, 200, and 300 DPI.

The API response was:

```text
HTTP 500: model failed to load, this may be due to resource limitations or an internal error
```

## Root Cause Evidence

The Ollama server log captured the failed load:

```text
requested context size too large for model num_ctx=262144 n_ctx_train=131072
load request=... KvSize:131072 ... GPULayers:17 ...
GGML_ASSERT(ggml_nbytes(src0) <= INT_MAX) failed
Load failed ... model failed to load
```

This identifies the failure at model loading in the CUDA backend. The model was being loaded with an excessive KV/context allocation and the runner terminated before inference began.

Current user environment reports `OLLAMA_CONTEXT_LENGTH=8192`, but the running Ollama process had produced oversized-context load attempts. Order Assurance therefore must not rely on inherited/global Ollama context state.

## Controlled Test

The same installed model was invoked with bounded request context:

| Request | Options | Result |
| --- | --- | --- |
| Text `/api/generate` | `num_ctx=2048` | HTTP 200 |
| Text `/api/generate` | `num_ctx=8192` | HTTP 200 |
| Text `/api/generate`, CPU forced | `num_ctx=2048`, `num_gpu=0` | HTTP 200 |
| Synthetic image `/api/generate` | `num_ctx=8192` | HTTP 200, OCR text returned |
| Synthetic image `/api/chat` | `num_ctx=8192` | HTTP 200, OCR text returned |

After the application change, `ollama ps` reported `glm-ocr:latest` running at `CONTEXT 8192` on GPU. The live backend OCR test passed using a generated, non-confidential image document.

A fresh standalone `ollama run glm-ocr:latest "Return exactly OK."` still failed after restarting the service, because that raw CLI load again selected the oversized context. For local validation, use the Order Assurance integration test or an API request containing `options.num_ctx=8192`; do not use unbounded `ollama run` as the OCR health gate.

## Fix Applied

- Added `OCR_CONTEXT_LENGTH`, defaulting to `8192`.
- Added `options: {"num_ctx": settings.ocr_context_length}` to `/api/generate` and `/api/chat` OCR payloads.
- Persisted `ocr_context_length` in OCR diagnostics.
- Retained `OCR_FAILED`, `provider_error`, and `manual_fallback_available=true` for provider failures.

This is an OCR acquisition fix only. Structured parsing and verification decision logic remain unchanged.

## Configuration Recommendation

Recommended local/demo configuration:

```env
OCR_ENABLED=true
OCR_PROVIDER=glm_ocr
OCR_MODEL=glm-ocr:latest
OCR_BASE_URL=http://localhost:11434
OCR_CONTEXT_LENGTH=8192
MODEL_LAYER2_ENABLED=false
```

For a Docker backend calling host Ollama:

```env
OCR_BASE_URL=http://host.docker.internal:11434
```

Keep OCR enabled for local/demo environments where provider health is monitored. Manual fallback remains necessary because approved real scanned PDF fixtures have not yet been supplied for field-accuracy regression testing.

## Not Performed

- No `ollama pull` or reinstall was performed because the installed model executes successfully with bounded context.
- No alternate OCR provider was selected.
- No private PDF content was logged or committed.

## Remaining Validation

- Supply approved redacted Customer PO and Vendor Bill PDFs in the local regression fixture path.
- Run extraction against those real scans and review field accuracy and diagnostics.
- Confirm Docker backend reaches host Ollama using the same bounded-context request.
