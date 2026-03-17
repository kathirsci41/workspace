"""
Full E2E Report — docplatform-v3
Tests complete user flow for one customer: upload all 5 doc types, inspect DB, test retrieval.

Usage (backend + celery must be running via start.ps1):
    python e2e_full_report.py                          # run Elite dataset (default)
    python e2e_full_report.py --dataset billion-honour # run specific dataset
    python e2e_full_report.py --all                    # run ALL datasets sequentially
    python e2e_full_report.py --customer SKY-001       # use specific customer
    python e2e_full_report.py --no-cleanup             # keep test POs in DB
    python e2e_full_report.py --doc COMPANY_INVOICE    # single doc type only

Covers:
  Phase 1 — Setup         : verify backend, pick customer, create PO
  Phase 2 — Upload+Extract: upload each doc, poll to completion, show timing + fields
  Phase 3 — DB Inspection : query Postgres tables directly (documents, metadata, references)
  Phase 4 — Retrieval     : test all API endpoints that read back the saved data
  Phase 5 — Summary       : overall scorecard
  Phase 6 — Multi-dataset : cross-dataset aggregate scorecard (only with --all)
"""

import argparse
import io
import json
import sys
import time
import textwrap
from datetime import datetime
from pathlib import Path

import httpx
import psycopg2
import psycopg2.extras

# ── UTF-8 output on Windows ───────────────────────────────────────────────────
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── ANSI colours ──────────────────────────────────────────────────────────────
R = "\033[0m"       # reset
B = "\033[1m"       # bold
DIM = "\033[2m"     # dim
CY = "\033[36m"     # cyan
GR = "\033[32m"     # green
YL = "\033[33m"     # yellow
RD = "\033[31m"     # red
MG = "\033[35m"     # magenta
BL = "\033[34m"     # blue

def c(color, s): return f"{color}{s}{R}"
def ok(s):  return c(GR, f"✅  {s}")
def err(s): return c(RD, f"❌  {s}")
def warn(s): return c(YL, f"⚠️  {s}")
def info(s): return c(CY, f"ℹ️  {s}")

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_BASE_URL   = "http://localhost:8000"
DB_DSN             = "host=127.0.0.1 port=5433 dbname=docplatform user=docplatform password=docplatform"
POLL_INTERVAL      = 2.0    # seconds
POLL_TIMEOUT       = 300    # seconds
HTTP_TIMEOUT       = 60

_TESTDO = Path("E:/PROJECTS/Experiments/Logistic/Phase 2.1.0/.testdo")

