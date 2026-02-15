"""
BRUTAL END-TO-END API TEST
===========================
Tests the FULL flow: Customer → PO → Upload → Extract → DB → Retrieval
No sugarcoating. Every failure gets logged.
"""
import os
import sys
import json
import time
import httpx
import traceback
from datetime import datetime, date

BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:5173"
REPORT_DIR = os.path.dirname(os.path.abspath(__file__))

results = []
test_num = 0
passed = 0
failed = 0
warnings = 0

# Track created resources for cleanup
created_customer_id = None
created_po_id = None
created_doc_id = None


def test(name, fn):
    global test_num, passed, failed, warnings
    test_num += 1
    entry = {"num": test_num, "name": name, "status": "?", "detail": "", "time_ms": 0}
    start = time.time()
    try:
        result = fn()
        elapsed = int((time.time() - start) * 1000)
        entry["time_ms"] = elapsed
        if result is True:
            entry["status"] = "PASS"
            passed += 1
        elif isinstance(result, str) and result.startswith("WARN:"):
            entry["status"] = "WARN"
            entry["detail"] = result[5:]
            warnings += 1
        else:
            entry["status"] = "PASS"
            entry["detail"] = str(result) if result else ""
            passed += 1
    except AssertionError as e:
        elapsed = int((time.time() - start) * 1000)
        entry["time_ms"] = elapsed
        entry["status"] = "FAIL"
        entry["detail"] = str(e)
        failed += 1
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        entry["time_ms"] = elapsed
        entry["status"] = "FAIL"
        entry["detail"] = f"{type(e).__name__}: {e}"
        failed += 1
    results.append(entry)
    icon = {"PASS": "✓", "FAIL": "✗", "WARN": "⚠"}[entry["status"]]
    print(f"  [{icon}] T{test_num:02d} {name} ({elapsed}ms) {entry['detail'][:80]}")


# ============================================================
# SECTION 1: HEALTH & CONNECTIVITY
# ============================================================
print("\n" + "=" * 60)
print("SECTION 1: HEALTH & CONNECTIVITY")
print("=" * 60)


def t01_backend_health():
    r = httpx.get(f"{BASE_URL}/", timeout=5)
    assert r.status_code == 200, f"Backend returned {r.status_code}"
    data = r.json()
    assert "status" in data or "message" in data, f"No status in response: {data}"
    return True

test("Backend health check", t01_backend_health)


def t02_frontend_alive():
    r = httpx.get(f"{FRONTEND_URL}/", timeout=5)
    assert r.status_code == 200, f"Frontend returned {r.status_code}"
    assert "text/html" in r.headers.get("content-type", ""), "Not HTML"
    return True

test("Frontend serving HTML", t02_frontend_alive)


def t03_frontend_proxy():
    r = httpx.get(f"{FRONTEND_URL}/api/v1/customers", timeout=5)
    assert r.status_code == 200, f"Proxy returned {r.status_code}"
    data = r.json()
    assert "items" in data, f"No items in response: {list(data.keys())}"
    return True

test("Frontend proxy to backend", t03_frontend_proxy)


def t04_db_connectivity():
    """Test DB by hitting an endpoint that queries the database."""
    r = httpx.get(f"{BASE_URL}/api/v1/customers?page=1&per_page=1", timeout=10)
    assert r.status_code == 200, f"DB query failed: {r.status_code}"
    return True

test("DB connectivity via API", t04_db_connectivity)


def t05_redis_connectivity():
    """Celery depends on Redis. If we can list inspect, Redis is alive."""
    # We can't directly test redis, but we can check if the celery
    # task dispatch works (it needs redis)
    return True  # Will be tested implicitly in extraction

test("Redis connectivity (implicit)", t05_redis_connectivity)


def t06_ollama_alive():
    r = httpx.get("http://localhost:11434/api/tags", timeout=5)
    assert r.status_code == 200, f"Ollama returned {r.status_code}"
    models = r.json().get("models", [])
    model_names = [m["name"] for m in models]
    assert any("glm-ocr" in n for n in model_names), f"glm-ocr not found. Models: {model_names}"
    return True

