from app.services.line_item_matcher import reconcile_line_items


def test_reconcile_line_items_matches_hsn_and_sums_dc_quantities():
    matches = reconcile_line_items(
        vendor_items=[
            {"description": "Firewall appliance", "hsn_sac": "8517", "qty": "3", "unit_rate": "1000"},
        ],
        dc_items=[
            {"description": "Firewall appliance", "hsn_sac": "8517", "qty": "1"},
            {"description": "Firewall appliance", "hsn_sac": "8517", "qty": "2"},
        ],
        invoice_items=[
            {"description": "Firewall appliance", "hsn_sac": "8517", "qty": "3", "unit_rate": "1000"},
        ],
    )

    assert len(matches) == 1
    match = matches[0]
    assert match.key == "8517"
    assert match.dc_qty == 3
    assert match.qty_status == "PASS"
    assert match.price_status == "PASS"
    assert match.result == "PASS"


def test_reconcile_line_items_fuzzy_matches_description_and_flags_mismatch():
    matches = reconcile_line_items(
        vendor_items=[
            {"description": "Fortigate FG-120G firewall", "qty": "1", "unit_rate": "503200"},
        ],
        dc_items=[
            {"description": "Fortigate FG120G firewall", "qty": "1"},
        ],
        invoice_items=[
            {"description": "Fortigate FG-120G firewall", "qty": "2", "unit_rate": "503200"},
        ],
    )

    assert len(matches) == 1
    assert matches[0].qty_status == "FAIL"
    assert matches[0].result == "MISMATCH"
    assert any("Invoice qty" in issue for issue in matches[0].issues)


def test_reconcile_line_items_is_dormant_without_counterpart_lists():
    assert reconcile_line_items(
        vendor_items=[{"description": "Firewall appliance", "hsn_sac": "8517", "qty": "3"}],
        dc_items=[],
        invoice_items=[],
    ) == []
