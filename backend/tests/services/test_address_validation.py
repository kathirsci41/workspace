from app.services.address_parser import validate_addresses, AddressMatchResult


def test_pin_code_match():
    result = validate_addresses(
        address_a="6-3-1090/B/1, Raj Bhavan Road, Somajiguda, Hyderabad - 500082",
        address_b="Raj Bhavan Rd, Somajiguda, Hyderabad 500082",
    )
    assert result == AddressMatchResult.MATCH


def test_different_pin_codes_mismatch():
    result = validate_addresses(
        address_a="Anna Nagar, Chennai - 600040",
        address_b="Banjara Hills, Hyderabad - 500034",
    )
    assert result == AddressMatchResult.MISMATCH


def test_no_pin_code_same_state_and_city_is_partial():
    result = validate_addresses(
        address_a="Some Road, Chennai, Tamil Nadu",
        address_b="Another Road, Chennai, Tamil Nadu",
    )
    assert result == AddressMatchResult.PARTIAL


def test_none_address_returns_skip():
    result = validate_addresses(address_a=None, address_b="Chennai 600040")
    assert result == AddressMatchResult.SKIP
