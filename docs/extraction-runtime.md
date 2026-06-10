# Extraction Runtime

Order Assurance uses a two-layer extraction flow. The release-candidate default strategy is:

- digital PDF text extraction enabled
- deterministic structured rules enabled
- manual fallback for scanned or low-text documents
- OCR enabled with `glm-ocr:latest` for Layer 1 text acquisition
- model Layer 2 available but disabled by default

## Layer 1: Text Acquisition

The backend first tries deterministic digital PDF text extraction. If the PDF has usable embedded text, OCR is skipped.

For scanned or low-text PDFs, pages are rendered with PyMuPDF and sent to `glm-ocr:latest` through Ollama. This is OCR text acquisition only. The OCR provider returns raw text, never structured fields and never business validation decisions.

If OCR is disabled, unavailable, times out, or returns no usable text, the document remains recoverable through manual entry.

## Layer 2: Structured Extraction

Acquired text is passed into the structured parser. The parser applies deterministic document-type rules first:

- `CUSTOMER_PO`
- `COMPANY_INVOICE`
- `COMPANY_DC`
- `COMPANY_PO`
- `VENDOR_INVOICE`

The parser returns extracted fields, parser route, confidence, missing required fields, field metadata, and failure diagnostics. Optional `gemma4:31b-cloud` Layer 2 can fill fields left unresolved by deterministic rules, but it is disabled by default and never evaluates bundle validity.

## Runtime Flags

```env
DIGITAL_TEXT_ENABLED=true
DIGITAL_TEXT_MAX_PAGES=10
OCR_ENABLED=true
OCR_PROVIDER=glm_ocr
OCR_MODEL=glm-ocr:latest
OCR_BASE_URL=http://localhost:11434
OCR_DPI=200
OCR_MAX_PAGES=5
OCR_TIMEOUT_SECONDS=90
OCR_RETRY_ATTEMPTS=1
OCR_MIN_TEXT_LENGTH=30
OCR_CONTEXT_LENGTH=8192
STRUCTURED_RULES_ENABLED=true
MODEL_LAYER2_ENABLED=false
MODEL_LAYER2_PROVIDER=ollama
MODEL_LAYER2_MODEL=gemma4:31b-cloud
MODEL_LAYER2_BASE_URL=http://localhost:11434
MODEL_LAYER2_TIMEOUT_SECONDS=120
MODEL_LAYER2_CONTEXT_LENGTH=8192
MODEL_LAYER2_RETRY_ATTEMPTS=1
```

For Docker backend calling host Ollama on Docker Desktop:

```env
OCR_BASE_URL=http://host.docker.internal:11434
```

`MODEL_LAYER2_ENABLED=false` is intentional. If enabled later, the model may extract JSON fields only; it must not perform business validation or set order status.

For Docker backend calling host Ollama for Layer 2:

```env
MODEL_LAYER2_BASE_URL=http://host.docker.internal:11434
```

## Layer Roles

| Layer | Runtime | Input | Output | Decision Authority |
| --- | --- | --- | --- | --- |
| Digital acquisition | PyMuPDF | PDF | Raw embedded text | None |
| OCR acquisition | `glm-ocr:latest` | Rendered page image | Raw visible text only | None |
| Structured rules | Python deterministic parser | Raw text | Canonical fields and evidence | None |
| Structured model, optional | `gemma4:31b-cloud` | Raw text and allowed schema | Strict JSON fields and evidence | None |
| Verification | Python verifier | Normalized fields | Bundle and section statuses | Sole authority |

Layer 2 is invoked only when enabled and deterministic extraction leaves schema fields unresolved. Rules values are retained on conflicts; a different model value is stored under `alternative_values` for review.

## Model Layer 2 Contract

Example acceptable model response:

```json
{
  "document_type": "VENDOR_INVOICE",
  "extracted_fields": {
    "po_reference": "1PTR2526000467",
    "invoice_total": 554600
  },
  "field_evidence": {
    "po_reference": "PO No: 1PTR2526000467",
    "invoice_total": "Grand Total: 554600"
  },
  "missing_required_fields": [],
  "confidence": 0.8,
  "failure_code": null,
  "failure_reason": null,
  "diagnostics": {
    "parser_route": "model_layer2",
    "warnings": [],
    "alternative_values": {}
  }
}
```

Business-decision fields such as `bundle_status`, `checks`, `issues`, and `recommendation` are removed if returned by a model.

