from app.services.document_normalizer import NormalizedDocument
from app.services.order_bundle_verifier import verify_order_bundle


def doc(document_id: str, document_type: str, **fields):
    return NormalizedDocument(document_id=document_id, document_type=document_type, fields=fields)


def test_customer_invoice_dc_so_and_customer_order_match_passes():
    summary = verify_order_bundle(
        [
            doc(
                "inv",
                "CUSTOMER_INVOICE",
                invoice_no="1ITR2526001878",
                customer_order_no="PMCH&RI/024/2025-2026",
                so_no="1OTM2526001611",
                customer_name="PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE",
                taxable_amount=741050,
            ),
            doc(
                "dc",
                "DELIVERY_CHALLAN",
                dc_no="1DNT2526DC3100",
                customer_order_no="PMCH&RI/024/2025-2026",
                so_no="1OTM2526001611",
                customer_name="PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE",
                estimated_amount=741050,
            ),
        ]
    )

    assert summary["customer_delivery_status"] in {"PASS", "PARTIAL_PASS"}
    assert any(check["check_id"] == "INVOICE_DC_SO_MATCH" and check["result"] == "PASS" for check in summary["checks"])
    assert any(check["check_id"] == "INVOICE_DC_CUSTOMER_ORDER_MATCH" and check["result"] == "PASS" for check in summary["checks"])


def test_amount_check_includes_diff_pct_and_uses_configurable_tolerance():
    summary = verify_order_bundle(
        [
            doc(
                "inv",
                "CUSTOMER_INVOICE",
                invoice_no="INV-1",
                customer_order_no="PO-1",
                so_no="SO-1",
                customer_name="Acme",
                taxable_amount=1000,
            ),
            doc(
                "dc",
                "DELIVERY_CHALLAN",
                dc_no="DC-1",
                customer_order_no="PO-1",
                so_no="SO-1",
                customer_name="Acme",
                estimated_amount=1015,
            ),
        ]
    )

    check = next(check for check in summary["checks"] if check["check_id"] == "INVOICE_DC_AMOUNT_MATCH")
    assert check["result"] == "PASS"
    assert check["diff"] == 15
    assert check["diff_pct"] == 1.48


def test_each_delivery_challan_reference_is_checked_independently():
    summary = verify_order_bundle(
        [
            doc("po", "CUSTOMER_PO", customer_po_no="PO-1", grand_total=1000),
            doc("inv", "CUSTOMER_INVOICE", invoice_no="INV-1", customer_order_no="PO-1", so_no="SO-1", customer_name="Acme", taxable_amount=1000, grand_total=1000),
            doc("dc-1", "DELIVERY_CHALLAN", dc_no="DC-1", customer_order_no="PO-1", so_no="SO-1", customer_name="Acme", estimated_amount=500),
            doc("dc-2", "DELIVERY_CHALLAN", dc_no="DC-2", customer_order_no="PO-2", so_no="SO-2", customer_name="Acme", estimated_amount=500),
        ]
    )

    assert any(
        check["check_id"] == "INVOICE_DC_SO_MATCH"
        and check["right_document_id"] == "dc-2"
        and check["result"] == "MISMATCH"
        for check in summary["checks"]
    )
    assert any(
        check["check_id"] == "CUSTOMER_PO_DC_ORDER_MATCH"
        and check["right_document_id"] == "dc-2"
        and check["result"] == "MISMATCH"
        for check in summary["checks"]
    )


def test_gstin_checks_are_emitted_only_for_present_values():
    summary = verify_order_bundle(
        [
            doc("vpo", "VENDOR_PO", vendor_po_no="PO-1", vendor_name="Alpha Systems", grand_total=1000),
            doc("bill", "VENDOR_INVOICE", vendor_invoice_no="BILL-1", po_reference="PO-1", vendor_name="Alpha Systems", invoice_total=1000),
        ]
    )

    assert not any("GSTIN" in check["check_id"] for check in summary["checks"])