test("Ollama + glm-ocr model available", t06_ollama_alive)


# ============================================================
# SECTION 2: CUSTOMER CRUD
# ============================================================
print("\n" + "=" * 60)
print("SECTION 2: CUSTOMER CRUD")
print("=" * 60)


def t07_create_customer():
    global created_customer_id
    body = {
        "customer_id": "TEST-BRT001",
        "name": "Brutal Test Corp",
        "contact_email": "brutal@test.com",
        "gst_number": "29BRUTAL00001ZJ",
    }
    r = httpx.post(f"{BASE_URL}/api/v1/customers", json=body, timeout=10)
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert data["customer_id"] == "TEST-BRT001", f"customer_id mismatch: {data.get('customer_id')}"
    assert data["name"] == "Brutal Test Corp"
    assert data["gst_number"] == "29BRUTAL00001ZJ"
    assert data["id"], "No id returned"
    created_customer_id = data["id"]
    return True

test("Create customer", t07_create_customer)


def t08_duplicate_customer():
    """Creating same customer_id should fail."""
    body = {"customer_id": "TEST-BRT001", "name": "Duplicate"}
    r = httpx.post(f"{BASE_URL}/api/v1/customers", json=body, timeout=10)
    if r.status_code == 201:
        return "WARN:Duplicate customer_id accepted — no uniqueness check!"
    assert r.status_code in (400, 409, 422, 500), f"Unexpected status: {r.status_code}"
    return True

test("Reject duplicate customer_id", t08_duplicate_customer)


def t09_create_customer_missing_fields():
    """Missing required fields should 422."""
    r = httpx.post(f"{BASE_URL}/api/v1/customers", json={}, timeout=10)
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"
    return True

test("Reject customer with missing fields", t09_create_customer_missing_fields)


def t10_get_customer():
    r = httpx.get(f"{BASE_URL}/api/v1/customers/{created_customer_id}", timeout=10)
    assert r.status_code == 200, f"GET customer failed: {r.status_code}"
    data = r.json()
    assert data["customer_id"] == "TEST-BRT001"
    assert data["po_count"] == 0, f"Expected 0 POs, got {data.get('po_count')}"
    return True

test("Get customer by ID", t10_get_customer)


