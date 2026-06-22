from __future__ import annotations

from datetime import datetime, timezone
from difflib import SequenceMatcher
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.vendor_master import VendorMasterRecord
from app.services.document_normalizer import NormalizedDocument
from app.services.gstin_validator import normalize_gstin, validate_gstin


def upsert_vendor(
    db: Session,
    gstin: str,
    name: str,
    state_code: str | None = None,
    *,
    tenant_id: str = "default",
) -> VendorMasterRecord:
    normalized_gstin = normalize_gstin(gstin)
    valid, reason = validate_gstin(normalized_gstin)
    if not valid:
        raise ValueError(f"Invalid GSTIN: {normalized_gstin or gstin} ({reason})")

    vendor_name = re.sub(r"\s+", " ", str(name or "").strip())
    if not vendor_name:
        raise ValueError("Vendor name is required.")

    now = datetime.now(timezone.utc)
    record = db.get(VendorMasterRecord, normalized_gstin)
    if record is None:
        record = VendorMasterRecord(
            gstin=normalized_gstin,
            tenant_id=tenant_id,
            vendor_name=vendor_name,
            state_code=state_code or normalized_gstin[:2],
            registered_at=now,
            last_seen_at=now,
        )
        db.add(record)
    else:
        record.vendor_name = vendor_name
        record.state_code = state_code or record.state_code or normalized_gstin[:2]
        record.last_seen_at = now
        record.is_active = True
    db.flush()
    return record


def check_vendor(db: Session, gstin: str, invoice_name: str, *, tenant_id: str = "default") -> list[str]:
    normalized_gstin = normalize_gstin(gstin)
    if not normalized_gstin or not invoice_name:
        return []

    record = db.get(VendorMasterRecord, normalized_gstin)
    if record is None or record.tenant_id != tenant_id:
        return []

    master_name = _norm_name(record.vendor_name)
    incoming_name = _norm_name(invoice_name)
    if not master_name or not incoming_name:
        return []

    ratio = SequenceMatcher(None, master_name, incoming_name).ratio()
    if ratio < 0.7:
        return [f"Vendor name mismatch: master='{record.vendor_name}', invoice='{invoice_name}'"]
    return []


def apply_vendor_master_checks(
    db: Session,
    documents: list[NormalizedDocument],
    summary: dict[str, Any],
    *,
    tenant_id: str = "default",
) -> dict[str, Any]:
    checks = summary.setdefault("checks", [])
    issues = summary.setdefault("issues", [])
    status = "PASS"

    for document in documents:
        if document.document_type != "VENDOR_INVOICE":
            continue
        gstin = _first_field(document, "vendor_gstin", "gstin")
        vendor_name = _first_field(document, "vendor_name", "supplier_name")
        if not gstin or not vendor_name:
            continue

        warnings = check_vendor(db, str(gstin), str(vendor_name), tenant_id=tenant_id)
        result = "REVIEW_REQUIRED" if warnings else "PASS"
        status = _max_status(status, result)
        message = warnings[0] if warnings else "Vendor master is consistent with extracted vendor invoice data."
        checks.append(
            {
                "check_id": "VENDOR_MASTER_NAME_MATCH",
                "check_name": "Vendor master name match",
                "result": result,
                "severity": "WARNING",
                "left_document_type": document.document_type,
                "left_document_id": document.document_id,
                "left_value": str(vendor_name),
                "right_document_type": "VENDOR_MASTER",
                "right_document_id": normalize_gstin(str(gstin)),
                "right_value": normalize_gstin(str(gstin)),
                "message": message,
            }
        )
        for warning in warnings:
            issues.append(
                {
                    "code": "VENDOR_MASTER_NAME_REVIEW_REQUIRED",
                    "message": warning,
                    "document_type": document.document_type,
                    "document_id": document.document_id,
                    "gstin": normalize_gstin(str(gstin)),
                }
            )
        upsert_vendor(db, str(gstin), str(vendor_name), tenant_id=tenant_id)

    if status != "PASS":
        summary["vendor_procurement_status"] = _max_status(summary.get("vendor_procurement_status") or "PASS", status)
        summary["bundle_status"] = _max_status(summary.get("bundle_status") or "OK", status)
    return summary


def _first_field(document: NormalizedDocument, *keys: str) -> Any:
    for key in keys:
        value = document.fields.get(key)
        if value not in (None, ""):
            return value
    return None


def _norm_name(value: str) -> str:
    text = re.sub(r"[^A-Z0-9 ]+", " ", str(value or "").upper())
    text = re.sub(r"\b(PVT|PRIVATE|LIMITED|LTD|P|P LTD|INDIA)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _max_status(current: str, candidate: str) -> str:
    order = {"OK": 0, "PASS": 0, "PARTIAL_PASS": 1, "REVIEW_REQUIRED": 2, "MISSING_DOCUMENTS": 3, "BLOCKED": 4, "MISMATCH": 5}
    return candidate if order.get(candidate, 0) > order.get(current, 0) else current
