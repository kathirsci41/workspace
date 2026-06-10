# Brutal Code Review — Order Assurance

**Review date:** 2026-05-23
**Reviewer scope:** `order-assurance/` only (backend, frontend, shared fixtures, docs, docker-compose).
**Method:** Static read of every Python and TypeScript source file referenced by the architecture map, plus `pytest backend/tests` (53 passed, 4 skipped), `npm test` (15 passed), `npm run build` (success), and `docker compose config` (valid).
**Stance:** Senior backend architect, AI extraction engineer, security reviewer, QA lead — brutally honest, evidence first.

---

## 1. Executive Verdict

The app is a **competent demo** for one customer (Panimalar) with hand-tuned regex extractors. It is **demo-safe today** under controlled conditions (single operator, trusted network, the seeded fixture, no real adversarial inputs). It is **NOT production-safe**. The shortest path to production is not "polish" — it is closing a tight set of integrity and security holes that today would either corrupt bundle status, leak document text, or accept fabricated references that downstream financial decisions depend on.

The core idea — deterministic-first extraction with optional model fallback, evidence-required references, manual-entry as the canonical recovery path — is sound. The verifier explicitly refuses to count vendor invoice amounts that lack a proven Vendor PO reference, which is the single most important business safety property and it is correct and tested.

