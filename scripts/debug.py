"""
DPP Debug Script — v1.0
========================
Run from the project root:

    python debug.py                   # code checks only (no services needed)
    python debug.py --live            # + connectivity checks (DB, Redis, storage)
    python debug.py --live --env .env # use a specific .env file

Checks covered
--------------
CODE (always run)
  1.  pipeline.py — ExtractionResult import
  2.  Upload validation — content_type OR-logic vs magic-bytes fallback
  3.  Chain completeness — hardcoded /6 in two files
  4.  Config default — debug=True leaking to production
  5.  .env.example — DEBUG=true leaking to production copies
  6.  Docker compose — nginx missing healthcheck condition on backend
  7.  Admin health check — legacy model check vs new provider config
  8.  Celery task — multiple asyncio.run() calls in extract_document
  9.  Port mismatch — stop_all.ps1 vs start.ps1 (Windows scripts)
  10. CORS default — localhost-only origins in Settings

LIVE (--live flag required)
  11. PostgreSQL — connection + migrations applied
  12. Redis — ping + key read/write
  13. Storage path — exists, readable, writable
  14. OCR / provider endpoint — reachable (Ollama tags or HTTP 200)
  15. Environment variable completeness — required keys present in .env
"""

import sys
import os
import re
import argparse
import textwrap
from pathlib import Path

# ── ANSI colours ─────────────────────────────────────────────────────────────

GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def _ok(msg):   print(f"  {GREEN}✔{RESET}  {msg}")
def _fail(msg): print(f"  {RED}✘{RESET}  {msg}")
def _warn(msg): print(f"  {YELLOW}⚠{RESET}  {msg}")
def _info(msg): print(f"  {CYAN}ℹ{RESET}  {msg}")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def _section(title: str):
    print(f"\n{BOLD}{CYAN}{'─' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * 60}{RESET}")


# ── Project root detection ────────────────────────────────────────────────────

def find_project_root() -> Path:
    """Walk up from CWD looking for backend/ and frontend/ together."""
    here = Path.cwd()
    for candidate in [here, *here.parents]:
        if (candidate / "backend").is_dir() and (candidate / "frontend").is_dir():
            return candidate
    # Fallback: just use CWD
    return here


# ═══════════════════════════════════════════════════════════════════════════════
# CODE CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

results: dict[str, bool | None] = {}   # check_id → passed/failed/skipped


def check(check_id: str, passed: bool, ok_msg: str, fail_msg: str, hint: str = ""):
    results[check_id] = passed
    if passed:
        _ok(ok_msg)
    else:
        _fail(fail_msg)
        if hint:
            for line in textwrap.wrap(hint, width=72):
                print(f"       {YELLOW}{line}{RESET}")


# ── Check 1: ExtractionResult import in pipeline.py ──────────────────────────

def check_extraction_result_import(root: Path):
    pipeline = root / "backend/app/services/extraction/pipeline.py"
    text = _read(pipeline)

    used = "ExtractionResult" in text
    # Only consider actual import lines — avoid greedy cross-line false positives
    import_lines = [
        line.strip() for line in text.splitlines()
        if (line.strip().startswith("from ") or line.strip().startswith("import "))
        and "ExtractionResult" in line
    ]
    imported = len(import_lines) > 0

    if not text:
        _warn("pipeline.py not found — skipping check")
        results["c1"] = None
        return

    check(
        "c1",
        not used or imported,
        "pipeline.py — ExtractionResult is imported",
        "pipeline.py:110 — ExtractionResult used but NOT imported → NameError at runtime",
        hint=(
            "Fix: add `ExtractionResult` to the import from "
            "app.services.extraction.providers.base"
        ),
    )


# ── Check 2: Upload validation OR-logic ──────────────────────────────────────