# ── Dataset: Elite Contractors ────────────────────────────────────────────────
_ELITE = _TESTDO / "Elite"
DATASETS = {
    "elite": {
        "label":      "Elite Contractors",
        "root":       _ELITE,
        "expected": {
            "COMPANY_PO": {
                "purchase_bill_no": "1PBTR252600529",
                "po_number":        "1PTR2526000405",
                "bill_no":          "C240847449",
            },
            "VENDOR_INVOICE": {
                "invoice_number":    "C240847449",
                "customer_order_no": "5002312554",
                "po_reference":      "965855",
            },
            "CUSTOMER_PO": {
                "po_number": "323-24/Hlite HO/AI",
                "po_date":   "December 5,2025",
                "bsif_name": "ELITE CONTRACTORS",
            },
            "COMPANY_DC": {
                "dc_number":      "1DNT2526DC2865",
                "po_reference":   "323-24/Hlite HO",
                "sales_order_no": "1OTM2526001448",
                "dispatch_to":    "ELITE CONTRACTORS",
            },
            "COMPANY_INVOICE": {
                "invoice_number": "1ITR2526001748",
                "so_number":      "1OTM2526001448",
                "total_amount":   "613600",
                "customer_name":  "ELITE CONTRACTORS",
            },
        },
        "docs": [
            {"path": _ELITE / "Skylark PO.pdf",
             "doc_type": "COMPANY_PO",     "label": "Skylark PO"},
            {"path": _ELITE / "C240847449 1OTM2526001448-Vendor Invoice.pdf",
             "doc_type": "VENDOR_INVOICE", "label": "Redington Tax Invoice"},
            {"path": _ELITE / "PO (2).pdf",
             "doc_type": "CUSTOMER_PO",    "label": "Elite Customer PO"},
            {"path": _ELITE / "1DNT2526DC2865.pdf",
             "doc_type": "COMPANY_DC",     "label": "Company DC 1DNT2526DC2865"},
            {"path": _ELITE / "1ITR2526001748.pdf",
             "doc_type": "COMPANY_INVOICE","label": "Company Invoice 1ITR2526001748"},
        ],
        "search_ref":  "C240847449",
        "so_ref":      "1OTM2526001448",
        "invoice_no":  "C240847449",
    },

    # ── Dataset: Billion Honour ───────────────────────────────────────────────
    "billion-honour": {
        "label":      "Billion Honour Accounting Services",
        "root":       _TESTDO / "Billion Honour",
        "expected": {
            "COMPANY_PO": {
                "purchase_bill_no": "1PBTR2526000483",
                "po_number":        "1PTR2526000428",
                "bill_no":          "2526PSI25079221",
            },
            "VENDOR_INVOICE": {
                "invoice_number":    "2526PSI25079221",
                "customer_order_no": "1PTR2526000428",  # "PO-1PTR2526000428" on doc
            },
            "CUSTOMER_PO": {
                "po_number": "BHAS-PO-IT-2025/26-022",
                "po_date":   "23.12.2025",
                "bsif_name": "BILLION HONOUR",
            },
            "COMPANY_DC": {
                "dc_number":      "1DNT2526DC2919",
                "po_reference":   "BHAS-PO-IT-2025/26-022",
                "sales_order_no": "1OTM2526001544",
                "dispatch_to":    "BILLION HONOUR",
            },
            "COMPANY_INVOICE": {
                "invoice_number": "1ITR2526001789",
                "po_reference":   "BHAS-PO-IT-2025/26-022",
                "so_number":      "1OTM2526001544",
                "customer_name":  "BILLION HONOUR",
                "total_amount":   "364502",
            },
        },
        "docs": [
            {"path": _TESTDO / "Billion Honour" / "Skylark PO.pdf",
             "doc_type": "COMPANY_PO",     "label": "Skylark PO"},
            {"path": _TESTDO / "Billion Honour" / "2526PSI25079221 1OTM2526001544-Vendor invoice.pdf",
             "doc_type": "VENDOR_INVOICE", "label": "Supreme Computers Tax Invoice"},
            {"path": _TESTDO / "Billion Honour" / "BHAS-PO-22.pdf",
             "doc_type": "CUSTOMER_PO",    "label": "Billion Honour Customer PO"},
            {"path": _TESTDO / "Billion Honour" / "1DNT2526DC2919 BILLION.pdf",
             "doc_type": "COMPANY_DC",     "label": "Company DC 1DNT2526DC2919"},
            {"path": _TESTDO / "Billion Honour" / "1ITR2526001789 BILLION.pdf",
             "doc_type": "COMPANY_INVOICE","label": "Company Invoice 1ITR2526001789"},
        ],
        "search_ref":  "2526PSI25079221",
        "so_ref":      "1OTM2526001544",
        "invoice_no":  "2526PSI25079221",
    },

    # ── Dataset: Addision & Co ────────────────────────────────────────────────
    "addision": {
        "label":      "Addision & Co Ltd",
        "root":       _TESTDO / "Addision",
        "expected": {
            "CUSTOMER_PO": {
                "bsif_name": "ADDISON",
                # po_number: "IGKPO/106399/2526" — exact format uncertain from OCR
            },
            "COMPANY_PO": {
                "purchase_bill_no": "1PBTR2526000518",
                "po_number":        "1PTR2526000457",
                "bill_no":          "CT2526011078",
            },
            "VENDOR_INVOICE": {
                "invoice_number": "CT2526011078",
                # po_reference: "1PTR2526000457" — verify on first run
            },
            "COMPANY_DC": {
                "dc_number":      "1DNT2526DC2995",
                "sales_order_no": "1OTM2526001596",
                "po_reference":   "IGKPO/106399/2526",
            },
            "COMPANY_INVOICE": {
                "invoice_number": "1ITR2526001841",
                "so_number":      "1OTM2526001596",
                "customer_name":  "ADDISON",
                "po_reference":   "IGKPO/106399/2526",
            },
        },
        "docs": [
            {"path": _TESTDO / "Addision" / "RAM PO Copy.pdf",
             "doc_type": "CUSTOMER_PO",    "label": "Addision Customer PO"},
            {"path": _TESTDO / "Addision" / "Skylark PO.pdf",
             "doc_type": "COMPANY_PO",     "label": "Skylark PO"},
            {"path": _TESTDO / "Addision" / "CT2526011078 1OTM2526001596-vendor invoice.pdf",
             "doc_type": "VENDOR_INVOICE", "label": "Comprint Tech Invoice CT2526011078"},
            {"path": _TESTDO / "Addision" / "1DNT2526DC2995 ADDISON-DC.pdf",
             "doc_type": "COMPANY_DC",     "label": "Company DC 1DNT2526DC2995"},
            {"path": _TESTDO / "Addision" / "1ITR2526001841 ADDISON-Customer Invoice.pdf",
             "doc_type": "COMPANY_INVOICE","label": "Company Invoice 1ITR2526001841"},
        ],
        "search_ref": "CT2526011078",
        "so_ref":     "1OTM2526001596",
        "invoice_no": "CT2526011078",
    },

    # ── Dataset: Bhimasugam Industries ───────────────────────────────────────
    # Note: PO-BSIF-059_compressed.pdf is 11.2 MB — skipped to avoid timeout.
    # Two DCs (DC2626, DC2628) and two invoices (1721, 1722) exist; using first pair.
    "bhimasugam": {
        "label":      "Bhimasugam Industries",
        "root":       _TESTDO / "Bhimasugam",
        "expected": {
            # CUSTOMER_PO skipped (11.2 MB file — too slow for E2E)
            "COMPANY_PO": {
                "po_number": "1PTR2526000382",
                "bill_no":   "10ID25B0310689",
            },
            "VENDOR_INVOICE": {
                "invoice_number": "10ID25B0310689",
                "po_reference":   "1PTR2526000382",
            },
            "COMPANY_DC": {
                "dc_number": "1DNT2526DC2626",
            },
            "COMPANY_INVOICE": {
                "invoice_number": "1ITR2526001721",
            },
        },
        "docs": [
            {"path": _TESTDO / "Bhimasugam" / "Skylark PO.pdf",
             "doc_type": "COMPANY_PO",     "label": "Skylark PO"},
            {"path": _TESTDO / "Bhimasugam" / "10ID25B0310689 1PTR2526000382-vendor invoice.pdf",
             "doc_type": "VENDOR_INVOICE", "label": "Vendor Invoice 10ID25B0310689"},
            {"path": _TESTDO / "Bhimasugam" / "1DNT2526DC2626.pdf",
             "doc_type": "COMPANY_DC",     "label": "Company DC 1DNT2526DC2626"},
            {"path": _TESTDO / "Bhimasugam" / "1ITR2526001721.pdf",
             "doc_type": "COMPANY_INVOICE","label": "Company Invoice 1ITR2526001721"},
        ],
        "search_ref": "10ID25B0310689",
        "so_ref":     "1OTM2526001387",   # seen in ITICHG filename
        "invoice_no": "10ID25B0310689",
    },

    # ── Dataset: Mando ────────────────────────────────────────────────────────
    # No CUSTOMER_PO PDF (only .msg email). PO number: 4500174759.
    # Two COMPANY_INVOICEs exist; using C Invoice 0.pdf.
    "mando": {
        "label":      "Mando",
        "root":       _TESTDO / "Mando",
        "expected": {
            # CUSTOMER_PO: no PDF (only .msg email) — skipped
            "COMPANY_PO": {
                # purchase_bill_no, po_number, bill_no: unknown without reading PDF
            },
            "VENDOR_INVOICE": {
                # invoice_number: unknown without reading PDF
            },
            "COMPANY_DC": {
                "po_reference": "4500174759",
            },
            "COMPANY_INVOICE": {
                "po_reference":  "4500174759",
                "customer_name": "MANDO",
            },
        },
        "docs": [
            {"path": _TESTDO / "Mando" / "Skylark PO.pdf",
             "doc_type": "COMPANY_PO",     "label": "Skylark PO"},
            {"path": _TESTDO / "Mando" / "Vendor invoice.pdf",
             "doc_type": "VENDOR_INVOICE", "label": "Vendor Invoice"},
            {"path": _TESTDO / "Mando" / "C DC.pdf",
             "doc_type": "COMPANY_DC",     "label": "Company DC"},
            {"path": _TESTDO / "Mando" / "C Invoice 0.pdf",
             "doc_type": "COMPANY_INVOICE","label": "Company Invoice 0"},
        ],
        "search_ref": "4500174759",
        "so_ref":     "4500174759",    # use PO number as fallback
        "invoice_no": "4500174759",
    },
}

