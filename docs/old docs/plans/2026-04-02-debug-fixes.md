# Debug.py Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 10 code quality and correctness issues identified by `debug.py` (currently 0/10 passing).

**Architecture:** Each fix is a targeted, isolated change. Ordered by severity: critical runtime bugs → logic bugs → config/env defaults → infrastructure. Tests for each fix are smoke-tested by re-running `debug.py` after each commit.

**Tech Stack:** FastAPI, Pydantic-Settings, SQLAlchemy, Celery, Docker Compose, PowerShell

---

## Cross-Check Results

All 10 errors confirmed against source:

| ID  | File | Line | Confirmed |
|-----|------|------|-----------|
| C1  | `backend/app/services/extraction/pipeline.py` | 110 | ✅ `ExtractionResult` used, not imported |
| C2  | `backend/app/api/v1/purchase_orders.py` | 160 | ✅ `or` logic rejects valid PDFs |
| C3  | `backend/app/api/v1/extraction.py` + `tasks.py` | 352, 458 | ✅ Both hardcode `/ 6` |
| C4  | `backend/app/config.py` | 67 | ✅ `debug: bool = True` |
| C5  | `.env.example` | 34 | ✅ `DEBUG=true` |
| C6  | `docker-compose.prod.yml` | 73–82 | ✅ nginx missing healthcheck condition; backend missing healthcheck block |
| C7  | `backend/app/api/v1/admin.py` | 58–67 | ✅ `_check_models()` ignores `layer1_provider` |
| C8  | `backend/app/services/extraction/tasks.py` | 78,143,173,189,192,207,231 | ✅ 7 `asyncio.run()` calls |
| C9  | `stop_all.ps1` | 4–8 | ✅ Kills 8000/5173 instead of 8002/5174 |
| C10 | `backend/app/config.py` | 64 | ✅ CORS hardcoded to `localhost:5174` |

---

## File Map

| File | Change |
|------|--------|
| `backend/app/services/extraction/pipeline.py` | Add `ExtractionResult` to import |
| `backend/app/api/v1/purchase_orders.py` | Change `or` → `and` in validation |
| `backend/app/api/v1/extraction.py` | Import `CHAIN_DOC_TYPES`; replace `/6` |
| `backend/app/services/extraction/tasks.py` | Import `CHAIN_DOC_TYPES`; replace `/6`; consolidate `asyncio.run()` |
| `backend/app/config.py` | Fix `debug` and `cors_origins` defaults |
| `.env.example` | Change `DEBUG=true` → `DEBUG=false` |
| `docker-compose.prod.yml` | Add backend healthcheck + nginx condition |
| `backend/app/api/v1/admin.py` | Update `_check_models()` for new provider config |
| `stop_all.ps1` | Fix port numbers to match `start.ps1` |

---

## Task 1 — C1: Fix ExtractionResult import in pipeline.py

**Files:**
- Modify: `backend/app/services/extraction/pipeline.py:29-33`

- [ ] **Step 1: Make the fix**

  Current imports (lines 29–33):
  ```python
  from app.services.extraction.providers.base import (
      Layer1Provider,
      Layer2Provider,
      OcrResult,
  )
  ```

  Change to:
  ```python
  from app.services.extraction.providers.base import (
      Layer1Provider,
      Layer2Provider,
      OcrResult,
      ExtractionResult,
  )
  ```

- [ ] **Step 2: Verify check passes**

  Run: `PYTHONUTF8=1 python debug.py`
  Expected: C1 now shows ✔

- [ ] **Step 3: Commit**

  ```bash
  git add backend/app/services/extraction/pipeline.py
  git commit -m "fix: import ExtractionResult in pipeline.py — was NameError at runtime"
  ```

---

## Task 2 — C2: Fix upload validation OR → AND

**Files:**
- Modify: `backend/app/api/v1/purchase_orders.py:160`

- [ ] **Step 1: Understand the bug**

  A PDF sent with `Content-Type: application/octet-stream` (common from some clients/proxies) has:
  - `ext = ".pdf"` → in `ALLOWED_EXTENSIONS` → first condition is False
  - `content_type = "application/octet-stream"` → not in `ALLOWED_MIME_TYPES` → second condition is True
  - With `or`, the whole expression is True → request rejected even though the file is valid.

- [ ] **Step 2: Make the fix**

  In `backend/app/api/v1/purchase_orders.py`, find line ~160:
  ```python
  if ext not in ALLOWED_EXTENSIONS or content_type not in ALLOWED_MIME_TYPES:
  ```

  Change to:
  ```python
  if ext not in ALLOWED_EXTENSIONS and content_type not in ALLOWED_MIME_TYPES:
  ```

