# backend/app/services/chain_validator.py
"""Orchestrates chain presence, reference validation, and billing completeness."""
import enum
from app.models.purchase_order import OrderScenario, ChainStatus, BillingType
from app.models.document import DocumentType
from app.services.po_service import get_scenario_chain
from app.services.reference_validator import (
    check_so_consistency,
    check_cpo_reference,
    check_vpo_reference,
    ReferenceCheckResult,
)
from app.services.billing_tracker import (
    check_full_billing,
    check_staged_billing,
    BillingStatus,
)


class SlotState(str, enum.Enum):
    WAITING = "waiting"
    RECEIVED = "received"
    VERIFIED = "verified"
    MISMATCH = "mismatch"
    CANCELLED = "cancelled"


def compute_chain_status(
    scenario: OrderScenario,
    po_number: str,
    so_number: str | None,
    po_total: float | None,
    billing_type: str,
    billing_milestones: list[dict],
    vpo_numbers: list[str],
    documents: list[dict],
    requires_install_report: bool,
    invoiced_total: float = 0.0,
) -> dict:
    """
    Compute full chain validation result.

    documents: list of dicts with keys:
      document_type, so_number, vpo_numbers, extraction_ok, cpo_ref,
      billing_stage (int | None), amount (float | None, for COMPANY_INVOICE)

    Returns:
        {
          chain_status: ChainStatus,
          missing_slots: list[DocumentType],
          missing_vendor_invoices: list[str],
          reference_checks: list[dict],
          billing: dict,
        }
    """
    required_types = get_scenario_chain(scenario) or []
    if requires_install_report:
        required_types = required_types + [DocumentType.INSTALLATION_REPORT]

    present_types = {d.get("document_type") for d in documents} - {None}
    missing_slots = [t for t in required_types if t not in present_types]

    # VPO slot tracking: each registered VPO needs a matching vendor invoice
    missing_vendor_invoices = []
    for vpo in (vpo_numbers or []):
        matched = any(
            vpo in (d.get("vpo_numbers") or [])
            for d in documents
            if d.get("document_type") == DocumentType.VENDOR_INVOICE
        )
        if not matched:
            missing_vendor_invoices.append(vpo)

    # Reference checks
    reference_checks = []
    has_mismatch = False

    for doc in documents:
        doc_type = doc.get("document_type")
        if doc_type is None:
            continue
        ok = doc.get("extraction_ok", True)

        if doc_type in (DocumentType.COMPANY_DC, DocumentType.COMPANY_INVOICE):
            so_result = check_so_consistency(
                extracted_so=doc.get("so_number") if ok else None,
                expected_so=so_number,
            )
            cpo_result = check_cpo_reference(
                extracted_cpo_ref=doc.get("cpo_ref") if ok else None,
                expected_po_number=po_number,
            )
            reference_checks.append({
                "document_type": doc_type,
                "check": "so_consistency",
                "result": so_result,
            })
            reference_checks.append({
                "document_type": doc_type,
                "check": "cpo_reference",
                "result": cpo_result,
            })
            if so_result == ReferenceCheckResult.MISMATCH:
                has_mismatch = True
            if cpo_result == ReferenceCheckResult.MISMATCH:
                has_mismatch = True

        if doc_type == DocumentType.VENDOR_INVOICE:
            vpo_result = check_vpo_reference(
                doc_vpo_numbers=doc.get("vpo_numbers") or [],
                registered_vpo_numbers=vpo_numbers or [],
            )
            reference_checks.append({
                "document_type": doc_type,
                "check": "vpo_reference",
                "result": vpo_result,
            })
            if vpo_result == ReferenceCheckResult.MISMATCH:
                has_mismatch = True

    # Billing completeness
    billing_result: dict = {}
    billing_complete = False

    if po_total:
        if billing_type == BillingType.STAGED and billing_milestones:
            stage_invoices = [
                {
                    "billing_stage": d.get("billing_stage"),
                    "amount": d.get("amount", 0),
                }
                for d in documents
                if d.get("document_type") == DocumentType.COMPANY_INVOICE
            ]
            billing_result = check_staged_billing(po_total, billing_milestones, stage_invoices)
            billing_complete = billing_result["overall"] == BillingStatus.COMPLETE
        else:
            billing_status = check_full_billing(invoiced_total, po_total)
            billing_result = {"overall": billing_status}
            billing_complete = billing_status == BillingStatus.COMPLETE

    # Determine chain_status — MISMATCH takes priority over INCOMPLETE
    if has_mismatch:
        chain_status = ChainStatus.MISMATCH
    elif missing_slots or missing_vendor_invoices:
        chain_status = ChainStatus.INCOMPLETE
    elif billing_complete:
        chain_status = ChainStatus.COMPLETE
    else:
        chain_status = ChainStatus.INCOMPLETE

    total_slots = len(required_types)
    verified_slots = total_slots - len(missing_slots)
    completeness_pct = round(verified_slots / total_slots * 100) if total_slots > 0 else 0

    return {
        "chain_status": chain_status,
        "completeness_pct": completeness_pct,
        "missing_slots": missing_slots,
        "missing_vendor_invoices": missing_vendor_invoices,
        "reference_checks": reference_checks,
        "billing": billing_result,
    }