# Back-compat aliases (resolved after args parse)
EXPECTED  = None
TEST_DOCS = None


# ── Logging helpers ───────────────────────────────────────────────────────────

def ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

def log(msg, indent=0):
    prefix = "  " * indent
    print(f"  {prefix}{c(DIM, ts())}  {msg}")

def phase(title):
    bar = "─" * (90 - len(title) - 4)
    print(f"\n{c(B+MG, f'[{title}]')} {c(DIM, bar)}")

def subheader(title):
    print(f"\n    {c(B+BL, title)}")

def banner(title, width=94):
    print(c(B+CY, "═" * width))
    pad = (width - len(title)) // 2
    print(c(B+CY, " " * pad + title))
    print(c(B+CY, "═" * width))


# ── DB helpers ────────────────────────────────────────────────────────────────

def db_connect():
    return psycopg2.connect(DB_DSN, cursor_factory=psycopg2.extras.RealDictCursor)

def db_query(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()

def print_table(rows, cols, indent=4):
    """Print rows as a formatted table."""
    if not rows:
        print(" " * indent + c(YL, "(no rows)"))
        return
    widths = {c: len(c) for c in cols}
    for row in rows:
        for col in cols:
            val = str(row.get(col, "")) if row.get(col) is not None else "NULL"
            widths[col] = max(widths[col], min(len(val), 40))
    sep = " " * indent + "┼".join("─" * (w + 2) for w in widths.values())
    hdr = " " * indent + "│".join(f" {c(B, col):<{w+8}} " for col, w in widths.items())
    print(" " * indent + "┌" + "┬".join("─" * (w + 2) for w in widths.values()) + "┐")
    print(hdr)
    print(" " * indent + "├" + "┼".join("─" * (w + 2) for w in widths.values()) + "┤")
    for row in rows:
        line_parts = []
        for col, w in widths.items():
            raw = str(row.get(col, "")) if row.get(col) is not None else c(DIM, "NULL")
            truncated = raw[:40] + ("…" if len(raw) > 40 else "")
            line_parts.append(f" {truncated:<{w}} ")
        print(" " * indent + "│" + "│".join(line_parts) + "│")
    print(" " * indent + "└" + "┴".join("─" * (w + 2) for w in widths.values()) + "┘")


# ── API helpers ───────────────────────────────────────────────────────────────

def api(client, method, url, **kwargs):
    t0 = time.perf_counter()
    r = getattr(client, method)(url, **kwargs)
    elapsed = time.perf_counter() - t0
    return r, elapsed

def get_or_create_customer(client, base, customer_id_filter=None):
    params = {"per_page": 20}
    if customer_id_filter:
        params["search"] = customer_id_filter
    r, _ = api(client, "get", f"{base}/api/v1/customers", params=params)
    r.raise_for_status()
    items = r.json().get("items", [])
    if customer_id_filter:
        for it in items:
            if it.get("customer_id") == customer_id_filter:
                return it
    if items:
        return items[0]
    # Create test customer
    r, _ = api(client, "post", f"{base}/api/v1/customers", json={
        "name": "E2E Test Customer", "customer_id": "E2E-TEST",
        "contact_email": "test@e2e.local"
    })
    r.raise_for_status()
    return r.json()

def create_test_po(client, base, customer_id):
    ts_str = datetime.now().strftime("%m%d%H%M%S")
    r, elapsed = api(client, "post", f"{base}/api/v1/purchase-orders", json={
        "customer_id": customer_id,
        "po_number": f"E2E-{ts_str}",
    })
    r.raise_for_status()
    return r.json(), elapsed

def upload_doc(client, base, po_id, doc):
    path = doc["path"]
    t0 = time.perf_counter()
    with open(path, "rb") as f:
        r = client.post(
            f"{base}/api/v1/purchase-orders/{po_id}/documents",
            data={"document_type": doc["doc_type"]},
            files={"file": (path.name, f, "application/pdf")},
            timeout=HTTP_TIMEOUT,
        )
    elapsed = time.perf_counter() - t0
    r.raise_for_status()
    return r.json(), elapsed

def poll_doc(client, base, doc_id):
    t0 = time.perf_counter()
    deadline = t0 + POLL_TIMEOUT
    prev_status = None
    status_changes = []
    while time.perf_counter() < deadline:
        r, _ = api(client, "get", f"{base}/api/v1/documents/{doc_id}", timeout=HTTP_TIMEOUT)
        if r.status_code == 200:
            d = r.json()
            status = d.get("status", "")
            if status != prev_status:
                elapsed = time.perf_counter() - t0
                status_changes.append((status, elapsed))
                prev_status = status
            if status not in ("UPLOADED", "EXTRACTING"):
                return d, time.perf_counter() - t0, status_changes
        time.sleep(POLL_INTERVAL)
    return None, time.perf_counter() - t0, status_changes


# ── Field checking ────────────────────────────────────────────────────────────

def field_ok(key, got, expected_map):
    exp = expected_map.get(key)
    if exp is None:
        return None
    got_str = str(got).strip() if got is not None else ""
    return exp.lower() in got_str.lower()


# ── Phase runners ─────────────────────────────────────────────────────────────

def run_phase1_setup(client, base, customer_filter):
    phase("PHASE 1 — SETUP")

    log("Checking backend connectivity...", indent=0)
    try:
        r, t = api(client, "get", f"{base}/api/v1/customers", params={"per_page": 1},
                   timeout=5)
        r.raise_for_status()
        log(ok(f"Backend reachable at {base} ({t*1000:.0f}ms)"))
    except Exception as e:
        log(err(f"Cannot reach backend: {e}"))
        log(c(YL, "  → Run: .\\start.ps1  (from project root in PowerShell)"))
        sys.exit(1)

    log("Resolving customer...", indent=0)
    customer = get_or_create_customer(client, base, customer_filter)
    log(ok(f"Customer : {c(B, customer.get('name'))} (sky_id={customer.get('customer_id')}, id={str(customer['id'])[:8]}...)"))

    log("Creating test PO...", indent=0)
    po, t = create_test_po(client, base, customer["id"])
    log(ok(f"PO       : {c(B, po['po_number'])} (id={str(po['id'])[:8]}...) — created in {t*1000:.0f}ms"))

    return customer, po


def run_phase2_extraction(client, base, po_id, docs, expected_map_all):
    phase("PHASE 2 — DOCUMENT UPLOAD & EXTRACTION")
    results = []

    for i, doc in enumerate(docs):
        doc_type = doc["doc_type"]
        label    = doc["label"]
        path     = doc["path"]
        size_kb  = path.stat().st_size // 1024
        n        = f"{i+1}/{len(docs)}"

        print(f"\n    {c(B,'┌')} {c(B+BL, n)} {c(B, doc_type)} — {label} ({size_kb} KB)")
        print(f"    {c(B,'│')}")

        # Upload
        log(f"[UPLOAD] Sending {path.name} to API...", indent=2)
        try:
            resp, upload_s = upload_doc(client, base, po_id, doc)
        except Exception as e:
            log(err(f"[UPLOAD] Failed: {e}"), indent=2)
            results.append({"doc_type": doc_type, "status": "UPLOAD_FAILED",
                            "upload_s": 0, "poll_s": 0, "doc": None})
            print(f"    {c(B,'└')}{'─'*80}")
            continue

        doc_id = resp.get("id") or resp.get("document_id")
        log(ok(f"[UPLOAD] Done in {upload_s:.2f}s — doc_id={str(doc_id)[:8]}..."), indent=2)

        # Poll
        log(f"[EXTRACT] Polling for completion (status: UPLOADED)...", indent=2)
        final, poll_s, transitions = poll_doc(client, base, doc_id)

        # Show status transitions
        for status, at_s in transitions:
            icon = "⏳" if status in ("UPLOADED", "EXTRACTING") else ("✅" if "PENDING" in status else "❌")
            log(f"[EXTRACT] {icon} {status} at +{at_s:.1f}s", indent=3)

        if final is None:
            log(err(f"[EXTRACT] TIMED OUT after {poll_s:.0f}s"), indent=2)
            results.append({"doc_type": doc_type, "status": "TIMEOUT",
                            "upload_s": upload_s, "poll_s": poll_s, "doc": None})
            print(f"    {c(B,'└')}{'─'*80}")
            continue

        status   = final.get("status", "UNKNOWN")
        meta     = final.get("metadata") or {}
        extracted = meta.get("extracted_data") or {}
        proc_ms  = meta.get("processing_time_ms") or 0
        conf     = meta.get("confidence_score") or 0
        model_v  = meta.get("model_version") or "unknown"
        last_err = meta.get("last_error") or ""
        total_s  = upload_s + poll_s
        queue_s  = max(0.0, total_s - upload_s - proc_ms / 1000)

        # Timing breakdown
        log("", indent=2)
        log(c(B, "── Timing ──────────────────────────────────────"), indent=2)
        log(f"  Upload (HTTP)       : {upload_s:6.2f}s", indent=2)
        log(f"  Queue + PDF conv    : {queue_s:6.2f}s  (estimated)", indent=2)
        log(f"  OCR + Extract       : {proc_ms/1000:6.2f}s  ← stored in metadata.processing_time_ms", indent=2)
        log(f"  Total E2E           : {total_s:6.2f}s", indent=2)
        log(f"  Model               : {model_v}", indent=2)
        log(f"  Confidence          : {conf}%  |  Status: {c(GR if 'PENDING' in status else RD, status)}", indent=2)
        if last_err:
            log(c(RD, f"  Last error          : {last_err[:120]}"), indent=2)

        # Field comparison
        log("", indent=2)
        log(c(B, "── Extracted Fields ────────────────────────────"), indent=2)
        expected_map = expected_map_all.get(doc_type, {})
        col = 22
        print(f"      {'Field':{col}}  {'Extracted':{col}}  {'Expected':{col}}  OK")
        print(f"      {'─'*col}  {'─'*col}  {'─'*col}  ──")

        all_ok = True
        field_results = {}
        for field, exp in expected_map.items():
            got = extracted.get(field)
            got_str = str(got)[:col] if got is not None else c(DIM, "(none)")
            ok_flag = field_ok(field, got, expected_map)
            icon = c(GR, "✅") if ok_flag else c(RD, "❌")
            if not ok_flag:
                all_ok = False
            print(f"      {field:{col}}  {got_str:{col}}  {exp:{col}}  {icon}")
            field_results[field] = {"got": got, "expected": exp, "ok": ok_flag}

        # Extra fields not in expected
        for field, val in extracted.items():
            if field not in expected_map and not field.startswith("_") and val is not None:
                print(f"      {field:{col}}  {str(val)[:col]:{col}}  {'(extra)':{col}}  {c(DIM,'  ℹ')}")

        summary_icon = ok("ALL CORRECT") if all_ok else err("SOME FIELDS FAILED")
        log(summary_icon, indent=2)

        results.append({
            "doc_type": doc_type, "status": status, "doc_id": str(doc_id),
            "upload_s": upload_s, "poll_s": poll_s, "total_s": total_s,
            "proc_ms": proc_ms, "conf": conf, "all_ok": all_ok,
            "field_results": field_results, "doc": final,
        })
        print(f"\n    {c(B,'└')}{'─'*80}")

    return results


def run_phase3_db(conn, po_id, doc_ids):
    phase("PHASE 3 — DATABASE INSPECTION")

    # ── purchase_orders ──
    subheader("TABLE: purchase_orders")
    rows = db_query(conn, """
        SELECT id::text, po_number, status, chain_completeness, created_at::text
        FROM purchase_orders WHERE id = %s
    """, (po_id,))
    if rows:
        r = rows[0]
        for k, v in r.items():
            print(f"      {c(B, k):<30} {v}")
    else:
        log(warn("PO not found in DB"))

    # ── documents ──
    subheader(f"TABLE: documents ({len(doc_ids)} rows)")
    if doc_ids:
        rows = db_query(conn, """
            SELECT id::text, document_type, filename, status, file_size,
                   page_count, mime_type, created_at::text
            FROM documents WHERE po_id = %s ORDER BY created_at
        """, (po_id,))
        print_table(rows, ["id", "document_type", "filename", "status", "file_size",
                           "page_count", "created_at"])

    # ── document_metadata ──
    subheader("TABLE: document_metadata")
    if doc_ids:
        rows = db_query(conn, """
            SELECT
                document_id::text,
                document_type,
                status,
                confidence_score,
                processing_time_ms,
                extraction_attempts,
                primary_ref_no,
                po_ref_no,
                doc_date::text,
                total_amount,
                model_version,
                extracted_at::text,
                last_error
            FROM document_metadata
            WHERE document_id = ANY(%s::uuid[])
            ORDER BY extracted_at
        """, ([str(d) for d in doc_ids],))
        print_table(rows, ["document_id", "document_type", "status", "confidence_score",
                           "processing_time_ms", "primary_ref_no", "po_ref_no",
                           "doc_date", "total_amount", "extraction_attempts",
                           "model_version"])

        # ── Show extracted_data JSON per doc ──
        subheader("EXTRACTED DATA (JSON) per document")
        meta_rows = db_query(conn, """
            SELECT document_type, extracted_data
            FROM document_metadata
            WHERE document_id = ANY(%s::uuid[])
            ORDER BY document_type
        """, ([str(d) for d in doc_ids],))
        for row in meta_rows:
            print(f"\n      {c(B+BL, row['document_type'])}")
            data = row['extracted_data'] or {}
            for k, v in data.items():
                if k.startswith("_"):
                    continue
                val_str = str(v)[:80] if v is not None else c(DIM, "null")
                print(f"        {k:<30} {val_str}")

    # ── reference_index ──
    subheader("TABLE: reference_index")
    if doc_ids:
        rows = db_query(conn, """
            SELECT
                id::text,
                document_type,
                ref_type,
                ref_value,
                document_id::text
            FROM reference_index
            WHERE po_id = %s
            ORDER BY document_type, ref_type
        """, (po_id,))
        log(f"Total index entries: {c(B, str(len(rows)))} — these are searchable cross-reference links")
        print_table(rows, ["document_type", "ref_type", "ref_value", "document_id"])


def run_phase4_retrieval(client, base, po_id, doc_ids, dataset):
    phase("PHASE 4 — RETRIEVAL TESTS")
    all_passed = True
    search_ref = dataset["search_ref"]
    so_ref     = dataset["so_ref"]
    invoice_no = dataset["invoice_no"]

    # ── GET PO ──
    subheader("GET /api/v1/purchase-orders/{id}")
    r, t = api(client, "get", f"{base}/api/v1/purchase-orders/{po_id}")
    if r.status_code == 200:
        d = r.json()
        log(ok(f"Retrieved PO in {t*1000:.0f}ms"))
        log(f"  po_number          = {d.get('po_number')}")
        log(f"  customer_name      = {d.get('customer_name')}")
        log(f"  status             = {d.get('status')}")
        log(f"  chain_completeness = {d.get('chain_completeness')}%")
    else:
        log(err(f"GET PO failed: {r.status_code}"))
        all_passed = False

    # ── Chain status ──
    subheader("GET /api/v1/purchase-orders/{id}/chain-status")
    r, t = api(client, "get", f"{base}/api/v1/purchase-orders/{po_id}/chain-status")
    if r.status_code == 200:
        d = r.json()
        log(ok(f"Retrieved chain status in {t*1000:.0f}ms — completeness: {d.get('completeness_pct')}%"))
        for doc_type, slots in d.get("chain", {}).items():
            if slots:
                slot = slots[0]
                icon = c(GR,"✅") if slot.get("status") in ("PENDING_REVIEW","VERIFIED") else c(RD,"❌")
                log(f"  {icon} {doc_type:<22} status={slot.get('status'):<20} ref={slot.get('ref_no') or '—'}")
            else:
                log(f"  {c(YL,'⬜')} {doc_type:<22} (no document)")
    else:
        log(err(f"Chain status failed: {r.status_code}"))
        all_passed = False

    # ── List documents for PO ──
    subheader("GET /api/v1/purchase-orders/{id}/documents")
    r, t = api(client, "get", f"{base}/api/v1/purchase-orders/{po_id}/documents")
    if r.status_code == 200:
        items = r.json().get("items", [])
        log(ok(f"Retrieved {len(items)} document(s) in {t*1000:.0f}ms"))
        for it in items:
            log(f"  {it.get('document_type'):<22} id={str(it.get('id',''))[:8]}...  status={it.get('status')}")
    else:
        log(err(f"List documents failed: {r.status_code}"))
        all_passed = False

    # ── GET individual document with metadata ──
    subheader("GET /api/v1/documents/{id}  [per document]")
    for doc_id in doc_ids[:3]:  # show first 3
        r, t = api(client, "get", f"{base}/api/v1/documents/{doc_id}")
        if r.status_code == 200:
            d = r.json()
            meta = d.get("metadata") or {}
            doc_type = d.get("document_type", "?")
            status   = d.get("status", "?")
            conf     = meta.get("confidence_score", "?")
            log(ok(f"{doc_type:<22} id={str(doc_id)[:8]}... status={status} conf={conf}% ({t*1000:.0f}ms)"))
        else:
            log(err(f"GET document {str(doc_id)[:8]} failed: {r.status_code}"))
            all_passed = False

    # ── Search: global ──
    subheader(f"GET /api/v1/search?q={search_ref}  (cross-doc reference)")
    r, t = api(client, "get", f"{base}/api/v1/search", params={"q": search_ref, "per_page": 10})
    if r.status_code == 200:
        d = r.json()
        total = d.get("total", 0)
        log(ok(f"Global search found {total} result(s) in {t*1000:.0f}ms"))
        for result in d.get("results", [])[:5]:
            log(f"  {result.get('document_type','?'):<22} ref_type={result.get('ref_type','?'):<20} value={result.get('ref_value','?')}")
    else:
        log(err(f"Search failed: {r.status_code}"))
        all_passed = False

    # ── Search by ref ──
    subheader(f"GET /api/v1/search/by-ref/{so_ref}  (SO number linkage)")
    r, t = api(client, "get", f"{base}/api/v1/search/by-ref/{so_ref}")
    if r.status_code == 200:
        d = r.json()
        total = d.get("total", 0)
        log(ok(f"By-ref search found {total} result(s) in {t*1000:.0f}ms") + " — should link COMPANY_DC ↔ COMPANY_INVOICE")
        for result in d.get("results", [])[:5]:
            log(f"  {result.get('document_type','?'):<22} ref_type={result.get('ref_type','?')}")
    else:
        log(warn(f"By-ref search returned {r.status_code}"))

    # ── Advanced search ──
    subheader(f"GET /api/v1/search/advanced?invoice_no={invoice_no}")
    r, t = api(client, "get", f"{base}/api/v1/search/advanced",
               params={"invoice_no": invoice_no, "per_page": 5})
    if r.status_code == 200:
        d = r.json()
        log(ok(f"Advanced search found {d.get('total',0)} result(s) in {t*1000:.0f}ms"))
    else:
        log(warn(f"Advanced search returned {r.status_code}"))

    return all_passed


def run_phase5_summary(results, retrieval_ok, start_time):
    phase("PHASE 5 — SUMMARY SCORECARD")

    total_elapsed = time.perf_counter() - start_time

    # Per-document row
    col = 22
    print(f"\n  {'Doc Type':{col}}  {'Status':<20}  {'Total':>8}  {'OCR+Ext':>8}  {'Conf':>5}  {'Fields'}")
    print(f"  {'─'*col}  {'─'*20}  {'─'*8}  {'─'*8}  {'─'*5}  {'─'*12}")

    docs_ok = 0
    total_fields_ok = 0
    total_fields = 0
    for r in results:
        status = r.get("status", "?")
        doc_ok = status in ("PENDING_REVIEW", "VERIFIED")
        if doc_ok:
            docs_ok += 1
        icon   = c(GR, "✅") if doc_ok else c(RD, "❌")
        total_s = r.get("total_s", 0)
        proc_s  = r.get("proc_ms", 0) / 1000
        conf    = r.get("conf", 0)
        fr      = r.get("field_results", {})
        fok     = sum(1 for v in fr.values() if v.get("ok") is True)
        ftotal  = len(fr)
        total_fields_ok += fok
        total_fields += ftotal
        field_score = f"{fok}/{ftotal}" if ftotal else "—"
        print(f"  {r['doc_type']:{col}}  {status:<20}  {total_s:>7.1f}s  {proc_s:>7.1f}s  {conf:>4}%  {field_score}  {icon}")

    # Overall
    print(f"\n  {'─'*80}")
    field_pct = int(total_fields_ok / total_fields * 100) if total_fields else 0
    print(f"  Documents extracted  : {docs_ok}/{len(results)}")
    print(f"  Field accuracy       : {total_fields_ok}/{total_fields} ({field_pct}%)")
    print(f"  Retrieval tests      : {ok('passed') if retrieval_ok else err('failed')}")
    print(f"  Total run time       : {total_elapsed:.1f}s")
    print()

    if docs_ok == len(results) and total_fields_ok == total_fields and retrieval_ok:
        print(f"  {c(B+GR, '🎉  ALL TESTS PASSED — pipeline is healthy!')}")
    else:
        print(f"  {c(B+YL, '⚠️   SOME TESTS FAILED — see details above')}")

    return {
        "docs_ok": docs_ok,
        "docs_total": len(results),
        "fields_ok": total_fields_ok,
        "fields_total": total_fields,
        "retrieval_ok": retrieval_ok,
        "elapsed_s": total_elapsed,
    }


def print_multi_dataset_scorecard(per_dataset: list):
    """Print aggregate scorecard across all datasets (Phase 6 for --all runs)."""
    print()
    bar = "═" * 94
    print(c(B+CY, bar))
    pad = (94 - 40) // 2
    print(c(B+CY, " " * pad + "PHASE 6 — MULTI-DATASET AGGREGATE SCORECARD"))
    print(c(B+CY, bar))

    col = 30
    print(f"\n  {'Dataset':{col}}  {'Docs':>5}  {'Fields':>12}  {'Accuracy':>8}  {'Time':>8}  Status")
    print(f"  {'─'*col}  {'─'*5}  {'─'*12}  {'─'*8}  {'─'*8}  {'─'*8}")

    grand_docs_ok = grand_docs = grand_fields_ok = grand_fields = 0
    grand_elapsed = 0.0

    for entry in per_dataset:
        ds  = entry["dataset"]
        s   = entry["score"]
        label = DATASETS[ds]["label"][:col]
        docs_str   = f"{s['docs_ok']}/{s['docs_total']}"
        fields_str = f"{s['fields_ok']}/{s['fields_total']}"
        pct = int(s['fields_ok'] / s['fields_total'] * 100) if s['fields_total'] else 0
        pct_str = f"{pct}%"
        time_str = f"{s['elapsed_s']:.0f}s"
        icon = c(GR, "✅") if s['docs_ok'] == s['docs_total'] and pct == 100 else (
               c(YL, "⚠️ ") if s['docs_ok'] > 0 else c(RD, "❌"))
        print(f"  {label:{col}}  {docs_str:>5}  {fields_str:>12}  {pct_str:>8}  {time_str:>8}  {icon}")

        grand_docs_ok    += s["docs_ok"]
        grand_docs       += s["docs_total"]
        grand_fields_ok  += s["fields_ok"]
        grand_fields     += s["fields_total"]
        grand_elapsed    += s["elapsed_s"]

    print(f"\n  {'─'*80}")
    grand_pct = int(grand_fields_ok / grand_fields * 100) if grand_fields else 0
    print(f"  {'TOTAL':{col}}  {grand_docs_ok}/{grand_docs:>3}  {grand_fields_ok}/{grand_fields:<9}  {grand_pct:>7}%  {grand_elapsed:>7.0f}s")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def run_single_dataset(client, base, dataset_key, args) -> dict:
    """Run the full E2E pipeline for one dataset. Returns score dict."""
    dataset  = DATASETS[dataset_key]
    all_docs = list(dataset["docs"])

    if hasattr(args, "doc") and args.doc:
        all_docs = [d for d in all_docs if d["doc_type"] == args.doc.upper()]

    # Filter missing files
    all_docs = [d for d in all_docs if d["path"].exists()]

    start_time = time.perf_counter()

    banner(
        f"E2E — {dataset['label'].upper():<40}  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print(f"  Backend  : {base}")
    print(f"  Dataset  : {c(B, dataset['label'])}")
    print(f"  Models   : qwen2.5vl:7b (OCR) + qwen2.5:7b (extract)")
    print(f"  Docs     : {len(all_docs)} — {', '.join(d['doc_type'] for d in all_docs)}")

    customer, po = run_phase1_setup(client, base, args.customer)
    results = run_phase2_extraction(client, base, po["id"], all_docs, dataset["expected"])
    doc_ids = [r["doc_id"] for r in results if r.get("doc_id")]
    retrieval_ok = True

    try:
        conn = db_connect()
        log(ok("Connected to Postgres at 127.0.0.1:5433"))
        run_phase3_db(conn, po["id"], doc_ids)
        conn.close()
    except Exception as e:
        log(err(f"DB connection failed: {e}"))
        log(warn("Phase 3 skipped — is PostgreSQL running?"))

    try:
        retrieval_ok = run_phase4_retrieval(client, base, po["id"], doc_ids, dataset)
    except Exception as e:
        log(err(f"Retrieval phase error: {e}"))
        retrieval_ok = False

    score = run_phase5_summary(results, retrieval_ok, start_time)

    no_cleanup = getattr(args, "no_cleanup", False)
    if not no_cleanup:
        try:
            client.delete(f"{base}/api/v1/purchase-orders/{po['id']}", timeout=30)
            log(ok(f"Cleaned up: test PO {po['po_number']} deleted."))
        except Exception as e:
            log(warn(f"Cleanup failed: {e}"))
    else:
        log(info(f"Test PO kept: {po['po_number']} (id={po['id'][:8]}...)"))

    print()
    print(c(B+CY, "═" * 94))
    return score


def main():
    # ── Report output directory ───────────────────────────────────────────────
    report_dir = Path(__file__).parent / "reports"
    report_dir.mkdir(exist_ok=True)
    ts_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    parser = argparse.ArgumentParser(description="Full E2E report for docplatform-v3")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--customer", help="Filter by customer_id (e.g. SKY-001)")
    parser.add_argument("--doc", help="Run only one doc type (e.g. COMPANY_INVOICE)")
    parser.add_argument("--no-cleanup", action="store_true")
    parser.add_argument("--all", action="store_true",
                        help="Run ALL datasets sequentially and print aggregate scorecard")
    parser.add_argument(
        "--dataset", default="elite",
        choices=list(DATASETS.keys()),
        help=f"Test dataset to use (default: elite). Options: {', '.join(DATASETS.keys())}",
    )
    args = parser.parse_args()

    base = args.base_url.rstrip("/")

    if args.all:
        # ── Multi-dataset mode ────────────────────────────────────────────────
        log_path = report_dir / f"e2e_all_{ts_stamp}.log"
        # Tee stdout → file
        orig_stdout = sys.stdout
        log_file = open(log_path, "w", encoding="utf-8")
        class _Tee:
            def write(self, s):
                orig_stdout.write(s)
                log_file.write(s)
            def flush(self):
                orig_stdout.flush()
                log_file.flush()
            # forward other attributes
            def __getattr__(self, name):
                return getattr(orig_stdout, name)
        sys.stdout = _Tee()

        print(c(B+CY, "═" * 94))
        print(c(B+CY, " " * 20 + f"FULL MULTI-DATASET E2E REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"))
        print(c(B+CY, "═" * 94))
        print(f"  Datasets : {', '.join(DATASETS.keys())}")
        print(f"  Log file : {log_path}")
        print()

        per_dataset = []
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            for ds_key in DATASETS:
                try:
                    score = run_single_dataset(client, base, ds_key, args)
                    per_dataset.append({"dataset": ds_key, "score": score})
                except Exception as e:
                    log(err(f"Dataset '{ds_key}' aborted: {e}"))
                    per_dataset.append({"dataset": ds_key, "score": {
                        "docs_ok": 0, "docs_total": 0,
                        "fields_ok": 0, "fields_total": 0,
                        "retrieval_ok": False, "elapsed_s": 0,
                    }})

        print_multi_dataset_scorecard(per_dataset)
        sys.stdout = orig_stdout
        log_file.close()
        print(f"\nLog saved → {log_path}")

    else:
        # ── Single-dataset mode ───────────────────────────────────────────────
        dataset  = DATASETS[args.dataset]
        all_docs = list(dataset["docs"])

        if args.doc:
            all_docs = [d for d in all_docs if d["doc_type"] == args.doc.upper()]
            if not all_docs:
                print(f"Unknown doc type: {args.doc}")
                sys.exit(1)

        missing = [d["path"] for d in all_docs if not d["path"].exists()]
        if missing:
            print(c(RD, "Missing test files:"))
            for p in missing:
                print(f"  {p}")
            sys.exit(1)

        log_path = report_dir / f"e2e_{args.dataset}_{ts_stamp}.log"
        orig_stdout = sys.stdout
        log_file = open(log_path, "w", encoding="utf-8")
        class _Tee:
            def write(self, s):
                orig_stdout.write(s)
                log_file.write(s)
            def flush(self):
                orig_stdout.flush()
                log_file.flush()
            def __getattr__(self, name):
                return getattr(orig_stdout, name)
        sys.stdout = _Tee()

        start_time = time.perf_counter()
        banner(f"FULL E2E REPORT — docplatform-v3   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Backend  : {base}")
        print(f"  Dataset  : {c(B, dataset['label'])}")
        print(f"  Models   : qwen2.5vl:7b (OCR) + qwen2.5:7b (extract)")
        print(f"  Test PDF : {all_docs[0]['path'].parent}")
        print(f"  Docs     : {len(all_docs)} — {', '.join(d['doc_type'] for d in all_docs)}")
        print(f"  Log file : {log_path}")

        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            customer, po = run_phase1_setup(client, base, args.customer)
            results = run_phase2_extraction(client, base, po["id"], all_docs, dataset["expected"])
            doc_ids = [r["doc_id"] for r in results if r.get("doc_id")]
            retrieval_ok = True

            try:
                conn = db_connect()
                log(ok("Connected to Postgres at 127.0.0.1:5433"))
                run_phase3_db(conn, po["id"], doc_ids)
                conn.close()
            except Exception as e:
                log(err(f"DB connection failed: {e}"))
                log(warn("Phase 3 skipped — is PostgreSQL running?"))

            try:
                retrieval_ok = run_phase4_retrieval(client, base, po["id"], doc_ids, dataset)
            except Exception as e:
                log(err(f"Retrieval phase error: {e}"))
                retrieval_ok = False

            run_phase5_summary(results, retrieval_ok, start_time)

            if not args.no_cleanup:
                try:
                    client.delete(f"{base}/api/v1/purchase-orders/{po['id']}", timeout=30)
                    log(ok(f"Cleaned up: test PO {po['po_number']} deleted."))
                except Exception as e:
                    log(warn(f"Cleanup failed: {e}"))
            else:
                log(info(f"Test PO kept: {po['po_number']} (id={po['id'][:8]}...)"))

        sys.stdout = orig_stdout
        log_file.close()
        print()
        print(c(B+CY, "═" * 94))
        print(f"\nLog saved → {log_path}")


if __name__ == "__main__":
    main()
