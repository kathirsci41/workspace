from app.services.extraction.unified_schema import (
    InvoiceSchema, PartyInfo, OrderDetails, LineItem, TaxSummary, FinancialSummary,
    to_flat_dict
)


def test_adapter_basic_fields():
    schema = InvoiceSchema(
        buyer=PartyInfo(name="Hindalco Industries", gstin="27AACCH3536G1ZM"),
        vendor=PartyInfo(name="Skylark Information Technologies", gstin="33AAGCS1406H1ZR"),
        order=OrderDetails(invoice_number="INV-001", po_number="PO-123"),
        financial=FinancialSummary(taxable_amount="100000", total_amount="118000"),
    )
    flat = to_flat_dict(schema)
    assert flat["customer_name"] == "Hindalco Industries"
    assert flat["vendor_invoice_no"] == "INV-001"
    assert flat["po_reference"] == "PO-123"
    assert flat["taxable_amount"] == "100000"


def test_adapter_line_items():
    schema = InvoiceSchema(
        line_items=[
            LineItem(description="EC-10106 SDWAN", qty="2", amount="1062000"),
        ]
    )
    flat = to_flat_dict(schema)
    assert "line_items" in flat
    assert flat["line_items"][0]["description"] == "EC-10106 SDWAN"
    assert flat["line_items"][0]["qty"] == "2"


def test_adapter_no_empty_keys():
    schema = InvoiceSchema()
    flat = to_flat_dict(schema)
    # No empty string keys (only _extraction_source)
    for k, v in flat.items():
        if k.startswith("_"):
            continue
        assert v, f"Key {k!r} should not be empty in output"
