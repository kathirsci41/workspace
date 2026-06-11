"""Phase 1e Panimalar extraction regression.

Re-extracts the 5 Panimalar documents from the accepted validation run
(real-doc-001-tradefix-final8) using the current codebase and confirms
all baseline fields are preserved.

Skips automatically if:
  - RUN_PANIMALAR_OCR_REGRESSION env var is not set to "1", or
  - the validation run storage is not present on disk.

To run manually:
  RUN_PANIMALAR_OCR_REGRESSION=1 python -m pytest tests/integration/test_panimalar_regression_phase1e.py -q
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

if not os.getenv("RUN_PANIMALAR_OCR_REGRESSION"):
    pytest.skip(
        "Skipped: set RUN_PANIMALAR_OCR_REGRESSION=1 to run OCR-dependent Panimalar regression.",
        allow_module_level=True,
    )

from app.config import Settings, replace_settings
from app.migrations.runner import run
from app.models.document import DocumentRecord
from app.models.order_bundle import OrderBundleRecord
from app.services.extraction_service import extract_document

_VAL_RUN = Path(__file__).resolve().parents[3] / "validation-runs" / "real-doc-001-tradefix-final8"
_STORAGE = _VAL_RUN / "storage" / "documents" / "c3f3810a-5d56-4428-8556-a1e25a7b64cc"

_DOCS = {
    "CUSTOMER_PO":    _STORAGE / "6e748b6e-85c0-4699-a0ff-3a0f13ffa63f_Customer PO_.pdf",
    "COMPANY_INVOICE": _STORAGE / "8046f33f-470d-4630-969b-2df4584bd838_Customer Invoice 1ITR2526001878.pdf",
    "COMPANY_DC":     _STORAGE / "9b5df38c-01dd-4816-818f-bc266e8a553f_DC 1DNT2526DC3100.pdf",
    "COMPANY_PO":     _STORAGE / "a12ce19d-d349-453a-b9c6-0763cd08635f_Vendor PO 1PTR2526000467.pdf",
    "VENDOR_INVOICE": _STORAGE / "c5638bf9-161e-4cf7-88ac-47f11cf258bb_Vendor Bill 2526PSI25087738.pdf",
}

# Original uploaded filenames from the accepted validation run — used as document.filename
# so parsers see the same name the real app sees (not the UUID-prefixed storage name).
_FILENAMES = {
    "CUSTOMER_PO":    "Customer PO_.pdf",
    "COMPANY_INVOICE": "Customer Invoice 1ITR2526001878.pdf",
    "COMPANY_DC":     "DC 1DNT2526DC3100.pdf",
    "COMPANY_PO":     "Vendor PO 1PTR2526000467.pdf",
    "VENDOR_INVOICE": "Vendor Bill 2526PSI25087738.pdf",
}

_BASELINE = {
    "COMPANY_DC": {
        "dc_no": "1DNT2526DC3100", "dc_date": "13/02/2026",
        "customer_name": "PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE",
        "customer_order_no": "PMCH&RI/024/2025-2026", "so_no": "1OTM2526001611",
        "dc_number": "1DNT2526DC3100", "total_quantity": 9,
        "estimated_amount": 741050, "total_amount": 741050,
    },
    "COMPANY_INVOICE": {
        "invoice_no": "1ITR2526001878", "invoice_date": "13/02/2026",
        "customer_name": "PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE",
        "customer_order_no": "PMCH&RI/024/2025-2026", "so_no": "1OTM2526001611",
        "net_amount": 874439, "tax_amount": 133389, "taxable_amount": 741050,
    },
    "COMPANY_PO": {
        "vendor_po_no": "1PTR2526000467", "po_date": "30/01/2026",
        "mode_of_bill": "ON FULL DELIVERY", "net_amount": 696200,
        "part_shipment_allowed": "NOT ALLOWED", "tax_amount": 106200, "taxable_amount": 590000,
    },
    "CUSTOMER_PO": {
        "customer_po_no": "PMCH&RI/024/2025-2026",
        "customer_po_date": "29.01.2026", "grand_total": 920459,
    },
    "VENDOR_INVOICE": {
        "vendor_invoice_no": "2526PSI25087738", "vendor_invoice_date": "12-02-2026",
        "po_reference": "1PTR2526000467", "taxable_amount": 470000, "invoice_total": 554600,
    },
}


@pytest.fixture(scope="module")
def _extraction_results(tmp_path_factory):
    missing = [name for name, p in _DOCS.items() if not p.exists()]
    if missing:
        pytest.skip(f"Accepted validation PDFs not present: {missing}")

    tmp = tmp_path_factory.mktemp("panimalar_reg")
    db_url = f"sqlite:///{tmp / 'reg.db'}"
    replace_settings(Settings(
        database_url=db_url,
        digital_text_enabled=True,
        structured_rules_enabled=True,
        ocr_enabled=True,
        model_layer2_enabled=False,
        evidence_capture_enabled=False,
    ))
    run("up")
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    db = sessionmaker(bind=engine, autoflush=False, autocommit=False)()

    now = datetime.now(timezone.utc)
    bundle = OrderBundleRecord(
        id=str(uuid4()), bundle_number="PANIMALAR-PHASE1E-REG",
        customer_name="PANIMALAR", created_at=now, updated_at=now,
    )
    db.add(bundle)
    db.flush()

    results = {}
    for doc_type, pdf_path in _DOCS.items():
        doc = DocumentRecord(
            id=str(uuid4()), order_bundle_id=bundle.id,
            document_type=doc_type, filename=_FILENAMES[doc_type],
            storage_path=str(pdf_path), status="UPLOADED",
            created_at=now, updated_at=now,
        )
        db.add(doc)
        db.flush()
        result = extract_document(db, doc, force=True)
        results[doc_type] = {
            "status": result["metadata"].status,
            "extracted_data": dict(result["metadata"].extracted_data or {}),
            "diagnostics": dict(result["metadata"].diagnostics or {}),
        }
        db.expire(doc)

    db.close()
    return results


@pytest.mark.parametrize("doc_type", list(_BASELINE.keys()))
def test_panimalar_field_regression_phase1e(doc_type, _extraction_results):
    result = _extraction_results[doc_type]
    actual = result["extracted_data"]
    expected = _BASELINE[doc_type]
    mismatches = {
        field: {"expected": exp, "actual": actual.get(field)}
        for field, exp in expected.items()
        if actual.get(field) != exp
    }
    assert result["status"] in ("EXTRACTED", "PENDING_REVIEW"), (
        f"{doc_type}: unexpected status {result['status']!r}"
    )
    assert not mismatches, (
        f"{doc_type}: field mismatches vs accepted baseline:\n"
        + "\n".join(f"  {f}: expected={v['expected']!r}, got={v['actual']!r}" for f, v in mismatches.items())
    )


def test_panimalar_vendor_invoice_number_uses_header_ocr_phase1k(_extraction_results):
    diagnostics = _extraction_results["VENDOR_INVOICE"]["diagnostics"]
    source = (
        diagnostics.get("field_metadata", {})
        .get("vendor_invoice_no", {})
        .get("source")
    )
    assert source == "ocr_header"
