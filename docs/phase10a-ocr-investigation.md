# Phase 10A OCR Investigation

## Scope

This investigation covers OCR text acquisition only. `glm-ocr` does not decide verification status. Structured rules process OCR text after acquisition, and the order bundle verifier remains the sole business decision-maker.

## Real PDF Regression Availability

The committed optional fixture directory currently contains `expected.json` and documentation only. No approved redacted PDFs were available for a real scanned regression run. The regression test remains skip-safe and now writes sanitized extraction and verification artifacts when PDF fixtures are supplied.

## Local Runtime Investigation

Configuration under test:

```env
OCR_ENABLED=true
OCR_PROVIDER=glm_ocr
OCR_MODEL=glm-ocr:latest
OCR_BASE_URL=http://localhost:11434
```

Observed local runtime facts:

- Ollama version: `0.24.0`.
- Installed model: `glm-ocr:latest`.
- Model metadata reports `glmocr` family, vision capability, and minimum Ollama requirement `0.15.5`.
- The installed model metadata reports vision capability.

## Synthetic Input Matrix

To avoid processing confidential content during diagnosis, a generated image containing test invoice/reference text was used.

| Variable | Values Tested |
| --- | --- |
| API endpoint | `/api/generate`, `/api/chat` |
| Image format | PNG, JPEG |
| DPI | 72, 150, 200, 300 |
| Image sizes | 336x336 through 1400x1400 |
| Payload size | 7,736 through 70,384 base64 characters |

Result: all 16 image request variants returned HTTP `500` with the same model-load error. Text-only requests through both endpoints also returned HTTP `500`.

## Root Cause Finding

The observed local failure is at model loading/runtime level, before useful OCR inference. It is not explained by:

- API endpoint selection;
- PNG versus JPEG encoding;
- rendered DPI or image size;
- base64 request size;
- inclusion of an image payload.

The server response reports: `model failed to load, this may be due to resource limitations or an internal error`.

The underlying Ollama runtime/resource cause is not exposed by the API response and requires local Ollama server log or runtime investigation outside the application.

## Application Hardening

- OCR page diagnostics now persist image format, DPI, rendered dimensions, image byte length, base64 byte length, endpoint strategy, OCR text length, duration, and provider error.
- Page-level `glm-ocr` failures with no OCR text are classified as `OCR_FAILED`, not `OCR_EMPTY`.
- Manual fallback remains available after provider failure.
- Raw OCR/document content is not included in investigation artifacts.

## Recommendation At Initial Investigation

The initial evidence supported strategy **B: keep `glm-ocr` optional and manual fallback primary** until the model-load failure could be isolated.

## Subsequent Runtime Resolution

A follow-up investigation found that the failed requests were loading `glmocr` through CUDA with an oversized context allocation. Ollama logs showed `num_ctx=262144`, `n_ctx_train=131072`, followed by `GGML_ASSERT(ggml_nbytes(src0) <= INT_MAX) failed`.

Order Assurance now sends `OCR_CONTEXT_LENGTH=8192` as `options.num_ctx` on OCR requests. With that bounded context, both text and synthetic-image calls to `glm-ocr:latest` succeed locally, and the live OCR integration test passes. Manual fallback remains the safe recovery path until approved redacted scans are tested.
