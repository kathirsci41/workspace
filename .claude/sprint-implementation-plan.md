# Order Assurance — 3-Sprint Implementation Plan
*Synthesised from: Platform Intelligence Report · Architecture Redesign Spec (ADR-001/002/003) · Extraction Pipeline Research · Grill-With-Docs Session (June 2026)*
*For: AI agent autonomous implementation*

---

## How to Read This Document

Each sprint is self-contained. Every task lists:
- **Files to create/edit** (exact paths)
- **What to do** (precise enough to implement without further research)
- **Test gate** (mandatory — sprint not done until all tests pass)

Run the test gate at the end of EACH task, not just at end of sprint. If tests fail, fix before proceeding.

Do NOT skip ahead. Sprint 2 depends on Sprint 1 migrations being applied. Sprint 3 depends on Sprint 2 verification models being in place.

---

## Git Discipline (Mandatory)

### Before any sprint or task begins

```bash
# Verify working tree is clean
git status
# If anything uncommitted:
git add -A
git commit -m "chore: checkpoint before <sprint/task name>"
git push
```

**Do not start implementation with uncommitted changes.** If the working tree is dirty, commit first.

### After every successful task (micro-commit)

After each task's test gate passes, immediately commit:

```bash
git add -A
git commit -m "<type>(<scope>): <what was done>"
git push
```

Commit type conventions:

| Task type | Commit type |
|---|---|
| New file (service, model, migration) | `feat` |
| Edit existing file | `fix` or `refactor` |
| Tests only | `test` |
| Config / infra | `chore` |
| Migration file | `migrate` |

Examples:
```
feat(extraction): add liteparse_extractor.py with bbox support
test(extraction): add unit tests for bbox_field_extractor
migrate(schema): add vendor_master table
refactor(ocr): apply bbox layer+merge in ocr_extraction_service
chore(deps): add liteparse to requirements
```

### Never batch tasks into one commit

One task = one commit. If a task has a migration + service file + test, they go in a single commit together. The next task starts a new commit.

### Sprint exit push

After the sprint exit gate passes:
```bash
git tag sprint-<N>-complete
git push --tags
```

---

## Context: What Exists Now

```
order-assurance/
  backend/
    app/
      config.py           ← settings, database_url points to SQLite
      database.py         ← SQLAlchemy sync engine, SessionLocal, get_db()
      models/             ← 8 ORM models (OrderBundleRecord, DocumentRecord, etc.)
      api/routes/
        dev.py            ← dev tools router (always mounted — fix in Task 1.6)
      services/
        extraction_queue.py       ← threading.Condition + deque (in-process, non-persistent)
        order_bundle_verifier.py  ← rules verifier, abs(left-right)<=2 hardcode, header-only, dcs[0] only
        ocr_extraction_service.py ← PP-OCRv4 → GLM-OCR → regex parser
  frontend/               ← React/Vite
  scripts/
    new-validation-run.ps1
```

Key pain points targeted:
1. SQLite → concurrent write failures under load (ADR-001)
2. In-process queue → lost jobs on restart (ADR-002)
3. Verifier → hard-coded ±2, no line items, no vendor master, single DC only (ADR-003)
4. OCR → PP-OCRv4 outdated, no table extraction, VLM fallback wrong implementation
5. No tenant isolation — expensive to add later (grill Q6)
6. Dev router always mounted in production (grill Q8)
7. `last_error` truncated at 500 chars (grill Q9)

---

## Sprint 1 — Database & Queue Foundation
*Goal: PostgreSQL, Celery+Redis, tenant_id scaffold, housekeeping fixes*
*Duration: ~5 days | Risk: Medium (schema migration, infra change)*

### Pre-Sprint Checklist

- [ ] PostgreSQL 16 running locally (`docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16`)
- [ ] Redis 7 running locally (`docker run -d -p 6379:6379 redis:7`)
- [ ] `pip install alembic psycopg2-binary celery[redis] redis`
- [ ] `.env` has `DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/order_assurance`

---

### Task 1.1 — Install Alembic and Create Initial Migration

**Files to create:**
- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/versions/0001_initial_schema.py`

**Steps:**

```bash
cd backend
alembic init alembic
```

Edit `backend/alembic/env.py`:
- Import `from app.models import Base`
- Set `target_metadata = Base.metadata`
- Read `DATABASE_URL` from env: `config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])`

Edit `backend/alembic.ini`:
- Set `script_location = alembic`
- Remove hardcoded `sqlalchemy.url` (set in env.py)

Generate initial migration:
```bash
cd backend
alembic revision --autogenerate -m "initial_schema"
```

Review generated migration — verify all 8 tables present: `order_bundles`, `documents`, `document_metadata`, `audit_events`, `reference_index`, `document_pages`, `text_sources`, `field_candidates`.

Apply:
```bash
alembic upgrade head
```

**Test gate:**
```bash
cd backend
python -m pytest tests/integration/test_migrations.py -q
```

---

### Task 1.2 — Update database.py for PostgreSQL

**File to edit:** `backend/app/database.py`

Replace engine creation block:
```python
# BEFORE
_SQLITE_CONNECT_ARGS = {"check_same_thread": False, "timeout": 60}
_engine = create_engine(
    settings.database_url,
    connect_args=_SQLITE_CONNECT_ARGS if settings.database_url.startswith("sqlite") else {},
)

# AFTER
def _make_engine(url: str):
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False, "timeout": 60})
    return create_engine(
        url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,   # reconnect on stale connections
        pool_recycle=300,     # recycle every 5 min
    )

_engine = _make_engine(settings.database_url)
```

**Test gate:**
```bash
cd backend
python -m pytest tests -q
# Record exact pass/skip/fail count
```

---

### Task 1.3 — Install Celery Worker

**Files to create:**
- `backend/app/worker.py`
- `backend/app/tasks/extraction_task.py`
- `backend/app/tasks/__init__.py`

**`backend/app/worker.py`:**
```python
from celery import Celery
import os

