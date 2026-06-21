"""Upload all sample bundles to the Order Assurance platform."""
import sys, json
from pathlib import Path
import urllib.request, urllib.error
import mimetypes, uuid, io

BASE = "http://localhost:8100/api"
SAMPLE = Path(__file__).parent.parent / "sample" / "extracted"


def post_json(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{BASE}{path}", data=body,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def upload_file(bundle_id, file_path, doc_type):
    boundary = uuid.uuid4().hex
    file_path = Path(file_path)
    file_bytes = file_path.read_bytes()
    mime = mimetypes.guess_type(file_path.name)[0] or "application/pdf"

    body = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="document_type"\r\n\r\n'
        f'{doc_type}\r\n'
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
        f'Content-Type: {mime}\r\n\r\n'
    ).encode() + file_bytes + f'\r\n--{boundary}--\r\n'.encode()

    req = urllib.request.Request(
        f"{BASE}/bundles/{bundle_id}/documents",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            resp = json.loads(r.read())
            print(f"    OK [{doc_type}]: {file_path.name}")
            return resp
    except urllib.error.HTTPError as e:
        print(f"    ERROR [{doc_type}]: {file_path.name} → {e.code} {e.read().decode()}")


def create_bundle(number, customer, po, so):
    resp = post_json("/bundles", {
        "bundle_number": number,
        "customer_name": customer,
        "customer_po_no": po,
        "so_no": so,
    })
    bid = resp["id"]
    print(f"  Created: {bid}  [{number}]")
    return bid


# ── 1. PANIMALAR ─────────────────────────────────────────────────────────────
print("\n=== Panimalar ===")
bid = create_bundle("Panimalar-001", "PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE",
                    "PNM/WO/2021-2022", "SO-PNM-001")
d = SAMPLE / "Panimalar"
upload_file(bid, d / "Customer PO_.pdf",                    "CUSTOMER_PO")
upload_file(bid, d / "Customer Invoice 1ITR2526001878.pdf", "CUSTOMER_INVOICE")
upload_file(bid, d / "DC 1DNT2526DC3100.pdf",               "DELIVERY_CHALLAN")
upload_file(bid, d / "Vendor PO 1PTR2526000467.pdf",        "VENDOR_PO")
upload_file(bid, d / "Vendor Bill 2526PSI25087738.pdf",     "VENDOR_INVOICE")

# ── 2. SRIRAM FINANCE ────────────────────────────────────────────────────────
print("\n=== Sriram Finance ===")
bid = create_bundle("SriramFin-001", "SHRIRAM FINANCE LIMITED",
                    "PO-SRIRAM-2526", "SO-SRIRAM-001")
d = SAMPLE / "Sriram fin"
upload_file(bid, d / "Purchase order shriram fin.pdf",  "CUSTOMER_PO")
upload_file(bid, d / "Tax Invoice Shriram fin.pdf",     "CUSTOMER_INVOICE")
upload_file(bid, d / "PO AMC corro health.pdf",         "VENDOR_PO")
upload_file(bid, d / "Tax invoice corro health.pdf",    "VENDOR_INVOICE")
upload_file(bid, d / "Purchase order Inflow.pdf",       "VENDOR_PO")
upload_file(bid, d / "Tax invoice inflow AMC.pdf",      "VENDOR_INVOICE")
upload_file(bid, d / "purchase order reddington.pdf",   "VENDOR_PO")
upload_file(bid, d / "Tax invoice reddington.pdf",      "VENDOR_INVOICE")

# ── 3. TRADE ─────────────────────────────────────────────────────────────────
print("\n=== Trade ===")
bid = create_bundle("Trade-001", "TRADE CUSTOMER", "TRADE-CPO-2526", "SO-TRADE-001")
d = SAMPLE / "Trade" / "Trade"
upload_file(bid, d / "TRADE - CUSTOMER PO.pdf",             "CUSTOMER_PO")
upload_file(bid, d / "TRADE - INVOICE 1ITR2526001785.pdf",  "CUSTOMER_INVOICE")
upload_file(bid, d / "TRADE - DC 1DNT2526DC2915.pdf",       "DELIVERY_CHALLAN")
upload_file(bid, d / "TRADE - PURCHASE ORDER.pdf",          "VENDOR_PO")
upload_file(bid, d / "TRADE - VENDOR BILL -C190224826.pdf", "VENDOR_INVOICE")
upload_file(bid, d / "TRADE -VENDOR BILL - C190224835.pdf", "VENDOR_INVOICE")

print("\nAll done.")