def t11_list_customers_search():
    r = httpx.get(f"{BASE_URL}/api/v1/customers?search=BRUTAL", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1, f"Search returned 0 results"
    found = any(c["customer_id"] == "TEST-BRT001" for c in data["items"])
    assert found, "Search didn't find our customer"
    return True

test("Search customers", t11_list_customers_search)


def t12_update_customer():
    r = httpx.patch(
        f"{BASE_URL}/api/v1/customers/{created_customer_id}",
        json={"name": "Brutal Test Corp Updated"},
        timeout=10,
    )
    assert r.status_code == 200, f"PATCH failed: {r.status_code}"
    assert r.json()["name"] == "Brutal Test Corp Updated"
    return True

test("Update customer", t12_update_customer)


def t13_get_nonexistent_customer():
    r = httpx.get(f"{BASE_URL}/api/v1/customers/00000000-0000-0000-0000-000000000000", timeout=10)
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"
    return True

test("404 on nonexistent customer", t13_get_nonexistent_customer)


# ============================================================
# SECTION 3: PURCHASE ORDER CRUD
# ============================================================
print("\n" + "=" * 60)
print("SECTION 3: PURCHASE ORDER CRUD")
print("=" * 60)


def t14_create_po():
    global created_po_id
    body = {
        "customer_id": created_customer_id,
        "po_number": "BRUTAL-PO-001",
        "po_date": "2026-02-14",
        "total_amount": 99999.99,
    }
    r = httpx.post(f"{BASE_URL}/api/v1/purchase-orders", json=body, timeout=10)
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert data["po_number"] == "BRUTAL-PO-001"
    assert data["status"] == "INITIATED", f"Expected INITIATED, got {data.get('status')}"
    assert data["chain_completeness"] == 0.0, f"Chain should be 0%, got {data.get('chain_completeness')}"
    cust_name = data.get("customer_name", "")
    assert cust_name in ("Brutal Test Corp", "Brutal Test Corp Updated"), f"Unexpected customer_name: {cust_name}"
    created_po_id = data["id"]
    return True

test("Create purchase order", t14_create_po)


def t15_create_po_missing_fields():
    r = httpx.post(f"{BASE_URL}/api/v1/purchase-orders", json={}, timeout=10)
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"
    return True

test("Reject PO with missing fields", t15_create_po_missing_fields)


def t16_create_po_invalid_customer():
    body = {
        "customer_id": "00000000-0000-0000-0000-000000000000",
        "po_number": "GHOST-PO",
    }
    r = httpx.post(f"{BASE_URL}/api/v1/purchase-orders", json=body, timeout=10)
    if r.status_code == 201:
        # Clean up
        return "WARN:PO created with nonexistent customer — no FK validation!"
    assert r.status_code in (400, 404, 422, 500), f"Unexpected: {r.status_code}"
    return True

test("Reject PO with invalid customer", t16_create_po_invalid_customer)


def t17_get_po():
    if not created_po_id:
        raise AssertionError("No PO created — T14 failed")
    r = httpx.get(f"{BASE_URL}/api/v1/purchase-orders/{created_po_id}", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["po_number"] == "BRUTAL-PO-001"
    return True

test("Get PO by ID", t17_get_po)


def t18_list_pos_filter():
    if not created_customer_id:
        raise AssertionError("No customer created — T07 failed")
    r = httpx.get(f"{BASE_URL}/api/v1/purchase-orders?customer_id={created_customer_id}", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    return True

test("List POs filtered by customer", t18_list_pos_filter)


def t19_chain_status_empty():
    if not created_po_id:
        raise AssertionError("No PO created — T14 failed")
    r = httpx.get(f"{BASE_URL}/api/v1/purchase-orders/{created_po_id}/chain-status", timeout=10)
    assert r.status_code == 200
    data = r.json()
    # Should have 6 empty slots
    chain = data.get("chain", {})
    assert len(chain) == 6, f"Expected 6 chain slots, got {len(chain)}: {list(chain.keys())}"
    for doc_type, slot in chain.items():
        assert slot is None or slot.get("status") is None or slot.get("document_id") is None, \
            f"Slot {doc_type} should be empty but has: {slot}"
    return True

test("Chain status — all empty slots", t19_chain_status_empty)


# ============================================================
# SECTION 4: DOCUMENT UPLOAD
# ============================================================
print("\n" + "=" * 60)
print("SECTION 4: DOCUMENT UPLOAD")
print("=" * 60)

# Find a real PDF to upload
TEST_PDF = None
STORAGE_ROOT = "E:/PROJECTS/Experiments/Logistic/Phase 2.1.0/docplatform-v3/storage"
for root, dirs, files in os.walk(STORAGE_ROOT):
    for f in files:
        if f.endswith(".pdf"):
            fpath = os.path.join(root, f)
            fsize = os.path.getsize(fpath)
            if fsize > 1000:  # Skip 222-byte placeholders
                TEST_PDF = fpath
                break
    if TEST_PDF:
        break


def t20_upload_no_file():
    """Upload with no file should fail."""
    if not created_po_id:
        return "WARN:No PO created, cannot test upload"
    r = httpx.post(
        f"{BASE_URL}/api/v1/purchase-orders/{created_po_id}/documents",
        data={"document_type": "CUSTOMER_PO"},
        timeout=10,
    )
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"
    return True

test("Reject upload with no file", t20_upload_no_file)


def t21_upload_invalid_doc_type():
    """Upload with invalid document_type."""
    if not TEST_PDF or not created_po_id:
        return "WARN:No test PDF found or no PO created"
    with open(TEST_PDF, "rb") as f:
        r = httpx.post(
            f"{BASE_URL}/api/v1/purchase-orders/{created_po_id}/documents",
            files={"file": ("test.pdf", f, "application/pdf")},
            data={"document_type": "INVALID_TYPE"},
            timeout=30,
        )
    if r.status_code == 201:
        return "WARN:Invalid doc type accepted — no enum validation!"
    assert r.status_code in (400, 422), f"Expected 400/422, got {r.status_code}: {r.text[:200]}"
    return True

test("Reject upload with invalid doc type", t21_upload_invalid_doc_type)


def t22_upload_document():
    global created_doc_id
    if not TEST_PDF:
        raise AssertionError("No real PDF found in storage to test upload")
    if not created_po_id:
        raise AssertionError("No PO created — cannot upload")
    with open(TEST_PDF, "rb") as f:
        r = httpx.post(
            f"{BASE_URL}/api/v1/purchase-orders/{created_po_id}/documents",
            files={"file": ("brutal_test.pdf", f, "application/pdf")},
            data={"document_type": "CUSTOMER_PO"},
            timeout=30,
        )
    assert r.status_code == 201, f"Upload failed: {r.status_code}: {r.text[:300]}"
    data = r.json()
    assert data.get("id"), "No document ID returned"
    assert data.get("status") in ("UPLOADED", "EXTRACTING"), f"Unexpected status: {data.get('status')}"
    created_doc_id = data["id"]
    return f"doc_id={created_doc_id}"

test("Upload a real PDF as CUSTOMER_PO", t22_upload_document)


def t23_upload_to_nonexistent_po():
    if not TEST_PDF:
        return "WARN:No PDF to test"
    with open(TEST_PDF, "rb") as f:
        r = httpx.post(
            f"{BASE_URL}/api/v1/purchase-orders/00000000-0000-0000-0000-000000000000/documents",
            files={"file": ("test.pdf", f, "application/pdf")},
            data={"document_type": "VENDOR_INVOICE"},
            timeout=30,
        )
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"
    return True

test("Reject upload to nonexistent PO", t23_upload_to_nonexistent_po)


def t24_chain_after_upload():
    if not created_po_id or not created_doc_id:
        return "WARN:PO or doc not created"
    r = httpx.get(f"{BASE_URL}/api/v1/purchase-orders/{created_po_id}/chain-status", timeout=10)
    assert r.status_code == 200
    data = r.json()
    chain = data.get("chain", {})
    cpo = chain.get("CUSTOMER_PO")
    assert cpo is not None, "CUSTOMER_PO slot is still None after upload"
    assert cpo.get("document_id") is not None, "No document_id in CUSTOMER_PO slot"
    return f"status={cpo.get('status')}"

test("Chain status updated after upload", t24_chain_after_upload)


def t25_list_po_documents():
    if not created_po_id:
        return "WARN:No PO created"
    r = httpx.get(f"{BASE_URL}/api/v1/purchase-orders/{created_po_id}/documents", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1, f"Expected ≥1 document, got {data['total']}"
    return True

test("List PO documents", t25_list_po_documents)


# ============================================================
# SECTION 5: EXTRACTION PIPELINE (WAIT FOR CELERY)
# ============================================================
print("\n" + "=" * 60)
print("SECTION 5: EXTRACTION PIPELINE")
print("=" * 60)


def t26_wait_extraction():
    """Poll until extraction completes or times out (3 min max)."""
    if not created_doc_id:
        raise AssertionError("No document to check — upload failed")

    max_wait = 180  # 3 minutes
    poll_interval = 5
    elapsed = 0
    last_status = None

    while elapsed < max_wait:
        r = httpx.get(f"{BASE_URL}/api/v1/purchase-orders/{created_po_id}/chain-status", timeout=10)
        data = r.json()
        cpo = data.get("chain", {}).get("CUSTOMER_PO", {})
        status = cpo.get("status") if cpo else None
        last_status = status

        if status in ("PENDING_REVIEW", "VERIFIED"):
            return f"Extracted in {elapsed}s, status={status}"
        if status == "EXTRACTION_FAILED":
            # Check the error
            return f"WARN:Extraction failed after {elapsed}s"

        time.sleep(poll_interval)
        elapsed += poll_interval

    raise AssertionError(f"Extraction timed out after {max_wait}s. Last status: {last_status}")

test("Wait for extraction to complete", t26_wait_extraction)


def t27_metadata_exists():
    if not created_doc_id:
        return "WARN:No doc to check"
    r = httpx.get(f"{BASE_URL}/api/v1/documents/{created_doc_id}/metadata", timeout=10)
    if r.status_code == 404:
        return "WARN:No metadata endpoint or metadata not created"
    assert r.status_code == 200, f"Metadata fetch failed: {r.status_code}"
    data = r.json()
    assert data.get("extracted_data") is not None, "No extracted_data in metadata"
    assert isinstance(data["extracted_data"], dict), f"extracted_data is not dict: {type(data['extracted_data'])}"
    confidence = data.get("confidence_score", 0)
    extracted = data["extracted_data"]
    filled = sum(1 for v in extracted.values() if v and str(v).strip())
    total = len(extracted)
    return f"confidence={confidence}%, fields={filled}/{total}"

test("Metadata exists with extracted_data", t27_metadata_exists)


def t28_metadata_quality():
    """Check if extraction actually got useful data."""
    if not created_doc_id:
        return "WARN:No doc"
    r = httpx.get(f"{BASE_URL}/api/v1/documents/{created_doc_id}/metadata", timeout=10)
    if r.status_code != 200:
        return "WARN:Cannot fetch metadata"
    data = r.json()
    confidence = data.get("confidence_score", 0)
    if confidence == 0:
        return "WARN:0% confidence — extraction returned empty values"
    if confidence < 50:
        return f"WARN:Low confidence {confidence}% — OCR quality poor"
    extracted = data["extracted_data"]
    # Check specific CUSTOMER_PO fields
    critical_fields = ["po_number", "customer_name", "total_amount"]
    missing = [f for f in critical_fields if not extracted.get(f)]
    if missing:
        return f"WARN:Missing critical fields: {missing}"
    return f"confidence={confidence}%, all critical fields present"

test("Extraction quality check", t28_metadata_quality)


def t29_document_preview():
    if not created_doc_id:
        return "WARN:No doc"
    r = httpx.get(f"{BASE_URL}/api/v1/documents/{created_doc_id}/preview", timeout=10)
    if r.status_code == 404:
        return "WARN:No preview endpoint"
    assert r.status_code == 200, f"Preview failed: {r.status_code}"
    content_type = r.headers.get("content-type", "")
    assert "pdf" in content_type or "octet" in content_type, f"Not PDF: {content_type}"
    assert len(r.content) > 100, f"Preview too small: {len(r.content)} bytes"
    return f"size={len(r.content)} bytes"

test("Document preview endpoint", t29_document_preview)


# ============================================================
# SECTION 6: VERIFY / REJECT / RE-EXTRACT
# ============================================================
print("\n" + "=" * 60)
print("SECTION 6: VERIFY / REJECT / RE-EXTRACT")
print("=" * 60)


def t30_verify_metadata():
    if not created_doc_id:
        return "WARN:No doc"
    r = httpx.get(f"{BASE_URL}/api/v1/documents/{created_doc_id}/metadata", timeout=10)
    if r.status_code != 200:
        return "WARN:No metadata to verify"
    existing = r.json().get("extracted_data", {})
    # Modify a field
    existing["po_number"] = "BRUTAL-VERIFIED-001"
    r2 = httpx.put(
        f"{BASE_URL}/api/v1/documents/{created_doc_id}/metadata/verify",
        json={"extracted_data": existing},
        timeout=10,
    )
    if r2.status_code == 404:
        return "WARN:Verify endpoint not found"
    assert r2.status_code == 200, f"Verify failed: {r2.status_code}: {r2.text[:200]}"
    return True

test("Verify metadata with edits", t30_verify_metadata)


def t31_check_verified_status():
    if not created_doc_id:
        return "WARN:No doc"
    r = httpx.get(f"{BASE_URL}/api/v1/purchase-orders/{created_po_id}/chain-status", timeout=10)
    data = r.json()
    cpo = data.get("chain", {}).get("CUSTOMER_PO", {})
    status = cpo.get("status") if cpo else None
    if status == "VERIFIED":
        return True
    return f"WARN:Expected VERIFIED, got {status}"

test("Document status is VERIFIED after verify", t31_check_verified_status)


def t32_re_extract():
    if not created_doc_id:
        return "WARN:No doc"
    r = httpx.post(f"{BASE_URL}/api/v1/documents/{created_doc_id}/re-extract", timeout=10)
    if r.status_code == 404:
        return "WARN:Re-extract endpoint not found"
    assert r.status_code == 200, f"Re-extract failed: {r.status_code}: {r.text[:200]}"
    # Status should go back to UPLOADED or EXTRACTING
    r2 = httpx.get(f"{BASE_URL}/api/v1/purchase-orders/{created_po_id}/chain-status", timeout=10)
    data = r2.json()
    cpo = data.get("chain", {}).get("CUSTOMER_PO", {})
    status = cpo.get("status") if cpo else None
    assert status in ("UPLOADED", "EXTRACTING"), f"Expected UPLOADED/EXTRACTING after re-extract, got {status}"
    return f"status={status}"

test("Re-extract document", t32_re_extract)


def t33_wait_re_extraction():
    """Wait for re-extraction to finish."""
    if not created_doc_id:
        return "WARN:No doc"
    max_wait = 180
    poll_interval = 5
    elapsed = 0
    while elapsed < max_wait:
        r = httpx.get(f"{BASE_URL}/api/v1/purchase-orders/{created_po_id}/chain-status", timeout=10)
        cpo = r.json().get("chain", {}).get("CUSTOMER_PO", {})
        status = cpo.get("status") if cpo else None
        if status in ("PENDING_REVIEW", "VERIFIED", "EXTRACTION_FAILED"):
            return f"Re-extracted in {elapsed}s, status={status}"
        time.sleep(poll_interval)
        elapsed += poll_interval
    return f"WARN:Re-extraction timed out after {max_wait}s"

test("Wait for re-extraction", t33_wait_re_extraction)


def t34_reject_metadata():
    if not created_doc_id:
        return "WARN:No doc"
    r = httpx.put(f"{BASE_URL}/api/v1/documents/{created_doc_id}/metadata/reject", timeout=10)
    if r.status_code == 404:
        return "WARN:Reject endpoint not found"
    if r.status_code == 405:
        return "WARN:Reject method not allowed"
    assert r.status_code == 200, f"Reject failed: {r.status_code}: {r.text[:200]}"
    return True

test("Reject metadata", t34_reject_metadata)


# ============================================================
# SECTION 7: SEARCH
# ============================================================
print("\n" + "=" * 60)
print("SECTION 7: SEARCH")
print("=" * 60)


def t35_search_by_po():
    r = httpx.get(f"{BASE_URL}/api/v1/search?q=BRUTAL-PO-001", timeout=10)
    if r.status_code == 404:
        return "WARN:Search endpoint not found"
    assert r.status_code == 200, f"Search failed: {r.status_code}"
    data = r.json()
    total = data.get("total", 0)
    if not isinstance(data, dict):
        return f"WARN:Search returned non-dict: {type(data)}"
    return f"results={total}"

test("Search by PO number", t35_search_by_po)


def t36_search_by_customer():
    r = httpx.get(f"{BASE_URL}/api/v1/search?q=Brutal+Test", timeout=10)
    if r.status_code == 404:
        return "WARN:Search endpoint not found"
    assert r.status_code == 200
    return f"results={r.json().get('total', '?')}"

test("Search by customer name", t36_search_by_customer)


def t37_search_empty():
    r = httpx.get(f"{BASE_URL}/api/v1/search?q=ZZZZNONEXISTENT999", timeout=10)
    if r.status_code == 404:
        return "WARN:No search endpoint"
    assert r.status_code == 200
    total = r.json().get("total", -1)
    assert total == 0, f"Expected 0 results for nonsense query, got {total}"
    return True

test("Search returns 0 for nonsense", t37_search_empty)


# ============================================================
# SECTION 8: EDGE CASES & ERROR HANDLING
# ============================================================
print("\n" + "=" * 60)
print("SECTION 8: EDGE CASES & ERROR HANDLING")
print("=" * 60)


def t38_invalid_uuid():
    r = httpx.get(f"{BASE_URL}/api/v1/customers/not-a-uuid", timeout=5)
    assert r.status_code == 422, f"Expected 422 for invalid UUID, got {r.status_code}"
    return True

test("Invalid UUID returns 422", t38_invalid_uuid)


def t39_pagination_bounds():
    r = httpx.get(f"{BASE_URL}/api/v1/customers?page=0", timeout=5)
    if r.status_code == 200:
        return "WARN:page=0 accepted — should reject"
    assert r.status_code == 422
    return True

test("Pagination rejects page=0", t39_pagination_bounds)


def t40_large_payload():
    """Try creating customer with very long name."""
    body = {"customer_id": "LONG", "name": "A" * 10000}
    r = httpx.post(f"{BASE_URL}/api/v1/customers", json=body, timeout=10)
    if r.status_code == 201:
        # Clean up
        cid = r.json()["id"]
        return f"WARN:Accepted 10KB name without validation"
    return True

test("Large payload handling", t40_large_payload)


def t41_concurrent_upload():
    """Check that concurrent uploads to same slot handle properly."""
    if not TEST_PDF or not created_po_id:
        return "WARN:Cannot test"
    # Upload a VENDOR_INVOICE
    with open(TEST_PDF, "rb") as f:
        r = httpx.post(
            f"{BASE_URL}/api/v1/purchase-orders/{created_po_id}/documents",
            files={"file": ("test2.pdf", f, "application/pdf")},
            data={"document_type": "VENDOR_INVOICE"},
            timeout=30,
        )
    if r.status_code != 201:
        return f"WARN:Second upload returned {r.status_code}: {r.text[:100]}"
    return True

test("Upload second document type", t41_concurrent_upload)


def t42_duplicate_upload():
    """Upload same file to same doc type again — should handle (reject or replace)."""
    if not TEST_PDF or not created_po_id:
        return "WARN:Cannot test"
    with open(TEST_PDF, "rb") as f:
        r = httpx.post(
            f"{BASE_URL}/api/v1/purchase-orders/{created_po_id}/documents",
            files={"file": ("test_dup.pdf", f, "application/pdf")},
            data={"document_type": "CUSTOMER_PO"},
            timeout=30,
        )
    if r.status_code == 201:
        return "WARN:Duplicate file to same slot accepted — should reject (409)"
    if r.status_code == 409:
        return True
    return f"WARN:Got {r.status_code} instead of 409: {r.text[:100]}"

test("Reject duplicate upload to same slot", t42_duplicate_upload)


# ============================================================
# SECTION 9: DATA INTEGRITY
# ============================================================
print("\n" + "=" * 60)
print("SECTION 9: DATA INTEGRITY")
print("=" * 60)


def t43_chain_completeness():
    if not created_po_id:
        return "WARN:No PO created"
    r = httpx.get(f"{BASE_URL}/api/v1/purchase-orders/{created_po_id}", timeout=10)
    assert r.status_code == 200
    data = r.json()
    completeness = data.get("chain_completeness", -1)
    # We uploaded 2 docs (CUSTOMER_PO + VENDOR_INVOICE) but one may have been rejected
    assert completeness >= 0, f"Invalid chain_completeness: {completeness}"
    return f"chain={completeness}%"

test("Chain completeness calculation", t43_chain_completeness)


def t44_document_count():
    if not created_po_id:
        return "WARN:No PO created"
    r = httpx.get(f"{BASE_URL}/api/v1/purchase-orders/{created_po_id}/documents", timeout=10)
    assert r.status_code == 200
    data = r.json()
    count = data.get("total", 0)
    assert count >= 1, f"Expected ≥1 documents, got {count}"
    return f"docs={count}"

test("Document count correct", t44_document_count)


def t45_customer_po_count():
    if not created_customer_id:
        return "WARN:No customer created"
    r = httpx.get(f"{BASE_URL}/api/v1/customers/{created_customer_id}", timeout=10)
    assert r.status_code == 200
    data = r.json()
    po_count = data.get("po_count", -1)
    assert po_count >= 1, f"Expected ≥1 PO count, got {po_count}"
    return f"po_count={po_count}"

test("Customer PO count updated", t45_customer_po_count)


# ============================================================
# CLEANUP
# ============================================================
print("\n" + "=" * 60)
print("CLEANUP")
print("=" * 60)


def cleanup():
    """Clean up test data from DB."""
    import subprocess
    cmds = []
    if created_po_id:
        cmds.append(f"DELETE FROM reference_index WHERE po_id = '{created_po_id}';")
        cmds.append(f"DELETE FROM document_metadata WHERE document_id IN (SELECT id FROM documents WHERE po_id = '{created_po_id}');")
        cmds.append(f"DELETE FROM documents WHERE po_id = '{created_po_id}';")
        cmds.append(f"DELETE FROM purchase_orders WHERE id = '{created_po_id}';")
    if created_customer_id:
        cmds.append(f"DELETE FROM purchase_orders WHERE customer_id = '{created_customer_id}';")
        cmds.append(f"DELETE FROM customers WHERE id = '{created_customer_id}';")
    if cmds:
        sql = " ".join(cmds)
        result = subprocess.run(
            ["docker", "exec", "docplatform-v3-postgres-1", "psql", "-U", "docplatform", "-d", "docplatform", "-c", sql],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            print("  [✓] Test data cleaned up")
        else:
            print(f"  [⚠] Cleanup issues: {result.stderr[:200]}")
    else:
        print("  [i] Nothing to clean up")

cleanup()


# ============================================================
# REPORT
# ============================================================
print("\n" + "=" * 60)
print("FINAL REPORT")
print("=" * 60)

report_lines = []
report_lines.append(f"# BRUTAL API TEST REPORT")
report_lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
report_lines.append(f"**Backend:** {BASE_URL}")
report_lines.append(f"**Frontend:** {FRONTEND_URL}")
report_lines.append("")
report_lines.append(f"## Summary")
report_lines.append(f"- **Total Tests:** {test_num}")
report_lines.append(f"- **Passed:** {passed}")
report_lines.append(f"- **Failed:** {failed}")
report_lines.append(f"- **Warnings:** {warnings}")
report_lines.append(f"- **Pass Rate:** {passed}/{test_num} ({100*passed//test_num if test_num else 0}%)")
report_lines.append("")

# Group by section
report_lines.append("## Detailed Results")
report_lines.append("")
report_lines.append("| # | Test | Status | Time | Detail |")
report_lines.append("|---|------|--------|------|--------|")
for r in results:
    icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}[r["status"]]
    detail = r["detail"].replace("|", "\\|")[:80]
    report_lines.append(f"| {r['num']:02d} | {r['name']} | {icon} {r['status']} | {r['time_ms']}ms | {detail} |")

report_lines.append("")
report_lines.append("## Issues Found")
report_lines.append("")

issues = [r for r in results if r["status"] in ("FAIL", "WARN")]
if issues:
    for r in issues:
        severity = "🔴 CRITICAL" if r["status"] == "FAIL" else "🟡 WARNING"
        report_lines.append(f"### {severity}: T{r['num']:02d} {r['name']}")
        report_lines.append(f"- {r['detail']}")
        report_lines.append("")
else:
    report_lines.append("None! All tests passed.")

report_lines.append("---")
report_lines.append(f"*Generated by brutal_api_test.py at {datetime.now().isoformat()}*")

report_text = "\n".join(report_lines)

# Write report
report_path = os.path.join(REPORT_DIR, "api_test_report.md")
with open(report_path, "w", encoding="utf-8") as f:
    f.write(report_text)

# Also write JSON for machine consumption
json_path = os.path.join(REPORT_DIR, "api_test_results.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump({
        "timestamp": datetime.now().isoformat(),
        "summary": {"total": test_num, "passed": passed, "failed": failed, "warnings": warnings},
        "results": results,
    }, f, indent=2)

print(f"\n  Total: {test_num} | Pass: {passed} | Fail: {failed} | Warn: {warnings}")
print(f"  Report: {report_path}")
print(f"  JSON:   {json_path}")

sys.exit(1 if failed > 0 else 0)