The model instruction requires a raw JSON object with no Markdown or prose. The runtime remains strict but tolerates one known provider behavior: a response consisting solely of one valid JSON object inside one Markdown code fence is unwrapped, validated, and recorded with `model_response_wrapped_in_code_fence`. Prose plus JSON, multiple JSON objects, malformed JSON, and extraneous Markdown are rejected.

For Vendor Invoice linking fields (`po_reference`, `customer_ref_no`, `external_doc_no`), a model value is usable only when the response contains evidence text for that field. An invoice amount without an evidenced Vendor PO reference cannot establish procurement coverage.

## Diagnostics

Document metadata diagnostics can include:

- `extraction_route`
- `model_version`
- `failure_code`
- `failure_reason`
- `raw_text_length`
- `ocr_text_length`
- `ocr_enabled`
- `ocr_provider`
- `ocr_model`
- `ocr_base_url_host_only`
- `ocr_dpi`
- `ocr_max_pages`
- `ocr_timeout_seconds`
- `ocr_pages_attempted`
- `ocr_page_results`
- `ocr_error`
- `ocr_context_length`
- `selected_orientation`
- `parser_route`
- `parser_confidence`
- `field_metadata`
- `model_layer2_enabled`
- `model_layer2_provider`
- `model_layer2_model`
- `model_layer2_used`
- `model_extracted_keys`
- `model_missing_fields`
- `model_failure_reason`
- `model_response_format`
- `model_response_warning`
- `model_validation_errors`
- `alternative_values`
- `confidence_summary`
- `final_extracted_keys`
- `final_missing_fields`
- `extraction_runs`
- `missing_required_fields`
- `extracted_field_keys`

The frontend shows these in a collapsed document-card diagnostics panel. Raw OCR text is not displayed by default.

## Failure Codes

- `TEXT_EXTRACTION_FAILED`: no usable text could be acquired.
- `OCR_EMPTY`: OCR ran but returned no useful text.
- `OCR_FAILED`: OCR provider failed or timed out.
- `STRUCTURED_PARSE_FAILED`: text exists, but field parsing failed.
- `REQUIRED_FIELDS_MISSING`: partial fields were extracted, but required fields are missing.
- `LOW_CONFIDENCE_EXTRACTION`: extraction confidence is too low for review-ready metadata.
- `MANUAL_ENTRY_REQUIRED`: user correction is needed.

## Manual Fallback

Users can manually correct extracted metadata in the document workflow. Manual saves:

- merge fields into `DocumentMetadata.extracted_data`
- set `extraction_source = manual_entry`
- rebuild references
- refresh verification
- create an audit event with field-level old/new values and a correction reason
- store field metadata with `source = manual_entry`

Manual entry does not mark documents verified automatically.

## Release-Candidate Behavior

Scanned documents are not treated as extraction failures with vague error text. If OCR is disabled, they are marked as requiring manual entry:

```json
{
  "ocr_enabled": false,
  "ocr_available": false,
  "failure_code": "MANUAL_ENTRY_REQUIRED",
  "failure_reason": "OCR is disabled; manual entry is required for scanned or low-text documents."
}
```

This keeps the workflow deterministic for demos and release-candidate testing while preserving a clear future path for OCR enablement.

If `glm-ocr` is enabled but unavailable, diagnostics include provider/model details and the manual fallback remains available:

```json
{
  "ocr_enabled": true,
  "ocr_provider": "glm_ocr",
  "ocr_model": "glm-ocr:latest",
  "failure_code": "OCR_FAILED",
  "failure_reason": "glm-ocr (glm-ocr:latest) failed: request timed out"
}
```

## Local `glm-ocr` Context Limit

`OCR_CONTEXT_LENGTH=8192` is sent explicitly with each Ollama OCR request. On the tested Windows workstation, relying on the running server default caused `glm-ocr:latest` to attempt an oversized CUDA allocation and terminate during model load. A bounded request context allowed both text and synthetic-image OCR requests to complete.

If the provider still fails, the application records `OCR_FAILED` and preserves manual entry; OCR failure never determines bundle verification status.

If optional structured Layer 2 fails or returns invalid JSON, the deterministic rules result is retained and manual fallback remains available. A model failure cannot set or alter verification status.

As of 2026-05-23, an opt-in live probe of `gemma4:31b-cloud` proposed plausible Vendor Invoice values but wrapped JSON in a Markdown code fence. Phase 10C hardening accepts that response only when the fence contains exactly one valid schema-limited JSON object, records a diagnostic warning, strips prohibited business fields, and requires evidence for Vendor PO references. Layer 2 remains disabled by default pending validation against representative redacted documents.