- [ ] **Step 3: Verify check passes**

  Run: `PYTHONUTF8=1 python debug.py`
  Expected: C2 now shows ✔

- [ ] **Step 4: Commit**

  ```bash
  git add backend/app/api/v1/purchase_orders.py
  git commit -m "fix: change OR to AND in upload validation — was rejecting valid PDFs from some clients"
  ```

---

## Task 3 — C3: Replace hardcoded `/6` in chain completeness

**Files:**
- Modify: `backend/app/api/v1/extraction.py:343-352`
- Modify: `backend/app/services/extraction/tasks.py:447-458`

`CHAIN_DOC_TYPES` is defined in `backend/app/services/po_service.py:29` as a 6-element list. Importing it means the divisor automatically tracks any future change to the document type set.

- [ ] **Step 1: Update extraction.py**

  In `backend/app/api/v1/extraction.py`, add to the imports at the top of the file (after the existing imports, around line 20):
  ```python
  from app.services.po_service import CHAIN_DOC_TYPES
  ```

  Then at line 352, change:
  ```python
  completeness = round((count / 6) * 100, 1)
  ```
  to:
  ```python
  completeness = round((count / len(CHAIN_DOC_TYPES)) * 100, 1)
  ```

- [ ] **Step 2: Update tasks.py**

  In `backend/app/services/extraction/tasks.py`, the imports already pull from `po_service` for other things — add `CHAIN_DOC_TYPES` to whatever import from `app.services.po_service` exists, or add a new import line if none exists. Then at line 458:
  ```python
  completeness = round((count / len(CHAIN_DOC_TYPES)) * 100, 1)
  ```

  > Note: tasks.py does NOT currently import from `po_service` — add a new line:
  > ```python
  > from app.services.po_service import CHAIN_DOC_TYPES
  > ```

- [ ] **Step 3: Verify check passes**

  Run: `PYTHONUTF8=1 python debug.py`
  Expected: C3 now shows ✔

- [ ] **Step 4: Commit**

  ```bash
  git add backend/app/api/v1/extraction.py backend/app/services/extraction/tasks.py
  git commit -m "fix: replace hardcoded /6 with len(CHAIN_DOC_TYPES) in chain completeness"
  ```

---

## Task 4 — C4 + C5 + C10: Fix config and env defaults

**Files:**
- Modify: `backend/app/config.py:64,67`
- Modify: `.env.example:34`

These three belong in one commit — they're all "safe defaults that should have been False/empty from day one".

- [ ] **Step 1: Fix config.py — two lines**

  In `backend/app/config.py`, make two changes:

  Line 64 — CORS default:
  ```python
  # Before
  cors_origins: List[str] = ["http://localhost:5174"]
  # After
  cors_origins: List[str] = []
  ```

  Line 67 — debug default:
  ```python
  # Before
  debug: bool = True
  # After
  debug: bool = False
  ```

- [ ] **Step 2: Fix .env.example**

  In `.env.example`, find line 34:
  ```
  DEBUG=true
  ```
  Change to:
  ```
  DEBUG=false
  ```

- [ ] **Step 3: Verify checks pass**

  Run: `PYTHONUTF8=1 python debug.py`
  Expected: C4, C5, C10 all show ✔

- [ ] **Step 4: Commit**

  ```bash
  git add backend/app/config.py .env.example
  git commit -m "fix: set debug=False and cors_origins=[] as safe production defaults; update .env.example"
  ```

---

## Task 5 — C9: Fix port mismatch in stop_all.ps1

**Files:**
- Modify: `stop_all.ps1:4-8`

`start.ps1` launches backend on **8002** and frontend on **5174**. `stop_all.ps1` kills **8000** and **5173** — wrong ports, leaving orphaned processes on every stop.

- [ ] **Step 1: Make the fix**

  In `stop_all.ps1`, change lines 4–8:
  ```powershell
  # Before
  $pids8000 = netstat -ano | Select-String ':8000 ' | ...
  foreach ($p in $pids8000) { ... Write-Host "Killed PID $p (port 8000)" }

  $pids5173 = netstat -ano | Select-String ':5173 ' | ...
  foreach ($p in $pids5173) { ... Write-Host "Killed PID $p (port 5173)" }
  ```
  ```powershell
  # After
  $pids8002 = netstat -ano | Select-String ':8002 ' | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique
  foreach ($p in $pids8002) { if ($p -match '^\d+$' -and $p -ne '0') { taskkill /PID $p /F 2>$null; Write-Host "Killed PID $p (port 8002)" } }

  $pids5174 = netstat -ano | Select-String ':5174 ' | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique
  foreach ($p in $pids5174) { if ($p -match '^\d+$' -and $p -ne '0') { taskkill /PID $p /F 2>$null; Write-Host "Killed PID $p (port 5174)" } }
  ```