def test_gstin_checks_validate_and_compare_present_vendor_values():
    summary = verify_order_bundle(
        [
            doc(
                "vpo",
                "VENDOR_PO",
                vendor_po_no="PO-1",
                vendor_name="Alpha Systems",
                vendor_gstin="33AAGCS1406H1ZR",
                grand_total=1000,
            ),
            doc(
                "bill",
                "VENDOR_INVOICE",
                vendor_invoice_no="BILL-1",
                po_reference="PO-1",
                vendor_name="Alpha Systems",
                vendor_gstin="33AAGCS1406H1ZR",
                invoice_total=1000,
            ),
        ]
    )

    assert any(check["check_id"] == "VENDOR_INVOICE_VENDOR_GSTIN_FORMAT" and check["result"] == "PASS" for check in summary["checks"])
    assert any(check["check_id"] == "VENDOR_GSTIN_MATCH" and check["result"] == "PASS" for check in summary["checks"])


def test_generic_vendor_po_gstin_is_validated_but_not_cross_compared():
    summary = verify_order_bundle(
        [
            doc(
                "vpo",
                "VENDOR_PO",
                vendor_po_no="PO-1",
                vendor_name="Alpha Systems",
                gstin="33AACCS3213Q1ZB",
                grand_total=1000,
            ),
            doc(
                "bill",
                "VENDOR_INVOICE",
                vendor_invoice_no="BILL-1",
                po_reference="PO-1",
                vendor_name="Alpha Systems",
                vendor_gstin="33AAGCS1406H1ZR",
                invoice_total=1000,
            ),
        ]
    )

    assert any(check["check_id"] == "VENDOR_PO_GSTIN_FORMAT" and check["result"] == "PASS" for check in summary["checks"])
    assert not any(check["check_id"] == "VENDOR_GSTIN_MATCH" for check in summary["checks"])
    assert not any(issue["code"] == "VENDOR_GSTIN_MISMATCH" for issue in summary["issues"])


def test_gst_math_checks_are_emitted_only_when_tax_data_is_present():
    summary = verify_order_bundle(
        [
            doc("inv", "CUSTOMER_INVOICE", invoice_no="INV-1", customer_order_no="PO-1", taxable_amount=1000),
        ]
    )

    assert not any(check["check_id"].endswith("_GST_MATH") for check in summary["checks"])


def test_gst_math_passes_when_expected_tax_matches_component_tax():
    summary = verify_order_bundle(
        [
            doc("inv", "CUSTOMER_INVOICE", invoice_no="INV-1", customer_order_no="PO-1", taxable_amount=1000, gst_rate=18, igst_amount=180),
        ]
    )

    check = next(check for check in summary["checks"] if check["check_id"] == "CUSTOMER_INVOICE_GST_MATH")
    assert check["result"] == "PASS"
    assert check["left_value"] == 180
    assert check["right_value"] == 180


def test_gst_math_mismatch_flags_present_values():
    summary = verify_order_bundle(
        [
            doc("bill", "VENDOR_INVOICE", vendor_invoice_no="BILL-1", taxable_amount=1000, gst_rate=18, cgst_amount=70, sgst_amount=70),
        ]
    )

    check = next(check for check in summary["checks"] if check["check_id"] == "VENDOR_INVOICE_GST_MATH")
    assert check["result"] == "MISMATCH"
    assert any(issue["code"] == "GST_MATH_MISMATCH" for issue in summary["issues"])


def test_line_item_checks_are_emitted_only_when_counterparts_are_present():
    summary = verify_order_bundle(
        [
            doc(
                "bill",
                "VENDOR_INVOICE",
                vendor_invoice_no="BILL-1",
                line_items=[{"description": "Firewall appliance", "hsn_sac": "8517", "qty": "3"}],
            ),
        ]
    )

    assert not any(check["check_id"].startswith("LINE_ITEM_") for check in summary["checks"])


