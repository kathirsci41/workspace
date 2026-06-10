# Risk Register

| Risk | Impact | Current Mitigation | Recommendation |
| --- | --- | --- | --- |
| Auth/RBAC deferred | Production access control is not ready. | Explicitly out of scope for current phase. | Implement dedicated Auth/RBAC phase before production. |
| Real scanned OCR imperfect | Vendor/customer scans may require manual correction. | `glm-ocr:latest` is used only for OCR text acquisition; manual metadata patch with audit event remains available. | Test against more real scanned bundles and tune rendering/OCR prompts. |
| Manual correction audit review UI missing | Audit data exists but is not easy to inspect. | Audit events are persisted. | Add audit timeline UI and export. |
| Lightweight migrations, not Alembic | Schema evolution can become hard as tables change. | SQL up/down migration exists. | Move to Alembic once schema stabilizes. |
| npm moderate vulnerabilities | Dependency risk remains. | No force upgrades were run. | Schedule dependency hardening and controlled upgrades. |
| Generated PDFs in tests | Real PDF layout coverage is limited. | Tests exercise real PDF text acquisition and parser path. | Add real fixture PDFs to CI-safe test fixtures. |
| No ERP integration | External order truth is not connected. | MVP uses uploaded/exported documents only. | Add ERP integration as a separate phase. |
| No line-item description matching | Product-level matching is not claimed. | Business scope explicitly excludes it. | Evaluate later with normalized SKU/catalog strategy. |
| Dev seed endpoint | Could expose demo data creation if enabled in production. | Environment-gated by `APP_ENV`/`ENABLE_DEV_TOOLS`. | Disable dev tools in production and omit dev router in hardened deployment. |
| Host Ollama dependency | OCR depends on `glm-ocr:latest` availability outside the app process. | Health endpoint reports OCR provider/model reachability and manual fallback remains available. | Decide whether to package or operate Ollama as managed infrastructure before production. |
| OCR text may be wrong | Bad OCR can create wrong extracted fields before review. | OCR never decides verification status; structured parser diagnostics and manual review remain required. | Add confidence thresholds and representative scanned-PDF regression suite. |
| Optional structured model output may be inaccurate | A model-derived value could be incomplete, poorly formatted, or conflict with visible data. | `gemma4:31b-cloud` is disabled by default; only one validated JSON object is accepted, a sole fenced JSON object is flagged, business-status fields are stripped, Vendor PO references require evidence, and deterministic rules win conflicts. | Validate prompts/provider output against redacted documents before considering limited enablement. |