The execution is rougher. Read endpoints quietly mutate database state. OCR raw text leaks into API responses (and into the UI's diagnostics panel). The cleanup CLI will silently delete the entire storage tree if pointed at the wrong DB. The Docker image's "production" defaults are overridden by the compose file to be a development container. None of these are demo blockers — all of them are production blockers.

**Top headline:** the verifier is honest, the orchestrator is brittle, and the surrounding plumbing leaks state and data.

---

## 2. Architecture Map

```
order-assurance/
├── backend/
│   ├── app/
│   │   ├── main.py                — FastAPI bootstrap; CORS pinned to localhost:5180.
│   │   ├── config.py              — frozen dataclass Settings from env; no validation.
│   │   ├── database.py            — SQLAlchemy engine + SessionLocal + init_db (create_all).
│   │   ├── logging_config.py      — request_id middleware, JSON/text formatter, log_event helper.
│   │   ├── migrations/
│   │   │   └── runner.py          — splits SQL on ";"; no version table.
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── bundles.py     — list/get/create/upload + verification-summary + export.xlsx.
│   │   │   │   ├── documents.py   — preview/preview-page-png/extract/re-extract/PATCH extracted-data/DELETE.
│   │   │   │   ├── dev.py         — /dev/seed-panimalar gated by ENABLE_DEV_TOOLS.
│   │   │   │   └── health.py      — calls OCR provider on every hit.
│   │   │   └── serializers.py     — document_to_dict/metadata_to_dict/etc.
│   │   ├── domain/
│   │   │   ├── enums.py           — declared, not enforced (DB stores raw strings).
│   │   │   └── types.py           — OrderBundle dataclass; UNUSED.
│   │   ├── models/                — SQLAlchemy: order_bundle/document/document_metadata/reference_index/audit_event.
│   │   ├── repositories/          — thin CRUD + replace_for_document.
│   │   ├── schemas/               — Pydantic create/read; ManualExtractedDataPatch has open dict.
│   │   ├── services/
│   │   │   ├── extraction_service.py        — ~470 lines orchestrator (the single most overloaded file).
│   │   │   ├── extraction/
│   │   │   │   ├── digital_text_extractor.py   — PyMuPDF text + Panimalar-specific regex.
│   │   │   │   ├── glm_ocr_client.py            — Ollama /api/generate w/ /api/chat fallback.
│   │   │   │   ├── model_layer2.py              — gated, evidence-required for references.
│   │   │   │   ├── model_prompts.py             — OCR + structured prompts.
│   │   │   │   ├── structured_text_parser.py    — label-then-regex extraction; FailureCode enum.
│   │   │   │   └── pdf_field_locator.py         — bbox lookup via fitz.search_for/word/dict iteration.
│   │   │   ├── verification_summary_service.py  — build summary + sync bundle status + sync bundle header.
│   │   │   ├── order_bundle_verifier.py         — section + bundle status + checks; vendor reference safety lives here.
│   │   │   ├── document_normalizer.py           — field aliasing/normalization; loose number/date logic.
│   │   │   ├── manual_metadata_service.py       — PATCH handler; writes audit event; rebuilds refs.
│   │   │   ├── reference_index_service.py       — flat list of REFERENCE_FIELDS; no source/provenance.
│   │   │   ├── audit_service.py                 — DB + in-memory; doc says "Phase 1, Phase 2 later".
│   │   │   ├── export_service.py                — openpyxl multi-sheet; calls sync (writes DB on a GET).
│   │   │   ├── storage_service.py               — uploads (reads ENTIRE body before size check).
│   │   │   ├── file_cleanup_service.py          — orphan sweeper with retention.
│   │   │   ├── address_parser.py                — 8 hardcoded Indian states + PIN regex.
│   │   │   └── demo_seed_service.py             — Panimalar fixture loader.
│   │   └── scripts/
│   │       ├── cleanup_files.py                 — calls init_db() then deletes orphans (dangerous default).
│   │       └── seed_panimalar_demo.py
│   ├── migrations/
│   │   ├── 001_initial_schema.sql
│   │   └── 001_initial_schema_down.sql
│   ├── tests/  unit/ + integration/             — 53 pass / 4 skipped (live OCR + live model + real PDF).
│   ├── Dockerfile                               — production defaults baked in; unpinned deps; root user.
│   ├── pyproject.toml                           — no version pins.
│   └── order_assurance.db                       — 196KB SQLite checked into working tree (not gitignored).
├── frontend/
│   ├── src/
│   │   ├── api/                                 — client.ts + bundles/documents/audit/verification/export.
│   │   ├── components/                          — DocumentCard, DocumentPreviewPanel, ManualMetadataForm, etc.
│   │   ├── pages/                               — BundleListPage, BundleDetailPage.
│   │   └── types/
│   ├── e2e/                                     — Playwright Panimalar happy-path + field highlighting.
│   ├── Dockerfile                               — nginx default config (no SPA fallback, no security headers).
│   ├── package.json                             — deps unpinned to majors only.
│   └── README mentions outstanding moderate npm audit findings.
├── shared/fixtures/panimalar_expected.json
├── docker-compose.yml                           — flips APP_ENV to development; exposes Postgres on 15432.
├── .env.example
└── docs/                                        — extraction-runtime, migration-notes, OCR investigations, etc.
```

Flow:
```
upload (PDF) ──► storage_service.save_upload_file (body→memory→PDF magic→size→disk)
              └► DocumentRepository.create (metadata row stub)
extract  ───────► extract_document
                  ├─ digital_text_extractor (PyMuPDF text per page)
                  ├─ if low text → glm_ocr_client.extract_text_with_ocr
                  ├─ structured_text_parser.parse_structured_text (rules)
                  ├─ if missing & model_layer2_enabled → model_layer2.extract_structured_fields_with_model
                  ├─ _merge_model_fields (rules win conflicts)
                  ├─ pdf_field_locator.build_field_locations (DIGITAL only)
                  ├─ metadata.extracted_data = fields + raw_text + raw_ocr_text   ← LEAK SURFACE
                  ├─ status = EXTRACTED / EXTRACTION_FAILED based on failure_code
                  └─ ReferenceIndexRepository.replace_for_document
PATCH extracted-data ─► manual_metadata_service.patch_extracted_data
                        ├─ merged extracted_data + extraction_source=manual_entry
                        ├─ field_metadata marked manual_entry per field
                        ├─ status recomputed against required_manual_fields_missing
                        ├─ ReferenceIndexRepository.replace_for_document
                        └─ AuditService.record_event (manual_extracted_data_patched)
verification-summary ─► build_verification_summary
                        ├─ for each doc: normalize_document
                        └─ verify_order_bundle (section + bundle status, checks, issues)
sync_bundle_status_from_verification ─► writes order_bundles.{status,customer_delivery_status,
                                                              vendor_procurement_status,
                                                              customer_po_no, so_no, customer_name}
                                        called from GET /bundles, GET /bundles/{id},
                                        GET /bundles/{id}/verification-summary,
                                        POST /documents/{id}/extract,
                                        POST /documents/{id}/re-extract,
                                        PATCH /documents/{id}/extracted-data,
                                        GET /bundles/{id}/export.xlsx,
                                        and demo_seed.
export.xlsx ────────────► build_bundle_export → sync_bundle_status_from_verification (write!) + 5 sheets.
```

`VerificationSummary` IS the source of truth for status; the bundle row is a denormalized cache that the sync function pushes into.

---

## 3. What Is Solid

- **Vendor PO reference safety is correct.** `order_bundle_verifier._vendor_procurement_status` (`backend/app/services/order_bundle_verifier.py:111`) and `_vendor_invoice_ref` only count a vendor invoice's amount toward Vendor PO coverage when a reference is proven. `test_vendor_bill_is_not_counted_without_matching_po_reference` enforces it. This is the single most important integrity property and it holds.
- **Model Layer 2 hardening.** `model_layer2.validate_model_json` strips forbidden business fields (BLOCKED_KEYS), drops unsupported fields, drops reference fields without evidence, rejects prose-wrapped or multi-object JSON, and tolerates a single code-fenced object with an explicit warning. Rules win over the model in `_merge_model_fields`. `test_model_layer2_does_not_accept_vendor_reference_without_evidence` and `test_model_layer2_rejects_prose_wrapped_json` cover the key safety paths.
- **Manual entry is auditable.** Every PATCH writes an `audit_events` row with old/new values and reason; export includes the Audit Trail sheet; manual-source fields are flagged with `source: manual_entry` and confidence 1.0.
- **Layered failure codes (`FailureCode` enum)** propagate through diagnostics so the UI can render specific messages (OCR_FAILED vs OCR_EMPTY vs REQUIRED_FIELDS_MISSING).
- **OCR client tolerates provider 5xx without crashing** and reports `ocr_status: provider_error` correctly; tests `test_glm_ocr_*_fails_softly` confirm.
- **Request IDs and event logs** with explicit "no raw text in logs" discipline (verified — no logger emits `extracted_data["raw_text"]`).
- **Tests pass:** 53/57 pytest, 15/15 vitest, build succeeds, compose config validates.

---

## 4. Critical Issues

### 4.1 Read endpoints mutate database state
`bundles.list_bundles` (line 35), `bundles.get_bundle` (line 44), `bundles.verification_summary` (line 94), and `bundles.export_bundle` (line 120) all invoke `sync_bundle_status_from_verification` and `db.commit()`. A simple `GET /bundles` rewrites every bundle row's status, header, and `updated_at`. Consequences:
- HTTP caching contract violated. CDNs/proxies that cache GETs would skip the writes; clients hitting cached responses would see stale UI status while the DB drifts.
- Concurrent listing while extraction is running can race-overwrite a status set milliseconds earlier.
- The frontend `refresh()` triggers FOUR mutations per user action (`getBundle` + `listBundleDocuments` + `getVerificationSummary` is three; export adds a fourth). Every click amplifies write load.

### 4.2 Raw OCR text and raw digital text persist in `extracted_data` and leak to clients
`extraction_service.py:289-293` stores `raw_text` and `raw_ocr_text` into `metadata.extracted_data`. The serializer (`api/serializers.py:24`) returns `extracted_data` verbatim. The frontend `DocumentCard.tsx:67-72` renders the first 1000 characters of `raw_ocr_text` in a diagnostics `<details>` panel with no env gate. README claims logs intentionally exclude raw text; that is true for logs and false for API responses and the UI. Any screenshot of a Panimalar bundle ships customer addresses, GSTINs, line items, and totals.

### 4.3 Upload reads entire body before enforcing size
`storage_service.save_upload_file` (line 25) calls `await file.read()` before the `len(content) > max_upload_bytes` check on line 28. A client can stream a 1GB request body and OOM the worker before the 413 fires. The 20MB default does not bound memory; it only bounds disk after the fact.

### 4.4 Cleanup CLI auto-creates the database, then nukes "orphans"
`scripts/cleanup_files.py:17` calls `init_db()` unconditionally inside `known_document_paths()`. If `DATABASE_URL` is misconfigured (different file, wrong host, typo), SQLAlchemy creates an empty schema, returns `known_paths = set()`, and then `cleanup_orphaned_files(..., dry_run=False)` deletes every file in storage that is older than `FILE_RETENTION_DAYS`. There is no safety net beyond `--dry-run`. This is a single typo away from total data loss.

### 4.5 Dev-tools and seeded data exposed by default in Docker
`docker-compose.yml:25` overrides the Dockerfile's `APP_ENV=production` with `APP_ENV: development` and `ENABLE_DEV_TOOLS: "true"`. The dev seed endpoint (`/api/dev/seed-panimalar`) authenticates only on these env flags. With no auth/RBAC anywhere in the app, anyone who can reach port 8100 can call seed (or any other endpoint). The Dockerfile's "production" defaults are a comforting lie.

### 4.6 Bundle status can drift because empty values are skipped during sync
`verification_summary_service.sync_bundle_status_from_verification:36` writes only when `if value`. Empty/None values from the verifier (e.g., a previously-set `vendor_procurement_status` after all vendor docs are deleted) are skipped and the stale value persists. A bundle that legitimately transitions to "no vendor side at all" cannot clear its old `REVIEW_REQUIRED` vendor status. Same problem for `customer_delivery_status` after invoice deletion. UI and export both ride on these stale fields.

### 4.7 Bundle header overwritten on every sync
`sync_bundle_status_from_verification:40-48` overwrites `customer_po_no`, `so_no`, `customer_name` from the latest `extracted_summary`. A failed re-extraction that returns partial garbage will clobber a previously good header. Combined with point 4.1, even a list-view refresh can churn header data.

### 4.8 PDF preview endpoint trusts the stored path
`documents.preview_document` and `documents.preview_document_page` open `document.storage_path` directly with `Path(path).is_file()` as the only guard. There is no check that the path is under `storage_root()`. If anything ever inserts a `storage_path` that points outside the storage tree (a migration bug, a manual DB tweak, future feature), the preview endpoint becomes an arbitrary-file-read. The upload path constructs safe targets today, so this is latent — but it is one bug away from CVE-grade.

---

## 5. High-Risk Issues

### 5.1 `gemma4:31b-cloud` is the Ollama Turbo cloud model
The `-cloud` suffix is Ollama's convention for hosted models. Enabling `MODEL_LAYER2_ENABLED=true` with the default model sends the first 12,000 characters of each document's text (`extraction/model_layer2.py:200`) to Ollama's hosted inference. No banner, no log warning, no env-key indicating "this is cloud", no documented privacy contract. README mentions "experiments" and "cloud-model privacy risk" is nowhere acknowledged in the customer-facing docs. Reviewers should assume that with Layer 2 on, every PDF body is sent to a third party.

### 5.2 No auth / RBAC anywhere
Documented as deferred, but worth restating: every endpoint accepts every request from any caller on the configured CORS origin. Seed, upload, delete, patch, export — all open. Behind `localhost` this is fine; behind any non-localhost LB it is a free-for-all.

### 5.3 Manual patch can quietly clean a previously failed extraction
`manual_metadata_service.patch_extracted_data:46-56` recomputes `metadata.status` and `document.status` based on `required_manual_fields_missing` only. The old `failure_code`, `failure_reason`, `ocr_error`, and pre-parse failure metadata stay in `diagnostics`. UI shows "EXTRACTED" status while the diagnostics panel still says "OCR_FAILED". Operator confusion is guaranteed; in worst case an export carries a "Failure Reason" column populated from a state the manual patch already cleared.

### 5.4 OCR rendering uses 200 DPI and no payload-size guard
`glm_ocr_client._render_page_png` renders each page at `dpi/72` matrix. For an A4 page that's ~1654×2339 pixels. Base64'd, each page is ~1–3MB JSON. With `OCR_MAX_PAGES=5` you can ship 15MB JSON to Ollama for one document. Concurrent uploads can saturate the OCR provider; nothing throttles the call rate.

### 5.5 Migration runner splits SQL on `;`
`backend/app/migrations/runner.py:24-27` splits the file on naive `;` and executes each chunk. A migration with a stored procedure, a `DO $$ ... $$` block, or a `;` inside a string literal will explode. No version table, no down-graceful-failure handling. Fine for one file; lethal for any non-trivial migration.

### 5.6 `init_db` competes with SQL migrations
`init_db()` calls `Base.metadata.create_all`, which Postgres maps `DateTime(timezone=True)` to `TIMESTAMP WITH TIME ZONE`, but the migration SQL declares `DATETIME` (Postgres normalizes to `TIMESTAMP WITHOUT TIME ZONE`). Whichever path runs first wins, and they disagree. Add Alembic or drop one path.

### 5.7 `pyproject.toml` has zero version pins
```toml
dependencies = [
  "fastapi", "uvicorn", "sqlalchemy", "python-multipart",
  "pymupdf", "openpyxl", "psycopg[binary]",
]
```
Backend Dockerfile uses `pip install --no-cache-dir <names>` with no constraints file. Tomorrow's `pip install` is not yesterday's. Reproducible builds: not possible.

### 5.8 Manual PATCH accepts any field keys
`schemas/document.ManualExtractedDataPatch.fields: dict[str, Any]` and `manual_metadata_service:23` does `merged.update(...)` without an allowlist. Clients can store arbitrary `extracted_data` keys, including ones that look like reference fields (`po_reference`, `customer_po_no`, etc.). The verifier reads only canonical aliases via `document_normalizer`, but the **ReferenceIndex** is rebuilt by iterating `REFERENCE_FIELDS` (`reference_index_service.py:8-20`) which DOES include `po_reference` and friends. A client PATCH can therefore manufacture a `reference_index` row, which is used for nothing today but is a sharp edge if anyone ever reads from it for cross-bundle lookup.

### 5.9 Bundle/document/metadata `updated_at` never auto-updates
SQLAlchemy columns lack `onupdate=` (`models/order_bundle.py:24`, `models/document.py:24`, `models/document_metadata.py:24`). Only `sync_bundle_status_from_verification` manually updates the bundle's `updated_at`. Document and metadata timestamps stay frozen at row creation through every re-extract, patch, and status change. Audit/forensics will mislead.

### 5.10 OCR raw_text persisted to DB
Beyond the API leak (4.2), `extracted_data` is `JSON NOT NULL` on `document_metadata`. Storing full OCR text per document inflates the DB by orders of magnitude on real corpora. Long term: row size explosion, query latency, backup cost.

### 5.11 Frontend nginx Dockerfile ships default config
No `try_files $uri /index.html` for SPA routing — a direct `/bundle/123` refresh 404s. No CSP, no `X-Frame-Options`, no `Referrer-Policy`, no `Strict-Transport-Security`. The PDF preview endpoint serves `Content-Disposition: inline` and is iframable; on a shared origin this is exploitable for clickjacking and credential proxy attacks if auth is ever added.

### 5.12 Health check executes outbound OCR call
`api/routes/health.py` invokes `check_ocr_provider_health(timeout_seconds=2)` on every hit. Load balancer health checks add a 2s tax and depend on an external service. If the OCR host blips, the LB de-rotates a healthy backend.

### 5.13 Customer/vendor name match aggressively strips suffixes
`order_bundle_verifier._norm_name` strips `\b(PVT|PRIVATE|LIMITED|LTD|P|P LTD|INDIA)\b`. The bare `P` is dangerous — strips legitimate single-character tokens from company names. Combined with `SequenceMatcher.ratio() >= 0.82`, two unrelated companies sharing a 4-word generic prefix can collide and "match".

---

## 6. Medium-Risk Issues

### 6.1 `extraction_service.py` is the god-orchestrator
~470 lines mixing: digital text extraction, OCR routing, structured parsing, model layer 2 invocation, field merging, failure-code rewriting, location building, metadata persistence, reference index rebuild, run history, and logging. Branches in `extract_document` mutate `diagnostics` from at least six places. Hard to test individually; hard to reason about ordering. Needs to be split into a small pipeline of stages with a single result object.

### 6.2 `sync_bundle_status_from_verification` is scattered across routes
Every route that touches a bundle calls it. Centralization is a virtue, but the calls are scattered (and inconsistently — some pre-build the summary, some don't). A single "after-write" hook or an `@bundle_consistency` decorator would prevent drift.

### 6.3 Customer-specific regexes in `digital_text_extractor.py`
`\b1ITR\d{10}\b|\b1ISR\d{10}\b` for invoice numbers, `\b1OTM\d{10}\b` for SO numbers, `\b1DNT\d{4}DC\d+\b` for DC numbers, `\b1PTR\d{10}\b` for vendor PO. These match exactly Panimalar's vendor's invoice template. The next customer breaks every digital extractor.

### 6.4 Address parser is a regex toy
`address_parser.parse_delivery_address` hardcodes 8 Indian states and treats any 6-digit number as a PIN. A document with GSTINs near the address area can produce false matches. There are no tests for adversarial inputs. The verifier never calls `validate_addresses` — it is dead code today.

### 6.5 Failure-code rewriting in extraction_service:248-265 is fragile
After parsing, the code conditionally clears or rewrites `failure_code`/`failure_reason` based on `blocking_missing`, fields presence, and `pre_parse_failure_code`. Six implicit precedence rules across three branches. A change anywhere flips correctness. Needs to be a single explicit precedence table with tests for each transition.

### 6.6 Tests are mostly happy-path with synthetic PDFs
Almost every integration test calls `_pdf_bytes("...")` which renders fresh PyMuPDF text. Real scanned PDFs are gated behind optional fixtures that `pytest.skip` when missing. There are no large-file tests, no path-traversal tests, no concurrent-extraction tests, no upload-with-tampered-content-type tests, no flooded-PDF (1000-page) tests, no "OCR returns malicious unicode" tests.

### 6.7 Storage path leaked in document serializer
`api/serializers.document_to_dict` returns `storage_path` (e.g., `/app/storage/documents/<bundle>/<uuid>_<filename>.pdf`). Useless to the client and exposes container filesystem layout.

### 6.8 Status enums are advisory only
`domain/enums.py` declares `BundleStatus`, `DocumentStatus`, `MetadataStatus`, etc. The DB stores raw strings; the schemas accept any string; the code writes raw string literals. Nothing prevents `bundle.status = "OOPS"`. Cheap fix; not done.

### 6.9 `reference_index_service.build_reference_index` does not capture source
Manual-entry and extracted references are indistinguishable in the table. If anyone later tries to audit "which references came from a model vs a human", they will have to cross-join `audit_events`. Add a `source` column.

### 6.10 `audit_events.document_id`/`order_bundle_id` are not foreign keys
SQL migration has them as nullable `VARCHAR(36)` only. Intentional for retention through deletion, but undocumented. A future "wipe demo data" routine that deletes bundles will leave dangling audit rows whose IDs no longer resolve. Either document or shadow-store the document_type/filename.

### 6.11 OCR retry has no backoff
`glm_ocr_client._call_ollama_generate_with_retries` retries up to `OCR_RETRY_ATTEMPTS+1` times immediately. A degraded Ollama is hammered. Add expo-backoff.

### 6.12 `_partial_billing_restricted` substring search
`order_bundle_verifier._partial_billing_restricted` returns True if `"NOT ALLOWED"` or `"ON FULL DELIVERY"` appears anywhere in the concatenated `part_shipment_allowed` + `mode_of_bill` text, case-insensitively. A vendor with a phrase like "Partial: NOT ALLOWED in stockists" would over-trigger. Acceptable for the demo; brittle for production.

### 6.13 `abs(diff) <= 2` amount tolerance
Fixed ₹2 rupee tolerance applies to every amount comparison. Fine for ₹500k–700k invoices; loose for ₹50 line items; tight for ₹50M projects. Make it a config + percentage hybrid.

### 6.14 Frontend `refresh()` is 4 parallel calls; failure of one collapses all
`Promise.all` rejects on first failure. If `listAuditEvents` is down the entire bundle view shows a loading state instead of partial data. Use `Promise.allSettled` and degrade gracefully.

### 6.15 README mismatch on Postgres port
README says "database: local Postgres exposed on `55432`". Docker-compose actually publishes `15432:5432`. Verified via `docker compose config`. Six numerals off.

### 6.16 `model_layer2._build_prompt` truncates raw_text at 12000 chars silently
No `diagnostics["model_input_truncated"]`. A long scanned PDF gets a head-only view and the operator never knows.

### 6.17 Demo seed bundle number contains a UUID4 fragment
`OA-PANIMALAR-DEMO-{uuid4[:8]}`. Fine for dev, but the demo flow promises uniqueness; if anyone scripts auto-seeding into a `WHERE bundle_number=` query, the variability is a footgun.

### 6.18 SQLite `order_assurance.db` and `tests/artifacts/` are not gitignored
`.gitignore` covers only caches and node_modules. The 196KB committed DB file may contain real test bundle data with real OCR text. `tests/artifacts/` includes `document-metadata-with-locations.json` (704+ lines) — confirmed to contain extraction snapshots.

### 6.19 Frontend export filename and backend filename disagree
Backend sets `Content-Disposition: attachment; filename="<bundle_number>-verification-report.xlsx"`; frontend `export.ts` overrides with `order-assurance-${bundleId}-verification-report.xlsx` (UUID, not bundle number). Annoying UX.

### 6.20 Audit Service docstring promises "Phase 2"
`audit_service.AuditService` says "The persistence adapter will be added in Phase 2" — yet Phase 2 has arrived (persistence works). Stale comments.

---

## 7. Low-Risk Issues

- `domain/types.py OrderBundle` dataclass is unused.
- `BundleStatus/SectionStatus/CheckResult/CheckSeverity/DocumentStatus/MetadataStatus` enums are declared but not enforced anywhere.
- ManualMetadataForm pre-selects `"field missing"` as the default reason — should be empty/unselected.
- `requestJson` includes `Content-Type: application/json` even when the body is undefined (for plain GETs). Harmless; noisy.
- `frontend/index.html` ships with a `<base href="/">` assumption that breaks if hosted under a subpath. Probably fine.
- `health` endpoint includes `service: "order-assurance"` — matches README. No version field — minor operational gap.
- Backend logs DEBUG-style page text length in `digital_text_extractor.py:23` via `logger.info`. Borderline acceptable; should be DEBUG.
- `VerificationSummaryCard` renders `vendor_procurement_status` as plain text while customer-delivery uses a `StatusBadge`. Visual asymmetry.

---

## 8. Backend Review

### Strengths
- Clean route layering. Repositories are thin; services own behavior.
- Logging discipline — every important transition gets a `log_event` with stable field names.
- Session lifecycle via FastAPI `Depends(get_db)` is correct.
- `wait_for_database` retries on startup.

### Weaknesses
- **Mutations in GETs (Critical 4.1).** Routes should call extraction/sync only on writes; reads should observe `VerificationSummary` from the verifier without committing. The bundle row is a cache; rebuild it on writes, not on reads.
- **Transactions are per-request `db.commit()`s** with no explicit boundaries; the extraction route does multiple `db.flush()` calls before its single commit. An exception mid-extraction leaves the metadata `EXTRACTING` and the document `EXTRACTING` until the next attempt. The session rollback in FastAPI's exception handler is not explicitly modelled — relies on connection scope. Audit/reproduction: not great.
- **CORS** is one-origin, `*` methods/headers, with credentials — acceptable behind localhost, becomes the wrong shape behind any reverse proxy on a different origin.
- **Config validation absent.** `Settings` is a frozen dataclass with `os.getenv` defaults; the boolean coercion accepts `"1/true/yes/on"` only, so a typo like `OCR_ENABLED=ON` works but `OCR_ENABLED=enabled` silently disables OCR.
- **`enable_dev_tools` defaults to True**. README documents the gate; default does not match documentation intent.
- **`storage_path` exposure** — see 6.7.
- **No global FastAPI exception handler** — unhandled exceptions return the FastAPI default 500 body, which may leak stack traces depending on uvicorn settings.

---

## 9. Extraction / Model Review

### Pipeline summary
```
PDF upload
 ├─► digital_text_extractor.extract_pdf_text_pages       (PyMuPDF, max=10 pages)
 │   └─► if joined_text < MIN_DIGITAL_TEXT_LENGTH (25 chars)
 │       └─► glm_ocr_client.extract_text_with_ocr        (Ollama /api/generate fallback /api/chat)
 │           ├─► PNG-render each page (DPI 200) → base64 → JSON → Ollama
 │           ├─► num_ctx = OCR_CONTEXT_LENGTH (8192)
 │           └─► provider/empty/text classification + per-page diagnostics
 ├─► structured_text_parser.parse_structured_text
 │   ├─► route=digital → extract_digital_fields (Panimalar regex)
 │   ├─► route=ocr_glm → _parse_customer_po / _parse_vendor_invoice / extract_digital_fields
 │   └─► FailureCode + missing_required_fields
 ├─► if MODEL_LAYER2_ENABLED & missing fields & text_for_parse
 │   └─► model_layer2.extract_structured_fields_with_model (gemma4:31b-cloud)
 │       ├─► system + per-doc prompt
 │       ├─► validate_model_json (strict JSON, fenced tolerated with warning)
 │       ├─► drop BLOCKED_KEYS / unsupported / non-evidence reference fields
 │       └─► rules win conflicts in _merge_model_fields
 ├─► pdf_field_locator.build_field_locations (only when digital_text_used)
 └─► metadata.extracted_data ← fields ∪ {raw_text, raw_ocr_text}
```

### Findings
- **Failure code precedence is the single trickiest part of the codebase.** Lines 248–265 of `extraction_service.py` rewrite `diagnostics["failure_code"]`/`failure_reason` based on the combination of `rules_failure_code`, `pre_parse_failure_code`, `blocking_missing`, and field presence. There are at least six implicit branches. Needs to become an explicit `ExtractionStatus` resolver with table-driven precedence and unit coverage for each transition. As is, a regression here flips bundle status without anyone noticing.
- **Failed-extraction can present as success.** Today the code at line 254 sets `failure_code = None` if `not blocking_missing and fields`. If `parsed["missing_required_fields"]` is empty but `final_missing` from schema is not, the document goes to `EXTRACTED` with a partial schema. The `final_missing_fields` diagnostic is populated but no UI or status reflects it. False-pass risk.
- **OCR safety:**
  - No payload-size guard (5.4).
  - Generate-then-chat fallback chain double-charges if the first fails.
  - `check_ocr_provider_health` returns reachable=True on any 2xx–4xx — does not confirm the model is loaded.
  - No backoff between retries.
  - `OCR_CONTEXT_LENGTH=8192` is hard-coded at request time — good.
- **Model Layer 2 safety: largely correct.** Strict JSON, evidence-required references, forbidden keys filtered, prose rejected, rules win. The two remaining gaps:
  - `raw_text[:12000]` truncation is silent (6.16).
  - Confidence (`0.8` / `0.6`) is only used for diagnostics, never to drop low-confidence model values for non-reference fields. Verifier consumes the field regardless.
  - The model can still hallucinate names/addresses/amounts (non-reference fields are not evidence-checked). Mitigations exist (rules win conflicts, only fills "missing" fields), but a hallucinated `vendor_name` flows through to the name-match check and can flip `VENDOR_NAME_MATCH` to PASS.
- **Cloud model identity (5.1).** Loudest privacy concern.
- **Forbidden-business-field stripping** is in `BLOCKED_KEYS` and is correctly tested.
- **`po_reference` is in `REFERENCE_FIELDS` and must have evidence.** Correctly tested.
- **Optional live tests** are properly gated. ✓

---

## 10. Verification Review

### Strengths
- Customer PO is treated as a source anchor when present; invoice/DC checked independently when absent (`order_bundle_verifier._customer_delivery_status:54-108`).
- Vendor PO/invoice ref check uses normalized reference matching (`_norm_ref` strips non-alphanumeric and uppercases).
- Unproven vendor invoice amounts are correctly NOT counted toward coverage (the key correctness property).
- Partial billing detection respects `NOT ALLOWED` / `ON FULL DELIVERY` text.
- Missing-document path emits explicit issues with `MISSING_DOCUMENTS` status.

### Weaknesses
- **MISMATCH on a WARNING check escalates to bundle MISMATCH.** `_has_result(checks, "MISMATCH")` does not consider severity — a name mismatch (WARNING) terminates `_customer_delivery_status` with MISMATCH, and `_bundle_status` then returns MISMATCH for the whole bundle. False MISMATCH risk.
- **Vendor billing coverage is only checked when matching invoices have amounts.** A matched vendor invoice with no amount silently passes through (no PASS/FAIL recorded). Combined with the unproven-reference safety, this is correct in design but should at least raise an issue.
- **Amount tolerance is fixed ₹2** (6.13).
- **Name matching uses ratcheted SequenceMatcher ≥0.82** with aggressive suffix stripping (5.13). Threshold is not tuned via tests.
- **Address verifier exists** (`address_parser.validate_addresses`) but is not called from `order_bundle_verifier.py`. Dead path. Either remove or wire it up.
- **`MISSING_DOCUMENTS` vs `BLOCKED` precedence**: `_bundle_status` returns MISMATCH > BLOCKED > MISSING_DOCUMENTS > REVIEW_REQUIRED > OK. The verifier never emits BLOCKED today, but `_max_status` and `_bundle_status` accept it. Future addition would work; today it is a dormant pathway.
- **Manual data vs extracted data distinction**: lives in `field_metadata[source]`. The verifier itself does not care about source, which is intentional (the data is the data). Audit can reconstruct provenance.

---

## 11. Manual Patch / Audit Review

### Strengths
- `audit_service.record_event` writes a row per patch with `patched_fields`, `changes` (old/new), `reason`, `actor`.
- `field_metadata` per-field source becomes `manual_entry` for patched fields; remaining fields keep their original source.
- `ReferenceIndexRepository.replace_for_document` rebuilds refs after every patch.
- `sync_bundle_status_from_verification` is called by the route.
- Audit Trail sheet in the export breaks changes out per field.

### Weaknesses
- **No field allowlist (5.8).**
- **`failure_code` and `failure_reason` are not cleared on manual patch (5.3).** Operator sees inconsistent diagnostics.
- **`extraction_source = "manual_entry"`** is set at the top level (`metadata.extracted_data["extraction_source"]`) but never cleared even on re-extract — so if you patch then re-extract, the doc still carries `extraction_source: manual_entry` in `extracted_data` while individual fields go back to `source: rules`. UI labelling becomes ambiguous.
- **`audit_events` rows never tie to a request_id** — every other log includes it; the audit table does not. Cross-correlation requires log scanning by timestamp.
- **No audit event when extraction runs** — only when manual patches happen. A failed extraction is logged but not audited. If you need a "who or what touched this bundle and when" trail, half the events are missing.
- **No way to revert a manual patch** — patches are additive only, and you cannot blank a field through the API (`if value not in (None, "")` filters out empty PATCH values in `manual_metadata_service:23`).

---

## 12. ReferenceIndex Review

### Strengths
- `replace_for_document` deletes then re-inserts: clean rebuild semantics.
- All call sites use the same path (`extraction_service`, `manual_metadata_service`, `demo_seed_service`).
- Indexes on `document_id`, `order_bundle_id`, `reference_type`, `reference_value`.

### Weaknesses
- **No source column** (6.9) — extracted vs manual indistinguishable.
- **`REFERENCE_FIELDS` (`reference_index_service.py:8-20`)** includes both `invoice_no`/`invoice_number` and `dc_no`/`dc_number` as separate types. Inconsistent — should normalize.
- **Reference type values are field names**, not canonical types. `customer_po_no` and `customer_order_no` may both appear for the same logical reference. Duplicate-ish rows.
- **No uniqueness constraint** — two extracts of the same document inserting the same `(document_id, reference_type, reference_value)` would create duplicates if `replace_for_document` were not called. The single path mitigates this in practice; relying on it is fragile.
- **Vendor invoice references without evidence are correctly NOT in the reference index** because the model strips them before they reach `extracted_data` — verified.

---

## 13. File / Storage / Preview Review

### Strengths
- PDF magic byte (`%PDF`) check on upload (`storage_service:26`).
- UUID-prefixed filenames prevent collisions and path escape via filename.
- `Path.name` strips parent components.
- Preview endpoint guards against `not Path(...).is_file()`.
- Per-page PNG endpoint validates `page_number` against `pdf.page_count`.

### Weaknesses
- **Read-before-size-check (4.3).**
- **Stored path trust (4.8).**
- **`get_pdf_page_count` swallows all exceptions** silently and returns None. Diagnostics will show `page_count: None` with no reason.
- **No max-page guard on `preview_document_page`** — a 10,000-page PDF will fit `page_number=9999` and the route renders the 9999th page synchronously. CPU/memory abuse.
- **`fitz.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))`** at 1.5x is reasonable; no concurrency limit.
- **Cleanup CLI (4.4).**
- **Storage path leak in API (6.7).**

---

## 14. Export Review

### Strengths
- Same `summary` as the UI (calls `sync_bundle_status_from_verification`).
- Five sheets: Verification Summary, Documents, Checks, Extracted Fields (source/confidence/evidence/page/bbox/failure), Audit Trail (per-change rows).
- Filters out `raw_*` keys from Extracted Fields (`export_service.py:102`).
- Returns `Content-Disposition` with `bundle_number`.

### Weaknesses
- **Export mutates DB (4.1) via sync.**
- **No memory bound** — `openpyxl.Workbook` is held entirely in memory; for a bundle with hundreds of docs the export can balloon.
- **No streaming response** — the byte buffer is built then returned as one response.
- **No CSV alternative** — Excel-only.
- **Audit Trail** sorted by `created_at DESC` (from `AuditRepository.list_for_bundle`). Excel users typically want ASC for a timeline. Minor UX.
- **Error path returns generic "Export failed"** with a 500 — the log carries `error=str(exc)` but the user sees nothing useful.

---

## 15. Frontend Integration Review

### Strengths
- API client centralized in `api/client.ts` with `X-Request-ID` capture in `debugLog`.
- Export double-click is prevented (`isExporting` state).
- E2E test exercises the seed → bundle list → bundle detail → review → export → audit flow.
- Component tests for DocumentCard, DocumentPreviewPanel, ManualMetadataForm, VerificationSummaryCard, ExtractedFieldsPanel, BundleListPage, BundleDetailPage.

### Weaknesses
- **`refresh()` uses `Promise.all` (6.14)** — one failure collapses the whole view.
- **DocumentCard renders raw OCR text** (4.2 / 5.10) without any env gate.
- **No error boundary** — render errors crash the page.
- **ManualMetadataForm default reason `"field missing"`** is pre-selected.
- **`patchExtractedData` is not debounced**; only export has a busy flag.
- **`selectedDocument` state is reconciled by ID** after refresh — OK, but the `key={selectedDocument.id}` on `ManualMetadataForm` forces remount on every refresh, blowing away unsaved edits while the user is typing.
- **Frontend filename overrides backend** (6.19).
- **Verification Summary** drops `vendor_procurement_status` to plain text (`<span>`) instead of a `StatusBadge`. Cosmetic asymmetry.
- **No retry on transient failures** — every API call surfaces error to the user.

---

## 16. Test Quality Review

### Classification

| Type | Count (approx.) | Files |
|------|-----------------|-------|
| Real unit | ~10 | `test_order_bundle_verifier.py`, `test_document_normalizer.py`, `test_model_layer2.py`, `test_structured_text_parser.py`, `test_pdf_field_locator.py`, `test_glm_ocr_client.py`, `test_config_flags.py` |
| Integration (synthetic PDFs) | ~15 | `test_bundle_workflow.py`, `test_extraction_workflow.py`, `test_logging.py`, `test_export_and_seed.py`, `test_dev_tools_gate.py`, `test_migrations.py`, `test_file_cleanup_service.py`, `test_cleanup_cli.py` |
| Generated-fixture | 1 | `shared/fixtures/panimalar_expected.json` consumed by integration tests |
| Real PDF optional (skipped when fixtures missing) | 1 | `test_real_pdf_regression.py` |
| Live model optional | 2 | `test_live_glm_ocr_optional.py`, `test_live_model_layer2_optional.py` |
| E2E | 2 | Playwright `panimalar-verification.spec.ts`, `field-highlighting.spec.ts` |

### Gaps
- **Over-mocked OCR/model paths.** `_pdf_bytes(text)` produces a fresh digital PDF every time — the rules path is well-tested, but the real-world stress of scanned PDFs is only covered if QA wires the optional fixtures.
- **No negative tests on storage_service.** Tampered Content-Type with PDF magic, large body, NUL-byte filenames, Unicode filenames — none.
- **No path-traversal tests** on `preview_document` / `preview_document_page` for malicious DB-injected paths.
- **No concurrent extraction tests.** Two simultaneous `POST /extract` on the same doc has undefined behavior.
- **No race tests** on `sync_bundle_status_from_verification`.
- **No large file tests** (max upload boundary).
- **No PDF-page-bomb tests** (1000-page PDF, preview pages 1..1000).
- **No tests of the `MISMATCH` on a WARNING check escalating to bundle MISMATCH** (see Section 10 weaknesses).
- **No test exercises the manual patch leaving `failure_code` stale** (5.3).
- **No test exercises the bundle header overwrite** (4.7).
- **No test exercises empty-status skip** (4.6 — try removing a document and confirm status updates).
- **Generated-only confidence problem:** `panimalar_expected.json` is the oracle for almost every integration test. If the oracle is wrong, every test passes wrongly.

---

## 17. Operational Readiness Review

| Area | Status |
|------|--------|
| Docker Compose | Works locally. Backend uses Postgres via service hostname `database`. **Compose flips to development mode and enables dev tools.** |
| Env vars | Reasonable defaults, no validation, boolean coercion is forgiving but not strict. |
| Migrations | One initial SQL file, runner splits on `;`, no version table, no Alembic. Conflicts with `init_db`. |
| Cleanup CLI | Works; **dangerous default** when DB is misconfigured (4.4). |
| Logging | Structured event stream, request IDs, JSON option, no raw text. Good. |
| Request IDs | Present in middleware; returned in `X-Request-ID` header; logged. ✓ |
| Docs | `architecture.md`, `extraction-runtime.md`, `production-readiness-checklist.md`, demo-script, OCR investigations. Cohesive set; some staleness (port mismatch). |
| CI | None visible. No `.github/workflows`. No CI evidence in repo. |
| Production blockers | See Section 20. |
| Local-only assumptions | `host.docker.internal` for OCR; `127.0.0.1` everywhere; nginx default config. |
| Hardcoded ports | 8100 (backend), 5180 (frontend), 15432 (Postgres). |
| Secret handling | None. No `.env`, no secrets manager integration. Hardcoded `order_assurance/order_assurance` in compose. |
| Non-Alembic migration risk | Yes (5.5/5.6). |
| Dependency vulns | Backend deps unpinned; frontend deps unpinned to majors; README acknowledges moderate npm audit findings. |
| Frontend nginx | Default config; no SPA fallback; no security headers; no HTTPS termination. |
| Docker image | Runs as root; no HEALTHCHECK; no pip constraints file. |
| Database | Default SQLite; compose uses Postgres; no connection pool tuning; no read replica strategy. |

---

## 18. Recommended Refactor Plan

### Phase A — Demo hygiene (1–2 days)
1. Stop storing `raw_text`/`raw_ocr_text` in `metadata.extracted_data`. Move them to a separate `metadata.diagnostics["raw_text_preview"]` field (truncated) and only emit when an explicit `?include_raw=true` query param is passed by an authenticated caller. Drop the UI's `DocumentCard` raw OCR preview behind `VITE_DEBUG_LOGS`.
2. Enforce upload size BEFORE reading body (cumulative byte counting in a streaming reader, or a global `MAX_REQUEST_SIZE` middleware).
3. Add `Path.resolve()` containment check in `preview_document*` so `storage_path` cannot escape `storage_root()`.
4. Make read endpoints idempotent. Move `sync_bundle_status_from_verification` calls out of GETs and into POSTs/PATCHes only. The summary endpoint can compute on the fly without committing.
5. Fix `cleanup_files.py`: never `init_db()`; fail loudly if the DB is missing; require an explicit `--storage-dir` flag and reject when `known_paths` is empty unless `--allow-empty` is passed.
6. Add `try_files $uri /index.html` to a frontend nginx config; add CSP and security headers.
7. Pin Python dependencies in a `requirements.txt`/`uv.lock`; copy that into the Dockerfile.
8. Add a non-root user to the backend Dockerfile + HEALTHCHECK.

### Phase B — Integrity (3–5 days)
1. Centralize status writes behind a single `BundleStateService` invoked only from mutation handlers; remove from reads.
2. Replace the failure-code rewrite logic in `extraction_service.py:248-265` with an explicit precedence table + unit tests covering each transition.
3. Add allowlist for `ManualExtractedDataPatch.fields` per document type; reject unknown keys with 400.
4. Clear `failure_code` / `failure_reason` on successful manual patch; emit a `manual_patch_cleared_failure` log event.
5. Add `source` and `created_at` columns to `reference_index`; track manual vs extracted.
6. Stop overwriting bundle header on every sync; write `customer_name`/`customer_po_no`/`so_no` ONLY when the previous value was null or the new value matches via reference index lookup (i.e., trust manual or first-seen, not last-seen).
7. Fix the empty-value skip in `sync_bundle_status_from_verification` — explicitly handle "no vendor side present" by clearing `vendor_procurement_status` to a sentinel (`NOT_APPLICABLE`).
8. Treat WARNING-severity MISMATCH as REVIEW_REQUIRED at the section level; only BLOCKER severity escalates.
9. `onupdate=` on `updated_at` columns or a single `before_flush` event listener.

### Phase C — Production safety (1–2 weeks)
1. Auth/RBAC layer (out of scope here but next).
2. Adopt Alembic; remove `init_db()` from runtime paths; document `python -m app.migrations.up` as the only init route.
3. Move dev-seed off `/api/dev/*` to a CLI-only entrypoint; remove the dev router from production builds via build flag.
4. Wrap OCR and Model Layer 2 calls with circuit breakers + expo-backoff; emit OCR provider degradation alerts.
5. Drop the OCR call from `/health`. Provide `/health/readiness` separately and have load balancers use the lightweight `/health/liveness`.
6. Document privacy contract for `gemma4:31b-cloud`. Require an explicit env flag like `MODEL_LAYER2_DATA_LEAVES_PREMISES_ACK=yes` to enable.
7. Replace customer-specific regex in `digital_text_extractor.py` with a template registry per customer/vendor format.
8. Address parser: feature-flag, expand state list, integrate with the verifier (today it's dead code).
9. CI pipeline: pytest + vitest + build + docker build + container scan + npm audit + dependency review.
10. Add `tests/artifacts/` and `*.db` to `.gitignore`. Purge committed SQLite from history.

---

## 19. Fix Priority List

Top to bottom:

1. **Stop mutating DB on GET** (Critical 4.1). Branch-level fix.
2. **Stop persisting `raw_text`/`raw_ocr_text` in `extracted_data`** (Critical 4.2 + High 5.10). Drop from API; gate UI preview.
3. **Validate upload size before reading body** (Critical 4.3).
4. **Cleanup CLI safety** (Critical 4.4) — never auto-init DB; refuse to run with empty known_paths.
5. **Compose: stop enabling dev mode by default** (Critical 4.5). Provide `docker-compose.dev.yml` as override, not the base.
6. **Restore empty-vendor-status handling** (Critical 4.6) and **stop overwriting bundle header** (Critical 4.7).
7. **Containment check on `storage_path`** (Critical 4.8).
8. **Document and require an explicit ack for Layer 2 cloud usage** (High 5.1).
9. **Clear failure code on manual patch** (High 5.3).
10. **Pin dependencies; non-root Docker user; nginx SPA + headers** (High 5.7/5.11).
11. **Refactor `extraction_service.py` failure-code precedence into a table** (Medium 6.5).
12. **Allowlist manual PATCH fields** (High 5.8).
13. **Move `init_db()` out of runtime paths; Alembic** (High 5.5/5.6).
14. **Onupdate timestamps** (High 5.9).
15. **Promise.allSettled in frontend refresh; error boundary; raw OCR preview behind env flag** (Medium 6.14).
16. **Backoff for OCR retries** (Medium 6.11).
17. **Address parser: wire up or remove** (Medium 6.4).
18. **Status enum enforcement** (Medium 6.8).
19. **Reference index source column** (Medium 6.9).
20. **Tests for negative paths, large files, race conditions, path traversal** (Medium 6.6).

---

## 20. Production Blockers

A bundle of issues that, individually or together, would block sign-off for production:

1. **Read endpoints mutating DB state** (4.1) — breaks caching/idempotency contracts and can churn status under load.
2. **Cleanup CLI deletes everything when misconfigured** (4.4) — single env typo, lose all uploaded PDFs.
3. **No auth/RBAC, dev tools on by default in compose** (4.5) — anyone reachable can seed, upload, patch, export, delete.
4. **Raw OCR/digital text in API responses** (4.2) — privacy contract violation; PII/business data leak.
5. **Upload reads body fully before size check** (4.3) — memory DoS vector.
6. **`gemma4:31b-cloud` is a hosted cloud model without explicit privacy ack** (5.1).
7. **Migration runner splits on `;` and no Alembic** (5.5) — any future migration with a non-trivial statement breaks production.
8. **`pyproject.toml` unpinned + no constraints file** (5.7) — non-reproducible builds.
9. **Docker image runs as root with no HEALTHCHECK; nginx ships default config without SPA fallback or security headers** (5.11).
10. **Bundle header / vendor status drift on sync** (4.6/4.7) — invisible corruption of business-visible fields.

---

## Closing

The verifier is the strongest part of this codebase. The orchestrator is the weakest. The plumbing is dangerous mostly because of small, fixable defaults: read endpoints that write, an upload path that reads before checking, a cleanup CLI that auto-creates databases, a compose file that flips a production image into dev mode, raw OCR text shipped to clients. None of these are conceptual mistakes — they are habits that need to be undone before a customer who is not Panimalar runs this app.

The path forward is not a rewrite. It is a tight three-phase tidy followed by a real production hardening pass.
