from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.document_metadata import DocumentMetadataRecord
from app.repositories.bundles import BundleRepository
from app.repositories.documents import DocumentRepository
from app.repositories.reference_index import ReferenceIndexRepository
from app.schemas.bundle import BundleCreate
from app.services.audit_service import AuditService
from app.services.manual_metadata_service import patch_extracted_data
from app.services.verification_summary_service import sync_bundle_status_from_verification


def seed_panimalar_demo(db: Session) -> dict:
    fixture = _panimalar_fixture()
    bundle = BundleRepository(db).create(
        BundleCreate(
            bundle_number=f"OA-PANIMALAR-DEMO-{str(uuid4())[:8]}",
            customer_name="PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE",
        )
    )
    db.flush()

    docs = {
        "customer_invoice": _create_seed_document(db, bundle.id, "COMPANY_INVOICE", "Customer Invoice 1ITR2526001878.pdf", fixture["customer_invoice"], "digital"),
        "delivery_challan": _create_seed_document(db, bundle.id, "COMPANY_DC", "DC 1DNT2526DC3100.pdf", fixture["delivery_challan"], "digital"),
        "vendor_po": _create_seed_document(db, bundle.id, "COMPANY_PO", "Vendor PO 1PTR2526000467.pdf", fixture["vendor_po"], "digital"),
        "vendor_invoice": _create_seed_document(db, bundle.id, "VENDOR_INVOICE", "Vendor Bill 2526PSI25087738.pdf", fixture["vendor_bill_manual_expected"], "manual_entry"),
    }

    summary = sync_bundle_status_from_verification(db, bundle.id)
    return {"bundle": bundle, "documents": docs, "verification_summary": summary}


def _create_seed_document(
    db: Session,
    bundle_id: str,
    document_type: str,
    filename: str,
    fields: dict,
    route: str,
):
    document = DocumentRepository(db).create(
        bundle_id=bundle_id,
        document_type=document_type,
        filename=filename,
        content_type="application/pdf",
        storage_path=None,
    )
    metadata: DocumentMetadataRecord = document.metadata_record
    if route == "manual_entry":
        result = patch_extracted_data(
            document=document,
            metadata=metadata,
            fields=fields,
            audit_service=AuditService(db),
            actor="seed",
            reason="Seeded Panimalar demo manual fallback.",
        )
        extracted = result["metadata"].extracted_data
    else:
        extracted = dict(fields)
        extracted["extraction_source"] = "seeded_fixture"
        metadata.extracted_data = extracted
        metadata.status = "EXTRACTED"
        metadata.diagnostics = {"extraction_route": route, "parser_route": "seed_fixture", "parser_confidence": 100.0}
        document.status = "PENDING_REVIEW"
    ReferenceIndexRepository(db).replace_for_document(
        document.id,
        extracted,
        bundle_id,
        document_type=document.document_type,
        diagnostics=metadata.diagnostics,
    )
    db.flush()
    return document


def _panimalar_fixture() -> dict:
    candidates = []
    if os.getenv("ORDER_ASSURANCE_SHARED_DIR"):
        candidates.append(Path(os.environ["ORDER_ASSURANCE_SHARED_DIR"]))
    module_path = Path(__file__).resolve()
    candidates.extend(
        [
            module_path.parents[3] / "shared",
            module_path.parents[2] / "shared",
            Path.cwd() / "shared",
        ]
    )
    for shared_dir in candidates:
        path = shared_dir / "fixtures" / "panimalar_expected.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["expected"]
    searched = ", ".join(str(path / "fixtures" / "panimalar_expected.json") for path in candidates)
    raise FileNotFoundError(f"Panimalar fixture not found. Searched: {searched}")
