from app.services.extraction.structured_text_parser import parse_structured_text


def test_invoice_total_fallback_fixes_detached_label():
    # label extraction grabs a small line-item; real total is the largest figure
    text = "Line Total\n9983.13\nTotal Amount [INR]\nInvoice Total [INR]\n... 463365.55 appears earlier ...\n463365.55"
    result = parse_structured_text("VENDOR_INVOICE", text, extraction_route="digital")
    assert result["fields"]["invoice_total"] == 463365.55


def test_invoice_total_fallback_overrides_implausibly_small_label_result():
    text = (
        "Invoice Total [INR]\n"
        "detached label with no nearby amount in the parser window "
        ".................................................................\n"
        "463365.55\n"
        "Tax Total\n"
        "9983.13"
    )
    result = parse_structured_text("VENDOR_INVOICE", text, extraction_route="digital")

    assert result["fields"]["invoice_total"] == 463365.55
    assert result["diagnostics"].get("invoice_total_source") == "fallback_largest"
    assert result["field_metadata"]["invoice_total"]["confidence"] == 0.5


def test_invoice_total_keeps_correct_label_result():
    # label result equals largest figure -> not overridden
    text = "Total before Tax\n425788.80\nTax Total\n76641.98\nInvoice Total\n502430.78"
    result = parse_structured_text("VENDOR_INVOICE", text, extraction_route="digital")
    assert result["fields"]["invoice_total"] == 502430.78


def test_invoice_total_fallback_sets_low_confidence():
    text = "Line Total\n9983.13\nInvoice Total\n463365.55"
    result = parse_structured_text("VENDOR_INVOICE", text, extraction_route="digital")
    diag = result.get("diagnostics", {})
    # when fallback fires, it is flagged for review
    if result["fields"]["invoice_total"] == 463365.55 and diag.get("invoice_total_source") == "fallback_largest":
        meta = result.get("field_metadata", {}).get("invoice_total", {})
        assert meta.get("confidence") == 0.5


def test_invoice_total_no_amounts_returns_none_safely():
    text = "Vendor bill with no decimal amounts here"
    result = parse_structured_text("VENDOR_INVOICE", text, extraction_route="digital")
    assert result["fields"].get("invoice_total") is None
