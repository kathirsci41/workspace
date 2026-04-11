import pytest
from app.services.po_service import derive_scenario
from app.models.purchase_order import OrderScenario


def test_no_vpos_no_hints_is_stock():
    result = derive_scenario(vpo_count=0, has_vendor_dc=False, has_service_hint=False)
    assert result == OrderScenario.STOCK


def test_no_vpos_with_vendor_dc_is_drop_ship():
    result = derive_scenario(vpo_count=0, has_vendor_dc=True, has_service_hint=False)
    assert result == OrderScenario.DROP_SHIP


def test_no_vpos_with_service_hint_is_amc():
    result = derive_scenario(vpo_count=0, has_vendor_dc=False, has_service_hint=True)
    assert result == OrderScenario.SERVICE_AMC


def test_one_vpo_is_procurement():
    result = derive_scenario(vpo_count=1, has_vendor_dc=False, has_service_hint=False)
    assert result == OrderScenario.PROCUREMENT


def test_multiple_vpos_is_procurement():
    result = derive_scenario(vpo_count=3, has_vendor_dc=False, has_service_hint=False)
    assert result == OrderScenario.PROCUREMENT
