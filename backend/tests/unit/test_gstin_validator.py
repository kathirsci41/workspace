from app.services.gstin_validator import validate_gstin


def test_valid_gstin_passes():
    valid, reason = validate_gstin("33AAGCS1406H1ZR")

    assert valid
    assert reason == ""


def test_invalid_gstin_format_fails():
    valid, reason = validate_gstin("33AAGCS1406H1Z")

    assert not valid
    assert "format invalid" in reason


def test_invalid_state_code_fails():
    valid, reason = validate_gstin("99AAGCS1406H1ZR")

    assert not valid
    assert reason == "Invalid state code: 99"