def check_upload_validation(root: Path):
    po_file = root / "backend/app/api/v1/purchase_orders.py"
    text = _read(po_file)

    # Look for the specific OR pattern that rejects valid PDFs
    bad_pattern = re.search(
        r"ext not in ALLOWED_EXTENSIONS\s+or\s+content_type not in ALLOWED_MIME",
        text,
    )
    good_pattern = re.search(
        r"ext not in ALLOWED_EXTENSIONS\s+and\s+content_type not in ALLOWED_MIME",
        text,
    )

    if not text:
        _warn("purchase_orders.py not found — skipping check")
        results["c2"] = None
        return

    check(
        "c2",
        good_pattern is not None or bad_pattern is None,
        "upload validation — uses AND logic (content-type OR magic-bytes)",
        "purchase_orders.py — OR logic rejects valid PDFs sent with content-type: application/octet-stream",
        hint=(
            "Change `ext not in ALLOWED_EXTENSIONS or content_type not in ...` "
            "to `and`. document_service already checks magic bytes as a fallback."
        ),
    )


# ── Check 3: Hardcoded /6 in chain completeness ───────────────────────────────

def check_hardcoded_chain_divisor(root: Path):
    files_to_check = [
        root / "backend/app/api/v1/extraction.py",
        root / "backend/app/services/extraction/tasks.py",
    ]
    offenders = []
    for f in files_to_check:
        text = _read(f)
        if re.search(r"count\s*/\s*6", text):
            offenders.append(f.name)

    check(
        "c3",
        len(offenders) == 0,
        "chain completeness — divisor is not hardcoded",
        f"hardcoded `/ 6` found in: {', '.join(offenders)} — will silently break if doc types change",
        hint="Replace `/ 6` with `/ len(CHAIN_DOC_TYPES)` and import CHAIN_DOC_TYPES from po_service.",
    )


# ── Check 4: debug=True default in Settings ───────────────────────────────────

def check_debug_default(root: Path):
    config = root / "backend/app/config.py"
    text = _read(config)

    debug_true = re.search(r"debug\s*:\s*bool\s*=\s*True", text)

    check(
        "c4",
        debug_true is None,
        "config.py — debug defaults to False",
        "config.py — debug: bool = True exposes SQL & stack traces if .env is missing DEBUG=false",
        hint="Change `debug: bool = True` to `debug: bool = False` in Settings.",
    )


# ── Check 5: .env.example has DEBUG=true ─────────────────────────────────────

def check_env_example_debug(root: Path):
    env_example = root / ".env.example"
    text = _read(env_example)

    if not text:
        _warn(".env.example not found — skipping check")
        results["c5"] = None
        return

    debug_true = re.search(r"^\s*DEBUG\s*=\s*true\s*$", text, re.IGNORECASE | re.MULTILINE)

    check(
        "c5",
        debug_true is None,
        ".env.example — DEBUG is not set to true",
        ".env.example has DEBUG=true — operators copying this to production will run in debug mode",
        hint="Change DEBUG=true to DEBUG=false in .env.example.",
    )


# ── Check 6: nginx depends_on backend without healthcheck ────────────────────

def check_nginx_healthcheck(root: Path):
    compose = root / "docker-compose.prod.yml"
    text = _read(compose)

    if not text:
        _warn("docker-compose.prod.yml not found — skipping check")
        results["c6"] = None
        return

    # Find nginx service block
    nginx_block_match = re.search(r"nginx:.*?(?=\n\S|\Z)", text, re.DOTALL)
    if not nginx_block_match:
        _warn("nginx service not found in docker-compose.prod.yml")
        results["c6"] = None
        return

    nginx_block = nginx_block_match.group(0)
    has_condition = "service_healthy" in nginx_block or "condition:" in nginx_block

    check(
        "c6",
        has_condition,
        "docker-compose.prod.yml — nginx waits for backend healthcheck",
        "docker-compose.prod.yml — nginx depends_on backend without condition: service_healthy → 502 on cold start",
        hint=(
            "Add `condition: service_healthy` under nginx depends_on: backend, "
            "and add a healthcheck to the backend service."
        ),
    )


# ── Check 7: Admin health check ignores new provider config ──────────────────

