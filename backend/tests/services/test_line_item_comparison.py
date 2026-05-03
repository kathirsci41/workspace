"""Tests for line item comparison between PO and delivery documents."""
import pytest
from app.services.item_matcher import compare_po_to_delivery, ItemMatchStatus


def test_exact_part_number_match_correct_qty():
    """Exact match on part number with correct quantity."""
    cpo_items = [{"part_no": "FG-120G", "description": "Firewall", "qty": 1}]
    dc_items = [{"part_no": "FG-120G", "description": "Firewall", "qty": 1}]
    results = compare_po_to_delivery(cpo_items, dc_items)
    assert results[0]["status"] == ItemMatchStatus.MATCHED
    assert results[0]["qty_shortfall"] == 0


def test_quantity_short():
    """Item matched but quantity delivered is less than ordered."""
    cpo_items = [{"part_no": "SFP-GE-T", "description": "SFP", "qty": 2}]
    dc_items = [{"part_no": "SFP-GE-T", "description": "SFP", "qty": 1}]
    results = compare_po_to_delivery(cpo_items, dc_items)
    assert results[0]["status"] == ItemMatchStatus.PARTIAL
    assert results[0]["qty_shortfall"] == 1


def test_item_missing_from_dc():
    """Some items from CPO are not in delivery document."""
    cpo_items = [
        {"part_no": "FG-120G", "qty": 1},
        {"part_no": "FORTICARE-5YR", "qty": 1},
    ]
    dc_items = [{"part_no": "FG-120G", "qty": 1}]
    results = compare_po_to_delivery(cpo_items, dc_items)
    missing = [r for r in results if r["status"] == ItemMatchStatus.MISSING]
    assert len(missing) == 1
    assert missing[0]["part_no"] == "FORTICARE-5YR"


def test_empty_dc_items_all_missing():
    """When DC is empty, all CPO items are missing."""
    cpo_items = [{"part_no": "FG-120G", "qty": 1}]
    results = compare_po_to_delivery(cpo_items, [])
    assert results[0]["status"] == ItemMatchStatus.MISSING


def test_case_insensitive_part_number_match():
    """Part number matching should be case-insensitive."""
    cpo_items = [{"part_no": "fg-120g", "qty": 1}]
    dc_items = [{"part_no": "FG-120G", "qty": 1}]
    results = compare_po_to_delivery(cpo_items, dc_items)
    assert results[0]["status"] == ItemMatchStatus.MATCHED