- [ ] **Step 2: Verify check passes**

  Run: `PYTHONUTF8=1 python debug.py`
  Expected: C9 now shows ✔

- [ ] **Step 3: Commit**

  ```bash
  git add stop_all.ps1
  git commit -m "fix: stop_all.ps1 was killing wrong ports (8000/5173) — corrected to 8002/5174"
  ```

---

## Task 6 — C6: Add backend healthcheck + nginx condition to docker-compose.prod.yml

**Files:**
- Modify: `docker-compose.prod.yml`

Two things required:
1. The `backend` service needs a `healthcheck` block (currently missing — nginx can't use `condition: service_healthy` without one).
2. The `nginx` `depends_on` needs `condition: service_healthy` for `backend` and `frontend`.

Note: `frontend` is a static build served by nginx in the container — it has no HTTP service to health-check, so `condition: service_started` is appropriate for it.

- [ ] **Step 1: Add healthcheck to backend service**

  In `docker-compose.prod.yml`, add a `healthcheck` block to the `backend` service (after the `volumes:` line):

  ```yaml
  backend:
    build:
      context: ./backend
      target: api
    restart: unless-stopped
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./storage:/app/storage
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/api/v1/health || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s
  ```

- [ ] **Step 2: Update nginx depends_on**

  Change the `nginx` service `depends_on` block from:
  ```yaml
  nginx:
    ...
    depends_on:
      - backend
      - frontend
  ```
  to:
  ```yaml
  nginx:
    ...
    depends_on:
      backend:
        condition: service_healthy
      frontend:
        condition: service_started
  ```

- [ ] **Step 3: Verify check passes**

  Run: `PYTHONUTF8=1 python debug.py`
  Expected: C6 now shows ✔

- [ ] **Step 4: Commit**

  ```bash
  git add docker-compose.prod.yml
  git commit -m "fix: add backend healthcheck and nginx service_healthy condition to docker-compose.prod.yml"
  ```

---

## Task 7 — C7: Update _check_models() in admin.py for new provider config

**Files:**
- Modify: `backend/app/api/v1/admin.py:58-67`

Currently `_check_models()` only branches on the legacy `settings.ocr_two_layer_enabled`. When the new provider abstraction is active (`settings.layer1_provider != ""`), it still checks the old Ollama `/api/tags` endpoint which may not apply (e.g. Datalab provider has no `/api/tags`).

The fix: if `layer1_provider` is set (non-empty), delegate health to the pipeline's own `health_check()` which already knows how to validate each provider. Otherwise fall back to the legacy model-list check.

- [ ] **Step 1: Add pipeline import to admin.py**

  In `backend/app/api/v1/admin.py`, add at the top with the other imports:
  ```python
  from app.services.extraction.pipeline import build_pipeline_from_config
  ```

- [ ] **Step 2: Replace _check_models()**

  Replace the existing `_check_models()` function (lines 58–67) with:
  ```python
  async def _check_models() -> str:
      try:
          # New provider abstraction takes precedence
          if settings.layer1_provider:
              pipeline = build_pipeline_from_config(settings)
              err = await pipeline.health_check()
              return "ok" if not err else f"error: {err}"
          # Legacy path: check Ollama model list
          if settings.ocr_two_layer_enabled:
              models_to_check = [settings.ocr_custom_model, settings.ocr_extractor_model]
          else:
              models_to_check = [settings.ocr_model_name]
          ok, missing = await check_models_available(settings.ocr_base_url, models_to_check)
          return "ok" if ok else f"missing: {missing}"
      except Exception as e:
          return f"error: {str(e)}"
  ```

- [ ] **Step 3: Verify check passes**

  Run: `PYTHONUTF8=1 python debug.py`
  Expected: C7 now shows ✔

- [ ] **Step 4: Commit**

  ```bash
  git add backend/app/api/v1/admin.py
  git commit -m "fix: admin health _check_models() now covers new layer1_provider abstraction"
  ```

---

## Task 8 — C8: Consolidate 7 asyncio.run() calls in tasks.py

**Files:**
- Modify: `backend/app/services/extraction/tasks.py`

**Why this matters:** Each `asyncio.run()` creates and destroys a new event loop. With 7 calls per document, that's 7 loop create/destroy cycles. When Celery runs with `gevent` pool, this crashes (gevent patches the event loop; re-creating it breaks the patch). Even with prefork pool, it's needlessly slow.

**Approach:** Extract all async pipeline calls from lines 143–243 into a single `async def _run_pipeline_async(...)` coroutine. Replace those 6 calls with one `asyncio.run(_run_pipeline_async(...))`. The health check at line 78 stays as a separate single `asyncio.run()` — it's already isolated and runs before the extraction loop.

- [ ] **Step 1: Add the async helper function**

  Insert this function directly above the `extract_document` Celery task definition (before line 61, i.e. after the imports and `_estimate_num_predict`):

  ```python
  async def _run_pipeline_async(
      pipeline,
      route,
      storage_path: str,
      doc_type: str,
      customer_hint: str,
      settings,
  ):
      """Run all async pipeline steps in a single event loop.

      Returns (raw_texts, markdown_pages, page_fields, total_time_ms).
      page_fields is None when pipeline.layer2 is None (legacy single-layer path).
      """
      from app.services.extraction.pdf_converter import PDFConverter
      from app.services.extraction.scan_preprocessor import preprocess_scan
      from app.services.extraction.hybrid_router import ExtractionRoute

      raw_texts = []
      total_time_ms = 0
      markdown_pages = []

      # Digital fast path
      if route == ExtractionRoute.DIGITAL:
          digital_result = await pipeline.try_digital(storage_path)
          if digital_result.markdown and len(digital_result.markdown.strip()) > 50:
              raw_texts = [digital_result.markdown]
          else:
              route = ExtractionRoute.SCANNED

      # OCR path
      if not raw_texts:
          converter = PDFConverter(
              dpi=settings.ocr_pdf_dpi,
              max_pages=settings.ocr_max_pages,
          )
          images_list = converter.convert_to_images(storage_path)

          for i, img in enumerate(images_list):
              page_label = f"p{i + 1}"
              if route == ExtractionRoute.SCANNED:
                  img = preprocess_scan(img)
              try:
                  ocr_result = await pipeline.run_ocr(img, doc_type, page_label)
                  raw_texts.append(ocr_result.markdown)
                  markdown_pages.append((ocr_result.markdown, ocr_result.elapsed_ms, page_label))
              except Exception as page_err:
                  err_msg = str(page_err)
                  if "unreachable" in err_msg or "offline" in err_msg:
                      raise
                  raw_texts.append("")
                  markdown_pages.append(("", 0, page_label))

          await pipeline.release_vram()
          if not settings.ocr_extractor_base_url:
              import time
              time.sleep(5)
              await pipeline.wait_until_ready()

      # Layer 2 extraction
      if pipeline.layer2 is None:
          return raw_texts, markdown_pages, None, total_time_ms

      page_fields = []
      if markdown_pages:
          for markdown, ocr_ms, page_label in markdown_pages:
              if not markdown or len(markdown.strip()) < 20:
                  page_fields.append({})
                  continue
              try:
                  validated = await pipeline.run_extraction(markdown, doc_type, customer_hint)
                  page_fields.append(validated)
                  total_time_ms += ocr_ms
              except Exception as page_err:
                  err_msg = str(page_err)
                  if "unreachable" in err_msg or "offline" in err_msg:
                      raise
                  page_fields.append({})
      else:
          validated = await pipeline.run_extraction(raw_texts[0], doc_type, customer_hint)
          page_fields = [validated]

      return raw_texts, markdown_pages, page_fields, total_time_ms
  ```

- [ ] **Step 2: Replace the extraction body in extract_document**

  In the `extract_document` task, replace the block from line 138 ("# 6. Digital fast path") through line 265 (end of the else/single-layer path) with:

  ```python
          raw_texts = []
          total_time_ms = 0
          markdown_pages = []

          # 6–8. Run all async pipeline steps in a single event loop
          try:
              raw_texts, markdown_pages, page_fields, total_time_ms = asyncio.run(
                  _run_pipeline_async(
                      pipeline, route, storage_path, doc_type, customer_hint, settings
                  )
              )
          except Exception as pipe_err:
              raise

          if page_fields is None:
              # Single-layer legacy path — ResponseParser handles merging
              _parser = ResponseParser()
              extracted_data = _parser.parse_and_merge(raw_texts, doc_type)
              extracted_data = validate_extracted_fields(extracted_data, doc_type)
              if not extracted_data:
                  raise RuntimeError(
                      "Extraction produced no data — all pages returned empty output"
                  )
          else:
              # Merge pages (first non-null wins)
              extracted_data = {}
              for pf in page_fields:
                  for key, value in pf.items():
                      if key.startswith("_"):
                          extracted_data[key] = value
                      elif key not in extracted_data or extracted_data[key] is None:
                          extracted_data[key] = value

              real_fields = {k: v for k, v in extracted_data.items() if not k.startswith("_")}
              if not real_fields:
                  raise RuntimeError(
                      "Extraction service returned no data — all pages failed or were empty"
                  )
  ```

  > Keep the `logger.info(f"Document {document_id}: route={route.value}")` line and the converter/image logging — move them into `_run_pipeline_async` if needed, or remove them since the async helper has its own flow.
  > The key point: there should now be exactly **2** `asyncio.run()` calls in the entire file: the health check (line ~78) and the new `_run_pipeline_async` call.

- [ ] **Step 3: Verify check passes**

  Run: `PYTHONUTF8=1 python debug.py`
  Expected: C8 now shows ✔ (`1 asyncio.run()` — the check allows ≤ 1 but the health check and the new wrapper make 2; if needed, consolidate them too).

  > If the check still fails because it counts 2 `asyncio.run()` calls, wrap the health check inside `_run_pipeline_async` as well by adding an optional `do_health_check: bool = True` param, or move both into one top-level runner. The check threshold is `count <= 1`.

- [ ] **Step 4: Full consolidation if needed (make count = 1)**

  If the check reports 2 `asyncio.run()` calls, consolidate the health check into the async function:

  Replace lines 75–103 (health check block) with:
  ```python
  async def _run_health_and_extract(pipeline, route, storage_path, doc_type, customer_hint, settings):
      """Combines health check + full extraction in one event loop."""
      health_err = await pipeline.health_check()
      if health_err:
          return health_err, None, None, None, None
      raw_texts, markdown_pages, page_fields, total_time_ms = await _run_pipeline_async(
          pipeline, route, storage_path, doc_type, customer_hint, settings
      )
      return None, raw_texts, markdown_pages, page_fields, total_time_ms
  ```

  And call it:
  ```python
  _preflight_error, raw_texts, markdown_pages, page_fields, total_time_ms = asyncio.run(
      _run_health_and_extract(pipeline, route, storage_path, doc_type, customer_hint, settings)
  )
  ```

  > This reduces to exactly 1 `asyncio.run()` call. The route variable must be determined before calling (via `HybridRouter().route(storage_path)` synchronously before `asyncio.run`).

- [ ] **Step 5: Verify final count**

  Run: `PYTHONUTF8=1 python debug.py`
  Expected: C8 ✔ (1 asyncio.run() found)

- [ ] **Step 6: Run a manual smoke test**

  Start the stack locally and trigger one document extraction. Confirm it completes without event-loop errors in the Celery logs.

- [ ] **Step 7: Commit**

  ```bash
  git add backend/app/services/extraction/tasks.py
  git commit -m "fix: consolidate 7 asyncio.run() calls into one in extract_document Celery task"
  ```

---

## Task 9 — Final verification

- [ ] **Step 1: Run all checks**

  ```bash
  PYTHONUTF8=1 python debug.py
  ```

  Expected output:
  ```
  ✔  pipeline.py — ExtractionResult is imported
  ✔  upload validation — uses AND logic (content-type OR magic-bytes)
  ✔  chain completeness — divisor is not hardcoded
  ✔  config.py — debug defaults to False
  ✔  .env.example — DEBUG is not set to true
  ✔  docker-compose.prod.yml — nginx waits for backend healthcheck
  ✔  admin.py health check — covers new LAYER1/LAYER2_PROVIDER config
  ✔  tasks.py — single asyncio.run() or fully sync (1 found)
  ✔  start.ps1 / stop_all.ps1 — ports are consistent
  ✔  config.py — CORS origins default is not localhost-locked

  Passed : 10
  Failed : 0
  ```

  Exit code: 0

---

## Notes

- **C8 complexity warning:** Task 8 is the most invasive change. The `extract_document` task is 400+ lines of interleaved sync DB work and async pipeline calls. If the refactor becomes risky mid-task, an acceptable intermediate: wrap *just* the 6 async calls inside the try block into one `asyncio.run()`, leaving the health check as a second call. That gives count=2 and fails C8, but is still much better than 7 and can be cleaned up in a follow-up.
- **C6 backend health check URL:** The health check URL `http://localhost:8000/api/v1/health` assumes the backend FastAPI app runs on port 8000 inside the container (default uvicorn). Verify this matches the CMD in `backend/Dockerfile` before deploying.
- **C7 note:** `build_pipeline_from_config` may raise if provider config is invalid — the `except Exception` in `_check_models` already handles this gracefully.
