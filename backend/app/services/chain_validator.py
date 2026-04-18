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
from app.services.address_parser import validate_addresses, AddressMatchResult
from app.services.cross_doc_validator import (
    check_ci_vs_cpo_total,
    check_vinv_sum_vs_vpo_total,
    check_gstin_consistency,
    check_name_consistency,
    check_serial_chain,
    check_vdc_vs_vinv_serials,
    check_dc_ref_on_ci,
    check_vpo_ref_on_vdc,
    check_vdc_ref_on_vinv,
    check_date_sequence,
    check_hsn_consistency,
    check_order_item_coverage,
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
            extracted_so = doc.get("so_number") if ok else None
            so_result = check_so_consistency(
                extracted_so=extracted_so,
                expected_so=so_number,
            )
            if so_result == ReferenceCheckResult.SKIP:
                so_skip_reason = "extraction_failed" if not ok else ("no_so_number" if not so_number else "no_extracted_value")
            else:
                so_skip_reason = None

            extracted_cpo = doc.get("cpo_ref") if ok else None
            cpo_result = check_cpo_reference(
                extracted_cpo_ref=extracted_cpo,
                expected_po_number=po_number,
            )
            if cpo_result == ReferenceCheckResult.SKIP:
                cpo_skip_reason = "extraction_failed" if not ok else "no_extracted_value"
            else:
                cpo_skip_reason = None

            reference_checks.append({
                "document_type": doc_type,
                "check": "so_consistency",
                "result": so_result,
                "extracted": extracted_so,
                "expected": so_number,
                "skip_reason": so_skip_reason,
            })
            reference_checks.append({
                "document_type": doc_type,
                "check": "cpo_reference",
                "result": cpo_result,
                "extracted": extracted_cpo,
                "expected": po_number,
                "skip_reason": cpo_skip_reason,
            })
            if so_result == ReferenceCheckResult.MISMATCH:
                has_mismatch = True
            if cpo_result == ReferenceCheckResult.MISMATCH:
                has_mismatch = True

    # VPO check — aggregated across all VENDOR_INVOICE documents (AND-logic)
    vendor_invoices = [d for d in documents if d.get("document_type") == DocumentType.VENDOR_INVOICE]
    if vendor_invoices or (vpo_numbers or []):
        doc_vpo_numbers_list = [
            (d.get("vpo_numbers") or []) if d.get("extraction_ok", True) else []
            for d in vendor_invoices
        ]
        vpo_result = check_vpo_reference(
            doc_vpo_numbers_list=doc_vpo_numbers_list,
            registered_vpo_numbers=vpo_numbers or [],
        )
        if vpo_result == ReferenceCheckResult.SKIP:
            vpo_skip_reason = "no_vpo_registered" if not (vpo_numbers or []) else "no_vendor_invoices"
        else:
            vpo_skip_reason = None
        all_invoice_vpos = [v for vpo_list in doc_vpo_numbers_list for v in vpo_list]
        reference_checks.append({
            "document_type": DocumentType.VENDOR_INVOICE,
            "check": "vpo_reference",
            "result": vpo_result,
            "extracted": ", ".join(all_invoice_vpos) if all_invoice_vpos else None,
            "expected": ", ".join(vpo_numbers or []) if vpo_numbers else None,
            "skip_reason": vpo_skip_reason,
        })
        if vpo_result == ReferenceCheckResult.MISMATCH:
            has_mismatch = True

    # Address consistency: CUSTOMER_PO delivery address vs COMPANY_DC delivery address
    cpo_address = next(
        (d.get("delivery_address") for d in documents if d.get("document_type") == DocumentType.CUSTOMER_PO),
        None,
    )
    cdc_address = next(
        (d.get("delivery_address") for d in documents if d.get("document_type") == DocumentType.COMPANY_DC),
        None,
    )
    addr_result = validate_addresses(cpo_address, cdc_address)
    if addr_result in (AddressMatchResult.MATCH, AddressMatchResult.PARTIAL):
        addr_check_result = ReferenceCheckResult.PASS
    elif addr_result == AddressMatchResult.MISMATCH:
        addr_check_result = ReferenceCheckResult.MISMATCH
        has_mismatch = True
    else:
        addr_check_result = ReferenceCheckResult.SKIP
    reference_checks.append({
        "document_type": DocumentType.CUSTOMER_PO,
        "check": "delivery_address",
        "result": addr_check_result,
        "extracted": cdc_address,
        "expected": cpo_address,
        "skip_reason": "missing_address" if addr_check_result == ReferenceCheckResult.SKIP else None,
    })

    # ── Module 3 cross-document checks ───────────────────────────────────────

    cpo_docs  = [d for d in documents if d.get("document_type") == DocumentType.CUSTOMER_PO]
    vpo_docs  = [d for d in documents if d.get("document_type") == DocumentType.COMPANY_PO]
    vinv_docs = [d for d in documents if d.get("document_type") == DocumentType.VENDOR_INVOICE and d.get("extraction_ok", True)]
    vdc_docs  = [d for d in documents if d.get("document_type") == DocumentType.VENDOR_DC]
    cdc_docs  = [d for d in documents if d.get("document_type") == DocumentType.COMPANY_DC]
    ci_docs   = [d for d in documents if d.get("document_type") == DocumentType.COMPANY_INVOICE]

    # 3A: Company Invoice total vs Customer PO total (MISMATCH)
    # Use invoiced_total (already-computed aggregate) so staged billing is handled correctly.
    # Only flag MISMATCH when invoiced_total > 0 (i.e., at least one invoice exists).
    ci_total_val = invoiced_total if invoiced_total and invoiced_total > 0 else None
    ci_cpo_result = check_ci_vs_cpo_total(ci_total_val, po_total)
    reference_checks.append({
        "document_type": DocumentType.COMPANY_INVOICE,
        "check": "ci_vs_cpo_total",
        "result": ci_cpo_result,
        "extracted": ci_total_val,
        "expected": po_total,
        "skip_reason": "missing_amount" if ci_cpo_result == ReferenceCheckResult.SKIP else None,
    })
    if ci_cpo_result == ReferenceCheckResult.MISMATCH:
        has_mismatch = True

    # 3A: Vendor Invoice sum vs Company PO total (WARNING — freight tolerance)
    vinv_totals = [d.get("amount") for d in vinv_docs if d.get("amount")]
    vpo_total_val = next((d.get("amount") for d in vpo_docs), None)
    vinv_vpo_result = check_vinv_sum_vs_vpo_total(vinv_totals, vpo_total_val)
    reference_checks.append({
        "document_type": DocumentType.VENDOR_INVOICE,
        "check": "vinv_sum_vs_vpo_total",
        "result": vinv_vpo_result,
        "extracted": sum(vinv_totals) if vinv_totals else None,
        "expected": vpo_total_val,
        "skip_reason": "missing_amount" if vinv_vpo_result == ReferenceCheckResult.SKIP else None,
    })
    # WARNING — intentionally NOT setting has_mismatch

    # 3B: Customer GSTIN consistency across CPO, CDC, CI (MISMATCH)
    customer_gstins = [d.get("customer_gstin") for d in cpo_docs + cdc_docs + ci_docs]
    gstin_customer = check_gstin_consistency(customer_gstins)
    reference_checks.append({
        "document_type": None,
        "check": "customer_gstin_consistency",
        "result": gstin_customer,
        "extracted": ", ".join(g for g in customer_gstins if g) or None,
        "expected": None,
        "skip_reason": "insufficient_data" if gstin_customer == ReferenceCheckResult.SKIP else None,
    })
    if gstin_customer == ReferenceCheckResult.MISMATCH:
        has_mismatch = True

    # 3B: Vendor GSTIN — WARNING only (Redington multi-state GSTINs are legitimate)
    vendor_gstins = [d.get("vendor_gstin") for d in vpo_docs + vinv_docs]
    gstin_vendor_raw = check_gstin_consistency(vendor_gstins)
    gstin_vendor = (
        ReferenceCheckResult.WARNING
        if gstin_vendor_raw == ReferenceCheckResult.MISMATCH
        else gstin_vendor_raw
    )
    reference_checks.append({
        "document_type": None,
        "check": "vendor_gstin_consistency",
        "result": gstin_vendor,
        "extracted": ", ".join(g for g in vendor_gstins if g) or None,
        "expected": None,
        "skip_reason": "insufficient_data" if gstin_vendor == ReferenceCheckResult.SKIP else None,
    })
    # vendor GSTIN is WARNING — NOT setting has_mismatch

    # 3B: Customer name fuzzy match (WARNING)
    customer_names = [d.get("customer_name") for d in cpo_docs + cdc_docs + ci_docs]
    name_result = check_name_consistency(customer_names)
    reference_checks.append({
        "document_type": None,
        "check": "customer_name_consistency",
        "result": name_result,
        "extracted": None,
        "expected": None,
        "skip_reason": "insufficient_data" if name_result == ReferenceCheckResult.SKIP else None,
    })

    # 3C: Serial chain — VINV serials must appear in CDC (MISMATCH)
    vinv_serials = [d.get("serial_numbers", []) for d in vinv_docs]
    cdc_serials  = [d.get("serial_numbers", []) for d in cdc_docs if d.get("extraction_ok", True)]
    serial_result = check_serial_chain(vinv_serials, cdc_serials)
    reference_checks.append({
        "document_type": DocumentType.VENDOR_INVOICE,
        "check": "serial_chain",
        "result": serial_result["result"],
        "extracted": ", ".join(serial_result.get("missing", [])) or None,
        "expected": None,
        "skip_reason": serial_result.get("skip_reason"),
    })
    if serial_result["result"] == ReferenceCheckResult.MISMATCH:
        has_mismatch = True

    # 3C: VDC serials must appear on VINV (MISMATCH)
    if vdc_docs:
        vdc_serials_flat = [s for d in vdc_docs for s in (d.get("serial_numbers") or []) if d.get("extraction_ok", True)]
        vdc_vinv = check_vdc_vs_vinv_serials(vdc_serials_flat, vinv_serials)
        reference_checks.append({
            "document_type": DocumentType.VENDOR_DC,
            "check": "vdc_vinv_serial_match",
            "result": vdc_vinv["result"],
            "extracted": ", ".join(vdc_vinv.get("missing", [])) or None,
            "expected": None,
            "skip_reason": vdc_vinv.get("skip_reason"),
        })
        if vdc_vinv["result"] == ReferenceCheckResult.MISMATCH:
            has_mismatch = True

    # 3D: Company DC number referenced on Company Invoice (WARNING)
    cdc_dc_numbers = [d.get("dc_number") for d in cdc_docs if d.get("dc_number")]
    ci_dc_refs = [d.get("dc_reference") for d in ci_docs]
    reference_checks.append({
        "document_type": None,  # cross-doc check — not tied to a single document type
        "check": "dc_ref_on_ci",
        "result": check_dc_ref_on_ci(cdc_dc_numbers, ci_dc_refs),
        "extracted": ", ".join(r for r in ci_dc_refs if r) or None,
        "expected": ", ".join(cdc_dc_numbers) or None,
        "skip_reason": None,
    })

    # 3D: VPO number referenced on Vendor DC (WARNING)
    if vdc_docs and vpo_numbers:
        vdc_po_refs = [d.get("po_reference") for d in vdc_docs if d.get("extraction_ok", True)]
        reference_checks.append({
            "document_type": None,  # cross-doc check
            "check": "vpo_ref_on_vdc",
            "result": check_vpo_ref_on_vdc(vdc_po_refs, vpo_numbers),
            "extracted": ", ".join(r for r in vdc_po_refs if r) or None,
            "expected": ", ".join(vpo_numbers),
            "skip_reason": None,
        })

    # 3D: Vendor DC number referenced on Vendor Invoice (WARNING)
    if vdc_docs and vinv_docs:
        vdc_numbers = [d.get("dc_number") for d in vdc_docs if d.get("dc_number")]
        vinv_dc_refs = [d.get("dc_reference") for d in vinv_docs]
        reference_checks.append({
            "document_type": None,  # cross-doc check
            "check": "vdc_ref_on_vinv",
            "result": check_vdc_ref_on_vinv(vdc_numbers, vinv_dc_refs),
            "extracted": ", ".join(r for r in vinv_dc_refs if r) or None,
            "expected": ", ".join(vdc_numbers) or None,
            "skip_reason": None,
        })

    # 3E: Date sequence
    dated_docs = [
        {
            "document_type": (
                d["document_type"].value
                if hasattr(d.get("document_type"), "value")
                else str(d.get("document_type", ""))
            ),
            "doc_date": d.get("doc_date"),
        }
        for d in documents
    ]
    for v in check_date_sequence(dated_docs):
        reference_checks.append({
            "document_type": v["earlier_type"],
            "check": "date_sequence",
            "result": ReferenceCheckResult.WARNING,
            "extracted": f"{v['later_type']} dated {v['delta_days']} days before {v['earlier_type']}",
            "expected": f"{v['later_type']} date >= {v['earlier_type']} date",
            "skip_reason": None,
        })

    # 3F: HSN consistency — customer loop (CPO, CDC, CI)
    customer_loop = [
        {
            "document_type": (
                d["document_type"].value
                if hasattr(d.get("document_type"), "value")
                else str(d.get("document_type", ""))
            ),
            "order_items": d.get("order_items", []),
        }
        for d in cpo_docs + cdc_docs + ci_docs if d.get("extraction_ok", True)
    ]
    for v in check_hsn_consistency(customer_loop):
        reference_checks.append({
            "document_type": None,
            "check": "hsn_consistency_customer",
            "result": ReferenceCheckResult.WARNING,
            "extracted": ", ".join(v["hsn_values"]),
            "expected": f"consistent HSN for {v['part_no']}",
            "skip_reason": None,
        })

    # 3F: HSN consistency — procurement loop (VPO, VINV)
    procurement_loop = [
        {
            "document_type": (
                d["document_type"].value
                if hasattr(d.get("document_type"), "value")
                else str(d.get("document_type", ""))
            ),
            "order_items": d.get("order_items", []),
        }
        for d in vpo_docs + vinv_docs if d.get("extraction_ok", True)
    ]
    for v in check_hsn_consistency(procurement_loop):
        reference_checks.append({
            "document_type": None,
            "check": "hsn_consistency_procurement",
            "result": ReferenceCheckResult.WARNING,
            "extracted": ", ".join(v["hsn_values"]),
            "expected": f"consistent HSN for {v['part_no']}",
            "skip_reason": None,
        })

    # ── Module 4: Order Item Coverage ────────────────────────────────────────

    # 4A: CPO vs CDC — did the company deliver all customer-ordered items?
    cpo_items = next((d.get("order_items", []) for d in cpo_docs), [])
    cdc_items_flat = [item for d in cdc_docs for item in (d.get("order_items") or [])]
    cpo_cdc = check_order_item_coverage(cpo_items, cdc_items_flat)
    reference_checks.append({
        "document_type": DocumentType.CUSTOMER_PO,
        "check": "cpo_vs_cdc_items",
        "result": cpo_cdc["result"],
        "extracted": ", ".join(p for p in cpo_cdc["missing_parts"] + cpo_cdc["partial_parts"] if p) or None,
        "expected": None,
        "skip_reason": cpo_cdc.get("skip_reason"),
    })
    # WARNING only — partial delivery is legitimate

    # 4B: VPO vs VINV — did the vendor supply all company-ordered items?
    if vpo_docs and vinv_docs:
        vpo_items = next((d.get("order_items", []) for d in vpo_docs), [])
        vinv_items_flat = [item for d in vinv_docs for item in (d.get("order_items") or [])]
        vpo_vinv = check_order_item_coverage(vpo_items, vinv_items_flat)
        reference_checks.append({
            "document_type": DocumentType.COMPANY_PO,
            "check": "vpo_vs_vinv_items",
            "result": vpo_vinv["result"],
            "extracted": ", ".join(p for p in vpo_vinv["missing_parts"] + vpo_vinv["partial_parts"] if p) or None,
            "expected": None,
            "skip_reason": vpo_vinv.get("skip_reason"),
        })
        # WARNING only

    # 4C: CDC vs CI — does the invoice cover all items on the delivery note?
    if cdc_docs and ci_docs:
        ci_items_flat = [item for d in ci_docs for item in (d.get("order_items") or [])]
        cdc_ci = check_order_item_coverage(cdc_items_flat, ci_items_flat)
        reference_checks.append({
            "document_type": DocumentType.COMPANY_DC,
            "check": "cdc_vs_ci_items",
            "result": cdc_ci["result"],
            "extracted": ", ".join(p for p in cdc_ci["missing_parts"] + cdc_ci["partial_parts"] if p) or None,
            "expected": None,
            "skip_reason": cdc_ci.get("skip_reason"),
        })
        # WARNING only

    # Billing completeness
    billing_result: dict = {"overall": BillingStatus.PENDING}
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