def test_line_item_checks_aggregate_delivery_challans():
    summary = verify_order_bundle(
        [
            doc(
                "inv",
                "CUSTOMER_INVOICE",
                invoice_no="INV-1",
                customer_order_no="PO-1",
                so_no="SO-1",
                customer_name="Acme",
                taxable_amount=3000,
                line_items=[{"description": "Firewall appliance", "hsn_sac": "8517", "qty": "3", "unit_rate": "1000"}],
            ),
            doc(
                "dc-1",
                "DELIVERY_CHALLAN",
                dc_no="DC-1",
                customer_order_no="PO-1",
                so_no="SO-1",
                customer_name="Acme",
                estimated_amount=1000,
                line_items=[{"description": "Firewall appliance", "hsn_sac": "8517", "qty": "1"}],
            ),
            doc(
                "dc-2",
                "DELIVERY_CHALLAN",
                dc_no="DC-2",
                customer_order_no="PO-1",
                so_no="SO-1",
                customer_name="Acme",
                estimated_amount=2000,
                line_items=[{"description": "Firewall appliance", "hsn_sac": "8517", "qty": "2"}],
            ),
            doc("vpo", "VENDOR_PO", vendor_po_no="PO-1", vendor_name="Alpha Systems", grand_total=3000),
            doc(
                "bill",
                "VENDOR_INVOICE",
                vendor_invoice_no="BILL-1",
                po_reference="PO-1",
                vendor_name="Alpha Systems",
                invoice_total=3000,
                line_items=[{"description": "Firewall appliance", "hsn_sac": "8517", "qty": "3", "unit_rate": "1000"}],
            ),
        ]
    )

    check = next(check for check in summary["checks"] if check["check_id"] == "LINE_ITEM_8517")
    assert check["result"] == "PASS"
    assert check["qty_status"] == "PASS"
    assert check["price_status"] == "PASS"
    assert check["right_value"] == {"dc_qty": 3, "invoice_qty": 3}


def test_vendor_bill_is_not_counted_without_matching_po_reference():
    summary = verify_order_bundle(
        [
            doc(
                "vpo",
                "VENDOR_PO",
                vendor_po_no="1PTR2526000467",
                vendor_name="SUPREME COMPUTERS INDIA P LTD",
                grand_total=696200,
                part_shipment_allowed="NOT ALLOWED",
                mode_of_bill="ON FULL DELIVERY",
            ),
            doc(
                "vbill",
                "VENDOR_INVOICE",
                vendor_invoice_no="2526PSI25087738",
                vendor_name="SUPREME COMPUTERS INDIA P LTD",
                invoice_total=554600,
            ),
        ]
    )

    assert summary["vendor_procurement_status"] in {"REVIEW_REQUIRED", "BLOCKED"}
    assert any(
        "reference missing" in issue["message"].lower() or "not counting" in issue["message"].lower()
        for issue in summary["issues"]
    )


def test_vendor_name_match_normalizes_legal_suffix_variants():
    summary = verify_order_bundle(
        [
            doc("vpo", "VENDOR_PO", vendor_po_no="PO-1", vendor_name="Supreme Computers India P LTD", grand_total=1000),
            doc(
                "bill",
                "VENDOR_INVOICE",
                vendor_invoice_no="BILL-1",
                po_reference="PO-1",
                vendor_name="Supreme Computers India Private Limited",
                invoice_total=1000,
            ),
        ]
    )

    assert any(check["check_id"] == "VENDOR_NAME_MATCH" and check["result"] == "PASS" for check in summary["checks"])


def test_partial_vendor_billing_with_not_allowed_is_review_required():
    summary = verify_order_bundle(
        [
            doc(
                "vpo",
                "VENDOR_PO",
                vendor_po_no="1PTR2526000467",
                vendor_name="SUPREME COMPUTERS INDIA P LTD",
                grand_total=696200,
                part_shipment_allowed="NOT ALLOWED",
                mode_of_bill="ON FULL DELIVERY",
            ),
            doc(
                "vbill",
                "VENDOR_INVOICE",
                vendor_invoice_no="2526PSI25087738",
                po_reference="1PTR2526000467",
                vendor_name="SUPREME COMPUTERS INDIA P LTD",
                invoice_total=554600,
            ),
        ]
    )

    assert summary["vendor_procurement_status"] == "REVIEW_REQUIRED"
    assert any(issue.get("difference") == 141600 for issue in summary["issues"])


def test_vendor_invoice_is_only_matched_to_referenced_vendor_po():
    summary = verify_order_bundle(
        [
            doc("vpo-a", "VENDOR_PO", vendor_po_no="PO-A", vendor_name="Alpha Systems", grand_total=1000),
            doc("vpo-b", "VENDOR_PO", vendor_po_no="PO-B", vendor_name="Beta Systems", grand_total=2000),
            doc("bill-a", "VENDOR_INVOICE", vendor_invoice_no="BILL-A", po_reference="PO-A", vendor_name="Alpha Systems", invoice_total=1000),
        ]
    )

    assert any(
        check["check_id"] == "VENDOR_PO_INVOICE_REFERENCE_MATCH"
        and check["left_document_id"] == "vpo-a"
        and check["right_document_id"] == "bill-a"
        and check["result"] == "PASS"
        for check in summary["checks"]
    )
    assert not any(
        check["check_id"] == "VENDOR_PO_INVOICE_REFERENCE_MATCH"
        and check["left_document_id"] == "vpo-b"
        and check["right_document_id"] == "bill-a"
        and check["result"] == "MISMATCH"
        for check in summary["checks"]
    )
    assert any(issue["code"] == "VENDOR_BILL_MISSING_FOR_PO" and issue["vendor_po_no"] == "PO-B" for issue in summary["issues"])