def check_admin_health_provider(root: Path):
    admin = root / "backend/app/api/v1/admin.py"
    text = _read(admin)

    if not text:
        _warn("admin.py not found — skipping check")
        results["c7"] = None
        return

    checks_new_provider = bool(re.search(r"layer1_provider|layer2_provider", text))
    checks_legacy_only  = bool(re.search(r"ocr_two_layer_enabled", text))

    check(
        "c7",
        checks_new_provider,
        "admin.py health check — covers new LAYER1/LAYER2_PROVIDER config",
        "admin.py _check_models() only checks legacy ocr_* settings — health is wrong when using new provider abstraction",
        hint=(
            "Branch on settings.layer1_provider in _check_models() "
            "and validate the relevant endpoint/credentials for each provider."
        ),
    )


# ── Check 8: Multiple asyncio.run() calls in Celery task ─────────────────────

def check_asyncio_run_in_celery(root: Path):
    tasks = root / "backend/app/services/extraction/tasks.py"
    text = _read(tasks)

    if not text:
        _warn("tasks.py not found — skipping check")
        results["c8"] = None
        return

    count = len(re.findall(r"asyncio\.run\(", text))

    check(
        "c8",
        count <= 1,
        f"tasks.py — single asyncio.run() or fully sync ({count} found)",
        f"tasks.py — {count} asyncio.run() calls create/destroy {count} event loops per task (slow + breaks gevent)",
        hint=(
            "Wrap the whole task body in one `asyncio.run(_async_impl(...))` "
            "and make the inner function fully async with await."
        ),
    )


# ── Check 9: Port mismatch in PS1 scripts ────────────────────────────────────

def check_port_mismatch(root: Path):
    start_ps1 = root / "start.ps1"
    stop_ps1  = root / "stop_all.ps1"

    if not start_ps1.exists() or not stop_ps1.exists():
        _warn("start.ps1 / stop_all.ps1 not found — skipping port mismatch check")
        results["c9"] = None
        return

    start_text = _read(start_ps1)
    stop_text  = _read(stop_ps1)

    start_ports = set(re.findall(r"\b(80\d\d|517\d)\b", start_text))
    stop_ports  = set(re.findall(r"\b(80\d\d|517\d)\b", stop_text))

    mismatch = start_ports - stop_ports
    check(
        "c9",
        len(mismatch) == 0,
        "start.ps1 / stop_all.ps1 — ports are consistent",
        f"Port mismatch between start.ps1 {start_ports} and stop_all.ps1 {stop_ports} — orphan processes on stop",
        hint="Ensure stop_all.ps1 kills the same ports that start.ps1 launches on (8002 and 5174).",
    )


# ── Check 10: CORS default is localhost-only ─────────────────────────────────