celery_app = Celery(
    "order_assurance",
    broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    include=["app.tasks.extraction_task"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,           # re-queue on worker crash
    worker_prefetch_multiplier=1,  # one task per worker (GPU-bound)
    task_track_started=True,
)
```

**`backend/app/tasks/extraction_task.py`:**
```python
from app.worker import celery_app
from app.database import SessionLocal
from app.services.ocr_extraction_service import run_extraction_for_document

@celery_app.task(
    bind=True,
    name="extraction.process_document",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
)
def process_document_task(self, document_id: str) -> dict:
    """Extract fields from a single document. Retries 3x on failure."""
    db = SessionLocal()
    try:
        result = run_extraction_for_document(db, document_id)
        return {"document_id": document_id, "status": "done", "fields": result}
    except Exception as exc:
        raise self.retry(exc=exc)
    finally:
        db.close()
```

**`backend/app/tasks/__init__.py`:** empty file.

Find and replace all extraction queue callers:
```bash
grep -r "OcrExtractionQueue\|acquire(" backend/app/api backend/app/services --include="*.py" -l
```

For each caller replace with:
```python
from app.tasks.extraction_task import process_document_task
task = process_document_task.delay(document_id)
# store task.id in DocumentRecord.celery_task_id (added in Task 1.4)
```

**Run worker (separate terminal):**
```bash
cd backend
celery -A app.worker.celery_app worker --loglevel=info --concurrency=1
```

**Test gate:**
```bash
cd backend
python -m pytest tests -q
# Record exact pass/skip/fail count
```

---

### Task 1.4 — Add `celery_task_id` and `last_verified_at` to Models

**Decision (grill Q2):** `last_verified_at` enables O(1) bundle list — skip re-verification if already verified and no docs changed.

**File to edit:** `backend/app/models/document.py`

Add after `last_error`:
```python
celery_task_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
```

**File to edit:** `backend/app/models/order_bundle.py` (or wherever `OrderBundleRecord` is defined)

Add after existing status columns:
```python
last_verified_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
```

**File to edit:** `backend/app/services/order_bundle_verifier.py`

At end of `verify_order_bundle()`, after writing status columns, add:
```python
from datetime import datetime, UTC
bundle.last_verified_at = datetime.now(UTC)
db.commit()
```

Generate migration:
```bash
cd backend
alembic revision --autogenerate -m "add_celery_task_id_last_verified_at"
alembic upgrade head
```

**Test gate:**
```bash
cd backend
python -m pytest tests -q
# Record: X passed, Y skipped, Z failed
```

---

### Task 1.5 — Add `tenant_id` to All Tables

**Decision (grill Q6):** Stub `tenant_id` now — single value `'default'` today, swap to real tenant from JWT when multi-user launches. Schema migration cost = zero later.

**Files to edit** — add `tenant_id` column to every model:
- `backend/app/models/order_bundle.py`
- `backend/app/models/document.py`
- `backend/app/models/document_metadata.py`
- `backend/app/models/audit_event.py`
- `backend/app/models/reference_index.py`

For each model, add:
```python
tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default", index=True)
```

**File to create:** `backend/app/middleware/tenant.py`

```python
"""
Tenant middleware — stubs tenant_id as 'default' for all requests.
When multi-user lands: extract tenant from JWT and set here.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Future: parse JWT and set real tenant
        request.state.tenant_id = "default"
        return await call_next(request)


def get_tenant_id(request: Request) -> str:
    return getattr(request.state, "tenant_id", "default")
```

**File to edit:** `backend/app/main.py`

Add middleware after CORS:
```python
from app.middleware.tenant import TenantMiddleware
app.add_middleware(TenantMiddleware)
```

Generate migration:
```bash
cd backend
alembic revision --autogenerate -m "add_tenant_id_all_tables"
alembic upgrade head
```

**Test gate:**
```bash
cd backend
python -m pytest tests -q
# Record exact count
```

---

### Task 1.6 — Fix `last_error` Column and Dev Router Gate

**Decision (grill Q9):** `last_error` VARCHAR(500) → VARCHAR(2000). Full OCR stack traces no longer truncated.

**Decision (grill Q8):** Dev router mounted unconditionally → gate on `APP_ENV`.

**File to edit:** `backend/app/models/document.py`

Change `last_error` column size:
```python
# BEFORE
last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)

# AFTER
last_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
```

**File to edit:** `backend/app/main.py`

Gate dev router mount:
```python
# BEFORE
app.include_router(dev_router, prefix=settings.api_prefix)

# AFTER
if settings.app_env == "development":
    app.include_router(dev_router, prefix=settings.api_prefix)
```

Also remove `enable_dev_tools` from `_require_dev_tools()` in `backend/app/api/routes/dev.py` — the gate is now at mount time, not at handler level. The handler guard becomes:
```python
def _require_dev_tools() -> None:
    # Router only mounted in development — this is belt-and-suspenders
    if settings.app_env != "development":
        raise HTTPException(status_code=403, detail="Development tools are disabled.")
```

Generate migration for `last_error` column change:
```bash
cd backend
alembic revision --autogenerate -m "last_error_varchar_2000"
alembic upgrade head
```

**Test gate:**
```bash
cd backend
python -m pytest tests/integration/test_dev_tools_gate.py tests -q
# Record exact count
```

---

### Sprint 1 Exit Gate

Run ALL five steps from CLAUDE.md section 4:

**Step 1 — Focused tests:**
```bash
cd backend
python -m pytest tests/integration/test_migrations.py tests/unit/test_database.py tests/integration/test_dev_tools_gate.py -v
```

**Step 2 — Migration tests:**
```bash
cd backend
python -m pytest tests/integration/test_migrations.py -q
```

**Step 3 — Full suite:**
```bash
cd backend
python -m pytest tests -q
# REQUIRED: show exact count
```

**Step 4 — Fresh validation run:**
```powershell
.\scripts\new-validation-run.ps1 -RunName sprint1-smoke
```
Verify DB contains all tables + `alembic_version` + `tenant_id` column on all tables.

**Step 5 — Unchanged components:**
Explicitly confirm: extraction parser, OCR, GLM-OCR fallback, regex parser, frontend, XLSX export behaviour unchanged.

Sprint 1 complete only when all 5 steps pass.

---

## Sprint 2 — OCR Pipeline Upgrade + Table Extraction
*Goal: PP-OCRv4 → PP-OCRv5, add PP-StructureV3 table extraction, PaddleOCR-VL-1.6 HuggingFace fallback*
*Duration: ~5 days | Risk: Medium (model swap, new extraction path)*

### Pre-Sprint Checklist

- [ ] Sprint 1 complete and all tests passing
- [ ] `pip install paddlepaddle paddleocr>=3.0`
- [ ] `pip install transformers accelerate torch` (for PaddleOCR-VL-1.6 HuggingFace)
- [ ] GPU available with ≥4GB VRAM
- [ ] HuggingFace model will auto-download on first call (~1.8GB): `PaddlePaddle/PaddleOCR-VL-1.6`

---

### Task 2.1 — Upgrade PP-OCRv4 → PP-OCRv5

**File to edit:** `backend/app/services/ocr_extraction_service.py`

Find the PaddleOCR initialisation (search for `PaddleOCR(`):

```python
# BEFORE
ocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=True, show_log=False)

# AFTER
ocr = PaddleOCR(
    use_angle_cls=True,
    lang='en',
    use_gpu=True,
    show_log=False,
    ocr_version='PP-OCRv5',
)
```

If `ocr_version` param not supported → upgrade: `pip install paddleocr --upgrade`

**Test gate:**
```bash
cd backend
python -m pytest tests/unit/test_ocr_extraction.py -v
```

---

### Task 2.2 — Add PP-StructureV3 Table Extractor

**File to create:** `backend/app/services/table_extraction_service.py`

```python
"""
Table extraction using PP-StructureV3.
Called on VENDOR_INVOICE and COMPANY_INVOICE document types only.
Returns list of line items from the main invoice table.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class LineItem:
    description: str = ""
    hsn_sac: str = ""
    quantity: float = 0.0
    unit: str = ""
    unit_price: float = 0.0
    taxable_amount: float = 0.0
    gst_rate: float = 0.0
    igst: float = 0.0
    cgst: float = 0.0
    sgst: float = 0.0
    total: float = 0.0
    raw: dict = field(default_factory=dict)


_structure_model = None


def _init_structure():
    from paddleocr import PPStructure
    return PPStructure(table=True, ocr=True, show_log=False, use_gpu=True)


def extract_tables(image_path: str) -> list[list[dict]]:
    """Run PP-StructureV3 on image_path. Returns list of tables as row-dicts."""
    global _structure_model
    if _structure_model is None:
        _structure_model = _init_structure()

    result = _structure_model(image_path)
    tables = []
    for region in result:
        if region.get("type") != "table":
            continue
        html = region.get("res", {}).get("html", "")
        if html:
            tables.append(_parse_html_table(html))
    return tables


def _parse_html_table(html: str) -> list[dict]:
    try:
        from html.parser import HTMLParser

        class _TableParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.rows, self._row, self._cell = [], [], []
                self._in_cell = False

            def handle_starttag(self, tag, attrs):
                if tag in ("td", "th"):
                    self._in_cell = True
                    self._cell = []
                elif tag == "tr":
                    self._row = []

            def handle_endtag(self, tag):
                if tag in ("td", "th"):
                    self._row.append(" ".join(self._cell).strip())
                    self._in_cell = False
                elif tag == "tr":
                    if self._row:
                        self.rows.append(self._row)

            def handle_data(self, data):
                if self._in_cell:
                    self._cell.append(data.strip())

        parser = _TableParser()
        parser.feed(html)
        if not parser.rows:
            return []
        headers = parser.rows[0]
        return [
            {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
            for row in parser.rows[1:]
        ]
    except Exception as exc:
        logger.warning("Table HTML parse failed: %s", exc)
        return []


def parse_line_items(table_rows: list[dict]) -> list[LineItem]:
    """Map raw table row dicts → LineItem objects. Handles Indian invoice column name variants."""
    items = []
    for row in table_rows:
        norm = {k.strip().lower().replace(" ", "_"): v for k, v in row.items()}

        def get(*keys) -> str:
            for k in keys:
                v = norm.get(k, "")
                if v:
                    return v
            return ""

        def to_float(s: str) -> float:
            try:
                return float(s.replace(",", "").replace("₹", "").strip() or 0)
            except ValueError:
                return 0.0

        item = LineItem(
            description=get("description", "item_description", "particulars", "product_name"),
            hsn_sac=get("hsn/sac", "hsn_sac", "hsn", "sac"),
            quantity=to_float(get("qty", "quantity", "nos")),
            unit=get("unit", "uom", "unit_of_measure"),
            unit_price=to_float(get("rate", "unit_price", "price")),
            taxable_amount=to_float(get("taxable_amount", "taxable_value", "amount")),
            gst_rate=to_float(get("gst_rate", "gst_%", "tax_rate")),
            igst=to_float(get("igst", "igst_amount")),
            cgst=to_float(get("cgst", "cgst_amount")),
            sgst=to_float(get("sgst", "sgst_amount")),
            total=to_float(get("total", "total_amount", "net_amount")),
            raw=row,
        )
        if item.description or item.taxable_amount:
            items.append(item)
    return items
```

**File to edit:** `backend/app/services/ocr_extraction_service.py`

After OCR text is obtained, for invoice doc types:
```python
from app.services.table_extraction_service import extract_tables, parse_line_items

if document_type in ("vendor_invoice", "company_invoice"):
    tables = extract_tables(image_path)
    if tables:
        line_items = parse_line_items(tables[0])
        extracted["line_items"] = [vars(li) for li in line_items]
```

**Test gate:**
```bash
cd backend
python -m pytest tests/unit/test_table_extraction.py tests/unit/test_ocr_extraction.py -v
```

If `tests/unit/test_table_extraction.py` doesn't exist, create a smoke test using a sample image from `validation-runs/`.

---

### Task 2.3 — Replace GLM-OCR Fallback with PaddleOCR-VL-1.6 (HuggingFace)

**Decision (grill Q3):** PaddleOCR-VL-1.6 is the #1 open-source document VLM (96.33 OmniDocBench). It is NOT in Ollama — load from HuggingFace `PaddlePaddle/PaddleOCR-VL-1.6` via `transformers`. Do NOT use Qwen2.5-VL.

**File to create:** `backend/app/services/paddleocr_vl_service.py`

```python
"""
PaddleOCR-VL-1.6 fallback OCR service.
Model: PaddlePaddle/PaddleOCR-VL-1.6 (0.9B VLM, HuggingFace)
Benchmark: 96.33 OmniDocBench — #1 open-source document VLM (July 2025)

Loaded lazily on first call. ~1.8GB VRAM. Requires GPU with ≥4GB VRAM.
NOT available via Ollama — loaded directly via transformers library.
"""
from __future__ import annotations
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_MODEL_ID = "PaddlePaddle/PaddleOCR-VL-1.6"
_model = None
_processor = None


def _load_model():
    global _model, _processor
    if _model is not None:
        return
    logger.info("Loading PaddleOCR-VL-1.6 from HuggingFace (first call — may take 30s)...")
    try:
        from transformers import AutoProcessor, AutoModelForCausalLM
        import torch

        _processor = AutoProcessor.from_pretrained(_MODEL_ID, trust_remote_code=True)
        _model = AutoModelForCausalLM.from_pretrained(
            _MODEL_ID,
            trust_remote_code=True,
            torch_dtype=torch.float16,
            device_map="auto",
        )
        logger.info("PaddleOCR-VL-1.6 loaded successfully.")
    except Exception as exc:
        logger.error("Failed to load PaddleOCR-VL-1.6: %s", exc)
        _model = None
        _processor = None


def extract_text_vl(image_path: str) -> str:
    """
    Run PaddleOCR-VL-1.6 on image_path and return extracted text.
    Returns empty string on failure — caller falls back to PP-OCRv5 result.
    """
    _load_model()
    if _model is None or _processor is None:
        logger.warning("PaddleOCR-VL-1.6 not available — skipping VLM fallback")
        return ""

    try:
        from PIL import Image
        import torch

        image = Image.open(image_path).convert("RGB")
        prompt = (
            "Extract all text from this document image. "
            "Preserve the original structure. Return plain text only."
        )

        inputs = _processor(
            text=prompt,
            images=image,
            return_tensors="pt",
        ).to(_model.device)

        with torch.no_grad():
            output_ids = _model.generate(
                **inputs,
                max_new_tokens=2048,
                do_sample=False,
            )

        # Decode only the generated tokens (skip input tokens)
        input_len = inputs["input_ids"].shape[1]
        generated = output_ids[0][input_len:]
        text = _processor.decode(generated, skip_special_tokens=True)
        return text.strip()

    except Exception as exc:
        logger.warning("PaddleOCR-VL-1.6 inference failed: %s", exc)
        return ""
```

**File to edit:** `backend/app/services/ocr_extraction_service.py`

Find the GLM-OCR fallback block and replace:
```python
# BEFORE
if ocr_confidence < CONFIDENCE_THRESHOLD:
    result = glm_ocr_fallback(image_path)

# AFTER
if ocr_confidence < CONFIDENCE_THRESHOLD:
    from app.services.paddleocr_vl_service import extract_text_vl
    vl_text = extract_text_vl(image_path)
    if vl_text:
        result = vl_text
    # else: keep PP-OCRv5 result as-is
```

**Test gate:**
```bash
cd backend
python -m pytest tests -q
# Record exact count
```

---

### Task 2.4 — Validation Run vs Accepted Baselines

```powershell
.\scripts\new-validation-run.ps1 -RunName sprint2-panimalar
.\scripts\new-validation-run.ps1 -RunName sprint2-trade
.\scripts\new-validation-run.ps1 -RunName sprint2-amc
```

Compare against accepted baselines (CLAUDE.md):
- Panimalar: 24/24 fields, zero failed statuses, XLSX passed
- Trade: zero failed statuses, XLSX passed
- AMC: 27/28 fields (Delivery Challan missing expected), XLSX passed

If any fixture regresses vs baseline, fix before proceeding to Sprint 3.

---

### Sprint 2 Exit Gate

**Step 1:** `python -m pytest tests/unit/test_ocr_extraction.py tests/unit/test_table_extraction.py -v`
**Step 2:** `python -m pytest tests/integration/test_migrations.py -q`
**Step 3:** `python -m pytest tests -q` — exact count required
**Step 4:** `.\scripts\new-validation-run.ps1 -RunName sprint2-smoke`
**Step 5:** Confirm ADR-001 (PostgreSQL), ADR-002 (Celery) unchanged. Only extraction/OCR changed.
**Step 6 (required — extraction changed):** All 3 real-document fixtures meet accepted baselines.

---

## Sprint 3 — Verification Engine + Vendor Master
*Goal: Replace hard-coded ±2 tolerance, add line-item matching, GSTIN validation, multi-DC support, vendor master*
*Duration: ~5 days | Risk: Low-Medium (pure logic change, no infra)*

### Pre-Sprint Checklist

- [ ] Sprint 1 and Sprint 2 complete
- [ ] `line_items` field present in extracted JSON (from Sprint 2 Task 2.2)
- [ ] All 3 real-document validation baselines still met

---

### Task 3.1 — ToleranceConfig (Replace Hard-Coded ±2)

**File to create:** `backend/app/services/tolerance_config.py`

```python
"""
Configurable tolerance for verification amount checks.
Replaces hard-coded abs(left - right) <= 2 in order_bundle_verifier.py.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ToleranceConfig:
    """
    Amount match tolerance.
    PASSES when: abs(left - right) <= max(absolute_floor, percentage * max(left, right))
    Defaults: 2% tolerance, ₹5 absolute floor.
    """
    percentage: float = 0.02
    absolute_floor: float = 5.0
    per_field: dict[str, float] = field(default_factory=dict)

    def passes(self, left: float, right: float, field_name: str = "") -> bool:
        pct = self.per_field.get(field_name, self.percentage)
        threshold = max(self.absolute_floor, pct * max(abs(left), abs(right), 1.0))
        return abs(left - right) <= threshold

    def diff_pct(self, left: float, right: float) -> float:
        denom = max(abs(left), abs(right), 1.0)
        return abs(left - right) / denom * 100


DEFAULT_TOLERANCE = ToleranceConfig()
```

**File to edit:** `backend/app/services/order_bundle_verifier.py`

Replace hard-coded tolerance check:
```python
# BEFORE (~line 339)
elif abs(left_value - right_value) <= 2:
    status = "PASS"

# AFTER
from app.services.tolerance_config import DEFAULT_TOLERANCE
elif DEFAULT_TOLERANCE.passes(left_value, right_value, field_name=check_name):
    status = "PASS"
```

Add diff_pct to check result:
```python
"diff": round(abs(left_value - right_value), 2),
"diff_pct": round(DEFAULT_TOLERANCE.diff_pct(left_value, right_value), 2),
```

**Test gate:**
```bash
cd backend
python -m pytest tests/unit/test_verifier.py -v
```

---

### Task 3.2 — GSTIN Extraction and Validation

**Decision (grill Q4):** Extract `gstin` field from ALL document types. If not present in a doc → status `SKIP` with reason `gstin_not_present`. Compare whatever is extracted. No hard failures for missing GSTIN.

**File to create:** `backend/app/services/gstin_validator.py`

```python
"""
GSTIN (Goods and Services Tax Identification Number) validation.
Format: 2-digit state code + 10-char PAN + 1-char entity + Z (literal) + 1 checksum
"""
import re

_GSTIN_PATTERN = re.compile(
    r'^[0-3][0-9][A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$'
)

VALID_STATE_CODES = {
    "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
    "21", "22", "23", "24", "25", "26", "27", "28", "29", "30",
    "31", "32", "33", "34", "35", "36", "37", "38",
    "97",  # Other Territory
}


def validate_gstin(gstin: str) -> tuple[bool, str]:
    """Returns (is_valid, reason). reason is empty string when valid."""
    if not gstin:
        return False, "GSTIN empty"
    gstin = gstin.strip().upper()
    if not _GSTIN_PATTERN.match(gstin):
        return False, f"GSTIN format invalid: {gstin}"
    state_code = gstin[:2]
    if state_code not in VALID_STATE_CODES:
        return False, f"Invalid state code: {state_code}"
    return True, ""
```

**File to edit:** `backend/app/services/order_bundle_verifier.py`

Replace the old GSTIN cross-check block with:

```python
from app.services.gstin_validator import validate_gstin

# --- GSTIN: try to extract from all doc types ---
GSTIN_DOC_KEYS = [
    "vendor_invoice",
    "company_invoice",
    "company_po",
    "customer_po",
    "company_dc",
]

gstin_map = {}
for doc_key in GSTIN_DOC_KEYS:
    doc_data = extracted.get(doc_key, {})
    # Try vendor_gstin first, then generic gstin field
    gstin_val = doc_data.get("vendor_gstin") or doc_data.get("gstin") or doc_data.get("bill_to_gstin")
    gstin_map[doc_key] = gstin_val

# Report not found
for doc_key, gstin_val in gstin_map.items():
    if not gstin_val:
        checks.append({
            "check": f"{doc_key}_gstin",
            "status": "SKIP",
            "reason": "gstin_not_present",
        })
        continue
    # Validate format
    valid, reason = validate_gstin(gstin_val)
    checks.append({
        "check": f"{doc_key}_gstin_format",
        "status": "PASS" if valid else "FAIL",
        "gstin": gstin_val,
        "reason": reason or f"GSTIN {gstin_val} valid",
    })

# Cross-compare extracted GSTINs (only compare present ones)
extracted_gstins = {k: v for k, v in gstin_map.items() if v}

# vendor_invoice.vendor_gstin should match company_po.gstin (same vendor on both docs)
vi_gstin = extracted_gstins.get("vendor_invoice")
po_gstin = extracted_gstins.get("company_po")
if vi_gstin and po_gstin and vi_gstin != po_gstin:
    checks.append({
        "check": "gstin_vendor_po_match",
        "status": "WARN",
        "detail": f"Vendor Invoice GSTIN {vi_gstin} ≠ Company PO GSTIN {po_gstin}",
    })
```

**Add GSTIN extraction rule to parser for remaining doc types:**

In `backend/app/services/ocr_extraction_service.py` (or the relevant parser rules file), add regex for `gstin` field to COMPANY_INVOICE, COMPANY_PO, CUSTOMER_PO, COMPANY_DC parsers:

```python
# Add to each doc type's extraction rules:
"gstin": r'\b([0-3][0-9][A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z])\b',
```

Note: Many docs genuinely have no GSTIN printed on them (e.g., Customer PO, DC). `SKIP` is the correct outcome for these — not a failure.

**Test gate:**
```bash
cd backend
python -m pytest tests/unit/test_gstin_validator.py tests/unit/test_verifier.py -v
```

---

### Task 3.3 — Multi-DC Verification Fix

**Decision (grill Q5):** Current verifier uses `dcs[0]` only. Fix: sum ALL DCs for amount match, check each DC independently for SO/PO reference match.

**File to edit:** `backend/app/services/order_bundle_verifier.py`

Find the DC handling block (search for `dcs[0]` or `primary_dc`) and replace:

```python
# BEFORE
dcs = [doc for doc in bundle.documents if doc.document_type == "COMPANY_DC"]
primary_dc = dcs[0]
# ... all checks use primary_dc only

# AFTER
dcs = [doc for doc in bundle.documents if doc.document_type == "COMPANY_DC"]

# Audit: how many DCs in this bundle
checks.append({
    "check": "dc_count",
    "status": "PASS",
    "value": len(dcs),
    "detail": f"{len(dcs)} delivery challan(s) found",
})

if not dcs:
    checks.append({"check": "dc_present", "status": "FAIL", "detail": "No delivery challan found"})
else:
    # Amount: SUM of all DCs vs invoice (not just dcs[0])
    dc_total_taxable = sum(
        float(dc.metadata.extracted_data.get("taxable_amount") or 0)
        for dc in dcs
        if dc.metadata and dc.metadata.extracted_data
    )
    dc_total_gross = sum(
        float(dc.metadata.extracted_data.get("total_amount") or dc.metadata.extracted_data.get("net_amount") or 0)
        for dc in dcs
        if dc.metadata and dc.metadata.extracted_data
    )

    # Reference check: EACH DC must match invoice SO/PO
    invoice_so = extracted.get("company_invoice", {}).get("so_no", "")
    invoice_po = extracted.get("company_invoice", {}).get("po_reference", "")

    for dc in dcs:
        dc_data = dc.metadata.extracted_data if dc.metadata else {}
        dc_so = dc_data.get("so_no", "")
        dc_po = dc_data.get("po_reference", "") or dc_data.get("customer_po_no", "")

        if invoice_so and dc_so and invoice_so != dc_so:
            checks.append({
                "check": "dc_so_match",
                "status": "FAIL",
                "dc_id": str(dc.id),
                "left": invoice_so,
                "right": dc_so,
                "detail": f"DC {dc.id} SO {dc_so} ≠ Invoice SO {invoice_so}",
            })
        else:
            checks.append({
                "check": "dc_so_match",
                "status": "PASS" if invoice_so else "SKIP",
                "dc_id": str(dc.id),
            })

    # Amount match: sum of all DCs vs invoice
    # (replaces the old primary_dc amount check)
    invoice_taxable = float(extracted.get("company_invoice", {}).get("taxable_amount") or 0)
    if dc_total_taxable and invoice_taxable:
        status = "PASS" if DEFAULT_TOLERANCE.passes(dc_total_taxable, invoice_taxable, "dc_invoice_amount") else "REVIEW_REQUIRED"
        checks.append({
            "check": "dc_invoice_amount_match",
            "status": status,
            "left_value": dc_total_taxable,
            "right_value": invoice_taxable,
            "detail": f"Sum of {len(dcs)} DC(s) ₹{dc_total_taxable} vs Invoice ₹{invoice_taxable}",
        })
```

**Test gate:**
```bash
cd backend
python -m pytest tests/unit/test_verifier.py -v -k "dc"
```

---

### Task 3.4 — Vendor Name Normalization

**Decision (grill Q7):** SequenceMatcher on raw names fails on `"P LTD"` vs `"Pvt Ltd"` vs `"Private Limited"`. Normalize suffixes first.

**File to edit:** `backend/app/services/order_bundle_verifier.py`

Add normalization function and use it in VENDOR_NAME_MATCH check:

```python
import re as _re

_COMPANY_SUFFIXES = _re.compile(
    r'\b(private\s+limited|pvt\.?\s*ltd\.?|p\.?\s*ltd\.?|limited|ltd\.?|llp|llc|inc\.?|corp\.?)\b',
    _re.IGNORECASE,
)

def _normalize_company_name(name: str) -> str:
    """Strip legal suffixes and normalize for fuzzy comparison."""
    if not name:
        return ""
    name = name.upper().strip()
    name = _COMPANY_SUFFIXES.sub("", name)
    name = _re.sub(r'[^A-Z0-9\s]', '', name)
    return _re.sub(r'\s+', ' ', name).strip()
```

Find the `VENDOR_NAME_MATCH` check in `verify_order_bundle()` and update:
```python
# BEFORE
ratio = SequenceMatcher(None, vendor_name_a.lower(), vendor_name_b.lower()).ratio()

# AFTER
ratio = SequenceMatcher(
    None,
    _normalize_company_name(vendor_name_a),
    _normalize_company_name(vendor_name_b)
).ratio()
# threshold: 0.85 (normalized names are shorter, closer match expected)
```

**Test gate:**
```bash
cd backend
python -m pytest tests/unit/test_verifier.py -v -k "vendor_name"
```

---

### Task 3.5 — GST Math Verification

**File to edit:** `backend/app/services/order_bundle_verifier.py`

Add GST math check:

```python
def _verify_gst_math(extracted: dict, tolerance) -> list[dict]:
    """Verify: taxable_amount × gst_rate ≈ igst OR (cgst + sgst)."""
    checks = []
    for doc_key in ("vendor_invoice", "company_invoice"):
        doc = extracted.get(doc_key, {})
        taxable = float(doc.get("taxable_amount") or 0)
        gst_rate_pct = float(doc.get("gst_rate") or doc.get("tax_rate") or 0)
        igst = float(doc.get("igst") or doc.get("igst_amount") or 0)
        cgst = float(doc.get("cgst") or doc.get("cgst_amount") or 0)
        sgst = float(doc.get("sgst") or doc.get("sgst_amount") or 0)

        if not (taxable and gst_rate_pct):
            continue

        expected_tax = round(taxable * gst_rate_pct / 100, 2)
        actual_tax = igst or (cgst + sgst)

        if not actual_tax:
            continue

        status = "PASS" if tolerance.passes(expected_tax, actual_tax, "gst_tax") else "FAIL"
        checks.append({
            "check": f"{doc_key}_gst_math",
            "status": status,
            "expected": expected_tax,
            "actual": actual_tax,
            "detail": f"₹{taxable} × {gst_rate_pct:.0f}% = ₹{expected_tax}, found ₹{actual_tax}",
        })
    return checks
```

Call from `verify_order_bundle()`:
```python
checks.extend(_verify_gst_math(extracted, DEFAULT_TOLERANCE))
```

**Test gate:**
```bash
cd backend
python -m pytest tests/unit/test_verifier.py -v -k "gst"
```

---

### Task 3.6 — Line-Item Reconciliation

**File to create:** `backend/app/services/line_item_matcher.py`

```python
"""
Three-way line-item reconciliation:
  Vendor Invoice ↔ Delivery Challan quantities ↔ Company Invoice

Matching key: HSN/SAC code (primary) → description fuzzy (fallback, cutoff=0.75).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import difflib

from app.services.tolerance_config import DEFAULT_TOLERANCE


@dataclass
class LineItemMatch:
    hsn: str
    description: str
    vendor_qty: Optional[float]
    dc_qty: Optional[float]
    invoice_qty: Optional[float]
    vendor_unit_price: Optional[float]
    invoice_unit_price: Optional[float]
    qty_status: str       # PASS / WARN / FAIL
    price_status: str     # PASS / WARN / FAIL / NA
    issues: list[str]


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _match_key(item: dict) -> str:
    return item.get("hsn_sac", "").strip() or item.get("description", "").strip().lower()


def _fuzzy_find(key: str, lookup: dict) -> Optional[dict]:
    if not key:
        return None
    matches = difflib.get_close_matches(key, lookup.keys(), n=1, cutoff=0.75)
    return lookup[matches[0]] if matches else None


def reconcile_line_items(
    vendor_items: list[dict],
    dc_items: list[dict],
    invoice_items: list[dict],
    tolerance=None,
) -> list[LineItemMatch]:
    tol = tolerance or DEFAULT_TOLERANCE
    dc_map = {_match_key(i): i for i in dc_items}
    inv_map = {_match_key(i): i for i in invoice_items}

    results = []
    for vi in vendor_items:
        key = _match_key(vi)
        dc_item = dc_map.get(key) or _fuzzy_find(key, dc_map)
        inv_item = inv_map.get(key) or _fuzzy_find(key, inv_map)

        v_qty = _to_float(vi.get("quantity"))
        d_qty = _to_float(dc_item.get("quantity")) if dc_item else None
        i_qty = _to_float(inv_item.get("quantity")) if inv_item else None
        v_price = _to_float(vi.get("unit_price"))
        i_price = _to_float(inv_item.get("unit_price")) if inv_item else None

        issues = []
        qty_status = "PASS"

        if d_qty is None:
            qty_status = "WARN"
            issues.append(f"Item '{key}' not found in DC")
        elif v_qty and not tol.passes(v_qty, d_qty, "quantity"):
            qty_status = "FAIL"
            issues.append(f"DC qty {d_qty} ≠ Vendor qty {v_qty}")

        if i_qty is None:
            if qty_status == "PASS":
                qty_status = "WARN"
            issues.append(f"Item '{key}' not found in Company Invoice")
        elif v_qty and i_qty and not tol.passes(v_qty, i_qty, "quantity"):
            qty_status = "FAIL"
            issues.append(f"Invoice qty {i_qty} ≠ Vendor qty {v_qty}")

        price_status = "NA"
        if v_price and i_price:
            price_status = "PASS" if tol.passes(v_price, i_price, "unit_price") else "FAIL"
            if price_status == "FAIL":
                issues.append(f"Price mismatch: Vendor ₹{v_price} ≠ Invoice ₹{i_price}")

        results.append(LineItemMatch(
            hsn=key,
            description=vi.get("description", ""),
            vendor_qty=v_qty,
            dc_qty=d_qty,
            invoice_qty=i_qty,
            vendor_unit_price=v_price,
            invoice_unit_price=i_price,
            qty_status=qty_status,
            price_status=price_status,
            issues=issues,
        ))

    return results
```

**File to edit:** `backend/app/services/order_bundle_verifier.py`

Add line-item reconciliation call:
```python
from app.services.line_item_matcher import reconcile_line_items

vendor_items = extracted.get("vendor_invoice", {}).get("line_items", [])
# Multi-DC: aggregate line items from ALL DCs
dc_items = []
for dc in dcs:
    dc_data = dc.metadata.extracted_data if dc.metadata else {}
    dc_items.extend(dc_data.get("line_items", []))
invoice_items = extracted.get("company_invoice", {}).get("line_items", [])

if vendor_items:
    matches = reconcile_line_items(vendor_items, dc_items, invoice_items)
    for m in matches:
        checks.append({
            "check": f"line_item_{m.hsn or m.description[:20]}",
            "qty_status": m.qty_status,
            "price_status": m.price_status,
            "issues": m.issues,
        })
        issues.extend(m.issues)
```

**Test gate:**
```bash
cd backend
python -m pytest tests/unit/test_line_item_matcher.py tests/unit/test_verifier.py -v
```

---

### Task 3.7 — Vendor Master (GSTIN Registry)

**File to create:** `backend/app/models/vendor_master.py`

```python
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime
from datetime import datetime, UTC
from app.database import Base


class VendorMasterRecord(Base):
    __tablename__ = "vendor_master"

    gstin: Mapped[str] = mapped_column(String(15), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default", index=True)
    vendor_name: Mapped[str] = mapped_column(String(256))
    trade_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    state_code: Mapped[str] = mapped_column(String(2))
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
    is_active: Mapped[bool] = mapped_column(default=True)
```

Register in `backend/app/models/__init__.py`:
```python
from app.models.vendor_master import VendorMasterRecord  # noqa: F401
```

Generate migration:
```bash
cd backend
alembic revision --autogenerate -m "add_vendor_master"
alembic upgrade head
```

**File to create:** `backend/app/services/vendor_master_service.py`

```python
"""
Vendor master — upsert on first successful extraction, flag on name divergence.
ponytail: no external GSTIN API — validate format + track internally only.
"""
from __future__ import annotations
from sqlalchemy.orm import Session
from app.models.vendor_master import VendorMasterRecord
from app.services.gstin_validator import validate_gstin
from datetime import datetime, UTC
import difflib


def upsert_vendor(db: Session, gstin: str, name: str, state_code: str) -> VendorMasterRecord:
    valid, _ = validate_gstin(gstin)
    if not valid:
        raise ValueError(f"Invalid GSTIN: {gstin}")

    record = db.get(VendorMasterRecord, gstin)
    if record is None:
        record = VendorMasterRecord(gstin=gstin, vendor_name=name, state_code=state_code)
        db.add(record)
    else:
        record.vendor_name = name
        record.last_seen_at = datetime.now(UTC)
    db.commit()
    return record


def check_vendor(db: Session, gstin: str, invoice_name: str) -> list[str]:
    """Return warning strings if vendor data conflicts with master. Empty = OK."""
    record = db.get(VendorMasterRecord, gstin)
    if record is None:
        return []  # first time — no master to compare against

    issues = []
    if invoice_name and record.vendor_name:
        ratio = difflib.SequenceMatcher(
            None, record.vendor_name.lower(), invoice_name.lower()
        ).ratio()
        if ratio < 0.7:
            issues.append(
                f"Vendor name mismatch: master='{record.vendor_name}', invoice='{invoice_name}'"
            )
    return issues
```

**File to edit:** `backend/app/services/order_bundle_verifier.py`

```python
from app.services.vendor_master_service import check_vendor

vendor_gstin = extracted.get("vendor_invoice", {}).get("vendor_gstin", "")
vendor_name = extracted.get("vendor_invoice", {}).get("vendor_name", "")
if vendor_gstin and vendor_name:
    vendor_issues = check_vendor(db, vendor_gstin, vendor_name)
    for vi_issue in vendor_issues:
        issues.append(vi_issue)
        checks.append({"check": "vendor_master", "status": "WARN", "detail": vi_issue})
```

**Test gate:**
```bash
cd backend
python -m pytest tests/unit/test_vendor_master.py tests/unit/test_verifier.py -v
```

---

### Sprint 3 Exit Gate

**Step 1:** `python -m pytest tests/unit/test_verifier.py tests/unit/test_line_item_matcher.py tests/unit/test_gstin_validator.py tests/unit/test_vendor_master.py -v`
**Step 2:** `python -m pytest tests/integration/test_migrations.py -q`
**Step 3:** `python -m pytest tests -q` — exact count required
**Step 4:** `.\scripts\new-validation-run.ps1 -RunName sprint3-smoke`
**Step 5:** OCR, parser, export, frontend unchanged. Only verifier + models changed.
**Step 6 (required):** All 3 real-document fixtures:
  - Panimalar: 24/24 fields, zero failed, XLSX passed, vendor partial billing only open issue
  - Trade: zero failed, XLSX passed
  - AMC: 27/28 fields (DC missing expected), XLSX passed

---

## Cross-Sprint Rules

1. **Never edit** `E:\PROJECTS\Experiments\Logistic\ODMP\backend\*` — read-only reference
2. **All test gates are blocking** — do not proceed if gate fails
3. **Migration files** — never edit an already-applied migration, always create new revision
4. **Celery worker** — must be running for extraction routes to work in Sprint 2+
5. **tenant_id** — always `"default"` until multi-user auth is added; never omit from new models
6. **Git checkpoint before each task** — `git status` must be clean before starting; commit dirty state first
7. **Micro-commit after each task** — test gate passes → `git add -A && git commit && git push` immediately; one task = one commit
8. **Sprint tag on exit** — `git tag sprint-N-complete && git push --tags` after exit gate passes
6. **Multi-DC** — never use `dcs[0]` alone; always iterate all DCs and sum for amount checks
7. **Environment variables** in `.env`:
   ```
   DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/order_assurance
   REDIS_URL=redis://localhost:6379/0
   APP_ENV=development
   ```

---

## Sprint 4 — LiteParse BBox Extraction (Local Spatial Extraction)
*Goal: Replace regex-on-raw-text with spatial bbox extraction for digital PDFs. Add line_items. Zero schema change.*
*Duration: ~5 days | Risk: Low (additive only — layer+merge means no regression possible)*
*Decision: Grill-With-Docs Session #2, June 2026 — 7 architectural decisions locked*

### Context: Why This Sprint Exists

Benchmark result (June 2026): LiteParse extracts 50–111% more text than PyMuPDF from digital PDFs, but feeding that richer text into the existing regex parser causes FEWER fields extracted (line-item amounts bleed into header regex patterns). The correct path is spatial extraction — use bboxes directly, not raw text.

LlamaExtract quality gap: current system extracts 8–13 header fields, zero line items, zero CGST/SGST breakdown. LlamaExtract (cloud reference) achieves full line_items (5–10 items), tax breakdowns, bank details. This sprint closes that gap locally.

Data sovereignty: all docs contain Indian B2B PII (GSTINs, amounts, vendor names). No cloud extraction. LiteParse is local, Apache 2.0, PDFium-based.

### Architecture Decisions (7 locked)

| Decision | Choice | Reason |
|---|---|---|
| A: Role of LiteParse | Augments, not replaces OCR providers | Existing OCR paths untouched; LiteParse adds bboxes for digital docs |
| Y: Extraction method | BBox spatial (label-proximity rules), NOT regex re-tune | Regex on LiteParse text = regression; spatial is the correct layer |
| P: Phasing | Sprint 4 separate phase | Too large for Sprint 3 scope |
| T: Schema strategy | Internal unified schema S + adapter → flat dict T | Verification engine and frontend see existing field names unchanged |
| E: PaddleOCR HTTP | Optional external server, fallback to existing paddle_provider | No subprocess complexity in backend process |
| G: Integration | Layer+merge — regex AND bbox both run, bbox wins on overlap | `{**regex_result, **bbox_result}` — regression caught by diff, not blind |
| J: line_items storage | Nested key in existing `extracted_data` JSON | Zero DB schema change; Build 2 promotes to relational table |

### Pre-Sprint Checklist

- [ ] Sprint 1, 2, and 3 complete (or at minimum: Sprint 3 line-item reconciliation in place)
- [ ] `pip install liteparse` (local, no API key, Apache 2.0)
- [ ] Benchmark run complete and confirmed: all 3 fixtures extract 200+ bboxes for digital PDFs
- [ ] Read `benchmark/server.py` to understand `extract_liteparse()` — reference implementation
- [ ] Do NOT start until user approves Sprint 4 plan

---

### Task 4.1 — LiteParse Text + BBox Extractor Layer

**Decision A + Y**: LiteParse runs alongside PyMuPDF for digital PDFs only. Returns bboxes for BBoxFieldExtractor. Does NOT replace paddle_provider or PP-OCRv5.

**File to create:** `backend/app/services/extraction/liteparse_extractor.py`

```python
"""
LiteParse digital text + bbox extractor.
Runs alongside PyMuPDF — does NOT replace OCR providers.
For digital PDFs only (ocr_enabled=False).
Scanned docs: returns empty result, existing OCR path handles them.

LiteParse: https://github.com/run-llama/liteparse (Apache 2.0, PDFium-based)
Benchmark: 50-111% more text than PyMuPDF; 222-242 bboxes on our fixtures.
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from liteparse import LiteParse, ParseError
    _LITEPARSE_AVAILABLE = True
except ImportError:
    _LITEPARSE_AVAILABLE = False
    logger.warning("liteparse not installed — bbox extraction disabled. pip install liteparse")


def _is_available() -> bool:
    return _LITEPARSE_AVAILABLE


def extract_bboxes(pdf_path: str) -> dict[str, Any]:
    """
    Extract text items with bounding boxes from a digital PDF.

    Returns:
        {
            "bboxes": list[{page, text, x, y, w, h}],
            "text": str,        # full concatenated text
            "pages": int,
            "is_digital": bool, # False = scanned, skip bbox extraction
            "error": str | None,
        }

    Safe: never raises. Returns {"bboxes": [], "is_digital": False} on any failure.
    """
    empty = {"bboxes": [], "text": "", "pages": 0, "is_digital": False, "error": None}

    if not _is_available():
        return {**empty, "error": "liteparse not installed"}

    try:
        # ocr_enabled=False: digital text only — no Tesseract/PaddleOCR needed.
        # Tesseract offline: set TESSDATA_PREFIX env var to dir with eng.traineddata.
        parser = LiteParse(ocr_enabled=False)
        result = parser.parse(pdf_path)

        bboxes: list[dict] = []
        for page in result.pages:
            for item in page.text_items:
                bboxes.append({
                    "page": page.page_num,
                    "text": item.text,
                    "x": round(item.x, 1),
                    "y": round(item.y, 1),
                    "w": round(item.width, 1),
                    "h": round(item.height, 1),
                })

        is_digital = len(result.text.strip()) > 30
        return {
            "bboxes": bboxes,
            "text": result.text,
            "pages": len(result.pages),
            "is_digital": is_digital,
            "error": None,
        }

    except ParseError as exc:
        logger.warning("LiteParse parse error on %s: %s", pdf_path, exc)
        return {**empty, "error": str(exc)}
    except Exception as exc:
        logger.warning("LiteParse unexpected error on %s: %s", pdf_path, exc)
        return {**empty, "error": str(exc)}


def extract_bboxes_from_bytes(pdf_bytes: bytes) -> dict[str, Any]:
    """Convenience wrapper — writes bytes to temp file, calls extract_bboxes."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    try:
        return extract_bboxes(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
```

**Test gate:**
```bash
cd backend
python -c "
from app.services.extraction.liteparse_extractor import extract_bboxes, _is_available
print('available:', _is_available())
# smoke test with any PDF from validation-runs/
import glob, os
pdfs = glob.glob('../validation-runs/**/*.pdf', recursive=True)
if pdfs:
    r = extract_bboxes(pdfs[0])
    print('bboxes:', len(r['bboxes']), 'digital:', r['is_digital'], 'error:', r['error'])
"
```

---

### Task 4.2 — BBoxFieldExtractor: Header Fields

**Decision Y**: Spatial label-proximity rules replace regex for header fields in digital PDFs. Labels found by text match → value is adjacent (right or below) bbox.

**File to create:** `backend/app/services/extraction/bbox_field_extractor.py`

```python
"""
BBox spatial field extractor for digital invoice PDFs.
Uses label-proximity rules on LiteParse bboxes.

Algorithm:
  1. Find label bbox matching known label text (e.g. "Invoice No", "GSTIN", "Date")
  2. Value = nearest bbox to the RIGHT of label on same row (ΔY < ROW_TOLERANCE)
     OR nearest bbox BELOW label within BELOW_MAX_Y distance if right is empty
  3. Row detection: bboxes with |y_a - y_b| < ROW_TOLERANCE are on the same row.
  4. Table detection: bboxes where x-positions form consistent column bands = table region.
     Header fields extracted OUTSIDE table region only; line items extracted separately.

Tuning constants — adjust if fixtures regress:
  ROW_TOLERANCE = 5    # pt — same row if ΔY < 5
  BELOW_MAX_Y   = 25   # pt — value "below" label if ΔY < 25
  RIGHT_MAX_X   = 300  # pt — value is "right of label" if ΔX < 300
"""
from __future__ import annotations

import re
from typing import Any

# ── Spatial tolerances (pt) ──────────────────────────────────────────────────
ROW_TOLERANCE = 5
BELOW_MAX_Y   = 25
RIGHT_MAX_X   = 300

# ── Label → field_name mapping (canonical, document-type-agnostic) ───────────
# Multiple label variants per field — first match wins.
LABEL_MAP: dict[str, list[str]] = {
    # Buyer / Customer
    "customer_name":      ["bill to", "buyer", "sold to", "customer name", "billed to"],
    "customer_gstin":     ["buyer gstin", "bill to gstin", "gstin of recipient"],
    # Vendor
    "vendor_name":        ["sold by", "from", "vendor", "seller", "supplier"],
    "vendor_gstin":       ["gstin", "supplier gstin", "seller gstin", "vendor gstin"],
    # Order references
    "po_reference":       ["po no", "p.o. no", "purchase order no", "po number", "po #"],
    "so_no":              ["so no", "s.o. no", "sales order no", "so number"],
    "customer_po_no":     ["your po", "customer po", "customer order no", "order no"],
    "vendor_invoice_no":  ["invoice no", "invoice number", "bill no", "tax invoice no"],
    "dc_number":          ["dc no", "challan no", "delivery challan no", "dc number"],
    # Dates
    "invoice_date":       ["invoice date", "bill date", "date of invoice", "date"],
    "dc_date":            ["challan date", "dc date", "delivery date"],
    "po_date":            ["po date", "order date", "purchase order date"],
    # Financial header (line totals handled by table extractor)
    "taxable_amount":     ["taxable amount", "taxable value", "subtotal", "sub total", "net amount before tax"],
    "igst_amount":        ["igst", "igst amount", "integrated tax"],
    "cgst_amount":        ["cgst", "cgst amount", "central tax"],
    "sgst_amount":        ["sgst", "sgst amount", "state tax", "utgst"],
    "total_amount":       ["total amount", "grand total", "invoice total", "net amount", "total payable"],
    "gst_rate":           ["gst %", "gst rate", "tax rate", "rate %"],
    # Vendor invoice specific
    "irn_number":         ["irn", "irn no", "invoice reference number"],
    "hsn_sac":            ["hsn", "hsn/sac", "hsn sac", "sac code", "hsn code"],
    # Shipping
    "ship_to":            ["ship to", "consignee", "delivery address"],
    "place_of_supply":    ["place of supply", "supply state"],
}


def _normalize(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation for label matching."""
    return re.sub(r"[:\-–•|]+$", "", text.lower().strip()).strip()


def _same_row(bbox_a: dict, bbox_b: dict) -> bool:
    return abs(bbox_a["y"] - bbox_b["y"]) < ROW_TOLERANCE


def _right_of(label: dict, candidate: dict) -> bool:
    return (
        candidate["x"] > label["x"] + label["w"] - 5
        and candidate["x"] - (label["x"] + label["w"]) < RIGHT_MAX_X
    )


def _below(label: dict, candidate: dict) -> bool:
    return (
        candidate["y"] > label["y"] + label["h"] - 2
        and candidate["y"] - (label["y"] + label["h"]) < BELOW_MAX_Y
        and abs(candidate["x"] - label["x"]) < 80  # roughly same x-column
    )


def _find_value(label_bbox: dict, all_bboxes: list[dict]) -> str:
    """Find value bbox for a given label bbox. Right-of wins over below."""
    same_row_right = [
        b for b in all_bboxes
        if _same_row(label_bbox, b) and _right_of(label_bbox, b) and b["text"].strip()
    ]
    if same_row_right:
        # Nearest right
        nearest = min(same_row_right, key=lambda b: b["x"])
        return nearest["text"].strip()

    below_bboxes = [
        b for b in all_bboxes
        if _below(label_bbox, b) and b["text"].strip()
    ]
    if below_bboxes:
        nearest = min(below_bboxes, key=lambda b: b["y"])
        return nearest["text"].strip()

    return ""


def extract_header_fields(bboxes: list[dict]) -> dict[str, Any]:
    """
    Extract header fields from LiteParse bboxes using label-proximity rules.

    Args:
        bboxes: list of {page, text, x, y, w, h} from liteparse_extractor

    Returns:
        dict of field_name → value (same key names as existing regex parser)
        Only includes fields where a non-empty value was found.
    """
    result: dict[str, Any] = {}

    # Build normalized label → bbox lookup (first occurrence wins per label variant)
    label_bbox_map: dict[str, dict] = {}
    for bbox in bboxes:
        norm = _normalize(bbox["text"])
        if norm and norm not in label_bbox_map:
            label_bbox_map[norm] = bbox

    # Resolve each field
    for field_name, label_variants in LABEL_MAP.items():
        for variant in label_variants:
            label_norm = variant.lower().strip()
            # Exact match first
            if label_norm in label_bbox_map:
                value = _find_value(label_bbox_map[label_norm], bboxes)
                if value:
                    result[field_name] = value
                    break
            # Prefix match (label text starts with variant)
            for norm_text, bbox in label_bbox_map.items():
                if norm_text.startswith(label_norm) or label_norm in norm_text:
                    value = _find_value(bbox, bboxes)
                    if value:
                        result[field_name] = value
                        break
            if field_name in result:
                break

    return result
```

**Test gate:**
```bash
cd backend
python -m pytest tests/unit/test_bbox_field_extractor.py -v
```

Create `tests/unit/test_bbox_field_extractor.py`:
```python
"""Unit tests for BBoxFieldExtractor — no PDF, pure bbox list."""
from app.services.extraction.bbox_field_extractor import extract_header_fields


def _bbox(text, x, y, w=80, h=10):
    return {"page": 1, "text": text, "x": x, "y": y, "w": w, "h": h}


def test_right_of_label():
    bboxes = [_bbox("Invoice No", 10, 100), _bbox("INV-001", 100, 100)]
    result = extract_header_fields(bboxes)
    assert result.get("vendor_invoice_no") == "INV-001"


def test_below_label():
    bboxes = [_bbox("Invoice No", 10, 100), _bbox("INV-001", 12, 115)]
    result = extract_header_fields(bboxes)
    assert result.get("vendor_invoice_no") == "INV-001"


def test_gstin_extraction():
    bboxes = [_bbox("GSTIN", 10, 50), _bbox("33AAGCS1406H1ZR", 100, 50)]
    result = extract_header_fields(bboxes)
    assert result.get("vendor_gstin") == "33AAGCS1406H1ZR"


def test_no_value_returns_empty():
    bboxes = [_bbox("Invoice No", 10, 100)]
    result = extract_header_fields(bboxes)
    assert "vendor_invoice_no" not in result
```

---

### Task 4.3 — Table Row Extractor: line_items

**Decision Y + J**: Y-band grouping extracts line items from digital PDFs. Stored as `extracted_data["line_items"]` — no DB schema change.

**Research finding**: PP-StructureV3 PP-TableMagic (running inside PaddleOCR HTTP server, Option E) is the better approach for SCANNED docs — it returns HTML table with row/col indices from rendered page images. For digital PDFs, LiteParse Y-band grouping is faster and more accurate (embedded text, no rendering artifacts). This task implements both paths.

**File to create:** `backend/app/services/extraction/table_row_extractor.py`

```python
"""
Table row extractor for line items in invoice PDFs.

Two paths:
  PATH A (digital PDF — primary): LiteParse Y-band grouping.
    Bboxes within ROW_TOLERANCE pt → same row.
    Column bands detected from header row (Description, Qty, Rate, Amount).
    Output: list of line item dicts.

  PATH B (scanned / optional): PP-StructureV3 PP-TableMagic via PaddleOCR HTTP server.
    Called only if PADDLEOCR_SERVER_URL is set and PATH A finds zero rows.
    Returns HTML table structure — parse with html.parser.
    Better accuracy on rendered/scanned images. Lower priority for digital PDFs.

Output schema (mirrors LlamaExtract line_items for consistency):
    {
        "description": str,
        "product_code": str | None,
        "hsn_sac": str | None,
        "qty": str | None,
        "uom": str | None,
        "unit_rate": str | None,
        "taxable_value": str | None,
        "tax_amount": str | None,
        "amount": str | None,
        "serial_numbers": list[str],
        "_raw": str,   # raw row text for diagnostics
    }

Storage: extracted_data["line_items"] = [list of above dicts]  (Option J — no migration)
"""
from __future__ import annotations

import logging
import os
import re
from html.parser import HTMLParser
from typing import Any

logger = logging.getLogger(__name__)

ROW_TOLERANCE = 5   # pt — bboxes within this ΔY are on same row
TABLE_HEADER_LABELS = {
    "description": ["description", "particulars", "item", "product name", "item description"],
    "product_code": ["product code", "part no", "part number", "item code", "model", "sku"],
    "hsn_sac":      ["hsn", "hsn/sac", "hsn sac", "sac", "hsn code"],
    "qty":          ["qty", "quantity", "nos", "pcs", "units"],
    "uom":          ["uom", "unit", "u.o.m.", "u/m"],
    "unit_rate":    ["rate", "unit rate", "unit price", "price", "mrp"],
    "taxable_value":["taxable", "taxable value", "taxable amount", "net value"],
    "tax_amount":   ["tax amount", "gst amount", "igst", "cgst", "sgst"],
    "amount":       ["amount", "total", "net amount", "value"],
}


def _group_rows(bboxes: list[dict]) -> list[list[dict]]:
    """Group bboxes into rows by Y proximity."""
    if not bboxes:
        return []
    sorted_bboxes = sorted(bboxes, key=lambda b: (b["y"], b["x"]))
    rows: list[list[dict]] = []
    current_row: list[dict] = [sorted_bboxes[0]]
    ref_y = sorted_bboxes[0]["y"]
    for bbox in sorted_bboxes[1:]:
        if abs(bbox["y"] - ref_y) < ROW_TOLERANCE:
            current_row.append(bbox)
        else:
            rows.append(sorted(current_row, key=lambda b: b["x"]))
            current_row = [bbox]
            ref_y = bbox["y"]
    rows.append(sorted(current_row, key=lambda b: b["x"]))
    return rows


def _detect_header_row(rows: list[list[dict]]) -> tuple[int, dict[str, float]]:
    """
    Find the table header row and build column_name → x_center mapping.
    Returns (row_index, col_map). col_map empty if no header found.
    """
    for i, row in enumerate(rows):
        row_text = " ".join(b["text"].lower() for b in row)
        # Header row must contain at least 2 of: description/qty/rate/amount
        hits = sum(1 for kw in ["description", "qty", "quantity", "rate", "amount", "hsn"]
                   if kw in row_text)
        if hits >= 2:
            col_map: dict[str, float] = {}
            for bbox in row:
                norm = bbox["text"].lower().strip()
                for field, variants in TABLE_HEADER_LABELS.items():
                    if any(v in norm or norm in v for v in variants):
                        col_map[field] = bbox["x"] + bbox["w"] / 2  # x_center
                        break
            return i, col_map
    return -1, {}


def _assign_columns(row: list[dict], col_map: dict[str, float]) -> dict[str, str]:
    """Assign each bbox in a data row to the nearest column."""
    result: dict[str, str] = {}
    if not col_map:
        # No header detected — return raw left-to-right text
        result["description"] = " | ".join(b["text"] for b in row)
        return result
    for bbox in row:
        x_center = bbox["x"] + bbox["w"] / 2
        nearest_col = min(col_map.items(), key=lambda kv: abs(kv[1] - x_center))
        col_name, _ = nearest_col
        # Append if multiple bboxes map to same column (e.g. long description)
        existing = result.get(col_name, "")
        result[col_name] = (existing + " " + bbox["text"]).strip() if existing else bbox["text"]
    return result


def _is_data_row(row: list[dict]) -> bool:
    """Filter out header rows, totals rows, blank rows."""
    if len(row) < 2:
        return False
    row_text = " ".join(b["text"].lower() for b in row)
    skip_patterns = [
        "total", "grand total", "sub total", "subtotal",
        "amount in words", "bank details", "terms", "declaration",
        "description", "particulars", "qty", "quantity",  # header row labels
    ]
    if any(p in row_text for p in skip_patterns):
        return False
    # Must have at least one numeric token (amount or quantity)
    if not re.search(r"\d[\d,]*\.?\d*", row_text):
        return False
    return True


def extract_line_items_from_bboxes(bboxes: list[dict]) -> list[dict[str, Any]]:
    """
    PATH A: Extract line items from LiteParse bboxes (digital PDF).
    Returns list of line item dicts. Empty list if no table found.
    """
    rows = _group_rows(bboxes)
    if not rows:
        return []

    header_idx, col_map = _detect_header_row(rows)
    data_start = header_idx + 1 if header_idx >= 0 else 0

    items: list[dict[str, Any]] = []
    for row in rows[data_start:]:
        if not _is_data_row(row):
            continue
        assigned = _assign_columns(row, col_map)
        item: dict[str, Any] = {
            "description":   assigned.get("description", ""),
            "product_code":  assigned.get("product_code"),
            "hsn_sac":       assigned.get("hsn_sac"),
            "qty":           assigned.get("qty"),
            "uom":           assigned.get("uom"),
            "unit_rate":     assigned.get("unit_rate"),
            "taxable_value": assigned.get("taxable_value"),
            "tax_amount":    assigned.get("tax_amount"),
            "amount":        assigned.get("amount"),
            "serial_numbers": [],
            "_raw": " | ".join(b["text"] for b in row),
        }
        # Only include rows with at least a description or amount
        if item["description"] or item["amount"]:
            items.append(item)

    return items


# ── PATH B: PP-StructureV3 table via PaddleOCR HTTP server (scanned docs) ────

class _TableHTMLParser(HTMLParser):
    """Parse PP-TableMagic HTML output into rows of cell strings."""
    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self._current_row: list[str] = []
        self._current_cell: str = ""
        self._in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._current_row = []
        elif tag in ("td", "th"):
            self._current_cell = ""
            self._in_cell = True

    def handle_endtag(self, tag):
        if tag == "tr" and self._current_row:
            self.rows.append(self._current_row)
        elif tag in ("td", "th"):
            self._current_row.append(self._current_cell.strip())
            self._in_cell = False

    def handle_data(self, data):
        if self._in_cell:
            self._current_cell += data


def _parse_table_html(html: str) -> list[list[str]]:
    """Parse PP-TableMagic HTML → list of rows (each row = list of cell strings)."""
    parser = _TableHTMLParser()
    parser.feed(html)
    return parser.rows


def extract_line_items_from_table_html(html: str) -> list[dict[str, Any]]:
    """
    PATH B: Convert PP-TableMagic HTML table to line_items list.
    Used when PaddleOCR HTTP server returns PP-StructureV3 table output.
    """
    rows = _parse_table_html(html)
    if not rows:
        return []

    # First row = header
    headers = [h.lower().strip() for h in rows[0]]
    col_index: dict[str, int] = {}
    for field, variants in TABLE_HEADER_LABELS.items():
        for i, h in enumerate(headers):
            if any(v in h or h in v for v in variants):
                col_index[field] = i
                break

    items: list[dict[str, Any]] = []
    for row in rows[1:]:
        if not row or all(c.strip() == "" for c in row):
            continue
        def cell(field: str) -> str | None:
            i = col_index.get(field)
            return row[i].strip() if i is not None and i < len(row) else None

        item: dict[str, Any] = {
            "description":   cell("description") or "",
            "product_code":  cell("product_code"),
            "hsn_sac":       cell("hsn_sac"),
            "qty":           cell("qty"),
            "uom":           cell("uom"),
            "unit_rate":     cell("unit_rate"),
            "taxable_value": cell("taxable_value"),
            "tax_amount":    cell("tax_amount"),
            "amount":        cell("amount"),
            "serial_numbers": [],
            "_raw": " | ".join(row),
        }
        if item["description"] or item["amount"]:
            items.append(item)

    return items
```

**Test gate:**
```bash
cd backend
python -m pytest tests/unit/test_table_row_extractor.py -v
```

Create `tests/unit/test_table_row_extractor.py`:
```python
from app.services.extraction.table_row_extractor import (
    extract_line_items_from_bboxes,
    extract_line_items_from_table_html,
    _group_rows,
)


def _bbox(text, x, y, w=80, h=10):
    return {"page": 1, "text": text, "x": x, "y": y, "w": w, "h": h}


def test_row_grouping():
    bboxes = [
        _bbox("A", 10, 100), _bbox("B", 100, 101),  # same row (ΔY=1)
        _bbox("C", 10, 120), _bbox("D", 100, 120),  # same row
    ]
    rows = _group_rows(bboxes)
    assert len(rows) == 2


def test_extract_line_items_basic():
    bboxes = [
        # header row
        _bbox("Description", 10, 50), _bbox("Qty", 200, 50),
        _bbox("Rate", 280, 50), _bbox("Amount", 360, 50),
        # data row 1
        _bbox("HP Laptop 15s", 10, 70), _bbox("2", 200, 70),
        _bbox("45000", 280, 70), _bbox("90000", 360, 70),
        # totals row — should be skipped
        _bbox("Total", 10, 90), _bbox("90000", 360, 90),
    ]
    items = extract_line_items_from_bboxes(bboxes)
    assert len(items) == 1
    assert items[0]["description"] == "HP Laptop 15s"
    assert items[0]["qty"] == "2"
    assert items[0]["amount"] == "90000"


def test_table_html_parsing():
    html = """<table>
    <tr><th>Description</th><th>Qty</th><th>Amount</th></tr>
    <tr><td>Fortigate FG-120G</td><td>1</td><td>503200</td></tr>
    </table>"""
    items = extract_line_items_from_table_html(html)
    assert len(items) == 1
    assert items[0]["description"] == "Fortigate FG-120G"
    assert items[0]["qty"] == "1"
    assert items[0]["amount"] == "503200"
```

---

### Task 4.4 — Unified Schema + Adapter (Internal S → Flat T)

**Decision T**: Build unified schema S internally as dataclasses. Adapter flattens to existing flat dict T. Verification engine and frontend see no change. Build 2 exposes S directly.

**File to create:** `backend/app/services/extraction/unified_schema.py`

```python
"""
Unified invoice schema S — internal representation.
NOT exposed to frontend or verification engine in Sprint 4.

Adapter: to_flat_dict(schema) → flat dict T (existing field names).
Sprint 4 only uses the adapter output. Build 2 can expose S directly.

Schema inspired by LlamaExtract reference outputs (Panimalar, Trade, AMC fixtures).
Field names match our existing normalized field names (not LlamaExtract's variable ones).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PartyInfo:
    name: str = ""
    gstin: str = ""
    address: str = ""
    state_code: str = ""
    pan: str = ""


@dataclass
class OrderDetails:
    po_number: str = ""
    so_number: str = ""
    invoice_number: str = ""
    invoice_date: str = ""
    po_date: str = ""
    irn: str = ""
    place_of_supply: str = ""


@dataclass
class LineItem:
    description: str = ""
    product_code: str | None = None
    hsn_sac: str | None = None
    qty: str | None = None
    uom: str | None = None
    unit_rate: str | None = None
    taxable_value: str | None = None
    tax_amount: str | None = None
    amount: str | None = None
    serial_numbers: list[str] = field(default_factory=list)


@dataclass
class TaxSummary:
    gst_rate: str = ""
    igst_amount: str = ""
    cgst_amount: str = ""
    sgst_amount: str = ""
    tax_type: str = ""  # "IGST" | "CGST+SGST"


@dataclass
class FinancialSummary:
    taxable_amount: str = ""
    total_tax: str = ""
    total_amount: str = ""
    amount_in_words: str = ""


@dataclass
class InvoiceSchema:
    """Unified schema S — applies to all 5 document types."""
    doc_type: str = ""
    buyer: PartyInfo = field(default_factory=PartyInfo)
    vendor: PartyInfo = field(default_factory=PartyInfo)
    order: OrderDetails = field(default_factory=OrderDetails)
    line_items: list[LineItem] = field(default_factory=list)
    tax: TaxSummary = field(default_factory=TaxSummary)
    financial: FinancialSummary = field(default_factory=FinancialSummary)
    ship_to: str = ""
    bank_details: str = ""
    _source: str = "regex"  # "regex" | "bbox" | "bbox+regex"


def to_flat_dict(schema: InvoiceSchema) -> dict[str, Any]:
    """
    Adapter: unified schema S → flat dict T (existing field names).
    Preserves all existing field names used by verification engine and frontend.
    line_items stored as nested key (Option J — no migration).
    """
    flat: dict[str, Any] = {}

    # Buyer / Customer
    if schema.buyer.name:      flat["customer_name"]    = schema.buyer.name
    if schema.buyer.gstin:     flat["customer_gstin"]   = schema.buyer.gstin
    if schema.buyer.address:   flat["customer_address"] = schema.buyer.address

    # Vendor / Seller
    if schema.vendor.name:     flat["vendor_name"]      = schema.vendor.name
    if schema.vendor.gstin:    flat["vendor_gstin"]     = schema.vendor.gstin
    if schema.vendor.address:  flat["vendor_address"]   = schema.vendor.address

    # Order details
    if schema.order.po_number:       flat["po_reference"]      = schema.order.po_number
    if schema.order.so_number:       flat["so_no"]             = schema.order.so_number
    if schema.order.invoice_number:  flat["vendor_invoice_no"] = schema.order.invoice_number
    if schema.order.invoice_date:    flat["invoice_date"]      = schema.order.invoice_date
    if schema.order.po_date:         flat["po_date"]           = schema.order.po_date
    if schema.order.irn:             flat["irn_number"]        = schema.order.irn
    if schema.order.place_of_supply: flat["place_of_supply"]   = schema.order.place_of_supply

    # Tax
    if schema.tax.gst_rate:     flat["gst_rate"]      = schema.tax.gst_rate
    if schema.tax.igst_amount:  flat["igst_amount"]   = schema.tax.igst_amount
    if schema.tax.cgst_amount:  flat["cgst_amount"]   = schema.tax.cgst_amount
    if schema.tax.sgst_amount:  flat["sgst_amount"]   = schema.tax.sgst_amount

    # Financial
    if schema.financial.taxable_amount: flat["taxable_amount"]   = schema.financial.taxable_amount
    if schema.financial.total_tax:      flat["total_tax"]        = schema.financial.total_tax
    if schema.financial.total_amount:   flat["total_amount"]     = schema.financial.total_amount

    # Other
    if schema.ship_to:       flat["ship_to"]       = schema.ship_to
    if schema.bank_details:  flat["bank_details"]  = schema.bank_details

    # line_items — nested key in flat dict (Option J, no migration)
    if schema.line_items:
        flat["line_items"] = [
            {
                "description":   li.description,
                "product_code":  li.product_code,
                "hsn_sac":       li.hsn_sac,
                "qty":           li.qty,
                "uom":           li.uom,
                "unit_rate":     li.unit_rate,
                "taxable_value": li.taxable_value,
                "tax_amount":    li.tax_amount,
                "amount":        li.amount,
                "serial_numbers": li.serial_numbers,
            }
            for li in schema.line_items
        ]

    # Diagnostics
    flat["_extraction_source"] = schema._source

    return flat
```

**Test gate:**
```bash
cd backend
python -m pytest tests/unit/test_unified_schema.py -v
```

Create `tests/unit/test_unified_schema.py`:
```python
from app.services.extraction.unified_schema import (
    InvoiceSchema, PartyInfo, OrderDetails, LineItem, TaxSummary, FinancialSummary,
    to_flat_dict
)


def test_adapter_basic_fields():
    schema = InvoiceSchema(
        buyer=PartyInfo(name="Hindalco Industries", gstin="27AACCH3536G1ZM"),
        vendor=PartyInfo(name="Skylark Information Technologies", gstin="33AAGCS1406H1ZR"),
        order=OrderDetails(invoice_number="INV-001", po_number="PO-123"),
        financial=FinancialSummary(taxable_amount="100000", total_amount="118000"),
    )
    flat = to_flat_dict(schema)
    assert flat["customer_name"] == "Hindalco Industries"
    assert flat["vendor_invoice_no"] == "INV-001"
    assert flat["po_reference"] == "PO-123"
    assert flat["taxable_amount"] == "100000"


def test_adapter_line_items():
    schema = InvoiceSchema(
        line_items=[
            LineItem(description="EC-10106 SDWAN", qty="2", amount="1062000"),
        ]
    )
    flat = to_flat_dict(schema)
    assert "line_items" in flat
    assert flat["line_items"][0]["description"] == "EC-10106 SDWAN"
    assert flat["line_items"][0]["qty"] == "2"


def test_adapter_no_empty_keys():
    schema = InvoiceSchema()
    flat = to_flat_dict(schema)
    # No empty string keys (only _extraction_source)
    for k, v in flat.items():
        if k.startswith("_"):
            continue
        assert v, f"Key {k!r} should not be empty in output"
```

---

### Task 4.5 — Layer+Merge Integration

**Decision G**: Both regex path AND bbox path run. Results merged: `{**regex_result, **bbox_result}`. Bbox wins on overlap. Implemented in the existing extraction service — this is the ONLY existing file modified in Sprint 4.

**File to edit:** `backend/app/services/extraction/ocr_extraction_service.py`

Find the section where `parse_structured_text` is called and regex result is built. After that call, add the bbox layer:

```python
# ── Sprint 4: LiteParse bbox layer (digital PDFs only) ───────────────────────
# Option G: layer+merge. Regex result already in `extracted`. Bbox result merged on top.
# Bbox wins on field overlap. line_items added as nested key (Option J).
from app.services.extraction.liteparse_extractor import extract_bboxes
from app.services.extraction.bbox_field_extractor import extract_header_fields
from app.services.extraction.table_row_extractor import extract_line_items_from_bboxes

def _apply_bbox_layer(pdf_path: str, regex_result: dict) -> dict:
    """
    Run LiteParse bbox extractor on digital PDF.
    Merge with regex result: {**regex_result, **bbox_result}.
    Returns merged dict. Returns regex_result unchanged if LiteParse fails or doc is scanned.
    """
    lp = extract_bboxes(pdf_path)
    if not lp["is_digital"] or lp["error"] or not lp["bboxes"]:
        return regex_result  # scanned or failed → regex only

    bbox_fields = extract_header_fields(lp["bboxes"])
    line_items = extract_line_items_from_bboxes(lp["bboxes"])

    if line_items:
        bbox_fields["line_items"] = line_items

    if not bbox_fields:
        return regex_result  # bbox found nothing → regex only

    merged = {**regex_result, **bbox_fields}
    merged["_extraction_source"] = "bbox+regex"
    return merged
```

Integration point — call after existing `parse_structured_text` returns:
```python
# existing code:
parser_result = parse_structured_text(
    document_type=document_type,
    raw_text=raw_text,
    extraction_route=extraction_route,
    filename=filename,
)
extracted = parser_result.get("fields") or parser_result.get("extracted_data") or {}

# NEW: apply bbox layer (Sprint 4, Option G)
if pdf_path and os.path.exists(pdf_path):
    extracted = _apply_bbox_layer(pdf_path, extracted)
```

**Important**: `pdf_path` must be available at this call site. If the extraction service currently only has `pdf_bytes`, write bytes to a temp file first (same pattern as `benchmark/server.py`).

**Test gate:**
```bash
cd backend
python -m pytest tests/unit/test_bbox_field_extractor.py tests/unit/test_table_row_extractor.py tests/unit/test_unified_schema.py -v
python -m pytest tests -q
# Record exact count — must not regress from Sprint 3 count
```

---

### Task 4.6 — Real-Document Validation (Sprint 4 Exit)

Sprint 4 changes extraction and frontend-visible fields. All 3 real-document fixtures required.

```powershell
.\scripts\new-validation-run.ps1 -RunName sprint4-panimalar
.\scripts\new-validation-run.ps1 -RunName sprint4-trade
.\scripts\new-validation-run.ps1 -RunName sprint4-amc
```

For each run, verify:

| Fixture | Minimum pass bar |
|---|---|
| Panimalar | ≥24/24 fields (bbox layer should ADD fields, never remove). Zero failed doc statuses. XLSX passed. |
| Trade | Zero failed doc statuses. XLSX passed. `line_items` present in VENDOR_INVOICE and COMPANY_INVOICE extracted_data. |
| AMC | ≥27/28 fields. Zero failed doc statuses (except existing missing DC). XLSX passed. `line_items` present. |

**Regression check**: compare `_extraction_source` values in extracted_data. Any doc showing `regex` (not `bbox+regex`) means LiteParse failed silently — investigate before declaring sprint done.

---

### Sprint 4 Exit Gate

All 5 steps from CLAUDE.md section 4:

**Step 1:** `python -m pytest tests/unit/test_bbox_field_extractor.py tests/unit/test_table_row_extractor.py tests/unit/test_unified_schema.py -v`

**Step 2:** No schema change in Sprint 4 — skip migration tests (confirm with `alembic current` — head should be same as Sprint 3).

**Step 3:** `python -m pytest tests -q` — exact count required. Must equal Sprint 3 count + new Sprint 4 tests.

**Step 4:** `.\scripts\new-validation-run.ps1 -RunName sprint4-smoke` — verify all 3 fixture baselines met.

**Step 5:** Confirm no changes to: Sprint 1 migrations, Celery/Redis queue, Sprint 3 verification engine, frontend. Only `ocr_extraction_service.py` + 4 new files added.

Sprint 4 complete only when all 5 steps pass and all 3 fixture baselines met.

---

## Build 2 Candidates (Post Sprint 4, Future)

These were scoped out of Sprint 4 for safety. Implement only after Sprint 4 baselines stable.

| Item | What it unlocks |
|---|---|
| Expose unified schema S directly to frontend | Frontend sees nested buyer_info{}, vendor_info{}, line_items[] — richer UI |
| line_items → relational table (Option K) | SQL queries on line items, cross-order analytics |
| LayoutLMv3 fine-tuned on our fixtures | ML extraction for complex/scanned layouts without rules |
| PP-TableMagic PATH B for digital complex tables | Better multi-column table accuracy when Y-band grouping fails |
| Multi-page concatenation for long descriptions | Descriptions that span rows in the PDF |
| TESSDATA_PREFIX offline Tesseract | Air-gapped deployment — pre-download `eng.traineddata`, set `TESSDATA_PREFIX` |

---

## Decisions Log (Grill-With-Docs Session, June 2026)

| # | Topic | Decision |
|---|---|---|
| Q1 | Auth | Skip — internal tool, add proper auth at multi-user phase |
| Q2 | Bundle list O(N) | `last_verified_at` column + write-back status after verification (Task 1.4) |
| Q3 | PaddleOCR-VL | HuggingFace `PaddlePaddle/PaddleOCR-VL-1.6` via transformers, NOT Ollama, NOT Qwen2.5-VL (Task 2.3) |
| Q4 | GSTIN | Extract from all doc types, SKIP if not present, compare whatever extracted (Task 3.2) |
| Q5 | Multi-DC | Sum all DCs for amount match, each DC checked independently for SO/PO reference (Task 3.3) |
| Q6 | Tenant isolation | `tenant_id VARCHAR(64) DEFAULT 'default'` on all tables + stub middleware (Task 1.5) |
| Q7 | Vendor name match | Normalize legal suffixes before SequenceMatcher (Task 3.4) |
| Q8 | Dev router | Gate mount on `APP_ENV == development`, drop `enable_dev_tools` bypass (Task 1.6) |
| Q9 | `last_error` | `VARCHAR(2000)` (Task 1.6) |

---

## Decisions Log (LiteParse Grill Session #2, June 2026)

| Decision | Choice | Full Rationale |
|---|---|---|
| A: Role of LiteParse | Augments OCR providers | OCR paths (PP-OCRv5, VL-1.6) unchanged. LiteParse adds spatial layer for digital docs only. |
| Y: Extraction method | BBox spatial rules | Benchmark proved: LiteParse text → existing regex = FEWER fields (line-item amounts bleed into header patterns). Spatial is the only correct path. |
| P: Phasing | Sprint 4 separate | 5 new files, 1 existing file edit, 3 test modules — too large for Sprint 3 scope. |
| T: Schema strategy | Internal S + adapter → T | LlamaExtract cloud outputs use DIFFERENT top-level field names per batch (buyer_info vs seller vs seller_details). Our normalized keys are already more consistent. Adapter keeps verification engine unchanged. |
| E: PaddleOCR HTTP | Optional external | No subprocess in backend. Server runs as separate process. Fallback to existing `paddle_provider.py` if not running. |
| G: Layer+merge | Both paths run | `{**regex_result, **bbox_result}`. Regression impossible — worst case bbox finds nothing and regex result is returned unchanged. |
| J: line_items storage | Nested key in extracted_data | Zero migration. `extracted_data["line_items"] = [...]`. Build 2 promotes to relational table. |

---

## Dependency Map

```
Sprint 1  ──►  Sprint 2  ──►  Sprint 3
   │              │               │
   ▼              ▼               ▼
PostgreSQL    PP-OCRv5        ToleranceConfig
Alembic       PP-StructureV3  GSTIN validator (all docs)
Celery        line_items []   LineItemMatcher (multi-DC aware)
Redis         PaddleOCR-VL   VendorMaster
tenant_id     HuggingFace    Vendor name normalize
last_verified_at              GST math check
dev router gate               multi-DC sum fix
last_error 2000
```

---

## File Change Summary

| Sprint | New files | Modified files |
|--------|-----------|----------------|
| 1 | `alembic/`, `app/worker.py`, `app/tasks/`, `app/middleware/tenant.py` | `app/database.py`, `app/main.py`, `app/api/routes/dev.py`, `app/models/document.py`, `app/models/order_bundle.py`, `app/models/*.py` (tenant_id), extraction route callers |
| 2 | `app/services/table_extraction_service.py`, `app/services/paddleocr_vl_service.py` | `app/services/ocr_extraction_service.py` |
| 3 | `app/services/tolerance_config.py`, `app/services/gstin_validator.py`, `app/services/line_item_matcher.py`, `app/services/vendor_master_service.py`, `app/models/vendor_master.py` | `app/services/order_bundle_verifier.py`, `app/models/__init__.py` |

Total: 14 new files, 10+ modified files.
No frontend changes. No XLSX export changes. No route structure changes (only queue dispatch method in Sprint 1).