def test_vendor_invoice_reference_to_unknown_po_is_not_counted():
    summary = verify_order_bundle(
        [
            doc("vpo-a", "VENDOR_PO", vendor_po_no="PO-A", vendor_name="Alpha Systems", grand_total=1000),
            doc("bill-x", "VENDOR_INVOICE", vendor_invoice_no="BILL-X", po_reference="PO-X", vendor_name="Alpha Systems", invoice_total=1000),
        ]
    )

    assert summary["vendor_procurement_status"] in {"REVIEW_REQUIRED", "BLOCKED"}
    assert any(issue["code"] == "VENDOR_BILL_REFERENCE_UNMATCHED" for issue in summary["issues"])
    assert not any(check["check_id"] == "VENDOR_BILLING_COVERAGE" and check["result"] == "PASS" for check in summary["checks"])


def test_multiple_vendor_bills_for_same_vendor_po_sum_coverage():
    summary = verify_order_bundle(
        [
            doc(
                "vpo",
                "VENDOR_PO",
                vendor_po_no="PO-1",
                vendor_name="Alpha Systems",
                grand_total=1000,
                part_shipment_allowed="ALLOWED",
            ),
            doc("bill-1", "VENDOR_INVOICE", vendor_invoice_no="BILL-1", po_reference="PO-1", vendor_name="Alpha Systems", invoice_total=400),
            doc("bill-2", "VENDOR_INVOICE", vendor_invoice_no="BILL-2", po_reference="PO-1", vendor_name="Alpha Systems", invoice_total=600),
        ]
    )

    assert any(
        check["check_id"] == "VENDOR_BILLING_COVERAGE" and check["result"] == "PASS" and check["right_value"] == 1000
        for check in summary["checks"]
    )
    assert not any(issue.get("code") == "VENDOR_PARTIAL_BILLING_REVIEW_REQUIRED" for issue in summary["issues"])


def test_empty_extracted_alias_vendor_po_does_not_create_missing_bill_issue():
    summary = verify_order_bundle(
        [
            doc("empty-vpo", "VENDOR_PO"),
            doc("vpo", "VENDOR_PO", vendor_po_no="PO-1", vendor_name="Alpha Systems", grand_total=1000),
            doc("bill", "VENDOR_INVOICE", vendor_invoice_no="BILL-1", po_reference="PO-1", vendor_name="Alpha Systems", invoice_total=1000),
        ]
    )

    assert not any(
        issue["code"] == "VENDOR_BILL_MISSING_FOR_PO" and issue.get("vendor_po_no") in (None, "")
        for issue in summary["issues"]
    )
    assert any(
        check["check_id"] == "VENDOR_BILLING_COVERAGE" and check["result"] == "PASS"
        for check in summary["checks"]
    )


def test_empty_extracted_alias_dc_does_not_become_primary_comparison_document():
    summary = verify_order_bundle(
        [
            doc("po", "CUSTOMER_PO", customer_po_no="PO-1", grand_total=1000),
            doc("invoice", "CUSTOMER_INVOICE", invoice_no="INV-1", customer_order_no="PO-1", so_no="SO-1", customer_name="Acme", taxable_amount=1000, grand_total=1000),
            doc("empty-dc", "DELIVERY_CHALLAN"),
            doc("dc", "DELIVERY_CHALLAN", dc_no="DC-1", customer_order_no="PO-1", so_no="SO-1", customer_name="Acme", estimated_amount=1000),
        ]
    )

    assert any(
        check["check_id"] == "CUSTOMER_PO_DC_ORDER_MATCH"
        and check["right_document_id"] == "dc"
        and check["result"] == "PASS"
        for check in summary["checks"]
    )