def check_cors_default(root: Path):
    config = root / "backend/app/config.py"
    text = _read(config)

    localhost_default = re.search(
        r'cors_origins\s*:\s*List\[str\]\s*=\s*\["http://localhost', text
    )

    check(
        "c10",
        localhost_default is None,
        "config.py — CORS origins default is not localhost-locked",
        "config.py — cors_origins defaults to localhost:5174; production breaks if CORS_ORIGINS not set in .env",
        hint="Change default to `cors_origins: List[str] = []` so production must explicitly configure it.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# LIVE CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

def load_env(env_path: Path) -> dict:
    """Load key=value pairs from a .env file into a dict."""
    env = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def check_env_completeness(env: dict):
    REQUIRED = [
        "DATABASE_URL", "SYNC_DATABASE_URL",
        "REDIS_URL", "NAS_BASE_PATH",
    ]
    missing = [k for k in REQUIRED if not env.get(k)]
    check(
        "l1",
        len(missing) == 0,
        ".env — all required keys present",
        f".env — missing required keys: {', '.join(missing)}",
        hint="Copy .env.example to .env and fill in all required values.",
    )


def check_postgres(env: dict):
    db_url = env.get("SYNC_DATABASE_URL") or env.get("DATABASE_URL", "")
    # Convert asyncpg URL to psycopg2
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    if not db_url:
        _warn("DATABASE_URL not set — skipping PostgreSQL check")
        results["l2"] = None
        return

    try:
        import psycopg2  # type: ignore
        conn = psycopg2.connect(db_url, connect_timeout=5)
        cur = conn.cursor()
        cur.execute("SELECT version()")
        row = cur.fetchone()
        ver = row[0].split(",")[0] if row and row[0] else "unknown"

        # Check alembic_version table
        try:
            cur.execute("SELECT version_num FROM alembic_version ORDER BY version_num")
            versions = [row[0] for row in cur.fetchall()]
        except Exception:
            versions = []

        conn.close()
        _ok(f"PostgreSQL — connected ({ver})")
        if versions:
            _info(f"  Applied migrations: {', '.join(versions)}")
        else:
            _warn("  No alembic_version entries found — migrations may not be applied")
        results["l2"] = True
    except ImportError:
        _warn("psycopg2 not installed — skipping PostgreSQL check (`pip install psycopg2-binary`)")
        results["l2"] = None
    except Exception as e:
        _fail(f"PostgreSQL — connection failed: {e}")
        results["l2"] = False


def check_redis_live(env: dict):
    redis_url = env.get("REDIS_URL", "redis://localhost:6380/0")

    try:
        import redis  # type: ignore
        r = redis.from_url(redis_url, socket_timeout=3)
        if r is None:
            raise RuntimeError("redis.from_url() returned None")
        r.ping()

        # Write/read test
        test_key = "_dpp_debug_probe"
        r.set(test_key, "ok", ex=5)
        val = r.get(test_key)
        r.delete(test_key)

        check(
            "l3",
            val in (b"ok", "ok"),
            f"Redis — ping OK + read/write OK ({redis_url})",
            f"Redis — read/write failed (ping OK but set/get returned {val!r})",
        )
    except ImportError:
        _warn("redis-py not installed — skipping Redis check (`pip install redis`)")
        results["l3"] = None
    except Exception as e:
        _fail(f"Redis — connection failed: {e}")
        results["l3"] = False


def check_storage_path(env: dict):
    nas = env.get("NAS_BASE_PATH", "")
    if not nas:
        _warn("NAS_BASE_PATH not set — skipping storage check")
        results["l4"] = None
        return

    path = Path(nas)
    if not path.exists():
        try:
            path.mkdir(parents=True, exist_ok=True)
            _ok(f"Storage — created missing path: {nas}")
            results["l4"] = True
        except Exception as e:
            _fail(f"Storage — path does not exist and cannot be created: {e}")
            results["l4"] = False
        return

    readable  = os.access(nas, os.R_OK)
    writable  = os.access(nas, os.W_OK)

    probe = path / "_dpp_write_probe"
    write_ok = False
    try:
        probe.write_text("ok")
        probe.unlink()
        write_ok = True
    except Exception:
        pass

    if readable and writable and write_ok:
        _ok(f"Storage — path exists, readable and writable: {nas}")
        results["l4"] = True
    elif readable and not writable:
        _fail(f"Storage — path exists but NOT writable: {nas}")
        results["l4"] = False
    else:
        _warn(f"Storage — path exists (readable={readable} writable={writable} write_probe={write_ok}): {nas}")
        results["l4"] = writable


def check_ocr_endpoint(env: dict):
    import urllib.request

    # Determine endpoint from env
    layer1 = env.get("LAYER1_PROVIDER", "").strip().lower()

    if layer1 == "datalab":
        url = env.get("DATALAB_BASE_URL", "https://api.datalab.to")
        api_key = env.get("DATALAB_API_KEY", "")
        if not api_key:
            _warn("DATALAB_API_KEY not set — cannot validate Datalab endpoint")
            results["l5"] = None
            return
        test_url = f"{url.rstrip('/')}/v1/marker"
    elif layer1 in ("openai_compat", ""):
        base_url = env.get("OCR_BASE_URL", env.get("OPENAI_COMPAT_BASE_URL", "http://localhost:11434"))
        test_url = f"{base_url.rstrip('/')}/api/tags"
    else:
        base_url = env.get("OCR_BASE_URL", "http://localhost:11434")
        test_url = f"{base_url.rstrip('/')}/api/tags"

    try:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req_obj = urllib.request.Request(test_url, headers={"User-Agent": "DPP-HealthCheck/1.0"})
        req = urllib.request.urlopen(req_obj, timeout=10, context=ctx)
        status = req.status
        check(
            "l5",
            status == 200,
            f"OCR endpoint — reachable: {test_url} (HTTP {status})",
            f"OCR endpoint — unexpected status {status}: {test_url}",
        )
    except Exception as e:
        _fail(f"OCR endpoint — unreachable: {test_url} → {e}")
        _info("  Documents will be parked as PENDING_MODEL until the endpoint comes back.")
        results["l5"] = False


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

def print_summary():
    passed  = [k for k, v in results.items() if v is True]
    failed  = [k for k, v in results.items() if v is False]
    skipped = [k for k, v in results.items() if v is None]

    _section("SUMMARY")
    print(f"  {GREEN}Passed : {len(passed)}{RESET}")
    print(f"  {RED}Failed : {len(failed)}{RESET}")
    if skipped:
        print(f"  {YELLOW}Skipped: {len(skipped)}{RESET}")

    if failed:
        print(f"\n  {BOLD}Action required:{RESET}")
        label_map = {
            "c1":  "pipeline.py — add ExtractionResult to imports",
            "c2":  "purchase_orders.py — change OR → AND in upload validation",
            "c3":  "extraction.py + tasks.py — replace hardcoded /6",
            "c4":  "config.py — change debug default to False",
            "c5":  ".env.example — change DEBUG=true to DEBUG=false",
            "c6":  "docker-compose.prod.yml — add healthcheck condition to nginx",
            "c7":  "admin.py — update _check_models() for new provider config",
            "c8":  "tasks.py — consolidate multiple asyncio.run() calls",
            "c9":  "start.ps1 / stop_all.ps1 — fix port mismatch",
            "c10": "config.py — change CORS default to empty list",
            "l1":  ".env — fill in all required keys",
            "l2":  "PostgreSQL — fix connection / run migrations",
            "l3":  "Redis — fix connection",
            "l4":  "Storage — fix path permissions",
            "l5":  "OCR endpoint — start the model server",
        }
        for k in failed:
            label = label_map.get(k, k)
            print(f"    {RED}✘{RESET}  [{k.upper()}] {label}")

    if not failed:
        print(f"\n  {GREEN}{BOLD}All checks passed ✔{RESET}")


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="DPP debug / pre-flight check script"
    )
    parser.add_argument(
        "--live", action="store_true",
        help="Also run live connectivity checks (DB, Redis, storage, OCR)",
    )
    parser.add_argument(
        "--env", default=".env",
        help="Path to .env file (default: .env in project root)",
    )
    args = parser.parse_args()

    root = find_project_root()
    print(f"\n{BOLD}DPP Debug Script{RESET}  —  project root: {root}")

    # ── Code checks ──────────────────────────────────────────────────────────
    _section("CODE CHECKS")
    check_extraction_result_import(root)
    check_upload_validation(root)
    check_hardcoded_chain_divisor(root)
    check_debug_default(root)
    check_env_example_debug(root)
    check_nginx_healthcheck(root)
    check_admin_health_provider(root)
    check_asyncio_run_in_celery(root)
    check_port_mismatch(root)
    check_cors_default(root)

    # ── Live checks ──────────────────────────────────────────────────────────
    if args.live:
        _section("LIVE CHECKS")
        env_path = root / args.env
        if not env_path.exists():
            _warn(f".env file not found at {env_path} — live checks may fail")
            env = {}
        else:
            env = load_env(env_path)
            _info(f"Loaded {len(env)} keys from {env_path}")

        check_env_completeness(env)
        check_postgres(env)
        check_redis_live(env)
        check_storage_path(env)
        check_ocr_endpoint(env)
    else:
        _info("Run with --live to also check DB, Redis, storage and OCR endpoint connectivity.")

    print_summary()
    sys.exit(1 if any(v is False for v in results.values()) else 0)


if __name__ == "__main__":
    main()
