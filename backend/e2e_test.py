"""
E2E Pipeline Test — measures time for each phase of the OCR extraction pipeline.

Tests all 5 Elite client documents through the running backend API.

Usage (backend must be running):
    python e2e_test.py
    python e2e_test.py --base-url http://localhost:8000
    python e2e_test.py --doc COMPANY_INVOICE   # test single doc type

Phases measured:
  Upload        — HTTP POST duration (file → server)
  Queue delay   — server received to Celery start (total - processing - upload)
  OCR+Extract   — processing_time_ms from metadata (Layer 1 + Layer 2 internal)
  Total E2E     — upload to PENDING_REVIEW / EXTRACTION_FAILED
"""

import argparse
import io
import json
import sys
import time
from pathlib import Path
from datetime import datetime

import httpx

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_BASE_URL = "http://localhost:8000"
POLL_INTERVAL = 2.0       # seconds between status polls
POLL_TIMEOUT  = 300       # max seconds to wait for extraction
HTTP_TIMEOUT  = 60        # seconds for individual HTTP calls

ELITE_ROOT = Path("E:/PROJECTS/Experiments/Logistic/Phase 2.1.0/.testdo/Elite")

# Ground-truth expected values per doc type
EXPECTED = {
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
        "bsif_name": "ELITE CONTRACTORS (CHENNAI) PRIVATE LIMITED",
    },
    "COMPANY_DC": {
        "dc_number":     "1DNT2526DC2865",
        "po_reference":  "323-24/Hlite HO/ AI",
        "sales_order_no": "1OTM2526001448",
        "dispatch_to":   "ELITE CONTRACTORS",  # partial match
    },
    "COMPANY_INVOICE": {
        "invoice_number": "1ITR2526001748",
        "so_number":      "1OTM2526001448",
        "total_amount":   "613600",  # compare as string prefix
        "customer_name":  "ELITE CONTRACTORS",  # partial match
    },
}

TEST_DOCS = [
    {"path": ELITE_ROOT / "Skylark PO.pdf",
     "doc_type": "COMPANY_PO",        "label": "Skylark PO"},
    {"path": ELITE_ROOT / "C240847449 1OTM2526001448-Vendor Invoice.pdf",
     "doc_type": "VENDOR_INVOICE",    "label": "Redington Tax Invoice"},
    {"path": ELITE_ROOT / "PO (2).pdf",
     "doc_type": "CUSTOMER_PO",       "label": "Elite Customer PO"},
    {"path": ELITE_ROOT / "1DNT2526DC2865.pdf",
     "doc_type": "COMPANY_DC",        "label": "Company DC"},
    {"path": ELITE_ROOT / "1ITR2526001748.pdf",
     "doc_type": "COMPANY_INVOICE",   "label": "Company Invoice"},
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def W(n, s): return str(s)[:n].ljust(n)  # pad/truncate to width n

def ms(v): return f"{v/1000:.2f}s" if v else "—"

def check_field(key, got, expected_map):
    """Returns (match_str, ok_bool). Partial match for long string fields."""
    exp = expected_map.get(key)
    if exp is None:
        return "—", None
    got_str = str(got) if got is not None else ""
    ok = exp.lower() in got_str.lower() or got_str.lower().startswith(exp.lower())
    return exp, ok


# ── API calls ─────────────────────────────────────────────────────────────────

def get_or_create_customer(client: httpx.Client, base: str) -> dict:
    """Return first existing customer or create a test one."""
    r = client.get(f"{base}/api/v1/customers", params={"per_page": 1})
    r.raise_for_status()
    items = r.json().get("items", [])
    if items:
        return items[0]
    # Create test customer
    r = client.post(f"{base}/api/v1/customers", json={
        "name": "E2E Test Customer",
        "customer_id": "E2E-TEST",
        "contact_email": "test@e2e.local",
    })
    r.raise_for_status()
    return r.json()


def create_test_po(client: httpx.Client, base: str, customer_id: str) -> dict:
    """Create a fresh PO for the E2E run."""
    ts = datetime.utcnow().strftime("%m%d%H%M%S")
    po_number = f"E2E-{ts}"
    r = client.post(f"{base}/api/v1/purchase-orders", json={
        "customer_id": customer_id,
        "po_number": po_number,
    })
    r.raise_for_status()
    return r.json()


def upload_document(client: httpx.Client, base: str, po_id: str, doc: dict) -> tuple[dict, float]:
    """Upload document. Returns (response_json, upload_time_s)."""
    path = doc["path"]
    t0 = time.perf_counter()
    with open(path, "rb") as f:
        r = client.post(
            f"{base}/api/v1/purchase-orders/{po_id}/documents",
            data={"document_type": doc["doc_type"]},
            files={"file": (path.name, f, "application/pdf")},
            timeout=HTTP_TIMEOUT,
        )
    upload_s = time.perf_counter() - t0
    r.raise_for_status()
    return r.json(), upload_s


def poll_document(client: httpx.Client, base: str, doc_id: str) -> tuple[dict | None, float]:
    """Poll until document leaves EXTRACTING/UPLOADED state. Returns (doc_json, wait_s)."""
    t0 = time.perf_counter()
    deadline = t0 + POLL_TIMEOUT
    while time.perf_counter() < deadline:
        r = client.get(f"{base}/api/v1/documents/{doc_id}", timeout=HTTP_TIMEOUT)
        if r.status_code == 200:
            d = r.json()
            status = d.get("status", "")
            if status not in ("UPLOADED", "EXTRACTING"):
                return d, time.perf_counter() - t0
        time.sleep(POLL_INTERVAL)
    return None, time.perf_counter() - t0


def delete_test_po(client: httpx.Client, base: str, po_id: str):
    """Clean up test PO after run."""
    try:
        client.delete(f"{base}/api/v1/purchase-orders/{po_id}", timeout=HTTP_TIMEOUT)
    except Exception:
        pass


# ── Report ────────────────────────────────────────────────────────────────────

SEP = "─" * 100

def print_doc_result(doc: dict, upload_s: float, poll_s: float, result: dict | None):
    doc_type = doc["doc_type"]
    label = doc["label"]

    print(f"\n{SEP}")
    print(f"  DOC: {label}  [{doc_type}]")
    print(f"  FILE: {doc['path'].name}  ({doc['path'].stat().st_size // 1024} KB)")
    print(SEP)

    if result is None:
        print(f"  ✗ TIMED OUT after {poll_s:.1f}s")
        return

    status = result.get("status", "UNKNOWN")
    meta   = result.get("metadata") or {}
    extracted = meta.get("extracted_data") or {}
    proc_ms   = meta.get("processing_time_ms") or 0
    confidence = meta.get("confidence_score") or 0
    last_error = meta.get("last_error") or ""

    total_s = upload_s + poll_s
    queue_s = max(0.0, total_s - upload_s - proc_ms / 1000)

    # ── Timing table ──
    print(f"  {'Phase':<20} {'Time':>10}")
    print(f"  {'─'*20} {'─'*10}")
    print(f"  {'Upload (HTTP)':20} {upload_s:>9.2f}s")
    if proc_ms:
        print(f"  {'Queue + PDF conv':20} {queue_s:>9.2f}s")
        print(f"  {'OCR + Extract':20} {proc_ms/1000:>9.2f}s  ← internal")
    print(f"  {'Total E2E':20} {total_s:>9.2f}s")
    print(f"  Status: {status}  |  Confidence: {confidence}%")
    if last_error:
        print(f"  Error: {last_error[:120]}")

    # ── Field comparison table ──
    expected_map = EXPECTED.get(doc_type, {})
    if not expected_map:
        return

    print()
    col = 24
    hdr = f"  {'Field':{col}}  {'Extracted':{col}}  {'Expected':{col}}  {'OK':^4}"
    print(hdr)
    print(f"  {'─'*col}  {'─'*col}  {'─'*col}  {'─'*4}")

    all_ok = True
    for field, exp in expected_map.items():
        got = extracted.get(field)
        got_str = str(got) if got is not None else "(none)"
        _, ok = check_field(field, got, expected_map)
        ok_icon = "✅" if ok else "❌"
        if not ok:
            all_ok = False
        print(f"  {W(col, field)}  {W(col, got_str)}  {W(col, exp)}  {ok_icon}")

    # Also show any other extracted fields not in expected
    for field, val in extracted.items():
        if field not in expected_map and not field.startswith("_") and val is not None:
            print(f"  {W(col, field)}  {W(col, str(val))}  {'(extra)':^{col}}  {'ℹ️':^4}")

    summary = "ALL CORRECT ✅" if all_ok else "SOME FIELDS WRONG ❌"
    print(f"\n  {summary}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="E2E pipeline test")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--doc", help="Run only this doc_type (e.g. COMPANY_INVOICE)")
    parser.add_argument("--no-cleanup", action="store_true", help="Keep test PO after run")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")

    docs = TEST_DOCS
    if args.doc:
        docs = [d for d in TEST_DOCS if d["doc_type"] == args.doc.upper()]
        if not docs:
            print(f"Unknown doc type: {args.doc}")
            sys.exit(1)

    # Verify files exist
    missing = [d["path"] for d in docs if not d["path"].exists()]
    if missing:
        print("Missing test files:")
        for p in missing:
            print(f"  {p}")
        sys.exit(1)

    width = 100
    print("=" * width)
    print(f"  E2E PIPELINE TEST  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Backend : {base}")
    print(f"  Models  : qwen2.5vl:7b (Layer 1) + qwen2.5:7b (Layer 2)")
    print(f"  Docs    : {len(docs)} document(s)")
    print("=" * width)

    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        # Check backend is up
        try:
            client.get(f"{base}/health", timeout=5)
        except Exception:
            pass  # /health may not exist — continue anyway

        # Get/create customer + PO
        print("\n  Setting up test PO...")
        try:
            customer = get_or_create_customer(client, base)
        except Exception as e:
            print(f"\n  ✗ Cannot reach backend at {base}: {e}")
            sys.exit(1)

        po = create_test_po(client, base, customer["id"])
        print(f"  Customer : {customer.get('name')} ({customer.get('customer_id')})")
        print(f"  PO       : {po['po_number']} (id={po['id'][:8]}...)")

        results_summary = []

        for doc in docs:
            print(f"\n  Uploading {doc['doc_type']}: {doc['path'].name} ...", end="", flush=True)
            try:
                resp, upload_s = upload_document(client, base, po["id"], doc)
            except Exception as e:
                print(f"\n  ✗ Upload failed: {e}")
                results_summary.append((doc["doc_type"], "UPLOAD_FAILED", 0, 0))
                continue

            doc_id = resp.get("id") or resp.get("document_id")
            print(f" uploaded in {upload_s:.2f}s. Polling...", end="", flush=True)

            final, poll_s = poll_document(client, base, doc_id)
            status = final.get("status", "TIMEOUT") if final else "TIMEOUT"
            print(f" {status} ({upload_s + poll_s:.1f}s total)")

            print_doc_result(doc, upload_s, poll_s, final)

            proc_ms = (final.get("metadata") or {}).get("processing_time_ms") or 0
            results_summary.append((doc["doc_type"], status, upload_s + poll_s, proc_ms))

        # ── Overall summary ────────────────────────────────────────────────
        print(f"\n{'=' * width}")
        print("  SUMMARY")
        print(f"{'=' * width}")
        print(f"  {'Doc Type':<22}  {'Status':<20}  {'Total':>8}  {'OCR+Ext':>8}")
        print(f"  {'─'*22}  {'─'*20}  {'─'*8}  {'─'*8}")
        for dt, st, total_s, proc_ms in results_summary:
            ok = "✅" if "PENDING" in st or "VERIFIED" in st else "❌"
            print(f"  {W(22, dt)}  {W(20, st)}  {total_s:>7.1f}s  {proc_ms/1000:>7.1f}s  {ok}")
        print("=" * width)

        # Cleanup
        if not args.no_cleanup:
            delete_test_po(client, base, po["id"])
            print(f"\n  Test PO {po['po_number']} deleted.")
        else:
            print(f"\n  Test PO {po['po_number']} kept (--no-cleanup).")


if __name__ == "__main__":
    main()
